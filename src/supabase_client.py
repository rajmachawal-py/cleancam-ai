"""
Shared Supabase client instance for CleanCam AI.
Used by both detect_severity.py and the dashboard API.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError(
        "Missing SUPABASE_URL or SUPABASE_KEY in .env — "
        "cannot connect to Supabase."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
