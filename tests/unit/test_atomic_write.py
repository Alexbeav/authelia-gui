"""
Unit tests for atomic write operations and backups.

Tests:
- Atomic write (temp → fsync → rename)
- No partial writes on failure
- Backup creation
- Backup pruning
- Last admin protection
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from app.config import Settings
from app.users_io import UsersFileHandler
from app.models import UsersFile, UserConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)


@pytest.fixture
def settings(temp_dir):
    """Create test settings."""
    settings = Mock(spec=Settings)
    settings.authelia_users_file = str(temp_dir / "users.yml")
    settings.backup_dir = str(temp_dir / "backups")
    settings.backup_keep = 3
    settings.admin_group = "admins"
    return settings


@pytest.fixture
def users_handler(settings):
    """Create UsersFileHandler with test settings."""
    return UsersFileHandler(settings)


class TestAtomicWrite:
    """Test atomic write operations."""

    def test_atomic_write_success(self, users_handler, settings):
        """Test successful atomic write."""
        # Create initial file
        users_file = UsersFile(users={
            "testuser": UserConfig(
                password="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
                displayname="Test User",
                email="test@example.com",
                groups=["users"]
            )
        })

        users_handler.save_users(users_file, create_backup=False)

        # Verify file exists and is valid
        assert Path(settings.authelia_users_file).exists()

        # Load and verify
        loaded = users_handler.load_users()
        assert "testuser" in loaded.users
        assert loaded.users["testuser"].email == "test@example.com"

    def test_no_partial_write_on_failure(self, users_handler, settings, temp_dir):
        """Test that failed writes don't leave partial files."""
        # Create initial valid file
        initial_users = UsersFile(users={
            "alice": UserConfig(
                password="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
                displayname="Alice",
                email="alice@example.com",
                groups=["users"]
            )
        })
        users_handler.save_users(initial_users, create_backup=False)

        # Get original content
        original_content = Path(settings.authelia_users_file).read_text()

        # Try to write invalid data (simulate failure during write)
        with patch('os.replace', side_effect=IOError("Simulated failure")):
            invalid_users = UsersFile(users={
                "bob": UserConfig(
                    password="$2b$12$xyzabcdefghijklmnopqrstuvwxyz123456789012345678",
                    displayname="Bob",
                    email="bob@example.com",
                    groups=["admins"]
                )
            })

            with pytest.raises(IOError):
                users_handler.save_users(invalid_users, create_backup=False)

        # Verify original file is unchanged
        current_content = Path(settings.authelia_users_file).read_text()
        assert current_content == original_content

        # Verify we can still load original data
        loaded = users_handler.load_users()
        assert "alice" in loaded.users
        assert "bob" not in loaded.users


class TestBackups:
    """Test backup functionality."""

    def test_backup_creation(self, users_handler, settings):
        """Test that backups are created before writes."""
        # Create initial file
        initial_users = UsersFile(users={
            "testuser": UserConfig(
                password="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
                displayname="Test User",
                email="test@example.com",
                groups=["users"]
            )
        })
        users_handler.save_users(initial_users, create_backup=False)

        # Make a change with backup
        updated_users = UsersFile(users={
            "testuser": UserConfig(
                password="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
                displayname="Test User Updated",
                email="test@example.com",
                groups=["users", "admins"]
            )
        })
        users_handler.save_users(updated_users, create_backup=True)

        # Verify backup was created
        backup_dir = Path(settings.backup_dir)
        backups = list(backup_dir.glob("users.yml.bak.*"))
        assert len(backups) > 0

    def test_backup_pruning(self, users_handler, settings):
        """Test that old backups are pruned."""
        # Create initial file
        initial_users = UsersFile(users={
            "testuser": UserConfig(
                password="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
                displayname="Test User",
                email="test@example.com",
                groups=["users"]
            )
        })
        users_handler.save_users(initial_users, create_backup=False)

        # Create multiple backups (more than BACKUP_KEEP)
        for i in range(5):
            users = UsersFile(users={
                f"user{i}": UserConfig(
                    password="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
                    displayname=f"User {i}",
                    email=f"user{i}@example.com",
                    groups=["users"]
                )
            })
            users_handler.save_users(users, create_backup=True)
            import time
            time.sleep(0.1)  # Ensure different timestamps

        # Verify only BACKUP_KEEP backups remain
        backup_dir = Path(settings.backup_dir)
        backups = list(backup_dir.glob("users.yml.bak.*"))
        assert len(backups) == settings.backup_keep


class TestLastAdminProtection:
    """Test last admin protection."""

    def test_cannot_delete_last_admin(self, users_handler):
        """Test that last admin cannot be deleted."""
        # Create users with one admin
        users = UsersFile(users={
            "admin1": UserConfig(
                password="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
                displayname="Admin One",
                email="admin1@example.com",
                groups=["admins", "users"]
            ),
            "user1": UserConfig(
                password="$2b$12$xyzabcdefghijklmnopqrstuvwxyz123456789012345678",
                displayname="User One",
                email="user1@example.com",
                groups=["users"]
            )
        })
        users_handler.save_users(users, create_backup=False)

        # Try to delete the last admin
        with pytest.raises(ValueError, match="last admin"):
            users_handler.delete_user("admin1")

        # Verify admin still exists
        loaded = users_handler.load_users()
        assert "admin1" in loaded.users

    def test_can_delete_admin_if_multiple_exist(self, users_handler):
        """Test that an admin can be deleted if others exist."""
        # Create users with multiple admins
        users = UsersFile(users={
            "admin1": UserConfig(
                password="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
                displayname="Admin One",
                email="admin1@example.com",
                groups=["admins"]
            ),
            "admin2": UserConfig(
                password="$2b$12$xyzabcdefghijklmnopqrstuvwxyz123456789012345678",
                displayname="Admin Two",
                email="admin2@example.com",
                groups=["admins"]
            )
        })
        users_handler.save_users(users, create_backup=False)

        # Delete one admin (should succeed)
        users_handler.delete_user("admin1")

        # Verify deletion
        loaded = users_handler.load_users()
        assert "admin1" not in loaded.users
        assert "admin2" in loaded.users

    def test_can_delete_non_admin(self, users_handler):
        """Test that non-admin users can be deleted."""
        # Create users
        users = UsersFile(users={
            "admin1": UserConfig(
                password="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
                displayname="Admin One",
                email="admin1@example.com",
                groups=["admins"]
            ),
            "user1": UserConfig(
                password="$2b$12$xyzabcdefghijklmnopqrstuvwxyz123456789012345678",
                displayname="User One",
                email="user1@example.com",
                groups=["users"]
            )
        })
        users_handler.save_users(users, create_backup=False)

        # Delete non-admin user (should succeed)
        users_handler.delete_user("user1")

        # Verify deletion
        loaded = users_handler.load_users()
        assert "user1" not in loaded.users
        assert "admin1" in loaded.users


class TestAddUser:
    """Test user addition."""

    def test_add_user_success(self, users_handler):
        """Test successful user addition."""
        users_handler.add_user(
            username="newuser",
            email="newuser@example.com",
            displayname="New User",
            password_hash="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
            groups=["users"]
        )

        # Verify user was added
        loaded = users_handler.load_users()
        assert "newuser" in loaded.users
        assert loaded.users["newuser"].email == "newuser@example.com"

    def test_cannot_add_duplicate_user(self, users_handler):
        """Test that duplicate usernames are rejected."""
        # Add first user
        users_handler.add_user(
            username="testuser",
            email="test@example.com",
            displayname="Test User",
            password_hash="$2b$12$abcdefghijklmnopqrstuvwxyz123456789012345678901",
            groups=["users"]
        )

        # Try to add duplicate
        with pytest.raises(ValueError, match="already exists"):
            users_handler.add_user(
                username="testuser",
                email="different@example.com",
                displayname="Different User",
                password_hash="$2b$12$xyzabcdefghijklmnopqrstuvwxyz123456789012345678",
                groups=["users"]
            )
