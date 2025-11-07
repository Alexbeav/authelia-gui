"""
Authelia User Management GUI - Main Application

FastAPI application with security middleware, user management, and audit logging.
"""
import logging
import json
import secrets
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.hash import bcrypt
from pydantic import ValidationError

from config import get_settings
from security import SecurityMiddleware
from users_io import UsersFileHandler, validate_no_duplicate_emails
from restart import apply_changes, restart_authelia
from audit import AuditLogger
from models import CreateUserRequest, UserListItem
from authelia_config import detect_watch_mode

# Initialize settings
settings = get_settings()

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Authelia User Management",
    description="Production-grade GUI for managing Authelia file provider users",
    version="0.1.0"
)

# Add security middleware
app.add_middleware(SecurityMiddleware, settings=settings)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Initialize handlers
users_handler = UsersFileHandler(settings)
audit_logger = AuditLogger(settings)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for container monitoring.

    Returns:
        JSON status
    """
    return {"status": "OK"}


@app.get("/watch-mode-status")
async def watch_mode_status():
    """
    Check watch mode status.

    Returns:
        JSON with watch mode information
    """
    try:
        watch_enabled = detect_watch_mode(settings.authelia_config_file)
        force_restart = settings.force_restart

        return {
            "watch_mode_enabled": watch_enabled,
            "force_restart": force_restart,
            "mode": "restart" if (force_restart or not watch_enabled) else "watch",
            "message": (
                "Restart forced by configuration" if force_restart
                else "Auto-reload enabled" if watch_enabled
                else "Restart required"
            )
        }
    except Exception as e:
        logger.error(f"Error checking watch mode status: {e}")
        return {
            "watch_mode_enabled": False,
            "force_restart": settings.force_restart,
            "mode": "restart",
            "message": "Watch mode detection failed, using restart",
            "error": str(e)
        }


@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    search: Optional[str] = Query(None, description="Search users by username or email")
):
    """
    Main dashboard showing all users.

    Args:
        request: Starlette request
        search: Optional search query

    Returns:
        Rendered dashboard template
    """
    try:
        # Load all users
        users_dict = users_handler.list_users()

        # Convert to list format
        users_list = []
        for username, user_config in users_dict.items():
            user_item = UserListItem(
                username=username,
                email=user_config.email,
                displayname=user_config.displayname,
                groups=user_config.groups,
                has_totp=False  # TODO: Read from database if available
            )
            users_list.append(user_item)

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            users_list = [
                u for u in users_list
                if search_lower in u.username.lower() or search_lower in u.email.lower()
            ]

        # Get CSRF token from request state (set by middleware)
        csrf_token = getattr(request.state, 'csrf_token', '')

        # Detect watch mode status
        try:
            watch_mode_enabled = detect_watch_mode(settings.authelia_config_file)
        except:
            watch_mode_enabled = False

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "users": users_list,
                "total_users": len(users_dict),
                "filtered_users": len(users_list),
                "search_query": search or "",
                "csrf_token": csrf_token,
                "admin_group": settings.admin_group,
                "watch_mode_enabled": watch_mode_enabled,
                "force_restart": settings.force_restart
            }
        )

    except Exception as e:
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "Failed to load dashboard",
                "details": str(e)
            },
            status_code=500
        )


@app.post("/users")
async def create_user(request: Request):
    """
    Create a new user.

    Requires:
    - RBAC: Admin group in X-Forwarded-Groups
    - CSRF: Valid token in X-CSRF-Token header

    Returns:
        JSON response with success/error
    """
    try:
        # Parse form data
        form_data = await request.form()

        # Build request object
        username = form_data.get('username', '').strip()
        email = form_data.get('email', '').strip()
        displayname = form_data.get('displayname', '').strip()
        password = form_data.get('password', '').strip()
        groups_str = form_data.get('groups', '')

        # Parse groups (comma-separated)
        groups = [g.strip() for g in groups_str.split(',') if g.strip()] if groups_str else []

        # Auto-generate password if not provided
        if not password:
            password = generate_secure_password()
            password_generated = True
        else:
            password_generated = False

        # Validate using Pydantic
        try:
            user_request = CreateUserRequest(
                username=username,
                email=email,
                displayname=displayname,
                password=password,
                groups=groups
            )
        except ValidationError as e:
            return JSONResponse(
                {"error": "Validation failed", "details": e.errors()},
                status_code=400
            )

        # Hash password using bcrypt
        password_hash = bcrypt.hash(password)
        hash_prefix = password_hash[:12]  # For audit log

        # Add user
        try:
            users_handler.add_user(
                username=user_request.username,
                email=user_request.email,
                displayname=user_request.displayname,
                password_hash=password_hash,
                groups=user_request.groups
            )
        except ValueError as e:
            return JSONResponse(
                {"error": str(e)},
                status_code=409
            )

        # Log audit event
        audit_logger.log_create_user(
            actor=request.state.actor,
            username=user_request.username,
            email=user_request.email,
            groups=user_request.groups,
            password_hash_prefix=hash_prefix,
            ip=request.state.ip
        )

        # Apply changes (restart or wait for watch mode)
        logger.info(f"Applying changes after creating user '{user_request.username}'")
        restart_success, restart_message = await apply_changes(settings, user_request.username)

        response_data = {
            "success": True,
            "username": user_request.username,
            "message": f"User '{user_request.username}' created successfully",
            "restart_status": {
                "success": restart_success,
                "message": restart_message
            }
        }

        # Include generated password if applicable (only shown once!)
        if password_generated:
            response_data["generated_password"] = password

        return JSONResponse(response_data)

    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        return JSONResponse(
            {"error": "Failed to create user", "details": str(e)},
            status_code=500
        )


@app.delete("/users/{username}")
async def delete_user(request: Request, username: str):
    """
    Delete a user.

    Requires:
    - RBAC: Admin group in X-Forwarded-Groups
    - CSRF: Valid token in X-CSRF-Token header

    Args:
        username: Username to delete

    Returns:
        JSON response with success/error
    """
    try:
        # Delete user (includes last-admin protection)
        try:
            users_handler.delete_user(username)
        except ValueError as e:
            # Check if it's the last admin error
            if "last admin" in str(e).lower():
                return JSONResponse(
                    {"error": str(e)},
                    status_code=409
                )
            return JSONResponse(
                {"error": str(e)},
                status_code=404
            )

        # Log audit event
        audit_logger.log_delete_user(
            actor=request.state.actor,
            username=username,
            ip=request.state.ip
        )

        # Apply changes (restart or wait for watch mode)
        logger.info(f"Applying changes after deleting user '{username}'")
        restart_success, restart_message = await apply_changes(settings, username)

        return JSONResponse({
            "success": True,
            "message": f"User '{username}' deleted successfully",
            "restart_status": {
                "success": restart_success,
                "message": restart_message
            }
        })

    except Exception as e:
        logger.error(f"Error deleting user {username}: {e}", exc_info=True)
        return JSONResponse(
            {"error": "Failed to delete user", "details": str(e)},
            status_code=500
        )


@app.get("/audit", response_class=JSONResponse)
async def get_audit_logs(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get audit logs (admin only).

    Query params:
        limit: Number of entries to return (max 1000)
        offset: Number of entries to skip (for pagination)

    Returns:
        JSON with audit log entries
    """
    try:
        logs = audit_logger.get_recent_logs(limit=limit, offset=offset)
        total = audit_logger.get_total_count()

        return JSONResponse({
            "logs": logs,
            "total": total,
            "limit": limit,
            "offset": offset
        })

    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}", exc_info=True)
        return JSONResponse(
            {"error": "Failed to fetch audit logs", "details": str(e)},
            status_code=500
        )


def generate_secure_password(length: int = 16) -> str:
    """
    Generate a secure random password.

    Args:
        length: Password length

    Returns:
        Random password string
    """
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower()
    )
