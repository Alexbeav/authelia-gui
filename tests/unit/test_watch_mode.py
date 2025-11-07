"""
Unit tests for watch mode detection and conditional restart logic.
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import yaml

from app.authelia_config import AutheliaConfigParser, detect_watch_mode
from app.config import Settings


class TestWatchModeDetection:
    """Test watch mode detection from configuration file."""

    def test_detect_watch_mode_enabled(self, tmp_path):
        """Test detection when watch mode is enabled."""
        config_file = tmp_path / "configuration.yml"

        # Create config with watch enabled
        config_data = {
            'authentication_backend': {
                'file': {
                    'path': '/config/users.yml',
                    'watch': True
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        # Test detection
        parser = AutheliaConfigParser(str(config_file))
        assert parser.is_watch_mode_enabled() is True

    def test_detect_watch_mode_disabled(self, tmp_path):
        """Test detection when watch mode is disabled."""
        config_file = tmp_path / "configuration.yml"

        # Create config with watch disabled
        config_data = {
            'authentication_backend': {
                'file': {
                    'path': '/config/users.yml',
                    'watch': False
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        # Test detection
        parser = AutheliaConfigParser(str(config_file))
        assert parser.is_watch_mode_enabled() is False

    def test_detect_watch_mode_missing(self, tmp_path):
        """Test detection when watch key is missing (defaults to False)."""
        config_file = tmp_path / "configuration.yml"

        # Create config without watch key
        config_data = {
            'authentication_backend': {
                'file': {
                    'path': '/config/users.yml'
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        # Test detection
        parser = AutheliaConfigParser(str(config_file))
        assert parser.is_watch_mode_enabled() is False

    def test_detect_watch_mode_no_file_backend(self, tmp_path):
        """Test detection when file backend is not configured."""
        config_file = tmp_path / "configuration.yml"

        # Create config without file backend
        config_data = {
            'authentication_backend': {
                'ldap': {
                    'url': 'ldap://localhost'
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        # Test detection
        parser = AutheliaConfigParser(str(config_file))
        assert parser.is_watch_mode_enabled() is False

    def test_detect_watch_mode_file_not_found(self):
        """Test detection when config file doesn't exist."""
        parser = AutheliaConfigParser("/nonexistent/config.yml")
        assert parser.is_watch_mode_enabled() is False

    def test_detect_watch_mode_invalid_yaml(self, tmp_path):
        """Test detection with invalid YAML."""
        config_file = tmp_path / "configuration.yml"

        with open(config_file, 'w') as f:
            f.write("invalid: yaml: content:\n  - broken")

        parser = AutheliaConfigParser(str(config_file))
        assert parser.is_watch_mode_enabled() is False

    def test_get_watch_config(self, tmp_path):
        """Test getting full watch configuration."""
        config_file = tmp_path / "configuration.yml"

        config_data = {
            'authentication_backend': {
                'file': {
                    'path': '/config/users.yml',
                    'watch': True
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        parser = AutheliaConfigParser(str(config_file))
        watch_config = parser.get_watch_config()

        assert watch_config['watch'] is True
        assert watch_config['path'] == '/config/users.yml'

    def test_reload_config(self, tmp_path):
        """Test config reload functionality."""
        config_file = tmp_path / "configuration.yml"

        # Initial config
        config_data = {
            'authentication_backend': {
                'file': {
                    'path': '/config/users.yml',
                    'watch': False
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        parser = AutheliaConfigParser(str(config_file))
        assert parser.is_watch_mode_enabled() is False

        # Update config
        config_data['authentication_backend']['file']['watch'] = True

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        # Reload and verify
        parser.reload_config()
        assert parser.is_watch_mode_enabled() is True

    def test_helper_function(self, tmp_path):
        """Test the detect_watch_mode helper function."""
        config_file = tmp_path / "configuration.yml"

        config_data = {
            'authentication_backend': {
                'file': {
                    'watch': True
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        assert detect_watch_mode(str(config_file)) is True


class TestConditionalRestart:
    """Test conditional restart logic based on watch mode."""

    @pytest.mark.asyncio
    async def test_apply_changes_with_force_restart(self):
        """Test that FORCE_RESTART=true always restarts."""
        from app.restart import apply_changes

        settings = Mock(spec=Settings)
        settings.force_restart = True
        settings.restart_cmd = 'echo "restart"'
        settings.health_url = 'http://localhost:9091/api/health'
        settings.health_timeout_seconds = 5

        # Mock restart_authelia to avoid actual restart
        with patch('app.restart.restart_authelia', new_callable=AsyncMock) as mock_restart:
            mock_restart.return_value = (True, "Restarted")

            success, message = await apply_changes(settings)

            # Should call restart even if watch mode is enabled
            mock_restart.assert_called_once()
            assert success is True

    @pytest.mark.asyncio
    async def test_apply_changes_watch_mode_enabled(self, tmp_path):
        """Test that watch mode enabled skips restart."""
        from app.restart import apply_changes

        # Create config with watch enabled
        config_file = tmp_path / "configuration.yml"
        config_data = {
            'authentication_backend': {
                'file': {
                    'watch': True
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        settings = Mock(spec=Settings)
        settings.force_restart = False
        settings.authelia_config_file = str(config_file)
        settings.watch_mode_timeout = 5
        settings.health_url = 'http://localhost:9091/api/health'

        # Mock both restart and watch wait
        with patch('app.restart.restart_authelia', new_callable=AsyncMock) as mock_restart, \
             patch('app.restart.wait_for_watch_mode_reload', new_callable=AsyncMock) as mock_watch:
            mock_watch.return_value = (True, "Watch mode applied")

            success, message = await apply_changes(settings)

            # Should NOT call restart
            mock_restart.assert_not_called()
            # Should call watch wait
            mock_watch.assert_called_once()
            assert success is True

    @pytest.mark.asyncio
    async def test_apply_changes_watch_mode_disabled(self, tmp_path):
        """Test that watch mode disabled triggers restart."""
        from app.restart import apply_changes

        # Create config with watch disabled
        config_file = tmp_path / "configuration.yml"
        config_data = {
            'authentication_backend': {
                'file': {
                    'watch': False
                }
            }
        }

        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        settings = Mock(spec=Settings)
        settings.force_restart = False
        settings.authelia_config_file = str(config_file)
        settings.restart_cmd = 'echo "restart"'
        settings.health_url = 'http://localhost:9091/api/health'
        settings.health_timeout_seconds = 5

        # Mock restart
        with patch('app.restart.restart_authelia', new_callable=AsyncMock) as mock_restart:
            mock_restart.return_value = (True, "Restarted")

            success, message = await apply_changes(settings)

            # Should call restart
            mock_restart.assert_called_once()
            assert success is True
