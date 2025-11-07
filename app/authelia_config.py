"""
Authelia configuration.yml parser for watch mode detection.
"""
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class AutheliaConfigParser:
    """Parser for Authelia configuration.yml to detect watch mode."""

    def __init__(self, config_path: str):
        """
        Initialize parser.

        Args:
            config_path: Path to Authelia configuration.yml
        """
        self.config_path = Path(config_path)
        self._watch_mode: Optional[bool] = None
        self._config_data: Optional[Dict[str, Any]] = None

    def load_config(self) -> bool:
        """
        Load and parse Authelia configuration file.

        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.config_path.exists():
            logger.warning(f"Authelia config file not found: {self.config_path}")
            return False

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config_data = yaml.safe_load(f)

            logger.info(f"Loaded Authelia config from {self.config_path}")
            return True

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse Authelia config: {e}")
            return False
        except Exception as e:
            logger.error(f"Error loading Authelia config: {e}")
            return False

    def is_watch_mode_enabled(self) -> bool:
        """
        Check if file provider watch mode is enabled.

        Returns:
            True if watch mode is enabled, False otherwise
        """
        # Return cached value if available
        if self._watch_mode is not None:
            return self._watch_mode

        # Load config if not already loaded
        if self._config_data is None:
            if not self.load_config():
                self._watch_mode = False
                return False

        try:
            # Navigate to authentication_backend.file.watch
            auth_backend = self._config_data.get('authentication_backend', {})

            if not auth_backend:
                logger.debug("No authentication_backend in config")
                self._watch_mode = False
                return False

            file_config = auth_backend.get('file', {})

            if not file_config:
                logger.debug("No file provider configured in authentication_backend")
                self._watch_mode = False
                return False

            # Check watch setting
            watch_enabled = file_config.get('watch', False)
            self._watch_mode = bool(watch_enabled)

            if self._watch_mode:
                logger.info("Watch mode is ENABLED in Authelia config")
            else:
                logger.info("Watch mode is DISABLED in Authelia config")

            return self._watch_mode

        except Exception as e:
            logger.error(f"Error checking watch mode: {e}")
            self._watch_mode = False
            return False

    def get_watch_config(self) -> Dict[str, Any]:
        """
        Get full watch configuration details.

        Returns:
            Dictionary with watch configuration, or empty dict if not available
        """
        if self._config_data is None:
            self.load_config()

        if self._config_data is None:
            return {}

        try:
            file_config = (
                self._config_data
                .get('authentication_backend', {})
                .get('file', {})
            )

            return {
                'watch': file_config.get('watch', False),
                'path': file_config.get('path', 'unknown')
            }

        except Exception as e:
            logger.error(f"Error getting watch config: {e}")
            return {}

    def reload_config(self) -> bool:
        """
        Force reload of configuration file.

        Returns:
            True if reloaded successfully
        """
        self._config_data = None
        self._watch_mode = None
        return self.load_config()


def detect_watch_mode(config_path: str) -> bool:
    """
    Simple helper function to detect watch mode.

    Args:
        config_path: Path to Authelia configuration.yml

    Returns:
        True if watch mode is enabled, False otherwise
    """
    parser = AutheliaConfigParser(config_path)
    return parser.is_watch_mode_enabled()
