# Changelog

All notable changes to Authelia User Management GUI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-11-07

### Added
- **Core Features**
  - User creation with strict validation and automatic password generation
  - User deletion with last-admin protection
  - Modern dashboard with search, modals, and toast notifications
  - Real-time user statistics display

- **Security**
  - RBAC enforcement via X-Forwarded-Groups header for all state-changing operations (POST, PUT, PATCH, DELETE)
  - CSRF protection using double-submit cookie pattern with signed tokens
  - Support for both X-CSRF-Token header and csrf_token form field
  - Session management with configurable TTL (default: 30 minutes)
  - Comprehensive security headers (CSP, X-Frame-Options, HSTS, etc.)
  - Auto-generated CSRF_SECRET if not provided

- **File Operations**
  - Atomic YAML writes using temp → fsync → rename pattern
  - Automatic backups with configurable retention (default: 10)
  - File locking with portalocker to prevent concurrent write corruption
  - Backup pruning to maintain disk space

- **Watch Mode Support**
  - Intelligent detection of Authelia's file provider watch mode
  - Conditional restart: skips restart when watch mode enabled
  - Health polling after restarts to verify Authelia availability
  - UI status indicator showing current mode (Auto-Reload, Restart Required, or Forced)
  - Configurable timeouts for both restart and watch mode

- **Validation & Safety**
  - Strict username regex: lowercase alphanumeric, 2-32 chars, with . _ - allowed (but not at start/end)
  - Email validation and normalization
  - Duplicate username detection
  - Duplicate email detection (case-insensitive)
  - Password minimum length: 12 characters
  - Bcrypt password hashing with proper salting
  - Last admin protection prevents deletion of final admin user

- **Audit Logging**
  - Complete audit trail in SQLite database
  - Logs actor, action, target, timestamp, IP address, and metadata
  - No plaintext passwords stored (only hash prefix for tracking)
  - Configurable database path via AUDIT_DB_PATH

- **Testing**
  - Comprehensive unit tests for RBAC enforcement
  - CSRF validation tests for all HTTP methods
  - Watch mode detection and conditional restart tests
  - Actor and IP extraction tests
  - Security headers validation tests
  - Atomic write and backup tests
  - Validation tests for user creation

- **Deployment**
  - Hardened Docker container running as non-root user (uid:gid 1000:1000)
  - Health check endpoint at /health
  - Configurable PORT with proper environment variable substitution
  - Minimal attack surface with Alpine-based image
  - Production-ready logging with configurable levels

### Configuration
- **New Environment Variables**
  - `PORT`: HTTP port (default: 8080)
  - `AUTHELIA_USERS_FILE`: Path to users.yml (default: /data/users.yml)
  - `AUTHELIA_CONFIG_FILE`: Path to configuration.yml for watch mode detection (default: /config/configuration.yml)
  - `BACKUP_DIR`: Backup directory (default: /data/backups)
  - `BACKUP_KEEP`: Number of backups to retain (default: 10)
  - `AUDIT_DB_PATH`: Audit database path (default: /data/audits.db)
  - `RESTART_CMD`: Command to restart Authelia (default: safe no-op with instructions)
  - `HEALTH_URL`: Authelia health check URL (default: http://authelia:9091/api/health)
  - `HEALTH_TIMEOUT_SECONDS`: Health check timeout (default: 30)
  - `FORCE_RESTART`: Force restart even if watch mode enabled (default: false)
  - `WATCH_MODE_TIMEOUT`: Watch mode reload timeout (default: 10)
  - `SESSION_TTL_MINUTES`: Session idle timeout (default: 30)
  - `ADMIN_GROUP`: Required admin group name (default: authelia-admins)
  - `CSRF_SECRET`: Secret for CSRF token signing (auto-generated if not set)
  - `LOG_LEVEL`: Logging level (default: INFO)

### Security
- All state-changing operations require admin group membership
- CSRF tokens validated on POST, PUT, PATCH, DELETE requests
- Session cookies with HttpOnly, Secure, and SameSite flags
- CSP prevents XSS and frame injection
- HSTS enforces HTTPS in production
- No secrets logged in audit trail

### Documentation
- Comprehensive README with:
  - Security model explanation
  - Environment variable documentation
  - Docker Compose examples
  - Reverse proxy configuration (Traefik, Nginx)
  - Troubleshooting guide
  - Watch mode behavior documentation
- Inline code documentation with docstrings
- Type hints throughout codebase

### Dependencies
- fastapi==0.104.1
- uvicorn[standard]==0.24.0
- pydantic==2.5.0
- pyyaml==6.0.1
- passlib[bcrypt]==1.7.4
- bcrypt==4.1.1
- itsdangerous==2.1.2
- httpx==0.25.1
- portalocker==2.8.2
- pytest==7.4.3
- pytest-asyncio==0.21.1
- playwright==1.40.0

### Notes
- This release is production-ready for homelab and SMB deployments
- Must be deployed behind Authelia with reverse proxy providing X-Forwarded-* headers
- Designed for Authelia file provider (not LDAP)
- Watch mode requires Authelia configuration: `authentication_backend.file.watch: true`
- RESTART_CMD must be configured by operator for restart functionality

### Known Limitations
- No user editing/update functionality (create and delete only)
- No password reset UI (use Authelia's built-in flows)
- No CSV import/export
- No LDAP backend support

[0.1.0]: https://github.com/Alexbeav/authelia-gui/releases/tag/v0.1.0
