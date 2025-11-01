# Authelia GUI Development Log

## 2025-11-01

### Initial Exploration and Planning

**Explored Authelia Setup:**
- Connected to Ulduar NAS via SSH
- Examined directory structure at `/volume1/docker/identity`
- Located Authelia configuration files:
  - users.yml at `/volume1/docker/identity/authelia/users.yml`
  - SQLite database at `/volume1/docker/identity/authelia/config/db.sqlite3`
  - Main config at `/volume1/docker/identity/authelia/config/configuration.yml`

**Current User Analysis:**
- Found 1 existing user: alexbeav (alexbeav@live.com)
- User has 2FA/TOTP enabled (verified in totp_configurations table)
- User is in "admins" group
- Password hashed with argon2id (v=19, m=65536, t=3, p=4)

**Database Schema Insights:**
- Examined SQLite schema - key tables identified:
  - `totp_configurations`: Stores 2FA TOTP setup (username, secret, last_used_at)
  - `webauthn_credentials`: Hardware key credentials
  - `user_preferences`: User's preferred 2FA method
  - `authentication_logs`: Login attempts and history
  - Various OAuth2 session tables

**Configuration Findings:**
- Authelia using file-based authentication backend
- Password refresh interval: 5 minutes
- TOTP issuer: alexbeav.synology.me
- Access control has 2-factor and 1-factor policies for different domains
- SMTP configured for notifications (Gmail)

**Documentation Created:**
- Created `claude.md`: Comprehensive project plan and architecture document
  - Outlined 4 development phases
  - Recommended Python + FastAPI stack
  - Documented security considerations
  - Defined project structure and implementation phases
- Created `devlog.md`: This development log to track progress

**Technology Stack Decision:**
Recommended Python + FastAPI because:
- Easy SQLite integration for reading 2FA status
- PyYAML for safe users.yml manipulation
- Lightweight and fast
- Can be easily Dockerized
- Good template support with Jinja2

**Next Steps:**
- Copy documentation files to NAS
- Set up development environment
- Begin Phase 1: Read-only dashboard implementation

---

## 2025-11-02

### Phase 1: Read-Only Dashboard ✅ COMPLETED

**Implementation:**
- Set up Python environment with FastAPI, PyYAML, and sqlite3
- Created data models (`models.py`) for UserDetail with all necessary fields
- Built YAML handler (`yaml_handler.py`) to safely read users.yml
- Built database handler (`database.py`) to query SQLite for 2FA status and auth logs
- Created beautiful responsive UI with Jinja2 templates
- Implemented dashboard showing:
  - Total users count
  - Users with 2FA enabled count
  - Table with username, display name, email, groups, 2FA status
  - Action buttons for viewing details and deleting users

**Key Files Created:**
- `main.py` - FastAPI application with routes
- `models.py` - Pydantic models for data validation
- `database.py` - SQLite database operations
- `yaml_handler.py` - YAML file reading/writing with backups
- `utils.py` - Password generation and hashing utilities
- `templates/base.html` - Base template with navigation
- `templates/dashboard.html` - Main dashboard
- `templates/user_detail.html` - User detail view
- `templates/error.html` - Error page
- `static/css/style.css` - Responsive styling

**Testing:**
- Successfully displayed existing user (alexbeav)
- Verified 2FA status from database
- Tested user detail view with authentication logs

---

### Phase 2: User Creation ✅ COMPLETED

**Initial Implementation:**
- Created user creation form with auto/manual password options
- Implemented group selection (admins, developers, users, custom)
- Added form validation (username, email, password length)
- Built user creation endpoint with duplicate checking

**Critical Challenge: Password Hash Compatibility**
- **Problem:** GUI-generated hashes using Python's passlib were incompatible with Authelia's Go-based argon2 validator
- **Symptoms:** Users created via GUI couldn't authenticate, even though passlib verified the hashes correctly
- **Testing:** Created multiple test users (test456, test789, testcopy, testsimple) - all failed authentication
- **Root Cause:** Subtle differences between passlib's argon2 implementation and Authelia's Go crypto library
- **Solution:** Modified `utils.py` to call Authelia's CLI via Docker exec:
  ```bash
  docker exec authelia authelia crypto hash generate argon2 --password <password>
  ```
- **Required Changes:**
  - Added Docker CLI to Dockerfile
  - Mounted Docker socket in docker-compose.yml: `/var/run/docker.sock:/var/run/docker.sock`
  - Updated hash_password() to parse CLI output with regex

**Path Configuration Issue:**
- **Problem:** GUI was writing to wrong users.yml path
- **Fix:** Updated volume mount from `.../config:/config` to `.../authelia:/authelia`
- **Updated:** AUTHELIA_PATH env variable and all file paths in main.py

**Admin Safeguard:**
- Implemented protection against deleting the last remaining admin user
- Added admin counting logic in delete_user endpoint
- Returns error if attempting to delete last admin

**Auto-Reload Challenge:**
- **Initial Approach:** Added `watch: true` and `refresh_interval: 30s` to configuration.yml
- **Problem:** File watching doesn't work reliably with Docker bind-mounted files
- **Solution:** Implemented automatic Authelia restart after user creation/deletion
  ```python
  subprocess.run(['docker', 'restart', 'authelia'], timeout=10)
  ```
- **Trade-off:** Brief downtime (~2-3 seconds) for reliability
- **User Feedback:** Accepted as reliable solution after testing confirmed immediate availability

**Final Features:**
- Auto-generated secure passwords (16+ characters)
- Manual password option (min 12 characters)
- Email field included (explicitly required)
- Multiple group assignment
- Success message with generated password display
- Automatic Authelia restart for immediate user availability

---

### UI Enhancements ✅ COMPLETED

**Dark Mode Implementation:**
- Added CSS custom properties for theming
- Created dark theme with proper contrast ratios:
  - Light mode: #f8fafc background, #0f172a text
  - Dark mode: #0f172a background, #f1f5f9 text
- Implemented theme toggle button with moon/sun icons
- Added localStorage persistence for theme preference
- Smooth 0.3s transitions between themes

**Layout Improvements:**
- Repositioned "Create User" button between header and stats
- Used flexbox for responsive dashboard header
- Made action buttons equal size (Details and Delete)
- Changed "View Details" to "Details" for brevity
- Styled Delete button in red (btn-danger)

**Responsive Design:**
- Mobile-friendly tables with horizontal scroll
- Stats cards stack on small screens
- Proper spacing and padding throughout
- Accessible navigation

---

### Deployment ✅ COMPLETED

**Docker Setup:**
- Created Dockerfile with Python 3.11-slim base
- Installed Docker CLI in container for Authelia integration
- Multi-stage build for better caching
- Exposed port 8080

**Docker Compose Configuration:**
```yaml
authelia-gui:
  container_name: authelia-gui
  build: /volume1/docker/identity/authelia-gui
  ports:
    - "172.16.1.8:8081:8080"
  volumes:
    - /volume1/docker/identity/authelia:/authelia
    - /var/run/docker.sock:/var/run/docker.sock
  restart: unless-stopped
```

**Security:**
- Internal-only access: Bound to 172.16.1.8:8081 (not exposed to internet)
- Not behind Traefik reverse proxy
- Removed SSL requirements for internal use
- File backups created before every write operation

**Testing:**
- Successfully created users that authenticate immediately
- Verified delete functionality with admin protection
- Confirmed dark mode persistence across sessions
- Tested on multiple browsers

---

### Remaining Work

**Phase 3: Password Management**
- [ ] Research Authelia's password reset mechanisms
- [ ] Implement password reset for existing users
- [ ] Add "Force Password Reset on Next Login" option
- [ ] Create password reset UI in user detail page
- [ ] Test password reset flow

**Technical Improvements**
- [ ] **CRITICAL:** Figure out how to refresh Authelia's user cache without restarting the container
  - Current solution works but causes ~2-3s downtime
  - Investigate Authelia API endpoints for reload
  - Research inotify alternatives for Docker volumes
  - Consider file checksum monitoring
  - Possible solutions to explore:
    - Authelia HTTP API (if it exists)
    - SIGHUP signal to reload config
    - Alternative volume mount strategies

**Future Enhancements**
- [ ] Add user editing functionality
- [ ] Implement group management
- [ ] Add bulk user operations
- [ ] Create audit log viewer
- [ ] Add email notifications for user creation
- [ ] Implement user search/filtering
- [ ] Export user list to CSV

---

## Project Status

**Current Version:** v0.1.0
**Status:** Fully functional for core use cases
**Access:** http://172.16.1.8:8081 (internal only)
**Repository:** To be created on GitHub

**Technology Stack:**
- Backend: FastAPI (Python 3.11)
- Templates: Jinja2
- Database: SQLite (read-only)
- Config: YAML (read/write with backups)
- Container: Docker
- Integration: Authelia CLI via docker exec

**Key Achievements:**
- Custom-built from scratch (no forked code)
- Solved critical password hash compatibility issue
- Implemented reliable user creation with auto-restart
- Beautiful responsive UI with dark mode
- Admin protection safeguards
- Production-ready deployment
