"""
YAML file operations for Authelia users.yml
"""
import yaml
from typing import Dict, List, Optional
import logging
import os
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)


class AutheliaYAMLHandler:
    """Handler for reading and writing Authelia users.yml"""

    def __init__(self, yaml_path: str):
        """
        Initialize YAML handler

        Args:
            yaml_path: Path to the users.yml file
        """
        self.yaml_path = yaml_path

    def read_users(self) -> Dict:
        """
        Read all users from users.yml

        Returns:
            Dictionary of users with their configuration
        """
        try:
            with open(self.yaml_path, 'r') as f:
                data = yaml.safe_load(f)

            if not data or 'users' not in data:
                logger.warning(f"No users found in {self.yaml_path}")
                return {}

            return data['users']

        except FileNotFoundError:
            logger.error(f"Users file not found: {self.yaml_path}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error reading users: {e}")
            return {}

    def get_user(self, username: str) -> Optional[Dict]:
        """
        Get a specific user's configuration

        Args:
            username: The username to retrieve

        Returns:
            User configuration dictionary or None if not found
        """
        users = self.read_users()
        return users.get(username)

    def get_all_users_list(self) -> List[Dict]:
        """
        Get all users as a list with username included

        Returns:
            List of user dictionaries with username field added
        """
        users = self.read_users()
        users_list = []

        for username, config in users.items():
            user_dict = {
                'username': username,
                'email': config.get('email', ''),
                'displayname': config.get('displayname', ''),
                'groups': config.get('groups', []),
                'password_hash': config.get('password', '')
            }
            users_list.append(user_dict)

        return users_list

    def backup_users_file(self) -> str:
        """
        Create a backup of the users.yml file

        Returns:
            Path to the backup file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{self.yaml_path}.backup_{timestamp}"

        try:
            shutil.copy2(self.yaml_path, backup_path)
            logger.info(f"Backup created: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            raise

    def write_users(self, users_dict: Dict, create_backup: bool = True) -> bool:
        """
        Write users dictionary to users.yml with proper YAML formatting

        Args:
            users_dict: Dictionary of users to write
            create_backup: Whether to create a backup before writing

        Returns:
            True if successful, False otherwise
        """
        try:
            if create_backup:
                self.backup_users_file()

            # Write YAML manually matching alexbeav format
            # (no quotes, with email field)
            with open(self.yaml_path, 'w') as f:
                f.write('users:\n')
                for username, config in users_dict.items():
                    f.write(f'  {username}:\n')
                    # Password without quotes
                    password = config.get('password', '')
                    f.write(f'    password: {password}\n')
                    # Displayname without quotes
                    displayname = config.get('displayname', '')
                    f.write(f'    displayname: {displayname}\n')
                    # Email field (required)
                    email = config.get('email', '')
                    f.write(f'    email: {email}\n')
                    # Groups
                    groups = config.get('groups', [])
                    f.write('    groups:\n')
                    for group in groups:
                        f.write(f'    - {group}\n')

            logger.info(f"Users file updated: {self.yaml_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing users file: {e}")
            return False

    def add_user(self, username: str, email: str, displayname: str,
                 password_hash: str, groups: List[str] = None) -> bool:
        """
        Add a new user to users.yml

        Args:
            username: Username for the new user
            email: Email address
            displayname: Display name
            password_hash: Argon2id hashed password
            groups: List of groups (default: empty list)

        Returns:
            True if successful, False otherwise
        """
        try:
            users = self.read_users()

            if username in users:
                logger.error(f"User {username} already exists")
                return False

            users[username] = {
                'password': password_hash,
                'displayname': displayname,
                'email': email,
                'groups': groups or []
            }

            return self.write_users(users)

        except Exception as e:
            logger.error(f"Error adding user {username}: {e}")
            return False

    def delete_user(self, username: str) -> bool:
        """
        Delete a user from users.yml

        Args:
            username: Username to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            users = self.read_users()

            if username not in users:
                logger.error(f"User {username} does not exist")
                return False

            del users[username]
            logger.info(f"Deleting user {username}")

            return self.write_users(users)

        except Exception as e:
            logger.error(f"Error deleting user {username}: {e}")
            return False
