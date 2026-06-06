from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import os

from services.supabase_services import (
    get_all_complaints,
    get_latest_complaint,
    get_complaints_by_severity,
)

# ------------------ PATH SETUP ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
EVIDENCE_BUCKET_URL = f"{SUPABASE_URL}/storage/v1/object/public/evidence"

# ------------------ APP ------------------
app = FastAPI(
    title="CleanCam AI Dashboard API",
    description="API for monitoring automated garbage complaints",
    version="3.0"
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


# ------------------ SSE NOTIFY & LOCATION MODELS ------------------
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


# ------------------ ROUTES ------------------
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


@app.get("/")
def root():
    """Redirect base URL to the dashboard."""
    return RedirectResponse(url="/dashboard")


@app.get("/dashboard")
def dashboard(request: Request):
    complaints = get_all_complaints()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "complaints": complaints}
    )


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


@app.get("/complaints")
def list_complaints():
    return get_all_complaints()


@app.get("/complaints/latest")
def latest_complaint():
    return get_latest_complaint()


@app.get("/complaints/severity/{level}")
def complaints_by_severity(level: str):
    return get_complaints_by_severity(level)


@app.get("/evidence/{image_name}")
def get_evidence_image(image_name: str):
    """Redirect to the Supabase Storage public URL for the evidence image."""
    if not image_name.lower().endswith(".jpg"):
        image_name += ".jpg"
    return RedirectResponse(url=f"{EVIDENCE_BUCKET_URL}/{image_name}")
