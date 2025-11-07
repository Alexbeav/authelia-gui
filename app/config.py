"""
Configuration management for Authelia GUI.

Reads environment variables at startup with sensible defaults.
All settings are immutable after initialization.
"""
import os
import secrets
from typing import Optional
from pydantic import BaseModel, Field, validator


class Settings(BaseModel):
    """Application configuration from environment variables."""

    # Server
    port: int = Field(default=8080, env='PORT')

    # File paths
    authelia_users_file: str = Field(
        default='/data/users.yml',
        env='AUTHELIA_USERS_FILE'
    )
    backup_dir: str = Field(
        default='/data/backups',
        env='BACKUP_DIR'
    )
    backup_keep: int = Field(
        default=10,
        env='BACKUP_KEEP'
    )
    audit_db_path: str = Field(
        default='/data/audits.db',
        env='AUDIT_DB_PATH'
    )

    # Authelia integration
    authelia_container: str = Field(
        default='authelia',
        env='AUTHELIA_CONTAINER'
    )
    authelia_config_file: str = Field(
        default='/config/configuration.yml',
        env='AUTHELIA_CONFIG_FILE'
    )
    restart_cmd: str = Field(
        default='echo "RESTART_CMD not configured - set this to restart Authelia (e.g., docker restart authelia or systemctl restart authelia)"',
        env='RESTART_CMD'
    )
    health_url: str = Field(
        default='http://authelia:9091/api/health',
        env='HEALTH_URL'
    )
    health_timeout_seconds: int = Field(
        default=30,
        env='HEALTH_TIMEOUT_SECONDS'
    )
    force_restart: bool = Field(
        default=False,
        env='FORCE_RESTART'
    )
    watch_mode_timeout: int = Field(
        default=10,
        env='WATCH_MODE_TIMEOUT'
    )

    # Security
    session_ttl_minutes: int = Field(
        default=30,
        env='SESSION_TTL_MINUTES'
    )
    admin_group: str = Field(
        default='authelia-admins',
        env='ADMIN_GROUP'
    )
    csrf_secret: str = Field(
        default_factory=lambda: secrets.token_hex(32),
        env='CSRF_SECRET'
    )

    # Logging
    log_level: str = Field(
        default='INFO',
        env='LOG_LEVEL'
    )

    class Config:
        env_file = '.env'
        case_sensitive = False

    @validator('backup_keep')
    def validate_backup_keep(cls, v):
        if v < 1:
            raise ValueError('BACKUP_KEEP must be at least 1')
        return v

    @validator('health_timeout_seconds')
    def validate_health_timeout(cls, v):
        if v < 1 or v > 300:
            raise ValueError('HEALTH_TIMEOUT_SECONDS must be between 1 and 300')
        return v

    @validator('session_ttl_minutes')
    def validate_session_ttl(cls, v):
        if v < 1 or v > 1440:
            raise ValueError('SESSION_TTL_MINUTES must be between 1 and 1440')
        return v


def get_settings() -> Settings:
    """
    Get application settings from environment.

    Returns:
        Settings object with configuration
    """
    return Settings(
        port=int(os.getenv('PORT', '8080')),
        authelia_users_file=os.getenv('AUTHELIA_USERS_FILE', '/data/users.yml'),
        backup_dir=os.getenv('BACKUP_DIR', '/data/backups'),
        backup_keep=int(os.getenv('BACKUP_KEEP', '10')),
        audit_db_path=os.getenv('AUDIT_DB_PATH', '/data/audits.db'),
        authelia_container=os.getenv('AUTHELIA_CONTAINER', 'authelia'),
        authelia_config_file=os.getenv('AUTHELIA_CONFIG_FILE', '/config/configuration.yml'),
        restart_cmd=os.getenv('RESTART_CMD', 'echo "RESTART_CMD not configured - set this to restart Authelia (e.g., docker restart authelia or systemctl restart authelia)"'),
        health_url=os.getenv('HEALTH_URL', 'http://authelia:9091/api/health'),
        health_timeout_seconds=int(os.getenv('HEALTH_TIMEOUT_SECONDS', '30')),
        force_restart=os.getenv('FORCE_RESTART', 'false').lower() == 'true',
        watch_mode_timeout=int(os.getenv('WATCH_MODE_TIMEOUT', '10')),
        session_ttl_minutes=int(os.getenv('SESSION_TTL_MINUTES', '30')),
        admin_group=os.getenv('ADMIN_GROUP', 'authelia-admins'),
        csrf_secret=os.getenv('CSRF_SECRET', secrets.token_hex(32)),
        log_level=os.getenv('LOG_LEVEL', 'INFO')
    )
