"""
User file I/O operations with atomic writes and backups.

Provides:
- Atomic YAML writes (temp → fsync → rename)
- Automatic backups with rotation
- Safe user addition/deletion
- Last admin protection
"""
import os
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging
import tempfile

from config import Settings
from models import UserConfig, UsersFile

logger = logging.getLogger(__name__)


class UsersFileHandler:
    """Handler for Authelia users.yml file operations."""

    def __init__(self, settings: Settings):
        """
        Initialize file handler.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.users_file_path = Path(settings.authelia_users_file)
        self.backup_dir = Path(settings.backup_dir)

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def load_users(self) -> UsersFile:
        """
        Load and parse users.yml file.

        Returns:
            UsersFile object with validated users

        Raises:
            FileNotFoundError: If users file doesn't exist
            ValueError: If YAML is invalid or validation fails
        """
        if not self.users_file_path.exists():
            logger.warning(f"Users file not found: {self.users_file_path}")
            return UsersFile(users={})

        try:
            with open(self.users_file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not data:
                return UsersFile(users={})

            if 'users' not in data or not isinstance(data['users'], dict):
                raise ValueError("Invalid users.yml format: missing or invalid 'users' key")

            # Validate structure using Pydantic model
            users_file = UsersFile(users=data['users'])

            logger.info(f"Loaded {len(users_file.users)} users from {self.users_file_path}")
            return users_file

        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            raise ValueError(f"Invalid YAML format: {e}")
        except Exception as e:
            logger.error(f"Error loading users file: {e}")
            raise

    def save_users(self, users_file: UsersFile, create_backup: bool = True) -> None:
        """
        Save users to file atomically with optional backup.

        Process:
        1. Create backup of current file (if exists and requested)
        2. Write to temporary file
        3. fsync to ensure data is written
        4. Atomic rename to target path
        5. Prune old backups

        Args:
            users_file: UsersFile object to save
            create_backup: Whether to create backup before writing

        Raises:
            IOError: If write fails
        """
        try:
            # Step 1: Create backup
            if create_backup and self.users_file_path.exists():
                self._create_backup()

            # Step 2: Write to temporary file in same directory (ensures same filesystem)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.users_file_path.parent,
                prefix='.users_tmp_',
                suffix='.yml'
            )

            try:
                # Convert to YAML-friendly dict
                data = {'users': {}}
                for username, user_config in users_file.users.items():
                    data['users'][username] = {
                        'password': user_config.password,
                        'displayname': user_config.displayname,
                        'email': user_config.email,
                        'groups': user_config.groups
                    }

                # Write YAML
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                    f.flush()
                    # Step 3: fsync to ensure data is on disk
                    os.fsync(f.fileno())

                # Step 4: Atomic rename
                os.replace(temp_path, self.users_file_path)

                logger.info(f"Successfully saved {len(users_file.users)} users to {self.users_file_path}")

            except Exception as e:
                # Clean up temp file on error
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise

            # Step 5: Prune old backups
            if create_backup:
                self._prune_backups()

        except Exception as e:
            logger.error(f"Error saving users file: {e}")
            raise IOError(f"Failed to save users file: {e}")

    def add_user(
        self,
        username: str,
        email: str,
        displayname: str,
        password_hash: str,
        groups: List[str]
    ) -> None:
        """
        Add a new user to the users file.

        Args:
            username: Username (validated)
            email: Email address (validated)
            displayname: Display name
            password_hash: Bcrypt password hash
            groups: List of group names

        Raises:
            ValueError: If user already exists or validation fails
            IOError: If write fails
        """
        users_file = self.load_users()

        if username in users_file.users:
            raise ValueError(f"User '{username}' already exists")

        # Create new user config (Pydantic will validate)
        new_user = UserConfig(
            password=password_hash,
            displayname=displayname,
            email=email,
            groups=groups
        )

        users_file.users[username] = new_user

        self.save_users(users_file, create_backup=True)

        logger.info(f"Added user '{username}' with groups: {groups}")

    def delete_user(self, username: str) -> None:
        """
        Delete a user from the users file.

        Includes protection against deleting the last admin.

        Args:
            username: Username to delete

        Raises:
            ValueError: If user doesn't exist or is last admin
            IOError: If write fails
        """
        users_file = self.load_users()

        if username not in users_file.users:
            raise ValueError(f"User '{username}' does not exist")

        # Check if this is the last admin
        admin_group = self.settings.admin_group
        user_groups = users_file.users[username].groups

        if admin_group in user_groups:
            # Count total admins
            admin_count = sum(
                1 for user in users_file.users.values()
                if admin_group in user.groups
            )

            if admin_count <= 1:
                raise ValueError(
                    f"Cannot delete last admin user. Admin group: '{admin_group}'"
                )

        del users_file.users[username]

        self.save_users(users_file, create_backup=True)

        logger.info(f"Deleted user '{username}'")

    def get_user(self, username: str) -> Optional[UserConfig]:
        """
        Get a specific user's configuration.

        Args:
            username: Username to retrieve

        Returns:
            UserConfig if found, None otherwise
        """
        users_file = self.load_users()
        return users_file.users.get(username)

    def list_users(self) -> Dict[str, UserConfig]:
        """
        Get all users.

        Returns:
            Dictionary mapping usernames to UserConfig objects
        """
        users_file = self.load_users()
        return users_file.users

    def _create_backup(self) -> Path:
        """
        Create a timestamped backup of the current users file.

        Returns:
            Path to backup file

        Raises:
            IOError: If backup creation fails
        """
        if not self.users_file_path.exists():
            raise IOError("Cannot backup: users file does not exist")

        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        backup_name = f"users.yml.bak.{timestamp}"
        backup_path = self.backup_dir / backup_name

        try:
            shutil.copy2(self.users_file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise IOError(f"Backup creation failed: {e}")

    def _prune_backups(self) -> None:
        """
        Remove old backups, keeping only the most recent BACKUP_KEEP files.
        """
        try:
            # Find all backup files
            backups = sorted(
                self.backup_dir.glob('users.yml.bak.*'),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # Remove excess backups
            for backup in backups[self.settings.backup_keep:]:
                backup.unlink()
                logger.info(f"Pruned old backup: {backup}")

        except Exception as e:
            logger.warning(f"Error pruning backups: {e}")


def validate_no_duplicate_emails(users_file: UsersFile) -> None:
    """
    Validate that no duplicate emails exist.

    Args:
        users_file: UsersFile to validate

    Raises:
        ValueError: If duplicate emails found
    """
    emails = {}
    for username, user in users_file.users.items():
        email_lower = user.email.lower()
        if email_lower in emails:
            raise ValueError(
                f"Duplicate email '{user.email}' for users "
                f"'{emails[email_lower]}' and '{username}'"
            )
        emails[email_lower] = username
