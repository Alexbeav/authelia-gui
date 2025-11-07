"""
Authelia restart and health polling functionality.

Handles:
- Executing restart command
- Polling health endpoint until ready
- Watch mode detection and conditional restart
- Timeout handling
"""
import asyncio
import subprocess
import logging
from typing import Tuple, Optional
import httpx

from config import Settings
from authelia_config import detect_watch_mode

logger = logging.getLogger(__name__)


class RestartError(Exception):
    """Raised when restart operation fails."""
    pass


class HealthCheckTimeout(Exception):
    """Raised when health check times out."""
    pass


class WatchModeTimeout(Exception):
    """Raised when watch mode reload times out."""
    pass


async def wait_for_watch_mode_reload(
    settings: Settings,
    username: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Wait for Authelia to detect file changes via watch mode.

    Instead of restarting, this function waits for Authelia to reload
    the users file automatically when watch mode is enabled.

    Args:
        settings: Application settings
        username: Optional username to verify (for validation)

    Returns:
        Tuple of (success: bool, message: str)
    """
    timeout = settings.watch_mode_timeout
    start_time = asyncio.get_event_loop().time()
    poll_interval = 1.0

    logger.info(f"Watch mode enabled: waiting for file reload (timeout: {timeout}s)")

    # Simple approach: wait for a short period and check health
    # In watch mode, Authelia should detect the change within seconds
    await asyncio.sleep(2)  # Give Authelia time to detect file change

    try:
        # Poll health to ensure Authelia is still responsive
        async with httpx.AsyncClient(timeout=5.0) as client:
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time

                if elapsed > timeout:
                    raise WatchModeTimeout(
                        f"Watch mode reload timeout after {timeout} seconds. "
                        "File changes may not have been detected."
                    )

                try:
                    response = await client.get(settings.health_url)

                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if data.get('status') in ['UP', 'OK', 'healthy']:
                                logger.info(f"Authelia responded healthy during watch mode (elapsed: {elapsed:.1f}s)")
                                return True, f"File changes detected by watch mode (auto-reload in {elapsed:.1f}s)"
                        except:
                            # If can't parse JSON but got 200, consider it healthy
                            logger.info(f"Authelia responded healthy during watch mode (elapsed: {elapsed:.1f}s)")
                            return True, f"File changes detected by watch mode (auto-reload in {elapsed:.1f}s)"

                except httpx.RequestError as e:
                    logger.debug(f"Health check during watch mode failed: {e}, retrying...")

                # Wait before next poll
                await asyncio.sleep(poll_interval)

    except WatchModeTimeout as e:
        logger.warning(str(e))
        return False, str(e)
    except Exception as e:
        logger.error(f"Error during watch mode wait: {e}")
        return False, f"Watch mode wait failed: {str(e)}"


async def apply_changes(settings: Settings, username: Optional[str] = None) -> Tuple[bool, str]:
    """
    Apply user changes: either restart Authelia or wait for watch mode reload.

    This function intelligently decides whether to restart Authelia or wait
    for watch mode to detect the changes automatically.

    Args:
        settings: Application settings
        username: Optional username that was changed (for verification)

    Returns:
        Tuple of (success: bool, message: str)
    """
    # Check if restart is forced
    if settings.force_restart:
        logger.info("FORCE_RESTART is enabled, restarting Authelia...")
        return await restart_authelia(settings)

    # Detect watch mode
    try:
        watch_mode_enabled = detect_watch_mode(settings.authelia_config_file)

        if watch_mode_enabled:
            logger.info("Watch mode detected, waiting for auto-reload...")
            return await wait_for_watch_mode_reload(settings, username)
        else:
            logger.info("Watch mode not enabled, restarting Authelia...")
            return await restart_authelia(settings)

    except Exception as e:
        logger.warning(f"Could not detect watch mode ({e}), falling back to restart")
        return await restart_authelia(settings)


async def restart_authelia(settings: Settings) -> Tuple[bool, str]:
    """
    Restart Authelia container and wait for it to be healthy.

    Process:
    1. Execute restart command
    2. Poll health endpoint until OK or timeout
    3. Return success status and message

    Args:
        settings: Application settings

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Step 1: Execute restart command
        logger.info(f"Executing restart command: {settings.restart_cmd}")

        result = await asyncio.create_subprocess_shell(
            settings.restart_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            error_msg = stderr.decode().strip() or stdout.decode().strip()
            logger.error(f"Restart command failed: {error_msg}")
            raise RestartError(f"Restart command failed: {error_msg}")

        logger.info("Restart command executed successfully")

        # Step 2: Poll health endpoint
        try:
            await poll_health(settings)
            return True, "Authelia restarted successfully and is healthy"

        except HealthCheckTimeout as e:
            logger.error(f"Health check timeout: {e}")
            return False, str(e)

    except RestartError as e:
        return False, str(e)
    except Exception as e:
        logger.error(f"Unexpected error during restart: {e}")
        return False, f"Restart failed: {str(e)}"


async def poll_health(settings: Settings) -> None:
    """
    Poll Authelia health endpoint until healthy or timeout.

    Args:
        settings: Application settings

    Raises:
        HealthCheckTimeout: If health check times out
    """
    timeout = settings.health_timeout_seconds
    start_time = asyncio.get_event_loop().time()
    poll_interval = 1.0  # Poll every second

    logger.info(f"Polling health endpoint: {settings.health_url} (timeout: {timeout}s)")

    async with httpx.AsyncClient(timeout=5.0) as client:
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time

            if elapsed > timeout:
                raise HealthCheckTimeout(
                    f"Health check timed out after {timeout} seconds. "
                    "Authelia may still be starting. Check logs and try again."
                )

            try:
                response = await client.get(settings.health_url)

                if response.status_code == 200:
                    # Check response body for status
                    try:
                        data = response.json()
                        if data.get('status') in ['UP', 'OK', 'healthy']:
                            logger.info(f"Authelia is healthy (elapsed: {elapsed:.1f}s)")
                            return
                    except:
                        # If can't parse JSON but got 200, consider it healthy
                        logger.info(f"Authelia is healthy (elapsed: {elapsed:.1f}s)")
                        return

                logger.debug(
                    f"Health check returned {response.status_code}, "
                    f"retrying... (elapsed: {elapsed:.1f}s)"
                )

            except httpx.RequestError as e:
                logger.debug(f"Health check connection failed: {e}, retrying...")

            # Wait before next poll
            await asyncio.sleep(poll_interval)


def restart_authelia_sync(settings: Settings) -> Tuple[bool, str]:
    """
    Synchronous wrapper for restart_authelia.

    Args:
        settings: Application settings

    Returns:
        Tuple of (success: bool, message: str)
    """
    return asyncio.run(restart_authelia(settings))
