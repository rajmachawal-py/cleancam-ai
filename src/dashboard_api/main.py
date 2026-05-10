from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
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
    version="2.0"
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

# ------------------ ROUTES ------------------
@app.get("/")
def health_check():
    return {"status": "CleanCam AI Dashboard API running", "version": "2.0", "database": "Supabase"}

@app.get("/dashboard")
def dashboard(request: Request):
    complaints = get_all_complaints()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "complaints": complaints}
    )

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
