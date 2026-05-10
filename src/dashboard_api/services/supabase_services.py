"""
Supabase service for the dashboard API.
Replaces sheets_services.py — reads complaints from the Supabase 'complaints' table.
"""

import sys
import os

# Add src/ to path so we can import the shared supabase client
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from supabase_client import supabase


# ---------- Complaint Queries ----------

def get_all_complaints() -> list[dict]:
    """Fetch all complaints from Supabase, newest first."""
    response = (
        supabase
        .table("complaints")
        .select("*")
        .order("timestamp", desc=True)
        .execute()
    )
    return response.data


def get_latest_complaint() -> dict:
    """Fetch the single most recent complaint."""
    response = (
        supabase
        .table("complaints")
        .select("*")
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else {}


def get_complaints_by_severity(severity: str) -> list[dict]:
    """Fetch complaints filtered by severity level."""
    response = (
        supabase
        .table("complaints")
        .select("*")
        .eq("severity", severity)
        .order("timestamp", desc=True)
        .execute()
    )
    return response.data


def insert_complaint(record: dict) -> dict:
    """Insert a new complaint record into the database."""
    response = (
        supabase
        .table("complaints")
        .insert(record)
        .execute()
    )
    return response.data[0] if response.data else {}
