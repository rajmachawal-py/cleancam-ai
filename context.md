# CleanCam AI — Project Context

> Use this file to onboard a new AI assistant onto the CleanCam AI project.
> Last updated: 2026-06-05

---

## 1. What is CleanCam AI?

A **Smart City AI project** that detects garbage accumulation from CCTV/webcam feeds using computer vision, and automatically:
1. Detects garbage using YOLOv8s
2. Classifies severity (Low / Medium / High / Critical)
3. Captures evidence & uploads it to Supabase Storage (cloud, no local saves)
4. Files automated complaints via n8n webhooks
5. Stores complaint records in Supabase PostgreSQL
6. Displays everything on a FastAPI dashboard with Chart.js analytics

---

## 2. Project Structure

```
CleanCam AI/
├── .env                            # All config (model path, thresholds, Supabase keys, etc.)
├── .gitignore
├── README.md                       # Animated GitHub README
├── requirements.txt                # Full pip dependencies
├── Garbage_dataset.zip             # Compressed Roboflow dataset (4730 train images)
├── yolov8s.pt                      # Pretrained base weights (downloaded during training)
├── yolo11n.pt                      # Alternate pretrained weights
├── walkthrough.md                  # Detailed technical walkthrough
│
├── model/
│   ├── train5/weights/best.pt      # OLD model (YOLOv8n, 10 epochs, CPU)
│   └── train_v2/weights/best.pt    # CURRENT model (YOLOv8s, 50 epochs, GPU)
│
├── src/
│   ├── detect_severity.py          # Main detection engine (webcam → YOLO → Supabase)
│   ├── retrain.py                  # GPU training script (RTX 4050 optimized)
│   ├── supabase_client.py          # Shared Supabase client (used by detect + dashboard)
│   ├── main.ipynb                  # Original training notebook (legacy, gitignored)
│   │
│   ├── tests/                      # Automated unit/integration tests (pytest)
│   │   ├── __init__.py
│   │   ├── test_api.py             # 20 integration tests for FastAPI backend
│   │   └── test_severity.py        # 15 unit tests for severity calculation
│   │
│   └── dashboard_api/
│       ├── main.py                 # FastAPI app (routes: /dashboard, /complaints, /auth/login)
│       ├── models/
│       │   └── complaint.py        # Pydantic models: ComplaintPayload, ComplaintRecord
│       ├── services/
│       │   ├── supabase_services.py  # DB queries (get_all, get_latest, get_by_severity)
│       │   └── sheets_services.py    # LEGACY Google Sheets (no longer used)
│       ├── templates/
│       │   ├── dashboard.html      # Dashboard UI w/ Manifest + Service Worker integration
│       │   └── login.html          # Secure login portal (glassmorphism UI)
│       └── static/
│           ├── css/
│           │   └── dashboard.css   # Dark theme w/ scanlines + auth/login styles
│           ├── manifest.json       # PWA manifest configurations
│           ├── sw.js               # Service worker caching static/dynamic routes
│           └── icons/              # PWA brand logo assets
│               ├── icon-192.png
│               └── icon-512.png
```

---

## 3. Environment Variables (.env)

```
MODEL_PATH          = "path/to/model/train_v2/weights/best.pt"
CONF_THRESHOLD      = 0.75          # YOLO confidence threshold (raised to reduce false positives)
MIN_BOX_AREA        = 500           # Minimum bounding box area to count
N8N_WEBHOOK_URL     = "https://..."  # n8n webhook for email alerts
LOCATION            = "123 Main St, Anytown"
SUPABASE_URL        = "https://xxx.supabase.co"
SUPABASE_KEY        = "eyJ..."      # Supabase anon key
```

---

## 4. Tech Stack

| Layer          | Technologies                                    |
|----------------|------------------------------------------------|
| Detection      | YOLOv8s · OpenCV · PyTorch (CUDA 12.8)         |
| Backend        | FastAPI · Uvicorn · Pydantic                    |
| Database       | Supabase (PostgreSQL + Storage buckets)         |
| Automation     | n8n · Webhooks · Gmail                          |
| Frontend       | Jinja2 · Chart.js v4.4.7 · Dark Mode UI        |
| Training       | Ultralytics · RTX 4050 6GB VRAM                 |

---

## 5. Key Architecture Decisions

### Detection Pipeline (`detect_severity.py`)
- Webcam feed → YOLO inference every frame → accumulate garbage area percentage
- If garbage ≥ 20% for 5+ minutes → trigger complaint
- Evidence is **encoded in-memory** (`cv2.imencode`) and uploaded directly to Supabase Storage — NO local file saving
- Complaint data is validated through Pydantic models before Supabase insert
- `load_dotenv()` explicitly loads `.env` from project root (not CWD)

### Supabase Setup
- **Database table**: `complaints` (columns: id, timestamp, location, severity, garbage_pct, duration_seconds, evidence_url)
- **Storage bucket**: `evidence` (public, stores JPEG evidence images)
- **RLS policies**: INSERT and SELECT allowed for `anon` role on both `complaints` table and `storage.objects`
- **Client**: Shared via `supabase_client.py`, imported by both detection engine and dashboard

### Dashboard (`dashboard_api/`)
- FastAPI app served with Uvicorn (`uvicorn main:app --reload`)
- Run from: `cd src/dashboard_api`
- Dashboard at: `http://127.0.0.1:8000/dashboard`
- Features: real-time complaint cards, Chart.js trends, severity filter bar, dark/light mode toggle
- Data injected via JSON data island pattern (`<script id="complaints-data">`) to avoid Jinja2/JS conflicts
- Evidence images served via redirect to Supabase Storage public URLs

### Model Training (`retrain.py`)
- Upgraded from YOLOv8n (nano) → YOLOv8s (small)
- Trained 50 epochs on RTX 4050 GPU with `workers=0` (Windows multiprocessing fix)
- Data augmentation: rotation ±10°, brightness/hue/saturation shifts, mosaic, mixup, random erasing
- Cosine LR schedule, early stopping patience=15
- Must be wrapped in `if __name__ == '__main__':` for Windows compatibility

---

## 6. Model Performance Comparison

| Metric       | v1 (nano, 10ep, CPU) | v2 (small, 50ep, GPU) | Improvement |
|-------------|---------------------|----------------------|-------------|
| Precision    | 0.679               | 0.731                | +7.7%       |
| Recall       | 0.477               | 0.578                | +21.2%      |
| mAP@50       | 0.547               | 0.650                | +18.8%      |
| mAP@50-95    | 0.295               | 0.361                | +22.4%      |
| Inference    | 49.4ms (CPU)        | 3.9ms (GPU)          | 12.7x faster|

---

## 7. What Has Been Completed ✅

1. **Supabase Migration** — Replaced Google Sheets with Supabase PostgreSQL + Storage
2. **Supabase RLS Policies** — Created INSERT/SELECT policies for `complaints` table and `storage.objects`
3. **Evidence Cloud Upload** — In-memory JPEG encoding → direct Supabase Storage upload (no local files)
4. **File Path Fix** — Evidence paths now use absolute project root paths
5. **dotenv Fix** — `.env` loads from project root explicitly, not CWD
6. **Model Retrain** — YOLOv8s, 50 epochs on GPU, +19% mAP improvement
7. **PyTorch GPU Setup** — Reinstalled `torch` with CUDA 12.8 for RTX 4050
8. **Windows Compatibility** — `if __name__ == '__main__'` guard + `workers=0` for multiprocessing
9. **Dashboard Modernization** — Chart.js trends, severity filters, dark mode, JSON data island pattern
10. **Pydantic Models** — `ComplaintPayload` and `ComplaintRecord` for type-safe data handling
11. **Confidence Threshold Tuning** — Raised from 0.3 → 0.75 to reduce false positives
12. **README Redesign** — Animated header, badges, mermaid diagrams, skill icons
13. **Gitignore Cleanup** — Covers dataset, models, .env, notebooks, merge artifacts, and pytest cache/coverage
14. **Automated Testing** — 35 unit & integration tests passing (`pytest` + `pytest-asyncio` + `httpx`) covering severity scoring, validation, and route auth
15. **Progressive Web App (PWA)** — Manifest integration, service worker (`sw.js`) cache, install support, and brand icons
16. **Secure Supabase Auth** — Cookie-based session tracking (`access_token`, HttpOnly, 24h), user verification, and protected/public route segregation

---

## 8. Known Issues & Limitations

1. **False Positives** — Model detects people/indoor scenes as garbage (confidence 0.60-0.76). Root cause: training dataset has no negative examples (people, rooms, clean streets). Fix: retrain with negative samples.
2. **n8n Webhook** — Returns 404 when n8n server is offline (expected behavior, not a bug)
3. **Single Camera** — Currently supports only one webcam feed

---

## 9. What's Next (Planned Features) 🚀

### Priority 1: Live Dashboard with Real-Time Updates
- WebSocket or SSE for auto-refreshing dashboard when new detections arrive
- Live camera feed thumbnail
- Real-time garbage percentage gauge

### Priority 2: PWA Push Notifications
- Push alerts when garbage is detected on PWA-installed devices

### Priority 3: Evidence Gallery
- Dedicated page showing all uploaded evidence images in a grid
- Lightbox zoom, date/severity filters
- Direct integration with Supabase Storage

### Priority 4: Analytics & Reporting
- Weekly/monthly trend reports
- Peak detection hours heatmap
- Auto-generated PDF reports

### Priority 5: Multi-Camera Support
- Handle multiple RTSP/webcam feeds
- Each camera reports with its own location tag

### Priority 6: Reduce False Positives
- Add negative training samples (people, empty rooms, clean streets)
- Retrain model with balanced dataset

---

## 10. How to Run the Project

### Detection Engine
```bash
cd "CleanCam AI"
.\venv\Scripts\activate
cd src
python detect_severity.py
# Press 'q' to quit, 'c' to force a complaint trigger
```

### Dashboard
```bash
cd "CleanCam AI/src/dashboard_api"
.\venv\Scripts\activate
uvicorn main:app --reload
# Open http://127.0.0.1:8000/dashboard
```

### Retrain Model
```bash
cd "CleanCam AI"
.\venv\Scripts\activate
python src/retrain.py
# Outputs to model/train_v2/weights/best.pt
```

---

## 11. Supabase Configuration Reference

### Table: `complaints`
```sql
CREATE TABLE complaints (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT now(),
    location TEXT NOT NULL,
    severity TEXT NOT NULL,
    garbage_pct FLOAT NOT NULL,
    duration_seconds INT NOT NULL,
    evidence_url TEXT DEFAULT ''
);
```

### RLS Policies Applied
```sql
-- complaints table
CREATE POLICY "Allow public insert" ON complaints FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow public select" ON complaints FOR SELECT USING (true);

-- storage.objects (evidence bucket)
CREATE POLICY "Allow public upload to evidence" ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'evidence');
CREATE POLICY "Allow public read from evidence" ON storage.objects FOR SELECT USING (bucket_id = 'evidence');
```

### Storage Bucket
- Name: `evidence`
- Public: Yes
- Content: JPEG evidence images named `garbage_YYYYMMDD-HHMMSS.jpg`

---

## 12. User Preferences

- **Styling**: Dark-Control-Panel aesthetic with scanlines and high-contrast alert badges
- **Dev Server**: FastAPI with `uvicorn --reload` for real-time feedback
- **OS**: Windows 11, PowerShell
- **GPU**: NVIDIA RTX 4050 Laptop GPU (6GB VRAM), CUDA 12.8
- **Python**: 3.12.9 with venv
- **PyTorch**: 2.11.0+cu128
