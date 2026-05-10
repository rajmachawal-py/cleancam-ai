from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ---------- Severity Helper ----------

def classify_severity(garbage_pct: float) -> str:
    """Classify garbage severity based on percentage of frame covered."""
    if garbage_pct >= 70:
        return "Critical"
    elif garbage_pct >= 40:
        return "High"
    elif garbage_pct >= 20:
        return "Medium"
    else:
        return "Low"


# ---------- N8N Webhook Payload ----------

class ComplaintPayload(BaseModel):
    """Payload sent to the n8n webhook for automated complaint filing."""
    location: str
    timestamp: str
    garbage_percentage: float = Field(..., ge=0, le=100)
    detected_time: float = Field(..., ge=0, description="Seconds garbage was detected")
    image_path: str


# ---------- Supabase Complaint Row ----------

class ComplaintRecord(BaseModel):
    """
    Represents a complaint row in the Supabase 'complaints' table.
    Used for inserts and reads from the database.
    """
    id: Optional[int] = None
    timestamp: Optional[datetime] = None
    location: str
    severity: str
    garbage_pct: float = Field(..., ge=0, le=100)
    duration_seconds: int = Field(..., ge=0)
    evidence_url: Optional[str] = None

    @classmethod
    def from_payload(cls, payload: ComplaintPayload, evidence_url: str = "") -> "ComplaintRecord":
        """Create a ComplaintRecord from a webhook payload + uploaded evidence URL."""
        return cls(
            location=payload.location,
            severity=classify_severity(payload.garbage_percentage),
            garbage_pct=payload.garbage_percentage,
            duration_seconds=int(payload.detected_time),
            evidence_url=evidence_url,
        )
