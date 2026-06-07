"""
Integration tests for FastAPI dashboard API endpoints.
Uses httpx.AsyncClient to test routes without a running server.

Tests cover both authenticated and unauthenticated access patterns.
"""
import sys
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Add src/ and src/dashboard_api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard_api"))

from dashboard_api.main import app, active_sessions


# =================== FIXTURES ===================

FAKE_TOKEN = "test-session-token-12345"
FAKE_USER = "test@cleancam.ai"


@pytest_asyncio.fixture
async def client():
    """Create an async test client (unauthenticated)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client():
    """Create an async test client with a valid auth session cookie."""
    # Inject a fake session into the server's session store
    active_sessions[FAKE_TOKEN] = FAKE_USER

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"access_token": FAKE_TOKEN}
    ) as ac:
        yield ac

    # Cleanup
    active_sessions.pop(FAKE_TOKEN, None)


# =================== ROOT REDIRECT ===================

class TestRootRedirect:
    @pytest.mark.asyncio
    async def test_root_unauthenticated_redirects_to_login(self, client):
        """Unauthenticated users should be redirected to /login."""
        response = await client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/login"

    @pytest.mark.asyncio
    async def test_root_authenticated_redirects_to_dashboard(self, auth_client):
        """Authenticated users should be redirected to /dashboard."""
        response = await auth_client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/dashboard"


# =================== AUTH ROUTES ===================

class TestAuthRoutes:
    @pytest.mark.asyncio
    async def test_login_page_renders(self, client):
        """GET /login should return the login form."""
        response = await client.get("/login")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Sign in" in response.text or "CleanCam" in response.text

    @pytest.mark.asyncio
    async def test_logout_clears_session(self, auth_client):
        """GET /auth/logout should redirect to /login and clear session."""
        response = await auth_client.get("/auth/logout", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


# =================== PROTECTED ROUTES (unauthenticated → redirect) ===================

class TestProtectedRoutesUnauthenticated:
    @pytest.mark.asyncio
    async def test_dashboard_redirects_to_login(self, client):
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 303

    @pytest.mark.asyncio
    async def test_complaints_redirects_to_login(self, client):
        response = await client.get("/complaints", follow_redirects=False)
        assert response.status_code == 303

    @pytest.mark.asyncio
    async def test_complaints_latest_redirects_to_login(self, client):
        response = await client.get("/complaints/latest", follow_redirects=False)
        assert response.status_code == 303

    @pytest.mark.asyncio
    async def test_complaints_severity_redirects_to_login(self, client):
        response = await client.get("/complaints/severity/High", follow_redirects=False)
        assert response.status_code == 303


# =================== PROTECTED ROUTES (authenticated → 200) ===================

class TestProtectedRoutesAuthenticated:
    @pytest.mark.asyncio
    async def test_dashboard_returns_html(self, auth_client):
        response = await auth_client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "CleanCam AI" in response.text

    @pytest.mark.asyncio
    async def test_list_complaints_returns_200(self, auth_client):
        response = await auth_client.get("/complaints")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_latest_complaint_returns_200(self, auth_client):
        response = await auth_client.get("/complaints/latest")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_complaints_by_severity_returns_200(self, auth_client):
        response = await auth_client.get("/complaints/severity/High")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_complaints_by_severity_invalid_returns_200_empty(self, auth_client):
        response = await auth_client.get("/complaints/severity/InvalidLevel")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# =================== PUBLIC ROUTES (no auth needed) ===================

class TestEvidenceRedirect:
    @pytest.mark.asyncio
    async def test_evidence_redirects_to_supabase(self, client):
        response = await client.get("/evidence/test_image.jpg", follow_redirects=False)
        assert response.status_code == 307
        location = response.headers.get("location", "")
        assert "supabase" in location or "evidence" in location

    @pytest.mark.asyncio
    async def test_evidence_appends_jpg(self, client):
        """If filename doesn't end in .jpg, it should be appended."""
        response = await client.get("/evidence/test_image", follow_redirects=False)
        assert response.status_code == 307
        location = response.headers.get("location", "")
        assert location.endswith(".jpg")


class TestLocationAPI:
    @pytest.mark.asyncio
    async def test_get_location_returns_200(self, client):
        response = await client.get("/api/location")
        assert response.status_code == 200
        data = response.json()
        assert "address" in data

    @pytest.mark.asyncio
    async def test_post_location_updates_address(self, client):
        new_location = {
            "address": "Test Street, Jalna, Maharashtra",
            "latitude": 19.84,
            "longitude": 75.88
        }
        response = await client.post("/api/location", json=new_location)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["location"]["address"] == "Test Street, Jalna, Maharashtra"

    @pytest.mark.asyncio
    async def test_post_location_missing_fields_uses_defaults(self, client):
        """latitude and longitude are optional."""
        response = await client.post("/api/location", json={"address": "Minimal"})
        assert response.status_code == 200
        data = response.json()
        assert data["location"]["address"] == "Minimal"
        assert data["location"]["latitude"] is None


class TestNotifyEndpoint:
    @pytest.mark.asyncio
    async def test_notify_broadcasts_event(self, client):
        payload = {
            "id": 999,
            "timestamp": "2026-06-07T12:00:00",
            "location": "Test Location",
            "severity": "High",
            "garbage_pct": 45.5,
            "duration_seconds": 350,
            "evidence_url": ""
        }
        response = await client.post("/notify", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "broadcast_sent"
        assert "clients" in data

    @pytest.mark.asyncio
    async def test_notify_missing_required_fields(self, client):
        """Missing required fields should return 422."""
        response = await client.post("/notify", json={"location": "Test"})
        assert response.status_code == 422
