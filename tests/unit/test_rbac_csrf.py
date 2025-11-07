"""
Unit tests for RBAC and CSRF protection.

Tests:
- RBAC enforcement via X-Forwarded-Groups
- CSRF validation
- Session management
- Security headers
"""
import pytest
from unittest.mock import Mock, AsyncMock
from starlette.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from app.config import Settings
from app.security import SecurityMiddleware, extract_actor, extract_ip


@pytest.fixture
def settings():
    """Create test settings."""
    settings = Mock(spec=Settings)
    settings.admin_group = "authelia-admins"
    settings.csrf_secret = "test-secret-key-32-chars-long!!"
    settings.session_ttl_minutes = 30
    return settings


class TestRBACEnforcement:
    """Test RBAC via X-Forwarded-Groups."""

    def test_rbac_allows_admin_group(self, settings):
        """Requests with admin group should pass RBAC."""
        from starlette.applications import Starlette
        from starlette.routing import Route

        async def endpoint(request: Request):
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[
            Route("/users", endpoint, methods=["POST"])
        ])
        app.add_middleware(SecurityMiddleware, settings=settings)

        client = TestClient(app)

        response = client.post(
            "/users",
            headers={
                "X-Forwarded-Groups": "authelia-admins,users",
                "X-CSRF-Token": "test-token"
            }
        )

        # Should not get 403 due to RBAC (may get 400 due to CSRF, but not 403)
        assert response.status_code != 403 or "Admin group" not in response.json().get("detail", "")

    def test_rbac_blocks_without_admin_group(self, settings):
        """Requests without admin group should be blocked."""
        from starlette.applications import Starlette
        from starlette.routing import Route

        async def endpoint(request: Request):
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[
            Route("/users", endpoint, methods=["POST"])
        ])
        app.add_middleware(SecurityMiddleware, settings=settings)

        client = TestClient(app)

        response = client.post(
            "/users",
            headers={
                "X-Forwarded-Groups": "users,developers",  # No admin group
            }
        )

        assert response.status_code == 403
        assert "Admin group" in response.json()["detail"]

    def test_rbac_blocks_missing_header(self, settings):
        """Requests without X-Forwarded-Groups should be blocked."""
        from starlette.applications import Starlette
        from starlette.routing import Route

        async def endpoint(request: Request):
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[
            Route("/users", endpoint, methods=["POST"])
        ])
        app.add_middleware(SecurityMiddleware, settings=settings)

        client = TestClient(app)

        response = client.post("/users")

        assert response.status_code == 403
        assert "Admin group" in response.json()["detail"]

    def test_rbac_allows_get_requests(self, settings):
        """GET requests should not require RBAC check."""
        from starlette.applications import Starlette
        from starlette.routing import Route

        async def endpoint(request: Request):
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[
            Route("/", endpoint, methods=["GET"])
        ])
        app.add_middleware(SecurityMiddleware, settings=settings)

        client = TestClient(app)

        # GET requests don't require admin group
        response = client.get("/")

        # Should not be blocked by RBAC (may have other issues)
        assert response.status_code != 403 or "Admin group" not in str(response.content)


class TestCSRFProtection:
    """Test CSRF validation."""

    def test_csrf_required_for_post(self, settings):
        """POST requests should require valid CSRF token."""
        from starlette.applications import Starlette
        from starlette.routing import Route

        async def endpoint(request: Request):
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[
            Route("/users", endpoint, methods=["POST"])
        ])
        app.add_middleware(SecurityMiddleware, settings=settings)

        client = TestClient(app)

        # POST without CSRF token should fail
        response = client.post(
            "/users",
            headers={
                "X-Forwarded-Groups": "authelia-admins"
            }
        )

        assert response.status_code == 400
        assert "CSRF" in response.json()["error"]

    def test_health_endpoint_bypasses_csrf(self, settings):
        """Health check endpoint should not require CSRF."""
        from starlette.applications import Starlette
        from starlette.routing import Route

        async def endpoint(request: Request):
            return JSONResponse({"status": "OK"})

        app = Starlette(routes=[
            Route("/health", endpoint, methods=["GET"])
        ])
        app.add_middleware(SecurityMiddleware, settings=settings)

        client = TestClient(app)

        response = client.get("/health")

        # Should succeed without CSRF
        assert response.status_code == 200


class TestActorExtraction:
    """Test actor (username) extraction."""

    def test_extract_actor_from_header(self):
        """Extract actor from X-Forwarded-User header."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-User": "testuser"}

        actor = extract_actor(request)
        assert actor == "testuser"

    def test_extract_actor_defaults_to_unknown(self):
        """Default to 'unknown' if header missing."""
        request = Mock(spec=Request)
        request.headers = {}

        actor = extract_actor(request)
        assert actor == "unknown"

    def test_extract_actor_strips_whitespace(self):
        """Actor should be stripped of whitespace."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-User": "  testuser  "}

        actor = extract_actor(request)
        assert actor == "testuser"


class TestIPExtraction:
    """Test IP address extraction."""

    def test_extract_ip_from_forwarded_for(self):
        """Extract IP from X-Forwarded-For (first in chain)."""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "192.168.1.100, 10.0.0.1"}
        request.client = None

        ip = extract_ip(request)
        assert ip == "192.168.1.100"

    def test_extract_ip_from_real_ip(self):
        """Extract IP from X-Real-IP if X-Forwarded-For missing."""
        request = Mock(spec=Request)
        request.headers = {"X-Real-IP": "192.168.1.200"}
        request.client = None

        ip = extract_ip(request)
        assert ip == "192.168.1.200"

    def test_extract_ip_from_client(self):
        """Fallback to client.host if headers missing."""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.300"

        ip = extract_ip(request)
        assert ip == "192.168.1.300"

    def test_extract_ip_defaults_to_unknown(self):
        """Default to 'unknown' if all sources missing."""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = None

        ip = extract_ip(request)
        assert ip == "unknown"


class TestSecurityHeaders:
    """Test security headers are added to responses."""

    def test_security_headers_present(self, settings):
        """Security headers should be added to all responses."""
        from starlette.applications import Starlette
        from starlette.routing import Route

        async def endpoint(request: Request):
            return JSONResponse({"status": "ok"})

        app = Starlette(routes=[
            Route("/", endpoint, methods=["GET"])
        ])
        app.add_middleware(SecurityMiddleware, settings=settings)

        client = TestClient(app)

        response = client.get("/")

        # Check for security headers
        assert "Content-Security-Policy" in response.headers
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Referrer-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "Strict-Transport-Security" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_csp_header_restricts_sources(self, settings):
        """CSP header should restrict sources to 'self'."""
        from starlette.applications import Starlette
        from starlette.routing import Route

        async def endpoint(request: Request):
            return Response("ok")

        app = Starlette(routes=[
            Route("/", endpoint, methods=["GET"])
        ])
        app.add_middleware(SecurityMiddleware, settings=settings)

        client = TestClient(app)

        response = client.get("/")

        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
