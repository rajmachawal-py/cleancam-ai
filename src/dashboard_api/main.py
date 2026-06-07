from fastapi import FastAPI, Request, Form, Cookie
from fastapi.responses import RedirectResponse, StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import os
import sys

# Add src/ to path so we can import the shared supabase client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.supabase_services import (
    get_all_complaints,
    get_latest_complaint,
    get_complaints_by_severity,
)
from supabase_client import supabase

# ------------------ PATH SETUP ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
EVIDENCE_BUCKET_URL = f"{SUPABASE_URL}/storage/v1/object/public/evidence"

# ------------------ APP ------------------
app = FastAPI(
    title="CleanCam AI Dashboard API",
    description="API for monitoring automated garbage complaints",
    version="4.0"
)

# ------------------ CORS (for detection engine POST /notify) ------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------ STATIC FILES ------------------
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static"
)

# ------------------ TEMPLATES ------------------
templates = Jinja2Templates(
    directory=os.path.join(BASE_DIR, "templates")
)

# ------------------ SSE CLIENT MANAGEMENT ------------------
# Each connected dashboard browser gets its own asyncio.Queue
sse_clients: set[asyncio.Queue] = set()


async def broadcast_event(event_type: str, data: dict):
    """Send an SSE event to all connected dashboard clients."""
    message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    dead_clients = []
    for queue in sse_clients:
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            dead_clients.append(queue)
    for q in dead_clients:
        sse_clients.discard(q)


async def sse_generator(queue: asyncio.Queue):
    """Yield SSE messages from a client's queue."""
    try:
        while True:
            message = await queue.get()
            yield message
    except asyncio.CancelledError:
        pass
    finally:
        sse_clients.discard(queue)


# ------------------ ACTIVE LOCATION SETUP ------------------
current_location = {
    "address": os.getenv("LOCATION", "Unknown Location"),
    "latitude": None,
    "longitude": None
}


# ------------------ MODELS ------------------
class LocationPayload(BaseModel):
    """Payload for updating the active camera location from browser geolocation."""
    address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class NotifyPayload(BaseModel):
    """Payload the detection engine sends to /notify after filing a complaint."""
    id: Optional[int] = None
    timestamp: Optional[str] = None
    location: str
    severity: str
    garbage_pct: float
    duration_seconds: int
    evidence_url: Optional[str] = ""


# ------------------ AUTH SESSION STORE ------------------
# Simple in-memory token store: maps access_token -> user_email
active_sessions: dict[str, str] = {}


def get_current_user(access_token: Optional[str] = None) -> Optional[str]:
    """Check if the access token corresponds to a valid session.
    Returns the user email if valid, None otherwise."""
    if not access_token:
        return None
    return active_sessions.get(access_token)


# =================== PUBLIC ROUTES (no auth) ===================
# These are used by the detection engine and must remain accessible

@app.get("/api/location")
def get_location():
    """Retrieve the current active location for the camera detection engine."""
    return current_location


@app.post("/api/location")
def update_location(payload: LocationPayload):
    """Update the current active location from browser geolocation."""
    global current_location
    current_location = payload.model_dump()
    return {"status": "success", "location": current_location}


@app.get("/stream")
async def sse_stream():
    """SSE endpoint — browsers connect here for real-time updates."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    sse_clients.add(queue)

    return StreamingResponse(
        sse_generator(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/notify")
async def notify_new_complaint(payload: NotifyPayload):
    """Called by the detection engine after a complaint is filed.
    Broadcasts the new complaint to all connected SSE dashboard clients."""
    data = payload.model_dump()
    await broadcast_event("new_complaint", data)
    return {"status": "broadcast_sent", "clients": len(sse_clients)}


@app.get("/evidence/{image_name}")
def get_evidence_image(image_name: str):
    """Redirect to the Supabase Storage public URL for the evidence image."""
    if not image_name.lower().endswith(".jpg"):
        image_name += ".jpg"
    return RedirectResponse(url=f"{EVIDENCE_BUCKET_URL}/{image_name}")


# =================== AUTH ROUTES ===================

@app.get("/login")
def login_page(request: Request, error: Optional[str] = None):
    """Render the login page."""
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error}
    )


@app.post("/auth/login")
def auth_login(request: Request, email: str = Form(...), password: str = Form(...)):
    """Authenticate user with Supabase Auth and set session cookie."""
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        access_token = auth_response.session.access_token
        user_email = auth_response.user.email

        # Store session
        active_sessions[access_token] = user_email

        # Redirect to dashboard with auth cookie
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            max_age=3600 * 24  # 24 hours
        )
        return response

    except Exception as e:
        error_msg = "Invalid email or password"
        if "Invalid login" in str(e) or "invalid" in str(e).lower():
            error_msg = "Invalid email or password"
        elif "not confirmed" in str(e).lower():
            error_msg = "Email not confirmed. Check your inbox."
        else:
            error_msg = f"Login failed: {str(e)[:100]}"

        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": error_msg},
            status_code=401
        )


@app.get("/auth/logout")
def auth_logout(access_token: Optional[str] = Cookie(None)):
    """Clear session and redirect to login."""
    if access_token and access_token in active_sessions:
        del active_sessions[access_token]

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response


# =================== PROTECTED ROUTES (require auth) ===================

@app.get("/")
def root(access_token: Optional[str] = Cookie(None)):
    """Redirect base URL to dashboard (if logged in) or login page."""
    user = get_current_user(access_token)
    if user:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")


@app.get("/dashboard")
def dashboard(request: Request, access_token: Optional[str] = Cookie(None)):
    """Render the dashboard — requires authentication."""
    user = get_current_user(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    complaints = get_all_complaints()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "complaints": complaints, "user_email": user}
    )


@app.get("/complaints")
def list_complaints(access_token: Optional[str] = Cookie(None)):
    user = get_current_user(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return get_all_complaints()


@app.get("/complaints/latest")
def latest_complaint(access_token: Optional[str] = Cookie(None)):
    user = get_current_user(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return get_latest_complaint()


@app.get("/complaints/severity/{level}")
def complaints_by_severity(level: str, access_token: Optional[str] = Cookie(None)):
    user = get_current_user(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    return get_complaints_by_severity(level)
