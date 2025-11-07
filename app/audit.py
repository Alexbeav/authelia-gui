"""
Audit logging for user management operations.

Stores audit records in SQLite database with:
- Timestamp
- Actor (username)
- Action (CREATE/DELETE)
- Target (username affected)
- Details (JSON metadata, no secrets)
- IP address
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

from config import Settings

logger = logging.getLogger(__name__)


class AuditLogger:
    """Handler for audit log database operations."""

    def __init__(self, settings: Settings):
        """
        Initialize audit logger.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.db_path = Path(settings.audit_db_path)

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

    def _init_database(self) -> None:
        """Create audit log table if it doesn't exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target TEXT NOT NULL,
                    details TEXT,
                    ip TEXT
                )
            """)

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON audit_log(timestamp DESC)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_actor
                ON audit_log(actor)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_target
                ON audit_log(target)
            """)

            conn.commit()
            conn.close()

            logger.info(f"Audit database initialized: {self.db_path}")

        except sqlite3.Error as e:
            logger.error(f"Failed to initialize audit database: {e}")
            raise

    def log_create_user(
        self,
        actor: str,
        username: str,
        email: str,
        groups: List[str],
        password_hash_prefix: str,
        ip: str
    ) -> None:
        """
        Log user creation event.

        Args:
            actor: Who performed the action
            username: Username that was created
            email: Email address
            groups: List of groups
            password_hash_prefix: First 12 chars of password hash (for tracking)
            ip: IP address of requester
        """
        details = {
            'email': email,
            'groups': groups,
            'hash_prefix': password_hash_prefix
        }

        self._log_event(
            actor=actor,
            action='CREATE',
            target=username,
            details=details,
            ip=ip
        )

    def log_delete_user(
        self,
        actor: str,
        username: str,
        ip: str
    ) -> None:
        """
        Log user deletion event.

        Args:
            actor: Who performed the action
            username: Username that was deleted
            ip: IP address of requester
        """
        self._log_event(
            actor=actor,
            action='DELETE',
            target=username,
            details={},
            ip=ip
        )

    def _log_event(
        self,
        actor: str,
        action: str,
        target: str,
        details: Dict[str, Any],
        ip: str
    ) -> None:
        """
        Log an audit event to database.

        Args:
            actor: Username performing action
            action: Action type (CREATE/DELETE)
            target: Target username
            details: Additional details as dict
            ip: IP address
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
            details_json = json.dumps(details)

            cursor.execute(
                """
                INSERT INTO audit_log (timestamp, actor, action, target, details, ip)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (timestamp, actor, action, target, details_json, ip)
            )

            conn.commit()
            conn.close()

            logger.info(
                f"Audit log: {action} user '{target}' by '{actor}' from {ip}",
                extra={
                    'actor': actor,
                    'action': action,
                    'target': target,
                    'ip': ip
                }
            )

        except sqlite3.Error as e:
            logger.error(f"Failed to write audit log: {e}")
            # Don't raise - audit failure shouldn't block operations

    def get_recent_logs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get recent audit log entries.

        Args:
            limit: Maximum number of entries to return
            offset: Number of entries to skip (for pagination)

        Returns:
            List of audit log entries as dicts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, timestamp, actor, action, target, details, ip
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )

            rows = cursor.fetchall()
            conn.close()

            logs = []
            for row in rows:
                log_entry = {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'actor': row['actor'],
                    'action': row['action'],
                    'target': row['target'],
                    'details': json.loads(row['details']) if row['details'] else {},
                    'ip': row['ip']
                }
                logs.append(log_entry)

            return logs

        except sqlite3.Error as e:
            logger.error(f"Failed to read audit logs: {e}")
            return []

    def get_logs_for_user(self, username: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get audit logs related to a specific user.

        Args:
            username: Username to filter by (as actor or target)
            limit: Maximum number of entries to return

        Returns:
            List of audit log entries as dicts
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, timestamp, actor, action, target, details, ip
                FROM audit_log
                WHERE actor = ? OR target = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (username, username, limit)
            )

            rows = cursor.fetchall()
            conn.close()

            logs = []
            for row in rows:
                log_entry = {
                    'id': row['id'],
                    'timestamp': row['timestamp'],
                    'actor': row['actor'],
                    'action': row['action'],
                    'target': row['target'],
                    'details': json.loads(row['details']) if row['details'] else {},
                    'ip': row['ip']
                }
                logs.append(log_entry)

            return logs

        except sqlite3.Error as e:
            logger.error(f"Failed to read audit logs for user {username}: {e}")
            return []

    def get_total_count(self) -> int:
        """
        Get total number of audit log entries.

        Returns:
            Count of audit log entries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM audit_log")
            count = cursor.fetchone()[0]

            conn.close()
            return count

        except sqlite3.Error as e:
            logger.error(f"Failed to get audit log count: {e}")
            return 0
