"""
Security middleware and utilities for Authelia GUI.

Implements:
- RBAC enforcement via X-Forwarded-Groups
- CSRF protection (double-submit cookie pattern)
- Session TTL management
- Security headers
- Actor extraction
"""
import json
import secrets
from datetime import datetime, timedelta
from typing import Optional, Callable
from itsdangerous import URLSafeTimedSerializer, BadSignature
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.datastructures import MutableHeaders
import logging

from config import Settings

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware for security headers, RBAC, CSRF, and session management.
    """

    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self.settings = settings
        self.csrf_serializer = URLSafeTimedSerializer(settings.csrf_secret, salt='csrf')
        self.session_serializer = URLSafeTimedSerializer(settings.csrf_secret, salt='session')

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security checks."""

        # Extract actor from forwarded headers
        actor = extract_actor(request)
        request.state.actor = actor

        # Extract IP address
        ip_address = extract_ip(request)
        request.state.ip = ip_address

        # Check session TTL for all requests except health check
        if request.url.path != '/health':
            session_valid = self._check_session(request)
            if not session_valid and request.url.path != '/':
                return JSONResponse(
                    {'error': 'Session expired', 'detail': 'Please refresh the page'},
                    status_code=401
                )

        # RBAC check for modifying endpoints (exempt /health and /watch-mode-status)
        if request.method in ['POST', 'DELETE', 'PUT', 'PATCH']:
            if request.url.path not in ['/health', '/watch-mode-status']:
                if not self._check_rbac(request):
                    logger.warning(
                        f"RBAC denied for {actor} from {ip_address} on {request.url.path}",
                        extra={'actor': actor, 'ip': ip_address, 'path': request.url.path}
                    )
                    return JSONResponse(
                        {'error': 'Forbidden', 'detail': f'Admin group "{self.settings.admin_group}" required'},
                        status_code=403
                    )

        # CSRF check for all state-changing requests: POST, PUT, PATCH, DELETE
        if request.method in ['POST', 'DELETE', 'PUT', 'PATCH']:
            if request.url.path not in ['/health', '/watch-mode-status']:
                if not await self._check_csrf(request):
                    logger.warning(
                        f"CSRF check failed for {actor} from {ip_address}",
                        extra={'actor': actor, 'ip': ip_address}
                    )
                    return JSONResponse(
                        {'error': 'CSRF validation failed', 'detail': 'Invalid or missing CSRF token'},
                        status_code=400
                    )

        # Process request
        response = await call_next(request)

        # Add security headers
        self._add_security_headers(response)

        # Update session cookie
        if request.url.path != '/health':
            self._update_session(response)

        # Add/refresh CSRF token (on GET requests for HTML pages)
        if request.url.path != '/health' and request.method == 'GET':
            self._set_csrf_cookie(response, request)

        return response

    def _check_rbac(self, request: Request) -> bool:
        """
        Check if request has required admin group.

        Args:
            request: Starlette request object

        Returns:
            True if authorized, False otherwise
        """
        forwarded_groups = request.headers.get('X-Forwarded-Groups', '')

        if not forwarded_groups:
            return False

        # Groups can be comma-separated or space-separated
        groups = [g.strip() for g in forwarded_groups.replace(',', ' ').split() if g.strip()]

        return self.settings.admin_group in groups

    async def _check_csrf(self, request: Request) -> bool:
        """
        Validate CSRF token from header or form matches cookie.

        Implements double-submit cookie pattern:
        - Token stored in 'csrf' cookie
        - Client sends it back via X-CSRF-Token header OR csrf_token form field

        Args:
            request: Starlette request object

        Returns:
            True if valid, False otherwise
        """
        # Get token from cookie
        cookie_token = request.cookies.get('csrf', '')
        if not cookie_token:
            return False

        # Get submitted token from either header or form
        submitted_token = request.headers.get('X-CSRF-Token', '')

        # If not in header, try form data
        if not submitted_token:
            try:
                # Check if content-type is form data
                content_type = request.headers.get('content-type', '')
                if 'multipart/form-data' in content_type or 'application/x-www-form-urlencoded' in content_type:
                    form = await request.form()
                    submitted_token = form.get('csrf_token', '')
            except:
                pass

        if not submitted_token:
            return False

        try:
            # Verify both tokens are valid (signed correctly)
            cookie_data = self.csrf_serializer.loads(cookie_token, max_age=3600)
            submitted_data = self.csrf_serializer.loads(submitted_token, max_age=3600)

            # They must match
            return cookie_data == submitted_data
        except BadSignature:
            return False

    def _check_session(self, request: Request) -> bool:
        """
        Check if session is still valid based on TTL.

        Args:
            request: Starlette request object

        Returns:
            True if valid, False if expired
        """
        session_cookie = request.cookies.get('session', '')

        if not session_cookie:
            # No session cookie means first visit, which is OK
            return True

        try:
            session_data = self.session_serializer.loads(
                session_cookie,
                max_age=self.settings.session_ttl_minutes * 60
            )
            return True
        except BadSignature:
            return False

    def _set_csrf_cookie(self, response: Response, request: Request = None) -> None:
        """
        Set/refresh CSRF token cookie.

        Token is stored in 'csrf' cookie and also made available
        to the request state for template rendering.

        Args:
            response: Starlette response object
            request: Optional request object to store token in state
        """
        token_value = secrets.token_hex(32)
        signed_token = self.csrf_serializer.dumps(token_value)

        response.set_cookie(
            key='csrf',
            value=signed_token,
            httponly=False,  # JS needs to read this for fetch requests
            secure=True,
            samesite='lax',  # Lax for form POSTs to work
            max_age=3600
        )

        # Store token in request state for template access
        if request:
            request.state.csrf_token = signed_token

    def _update_session(self, response: Response) -> None:
        """
        Update session cookie with current timestamp.

        Args:
            response: Starlette response object
        """
        session_data = {'last_seen': datetime.utcnow().isoformat()}
        signed_session = self.session_serializer.dumps(session_data)

        response.set_cookie(
            key='session',
            value=signed_session,
            httponly=True,
            secure=True,
            samesite='strict',
            max_age=self.settings.session_ttl_minutes * 60
        )

    def _add_security_headers(self, response: Response) -> None:
        """
        Add security headers to response.

        Args:
            response: Starlette response object
        """
        headers = MutableHeaders(response.headers)

        headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none';"
        headers['X-Frame-Options'] = 'DENY'
        headers['Referrer-Policy'] = 'no-referrer'
        headers['Strict-Transport-Security'] = 'max-age=31536000'
        headers['X-Content-Type-Options'] = 'nosniff'
        headers['X-XSS-Protection'] = '1; mode=block'

        response.headers.update(headers)


def extract_actor(request: Request) -> str:
    """
    Extract actor (username) from forwarded headers.

    Args:
        request: Starlette request object

    Returns:
        Username or 'unknown'
    """
    actor = request.headers.get('X-Forwarded-User', '').strip()
    return actor if actor else 'unknown'


def extract_ip(request: Request) -> str:
    """
    Extract IP address from forwarded headers or client.

    Args:
        request: Starlette request object

    Returns:
        IP address string
    """
    # Try X-Forwarded-For first (take first IP in chain)
    forwarded_for = request.headers.get('X-Forwarded-For', '').strip()
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()

    # Fall back to X-Real-IP
    real_ip = request.headers.get('X-Real-IP', '').strip()
    if real_ip:
        return real_ip

    # Fall back to client host
    if request.client:
        return request.client.host

    return 'unknown'


def generate_csrf_token(settings: Settings) -> str:
    """
    Generate a new CSRF token.

    Args:
        settings: Application settings

    Returns:
        Signed CSRF token
    """
    serializer = URLSafeTimedSerializer(settings.csrf_secret, salt='csrf')
    token_value = secrets.token_hex(32)
    return serializer.dumps(token_value)


def get_csrf_token_from_cookie(request: Request, settings: Settings) -> Optional[str]:
    """
    Extract and verify CSRF token from cookie.

    Args:
        request: Starlette request object
        settings: Application settings

    Returns:
        Token value if valid, None otherwise
    """
    cookie_token = request.cookies.get('csrf_token', '')
    if not cookie_token:
        return None

    try:
        serializer = URLSafeTimedSerializer(settings.csrf_secret, salt='csrf')
        return serializer.loads(cookie_token, max_age=3600)
    except BadSignature:
        return None
