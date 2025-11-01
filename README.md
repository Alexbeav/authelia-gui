# Authelia User Management GUI

A modern, lightweight web GUI for managing Authelia users. Built with FastAPI and designed for self-hosted authentication deployments.

![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **User Dashboard** - View all users with 2FA status at a glance
- **User Creation** - Create new users with auto-generated or manual passwords
- **User Deletion** - Remove users with admin protection safeguards
- **2FA Status** - Real-time display of TOTP configuration status
- **Authentication Logs** - View recent login attempts per user
- **Dark Mode** - Eye-friendly theme with persistent preference
- **Responsive Design** - Works seamlessly on desktop and mobile
- **Admin Protection** - Prevents deletion of the last admin user
- **Automatic Backups** - Creates backups before modifying users.yml

## Technology Stack

- Backend: FastAPI (Python 3.11)
- Templates: Jinja2
- Database: SQLite (read-only for 2FA status)
- Config: YAML (read/write with backups)
- Deployment: Docker
- Integration: Authelia CLI via docker exec

## Quick Start

### Prerequisites

- Authelia v4.x running in Docker
- Docker and Docker Compose
- Access to Authelia configuration directory
- Access to Docker socket (for password hashing)

### Installation

1. Clone this repository:
```bash
git clone https://github.com/Alexbeav/authelia-gui.git
cd authelia-gui
```

2. Configure docker-compose.yml with your paths:
```yaml
services:
  authelia-gui:
    container_name: authelia-gui
    build: ./authelia-gui
    ports:
      - "172.16.1.8:8081:8080"  # Change to your internal IP
    volumes:
      - /path/to/authelia:/authelia
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - AUTHELIA_PATH=/authelia
    restart: unless-stopped
```

3. Build and run:
```bash
docker-compose up -d authelia-gui
```

4. Access at http://YOUR_IP:8081

## Usage

### Creating a User
1. Click "+ Create User"
2. Fill in username, email, display name
3. Choose auto-generate or manual password
4. Select groups
5. Save - Authelia will restart automatically

### Deleting a User
1. Click "Delete" (red button)
2. Confirm deletion
3. User removed and Authelia restarted

**Note:** Cannot delete the last admin user

## Security

- **Internal use only** - Do not expose to internet
- Bind to internal IP only
- File backups created before all write operations
- Admin safeguards prevent lockout

## Known Limitations

- Authelia restarts after user changes (~2-3s downtime)
- File watching doesn't work reliably with Docker bind mounts
- Database is read-only (2FA status only)

## Roadmap

**Phase 3: Password Management**
- Password reset for existing users
- Force password reset on next login
- Password reset UI

**Technical Improvements**
- Eliminate restart requirement
- User editing functionality
- Group management
- Bulk operations
- Audit log viewer

## Development

Local development:
```bash
pip install -r requirements.txt
cd app
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

## Contributing

Contributions welcome! Please submit Pull Requests.

## License

MIT License

## Acknowledgments

Built for [Authelia](https://www.authelia.com/) with love for self-hosters.

## Support

For issues or feature requests, please open an issue on GitHub.

---

**Current Version:** v0.1.0
**Status:** Production-ready
**Last Updated:** 2025-11-02
