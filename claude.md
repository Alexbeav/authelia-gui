# Authelia User Management GUI

## Project Overview
This project aims to create a simple, lightweight web-based GUI for managing Authelia users on the Ulduar Synology NAS. Authelia is an authentication and authorization server that provides single sign-on and two-factor authentication for web applications.

## Current State
- **Authelia Location**: `/volume1/docker/identity`
- **Users File**: `/volume1/docker/identity/authelia/users.yml`
- **Database**: `/volume1/docker/identity/authelia/config/db.sqlite3`
- **Current Users**:
  - alexbeav@live.com (username: alexbeav, 2FA enabled)

## Data Storage Architecture

### users.yml
Contains basic user authentication information:
- Username
- Hashed password (argon2id)
- Display name
- Email address
- Groups (e.g., admins)

Example structure:
```yaml
users:
  alexbeav:
    password: '$argon2id$v=19$m=65536,t=3,p=4$...'
    displayname: 'Alexandros Mandravillis'
    email: alexbeav@live.com
    groups:
      - admins
```

### db.sqlite3
Contains extended user data and session information:
- **totp_configurations**: TOTP/2FA setup status and configuration
- **webauthn_credentials**: Hardware key/WebAuthn credentials
- **user_preferences**: User's preferred 2FA method
- **authentication_logs**: Login history and attempt logs

## Project Goals

### Phase 1 - View Users (MVP)
Create a read-only dashboard showing:
- Username
- Email address
- Display name
- 2FA Status (TOTP enabled/disabled)
- Groups/Roles
- Last login information (if available)

### Phase 2 - User Creation
Add functionality to:
- Create new users with username, email, display name
- Generate secure initial passwords
- Assign users to groups
- Send welcome emails with initial credentials

### Phase 3 - Password Management
Implement features to:
- Force password reset on next login
- Reset user passwords
- Set password expiration policies

### Phase 4 - Enhanced Features (Future)
- Disable/enable user accounts
- Manage user groups
- View authentication logs per user
- Manage 2FA devices (view, revoke)
- WebAuthn device management

## Technical Architecture

### Technology Stack Options

#### Option 1: Python + Flask/FastAPI (Recommended)
**Pros:**
- Easy SQLite integration
- Simple YAML parsing
- Lightweight and fast
- Good for server-side rendering
- Can run as a Docker container alongside Authelia

**Stack:**
- Backend: FastAPI or Flask
- Frontend: Jinja2 templates + Tailwind CSS (or similar)
- Database: Direct SQLite3 access (read-only for 2FA data)
- YAML: PyYAML for users.yml manipulation

#### Option 2: Node.js + Express
**Pros:**
- Modern JavaScript ecosystem
- Easy JSON/YAML handling
- Good npm package availability

**Stack:**
- Backend: Express.js
- Frontend: EJS/Pug templates or React/Vue SPA
- Database: better-sqlite3 or sqlite3
- YAML: js-yaml

#### Option 3: Go
**Pros:**
- Single binary deployment
- Fast and efficient
- Good concurrency for future scaling

**Stack:**
- Backend: Gin or Echo framework
- Frontend: HTML templates
- Database: go-sqlite3
- YAML: gopkg.in/yaml.v3

### Recommended Approach: Python + FastAPI

#### Project Structure
```
/volume1/docker/identity/authelia-gui/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── models.py            # Data models (User, TOTP, etc.)
│   ├── database.py          # SQLite database connections
│   ├── yaml_handler.py      # YAML file operations
│   ├── auth.py              # Authentication for GUI access
│   └── routers/
│       ├── users.py         # User management endpoints
│       └── dashboard.py     # Dashboard views
├── templates/
│   ├── base.html           # Base template
│   ├── dashboard.html      # User list view
│   ├── user_create.html    # User creation form
│   └── user_detail.html    # User detail view
├── static/
│   ├── css/
│   └── js/
├── requirements.txt
├── Dockerfile
├── docker-compose.yml      # To run GUI alongside Authelia
└── README.md
```

#### Security Considerations
1. **Authentication**: GUI must be protected (use Authelia itself or basic auth)
2. **File Permissions**: Ensure proper read/write access to users.yml
3. **Backup**: Always backup users.yml before modifications
4. **Password Hashing**: Use Authelia's argon2id settings for new passwords
5. **Validation**: Strict input validation for all user data
6. **Audit Logging**: Log all user management actions

#### Integration with Authelia
- Read-only access to db.sqlite3 (don't modify it directly)
- Read/write access to users.yml with proper file locking
- After modifying users.yml, may need to restart Authelia or wait for refresh interval (currently 5m)
- Consider adding API endpoint to trigger Authelia reload

## Implementation Phases

### Phase 1: Setup & Read-Only Dashboard
1. Set up Python environment and dependencies
2. Create database reader for SQLite
3. Create YAML reader for users.yml
4. Build basic dashboard UI showing all users
5. Display user details with 2FA status

### Phase 2: User Creation
1. Create user creation form
2. Implement argon2id password hashing
3. Add YAML write functionality with backup
4. Add user to users.yml
5. Optional: Email notification to new user

### Phase 3: Password Reset Flag
1. Research password reset mechanism in Authelia
2. Implement force password reset on next login
3. Add UI controls for password management

### Phase 4: Enhancement & Deployment
1. Dockerize the application
2. Add to docker-compose.yml
3. Secure with Authelia authentication
4. Add comprehensive error handling
5. Create user documentation

## Development Guidelines

### Code Standards
- Follow PEP 8 for Python code
- Use type hints throughout
- Write docstrings for all functions
- Include error handling and logging

### Testing Strategy
- Test with backup copies of users.yml
- Verify password hashing matches Authelia's format
- Test concurrent access scenarios
- Validate YAML output format

### Deployment
- Run as Docker container
- Mount /volume1/docker/identity/authelia as volume
- Expose on internal port (e.g., 8080)
- Access via Traefik with Authelia protection

## Next Steps
1. Create development environment
2. Build Phase 1 MVP (read-only dashboard)
3. Test with existing user data
4. Iterate based on functionality needs

## References
- [Authelia Documentation](https://www.authelia.com/overview/)
- [Authelia File Backend](https://www.authelia.com/configuration/first-factor/file/)
- [Argon2 Password Hashing](https://www.authelia.com/reference/guides/passwords/)
