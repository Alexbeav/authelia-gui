"""
Authelia User Management GUI - FastAPI Application
"""
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import List, Optional
import logging
import os

from models import UserDetail
from database import AutheliaDatabase
from yaml_handler import AutheliaYAMLHandler
from utils import generate_secure_password, hash_password, validate_username, validate_email

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Authelia User Management",
    description="Simple GUI for managing Authelia users",
    version="0.1.0"
)

# Paths configuration - will be mounted from Docker
# Note: users.yml is in parent directory of config
AUTHELIA_PATH = os.getenv('AUTHELIA_PATH', '/authelia')
USERS_YAML_PATH = os.path.join(AUTHELIA_PATH, 'users.yml')
DB_PATH = os.path.join(AUTHELIA_PATH, 'config', 'db.sqlite3')

# Initialize handlers
yaml_handler = AutheliaYAMLHandler(USERS_YAML_PATH)
db_handler = AutheliaDatabase(DB_PATH)

# Setup templates and static files
templates = Jinja2Templates(directory="../templates")
app.mount("/static", StaticFiles(directory="../static"), name="static")


def get_users_with_details() -> List[UserDetail]:
    """
    Get all users with their 2FA status from both YAML and database

    Returns:
        List of UserDetail objects
    """
    users_list = []

    # Get users from YAML
    yaml_users = yaml_handler.get_all_users_list()

    # Get TOTP configs from database
    totp_configs = db_handler.get_all_totp_configs()

    # Combine the data
    for user in yaml_users:
        username = user['username']
        totp_config = totp_configs.get(username)

        user_detail = UserDetail(
            username=username,
            email=user.get('email', ''),
            displayname=user.get('displayname', ''),
            groups=user.get('groups', []),
            has_totp=totp_config is not None,
            totp_last_used=totp_config.get('last_used_at') if totp_config else None,
            totp_created_at=totp_config.get('created_at') if totp_config else None
        )

        users_list.append(user_detail)

    return users_list


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Main dashboard showing all users

    Args:
        request: FastAPI request object

    Returns:
        Rendered HTML template
    """
    try:
        users = get_users_with_details()
        logger.info(f"Dashboard loaded with {len(users)} users")

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "users": users,
                "total_users": len(users),
                "users_with_2fa": sum(1 for u in users if u.has_totp)
            }
        )
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_message": f"Error loading dashboard: {str(e)}"
            }
        )


@app.get("/user/{username}", response_class=HTMLResponse)
async def user_detail(request: Request, username: str):
    """
    Detailed view of a specific user

    Args:
        request: FastAPI request object
        username: Username to display

    Returns:
        Rendered HTML template
    """
    try:
        # Get user from YAML
        user_config = yaml_handler.get_user(username)

        if not user_config:
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error_message": f"User '{username}' not found"
                }
            )

        # Get TOTP status from database
        totp_config = db_handler.get_totp_status(username)

        # Get recent auth logs
        auth_logs = db_handler.get_authentication_logs(username, limit=10)

        user_detail = UserDetail(
            username=username,
            email=user_config.get('email', ''),
            displayname=user_config.get('displayname', ''),
            groups=user_config.get('groups', []),
            has_totp=totp_config is not None,
            totp_last_used=totp_config.get('last_used_at') if totp_config else None,
            totp_created_at=totp_config.get('created_at') if totp_config else None
        )

        return templates.TemplateResponse(
            "user_detail.html",
            {
                "request": request,
                "user": user_detail,
                "auth_logs": auth_logs
            }
        )

    except Exception as e:
        logger.error(f"Error loading user {username}: {e}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_message": f"Error loading user: {str(e)}"
            }
        )


@app.get("/create-user", response_class=HTMLResponse)
async def create_user_form(request: Request):
    """
    Display user creation form

    Args:
        request: FastAPI request object

    Returns:
        Rendered HTML template
    """
    return templates.TemplateResponse(
        "create_user.html",
        {
            "request": request,
            "success": False,
            "error": None
        }
    )


@app.post("/create-user", response_class=HTMLResponse)
async def create_user(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    displayname: str = Form(...),
    password_mode: str = Form(...),
    manual_password: Optional[str] = Form(None),
    groups: List[str] = Form([]),
    custom_groups: Optional[str] = Form(None)
):
    """
    Create a new user

    Args:
        request: FastAPI request object
        username: Username for the new user
        email: Email address
        displayname: Display name
        password_mode: Either 'auto' or 'manual'
        manual_password: Password if manual mode
        groups: List of selected groups
        custom_groups: Comma-separated custom groups

    Returns:
        Rendered HTML template with success/error message
    """
    try:
        # Validate username
        is_valid, error_msg = validate_username(username)
        if not is_valid:
            return templates.TemplateResponse(
                "create_user.html",
                {
                    "request": request,
                    "success": False,
                    "error": error_msg,
                    "form_data": {"username": username, "email": email, "displayname": displayname}
                }
            )

        # Validate email
        is_valid, error_msg = validate_email(email)
        if not is_valid:
            return templates.TemplateResponse(
                "create_user.html",
                {
                    "request": request,
                    "success": False,
                    "error": error_msg,
                    "form_data": {"username": username, "email": email, "displayname": displayname}
                }
            )

        # Check if user already exists
        existing_user = yaml_handler.get_user(username)
        if existing_user:
            return templates.TemplateResponse(
                "create_user.html",
                {
                    "request": request,
                    "success": False,
                    "error": f"User '{username}' already exists",
                    "form_data": {"username": username, "email": email, "displayname": displayname}
                }
            )

        # Generate or use manual password
        if password_mode == 'manual':
            if not manual_password or len(manual_password) < 12:
                return templates.TemplateResponse(
                    "create_user.html",
                    {
                        "request": request,
                        "success": False,
                        "error": "Manual password must be at least 12 characters",
                        "form_data": {"username": username, "email": email, "displayname": displayname}
                    }
                )
            plain_password = manual_password
        else:
            plain_password = generate_secure_password()

        # Hash the password
        password_hash = hash_password(plain_password)

        # Process groups
        all_groups = list(groups)
        if custom_groups:
            custom_list = [g.strip() for g in custom_groups.split(',') if g.strip()]
            all_groups.extend(custom_list)

        # Remove duplicates
        all_groups = list(set(all_groups))

        # Create the user
        success = yaml_handler.add_user(
            username=username,
            email=email,
            displayname=displayname,
            password_hash=password_hash,
            groups=all_groups
        )

        if success:
            logger.info(f"User '{username}' created successfully")

            # Restart Authelia to immediately load the new user
            # This is more reliable than file watching with bind mounts
            try:
                import subprocess
                subprocess.run(
                    ['docker', 'restart', 'authelia'],
                    capture_output=True,
                    timeout=10
                )
                logger.info("Authelia restarted to load new user")
            except Exception as e:
                logger.warning(f"Could not restart Authelia: {e}")

            return templates.TemplateResponse(
                "create_user.html",
                {
                    "request": request,
                    "success": True,
                    "error": None,
                    "created_username": username,
                    "generated_password": plain_password if password_mode == 'auto' else "••••••••"
                }
            )
        else:
            return templates.TemplateResponse(
                "create_user.html",
                {
                    "request": request,
                    "success": False,
                    "error": "Failed to create user. Check logs for details.",
                    "form_data": {"username": username, "email": email, "displayname": displayname}
                }
            )

    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return templates.TemplateResponse(
            "create_user.html",
            {
                "request": request,
                "success": False,
                "error": f"Error creating user: {str(e)}",
                "form_data": {"username": username, "email": email, "displayname": displayname}
            }
        )


@app.post("/delete-user/{username}")
async def delete_user(request: Request, username: str):
    """
    Delete a user from users.yml

    Args:
        request: FastAPI request object
        username: Username to delete

    Returns:
        Redirect to dashboard with success/error message
    """
    try:
        # Check if user exists
        user_config = yaml_handler.get_user(username)

        if not user_config:
            logger.warning(f"Attempt to delete non-existent user: {username}")
            return RedirectResponse(url="/?error=user_not_found", status_code=303)

        # Check if user is an admin
        user_groups = user_config.get('groups', [])
        if 'admins' in user_groups:
            # Count total admins
            all_users = yaml_handler.get_all_users_list()
            admin_count = sum(1 for u in all_users if 'admins' in u.get('groups', []))

            if admin_count <= 1:
                logger.warning(f"Attempt to delete last admin user: {username}")
                return RedirectResponse(url="/?error=last_admin", status_code=303)

        # Delete the user
        success = yaml_handler.delete_user(username)

        if success:
            logger.info(f"User '{username}' deleted successfully")

            # Restart Authelia to immediately remove the user
            try:
                import subprocess
                subprocess.run(
                    ['docker', 'restart', 'authelia'],
                    capture_output=True,
                    timeout=10
                )
                logger.info("Authelia restarted to remove user")
            except Exception as e:
                logger.warning(f"Could not restart Authelia: {e}")

            return RedirectResponse(url="/?success=user_deleted", status_code=303)
        else:
            logger.error(f"Failed to delete user '{username}'")
            return RedirectResponse(url="/?error=delete_failed", status_code=303)

    except Exception as e:
        logger.error(f"Error deleting user {username}: {e}")
        return RedirectResponse(url="/?error=delete_error", status_code=303)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "users_file": os.path.exists(USERS_YAML_PATH),
        "database": os.path.exists(DB_PATH)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
