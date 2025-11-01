"""
SQLite database operations for reading Authelia data
"""
import sqlite3
from typing import Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AutheliaDatabase:
    """Handler for reading Authelia SQLite database"""

    def __init__(self, db_path: str):
        """
        Initialize database connection

        Args:
            db_path: Path to the Authelia SQLite database
        """
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_totp_status(self, username: str) -> Optional[Dict]:
        """
        Get TOTP/2FA status for a specific user

        Args:
            username: The username to check

        Returns:
            Dictionary with TOTP info or None if not configured
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT username, created_at, last_used_at, algorithm, digits, period
                FROM totp_configurations
                WHERE username = ?
            """

            cursor.execute(query, (username,))
            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    'username': row['username'],
                    'created_at': row['created_at'],
                    'last_used_at': row['last_used_at'],
                    'algorithm': row['algorithm'],
                    'digits': row['digits'],
                    'period': row['period']
                }
            return None

        except sqlite3.Error as e:
            logger.error(f"Database error getting TOTP status for {username}: {e}")
            return None

    def get_all_totp_configs(self) -> Dict[str, Dict]:
        """
        Get all TOTP configurations

        Returns:
            Dictionary mapping usernames to their TOTP configs
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT username, created_at, last_used_at, algorithm, digits, period
                FROM totp_configurations
            """

            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()

            totp_configs = {}
            for row in rows:
                totp_configs[row['username']] = {
                    'created_at': row['created_at'],
                    'last_used_at': row['last_used_at'],
                    'algorithm': row['algorithm'],
                    'digits': row['digits'],
                    'period': row['period']
                }

            return totp_configs

        except sqlite3.Error as e:
            logger.error(f"Database error getting all TOTP configs: {e}")
            return {}

    def get_authentication_logs(self, username: str, limit: int = 10) -> list:
        """
        Get recent authentication logs for a user

        Args:
            username: The username to get logs for
            limit: Maximum number of logs to return

        Returns:
            List of authentication log entries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT time, successful, banned, auth_type, remote_ip, request_uri
                FROM authentication_logs
                WHERE username = ?
                ORDER BY time DESC
                LIMIT ?
            """

            cursor.execute(query, (username, limit))
            rows = cursor.fetchall()
            conn.close()

            logs = []
            for row in rows:
                logs.append({
                    'time': row['time'],
                    'successful': bool(row['successful']),
                    'banned': bool(row['banned']),
                    'auth_type': row['auth_type'],
                    'remote_ip': row['remote_ip'],
                    'request_uri': row['request_uri']
                })

            return logs

        except sqlite3.Error as e:
            logger.error(f"Database error getting auth logs for {username}: {e}")
            return []
