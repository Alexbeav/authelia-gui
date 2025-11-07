# Authelia User Management GUI v0.2

Production-grade web interface for managing [Authelia](https://www.authelia.com/) file provider users with comprehensive security features and intelligent watch mode support.

![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **User Management**: Create and delete users with strict validation
- **Security**: RBAC, CSRF protection, session management, security headers
- **Atomic Operations**: Safe file writes with backups and rollback
- **Audit Logging**: Complete audit trail of all operations in SQLite
- **Intelligent Restart**: Automatically detects Authelia watch mode and adapts behavior
- **Health Monitoring**: Automated Authelia restart with health polling when needed
- **Last Admin Protection**: Prevents deletion of the last administrator
- **Responsive UI**: Clean, modern interface with modal dialogs, toast notifications, and watch mode status indicator

## Architecture

Built with production-grade security and reliability:

- **Framework**: FastAPI with Uvicorn (async ASGI)
- **Security**: Starlette middleware for RBAC, CSRF, and session management
- **Validation**: Pydantic models with strict validation rules
- **Storage**: Atomic YAML writes with fsync, automated backups
- **Audit**: SQLite database with full operation history
- **Watch Mode Detection**: Intelligent detection of Authelia's file provider watch mode
- **Adaptive Behavior**: Automatically chooses between restart or watch-based reload
- **Deployment**: Hardened Docker container running as non-root user

## Security Features

### RBAC (Role-Based Access Control)
- Enforces admin group membership via `X-Forwarded-Groups` header
- All state-changing operations require admin privileges
- Configurable admin group name (default: `authelia-admins`)

### CSRF Protection
- Double-submit cookie pattern using `itsdangerous`
- All POST requests must include valid `X-CSRF-Token` header
- Tokens expire after 1 hour

### Session Management
- 30-minute idle timeout (configurable)
- Signed session cookies with timestamp
- Automatic session refresh on activity

### Security Headers
```
Content-Security-Policy: default-src 'self'; frame-ancestors 'none';
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Strict-Transport-Security: max-age=31536000
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
```

## Watch Mode Support

The GUI intelligently detects whether Authelia's file provider has watch mode enabled and adapts its behavior accordingly.

### How It Works

1. **Detection**: The GUI reads your Authelia `configuration.yml` and checks the `authentication_backend.file.watch` setting
2. **Adaptive Behavior**:
   - **Watch Mode Enabled** (`watch: true`): GUI waits for Authelia to auto-detect file changes (typically 1-2 seconds)
   - **Watch Mode Disabled** (`watch: false` or missing): GUI triggers a container restart and polls health endpoint
   - **Force Restart** (`FORCE_RESTART=true`): Always restarts regardless of watch mode setting

### Authelia Configuration

To enable watch mode in Authelia, add this to your `configuration.yml`:

```yaml
authentication_backend:
  file:
    path: /config/users.yml
    watch: true  # Enable automatic file change detection
```

### Environment Variables

- **`AUTHELIA_CONFIG_FILE`** (default: `/config/configuration.yml`): Path to Authelia's configuration file for watch mode detection
- **`FORCE_RESTART`** (default: `false`): Set to `true` to always restart Authelia, bypassing watch mode
- **`WATCH_MODE_TIMEOUT`** (default: `10`): Seconds to wait for watch mode reload before timeout

### UI Indicator

The dashboard displays a status badge showing the current mode:

- 🟢 **Auto-Reload (Watch Enabled)**: File changes detected automatically within seconds
- 🟡 **Restart (Forced)**: Restart is forced via `FORCE_RESTART` setting
- 🔵 **Restart Required**: Watch mode not enabled, changes applied via restart

### Benefits

- **Faster Updates**: Watch mode typically applies changes in 1-2 seconds vs 10-30 seconds for restart
- **No Downtime**: Authelia remains available while reloading user file
- **Automatic Detection**: No manual configuration needed—GUI adapts automatically
- **Override Option**: Can force restarts if needed via `FORCE_RESTART=true`

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Authelia instance with file provider
- Reverse proxy (Traefik, Nginx, etc.) configured to forward headers

### Docker Compose Example

```yaml
version: '3.8'

services:
  authelia-gui:
    image: authelia-gui:0.2.0
    build: .
    container_name: authelia-gui
    user: "1000:1000"
    environment:
      PORT: 8080
      AUTHELIA_USERS_FILE: /data/users.yml
      AUTHELIA_CONFIG_FILE: /data/configuration.yml
      BACKUP_DIR: /data/backups
      BACKUP_KEEP: 10
      AUTHELIA_CONTAINER: authelia
      RESTART_CMD: docker restart authelia
      HEALTH_URL: http://authelia:9091/api/health
      HEALTH_TIMEOUT_SECONDS: 30
      WATCH_MODE_TIMEOUT: 10
      FORCE_RESTART: false
      SESSION_TTL_MINUTES: 30
      ADMIN_GROUP: authelia-admins
      CSRF_SECRET: your-secure-secret-here-32-chars
      AUDIT_DB_PATH: /data/audits.db
      LOG_LEVEL: INFO
    volumes:
      - /volume1/docker/identity/authelia:/data
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - authelia-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

### Reverse Proxy Configuration

#### Traefik Example

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.authelia-gui.rule=Host(`auth-users.example.com`)"
  - "traefik.http.routers.authelia-gui.entrypoints=websecure"
  - "traefik.http.routers.authelia-gui.tls=true"

  # Require authentication via Authelia
  - "traefik.http.routers.authelia-gui.middlewares=authelia@docker"

  # Forward user and groups headers
  - "traefik.http.middlewares.authelia.forwardauth.address=http://authelia:9091/api/verify?rd=https://auth.example.com"
  - "traefik.http.middlewares.authelia.forwardauth.trustForwardHeader=true"
  - "traefik.http.middlewares.authelia.forwardauth.authResponseHeaders=Remote-User,Remote-Groups,Remote-Name,Remote-Email"
```

#### Nginx Example

```nginx
location / {
    # Forward to Authelia for authentication
    auth_request /authelia;

    # Get user info from Authelia
    auth_request_set $user $upstream_http_remote_user;
    auth_request_set $groups $upstream_http_remote_groups;

    # Forward headers to application
    proxy_set_header X-Forwarded-User $user;
    proxy_set_header X-Forwarded-Groups $groups;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;

    proxy_pass http://authelia-gui:8080;
}

location /authelia {
    internal;
    proxy_pass http://authelia:9091/api/verify;
    proxy_set_header X-Original-URL $scheme://$http_host$request_uri;
    proxy_set_header Content-Length "";
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | HTTP port to listen on |
| `AUTHELIA_USERS_FILE` | `/data/users.yml` | Path to Authelia users file |
| `AUTHELIA_CONFIG_FILE` | `/config/configuration.yml` | Path to Authelia config for watch mode detection |
| `BACKUP_DIR` | `/data/backups` | Directory for user file backups |
| `BACKUP_KEEP` | `10` | Number of backups to retain |
| `AUTHELIA_CONTAINER` | `authelia` | Authelia container name |
| `RESTART_CMD` | `docker restart authelia` | Command to restart Authelia |
| `HEALTH_URL` | `http://authelia:9091/api/health` | Authelia health check URL |
| `HEALTH_TIMEOUT_SECONDS` | `30` | Health check timeout (seconds) |
| `WATCH_MODE_TIMEOUT` | `10` | Watch mode reload timeout (seconds) |
| `FORCE_RESTART` | `false` | Force restart even if watch mode is enabled |
| `SESSION_TTL_MINUTES` | `30` | Session idle timeout |
| `ADMIN_GROUP` | `authelia-admins` | Required admin group name |
| `CSRF_SECRET` | auto-generated | Secret for CSRF token signing (32+ chars) |
| `AUDIT_DB_PATH` | `/data/audits.db` | Path to audit database |
| `LOG_LEVEL` | `INFO` | Logging level |

## Validation Rules

### Username
- Pattern: `^[a-z0-9][a-z0-9._-]{1,30}[a-z0-9]$`
- Length: 2-32 characters
- Characters: lowercase letters, numbers, dots, underscores, hyphens
- Cannot start or end with dot, underscore, or hyphen

### Email
- Must contain `@` and domain with `.`
- Normalized to lowercase

### Password
- Minimum length: 12 characters (when manually provided)
- Auto-generated passwords: 16 characters with mixed complexity
- Stored as bcrypt hash ($2a$, $2b$, or $2y$)

### Groups
- Normalized to lowercase
- Whitespace trimmed
- Duplicates removed
- Empty strings filtered out

## Development

### Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run unit tests
pytest tests/unit -v

# Run E2E tests (requires Playwright)
playwright install
npx playwright test
```

### Running Locally

```bash
# Set environment variables
export AUTHELIA_USERS_FILE=/path/to/users.yml
export BACKUP_DIR=/path/to/backups
export RESTART_CMD="echo 'Mock restart'"
export HEALTH_URL="http://localhost:9091/api/health"

# Run application
cd app
python -m uvicorn app:app --reload --port 8080
```

### Building Docker Image

```bash
docker build -t authelia-gui:0.2.0 .
```

## Troubleshooting

### Watch mode not detecting changes

**Symptom**: Dashboard shows "Auto-Reload" but changes not reflected in Authelia
**Solution**:
- Verify `authentication_backend.file.watch: true` is set in Authelia's `configuration.yml`
- Check Authelia logs for file watcher errors (common with some Docker bind mounts)
- Increase `WATCH_MODE_TIMEOUT` if Authelia is slow to detect changes
- Use `FORCE_RESTART=true` to bypass watch mode and force restarts

### Watch mode timeout

**Symptom**: "Watch mode reload timeout after 10 seconds"
**Solution**:
- Changes are already saved to the file
- Check Authelia logs to verify file detection is working
- Increase `WATCH_MODE_TIMEOUT` environment variable
- Verify `HEALTH_URL` is correct and Authelia is responding

### Users file not updating

**Symptom**: Changes not reflected in Authelia
**Solution**:
- Check the watch mode status badge on the dashboard
- If using watch mode, check Authelia logs for file watcher issues with Docker bind mounts
- If using restart mode, verify `RESTART_CMD` has permission to restart the container
- GUI saves changes regardless—check the backup directory to confirm file writes

### Health check timeout

**Symptom**: "Health check timed out after 30 seconds"
**Solution**:
- Changes are saved successfully to users file
- Increase `HEALTH_TIMEOUT_SECONDS` or check Authelia startup time
- Verify `HEALTH_URL` is accessible from the GUI container
- Check Authelia container logs for startup errors

### Cannot delete last admin

**Symptom**: "Cannot delete last admin user"
**Solution**: This is intentional protection. Create another admin user first before deleting.

### RBAC 403 errors

**Symptom**: "Admin group required"
**Solution**: Ensure reverse proxy forwards `X-Forwarded-Groups` header and user is in `ADMIN_GROUP`.

### CSRF validation failed

**Symptom**: "Invalid or missing CSRF token"
**Solution**: Ensure JavaScript is enabled and cookies are allowed. Check browser console for errors.

### Cannot read Authelia configuration

**Symptom**: Watch mode detection fails, always uses restart
**Solution**:
- Verify `AUTHELIA_CONFIG_FILE` points to the correct path
- Ensure the configuration file is mounted in the GUI container
- Check file permissions—GUI must have read access to configuration.yml
- Fallback to restart mode is safe—no functionality is lost

## Security Best Practices

1. **Deploy behind Authelia**: Never expose this GUI publicly without authentication
2. **Use HTTPS**: Always use TLS/SSL (handled by reverse proxy)
3. **Restrict admin group**: Only assign `ADMIN_GROUP` to trusted users
4. **Rotate CSRF secret**: Generate a new `CSRF_SECRET` periodically
5. **Monitor audit logs**: Regularly review `/audit` endpoint for suspicious activity
6. **Backup database**: Backup `/data/audits.db` along with users file
7. **Mount docker socket read-only**: Use `:ro` when mounting docker socket

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please ensure:
- All tests pass (`pytest`)
- Code follows PEP 8
- Security best practices maintained
- Documentation updated

## Support

For issues, questions, or contributions, please visit the GitHub repository.

---

**Version:** v0.2.0
**Status:** Production-ready
**Last Updated:** 2025-11-07
