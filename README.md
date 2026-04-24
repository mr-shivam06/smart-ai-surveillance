<div align="center">

<img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
<img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black"/>
<img src="https://img.shields.io/badge/YOLOv8-Ultralytics-FF6B6B?style=for-the-badge"/>
<img src="https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge"/>

# 🎯 AI-Powered Intelligent Traffic & Surveillance System

**A production-grade, CPU-optimised multi-camera surveillance system built from scratch.**  
Real-time detection · Persistent Re-ID · Behaviour analysis · Fire detection · FastAPI + React dashboard

[Features](#-features) · [Architecture](#-system-architecture) · [Setup](#-installation--setup) · [Demo](#-demo-moments) · [Roadmap](#-future-roadmap)

</div>

---

## 📌 Overview

This system is a fully modular, real-time AI surveillance platform that works across roads, campuses, and private spaces. It is optimised for **CPU-only Windows machines**, supports **4+ simultaneous cameras**, and ships with a production-ready React dashboard and FastAPI backend.

Built over **20 days** across 5 development phases, the system covers everything from basic detection and face recognition to fire/smoke alerts, behaviour analysis, and a fully interactive React dashboard with ID focus mode and vehicle search.

> **Internship/Portfolio Level** — Every architectural decision is explainable, every alert is traceable, and every feature is built to be demonstrated.

---

## ✅ Build Status

| Phase | Days | Focus | Status |
|-------|------|-------|--------|
| Phase 1 | 1–4 | Foundation: Detection, Tracking, Multi-camera, Face Recognition | ✅ Complete |
| Phase 2 | 5–7 | Stable Re-ID, Vehicle Colour, Ambulance Detection | ✅ Complete |
| Phase 3 | 8–11 | Behaviour Analysis, Accident/Dwell/Zones/Crowd, Fire & Smoke | ✅ Complete |
| Phase 4 | 13–15 | FastAPI Backend, WebSocket Streaming, CPU Efficiency | ✅ Complete |
| Phase 5 | 16–20 | React Dashboard, Alert Panel, ID Focus, Vehicle Search, Demo Mode | ✅ Complete |

---

## 🌟 Features

### 🔍 Detection & Tracking
- **YOLOv8n** — Real-time object detection (persons, vehicles, 80 COCO classes) at 15+ FPS on CPU
- **DeepSORT** — Frame-to-frame tracking with persistent `track_id`, ghost-box fix, occlusion handling
- **Two-layer Re-ID** — OSNet-x0.25 appearance embeddings with 60s TTL gallery; same person re-appears with the same ID after occlusion
- **Global IDs** — `G-xxx` cross-camera identities managed by a singleton GalleryManager

### 😀 Person Intelligence
- **FaceNet** — Known-face recognition with cached embeddings per `track_id` (saves 80% of FaceNet calls)
- **Movement trails** — Last 20 centroids drawn as fading polyline on canvas
- **Dwell time** — Per-track timer; fires `LOITERING` alert after configurable threshold (default 60s)
- **Zone entry/exit** — Named polygon zones loaded from `zones.json`; `ZONE_ENTER` / `ZONE_EXIT` events with near-zero compute cost

### 🚗 Vehicle Intelligence
- **Colour extraction** — MiniBatchKMeans (k=3) on vehicle crop; maps dominant cluster to named colour (red, white, black, silver, blue…)
- **Vehicle history** — SQLite registry: class, colour, first/last seen, camera ID, frame count
- **Ambulance detection** — Colour pre-filter (white/yellow) + OCR text match; `PRIORITY` alert with no cooldown
- **Wrong-direction detection** — Velocity vector vs configured lane direction; flags angular deviation > 90°
- **Traffic state** — Rolling 150-frame vehicle count: `NORMAL` / `HEAVY` / `CONGESTION`; virtual counting line

### 🔥 Safety Alerts
- **Fire & smoke detection** — Separate YOLOv8n fine-tuned on D-Fire dataset (~21k images); smoke detected first as early warning; `CRITICAL` alert, red tint overlay on camera feed, auto-snapshot
- **Accident detection** — 3-gate logic: IoU > 0.15 + velocity drop to near-zero + condition held ≥ 2 seconds; auto-saved annotated snapshot, no cooldown
- **Crowd density** — Person count threshold + Gaussian heatmap overlay (scipy + OpenCV `applyColorMap`); toggleable from dashboard

### 🖥 Dashboard
- **Multi-camera canvas grid** — `<canvas>` rendering (not `<img>`); requestAnimationFrame draw loop; click any tile to expand fullscreen
- **Live alert ticker** — Severity chips (CRITICAL=red, HIGH=amber, INFO=teal), acknowledge button, unread count badge, Web Audio API tone on CRITICAL
- **Stats page** — Recharts AreaChart + PieChart; per-camera stat cards; zone activity panel
- **ID focus mode** — Click any bounding box → detail panel: name/UNKNOWN, zones entered/exited, dwell time, trail toggle, camera history
- **Vehicle search** — Filter by colour, date range; results table loads < 50ms; click row for full timeline
- **Demo mode** — Pre-recorded video files + hardcoded event injection (fire @ t=30s, accident @ t=90s, ambulance @ t=150s); no live camera needed

---

## 🧠 System Architecture

```
Camera Input (file · webcam · RTSP)
         │
         ▼
  Frame Preprocessor
  resize 640×480 · frame skip · FrameQueue(maxsize=2)
         │
         ▼
  ┌─────────────────────────────────┐
  │   Shared YOLOv8n (single inst.) │  ← round-robin across all cameras
  │   staggered frame offsets       │
  └─────────────────────────────────┘
         │
         ▼
  DeepSORT Tracker ──→ OSNet Re-ID Gallery ──→ Global ID (G-xxx)
         │
    ┌────┴────┐
    ▼         ▼
PERSON      VEHICLE
PIPELINE    PIPELINE
  │           │
  ├ FaceNet   ├ Colour extraction (k-means)
  ├ Dwell     ├ Vehicle history (SQLite)
  ├ Zones     ├ Traffic state
  ├ Trail     ├ Wrong direction
  └ Loiter    └ Ambulance detect
         │
         ▼
  BehaviorAnalyzer
  ├ AccidentDetector  (3-gate IoU + velocity)
  ├ CrowdAnalyzer     (count + Gaussian heatmap)
  ├ ZoneManager       (polygon point-in-test, zones.json)
  ├ DwellTracker      (per-track timer)
  └ TrafficAnalyzer   (rolling average, counting line)
         │
         └──→ FireDetector  (D-Fire YOLOv8n · every 3 frames · 320px)
         │
         ▼
  AlertSystem  (cooldown dict · severity levels · log + DB)
         │
         ▼
  FastAPI Backend
  ├ REST  /api/alerts · /api/vehicles · /api/stats · /api/cameras
  ├ WebSocket  /ws/camera/{id}  (binary JPEG + JSON events on one socket)
  └ JWT middleware · SQLite (aiosqlite) · /docs Swagger auto-generated
         │
         ▼
  React Dashboard
  ├ CamerasPage   (canvas grid · expand · count chips)
  ├ AlertsPage    (live ticker · severity chips · acknowledge · audio)
  ├ StatsPage     (AreaChart · PieChart · zone activity · heatmap toggle)
  ├ VehiclesPage  (search by colour · vehicle history timeline)
  └ TrackingPage  (Re-ID matches · cross-camera history)
```

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Detection | YOLOv8n (Ultralytics), D-Fire fine-tuned YOLOv8n |
| Tracking | DeepSORT, OSNet-x0.25 (torchreid) |
| Face Recognition | FaceNet (facenet-pytorch) |
| Re-ID | OSNet appearance embeddings, cosine similarity gallery |
| Backend | FastAPI, aiosqlite, python-jose, passlib |
| Frontend | React 18, Vite, Zustand, React Query, Recharts, TailwindCSS |
| Computer Vision | OpenCV, scipy, scikit-learn (k-means) |
| Language | Python 3.11, JavaScript (ES2022) |
| Storage | SQLite, pickle (face embeddings) |

---

## ⚙️ Installation & Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Windows 10/11 or Ubuntu 22.04
- No GPU required — fully CPU optimised

### 1. Clone & backend setup

```bash
git clone https://github.com/mr-shivam06/smart-ai-surveillance.git
cd smart-ai-surveillance

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure cameras

Edit `config.json`:

```json
{
  "cameras": [
    {"id": "cam1", "source": "videos/test1.mp4"},
    {"id": "cam2", "source": "videos/test2.mp4"}
  ],
  "zones": [
    {
      "name": "Entry",
      "type": "monitored",
      "points": [[100,100],[300,100],[300,300],[100,300]]
    }
  ],
  "loitering_seconds": 60,
  "crowd_threshold": 10,
  "demo_mode": false
}
```

### 3. Register known faces (optional)

```bash
python register_face.py --name "Shivam" --image path/to/photo.jpg
```

### 4. Run the system

**Terminal 1 — Backend:**
```bash
uvicorn api_main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** → login → system is live.

### 5. Demo mode (no camera needed)

```bash
# Set "demo_mode": true in config.json
# Events inject automatically: fire@30s · accident@90s · ambulance@150s
python main.py --demo
```

---

## 🎯 Demo Moments

These are the three moments that stop interviewers mid-sentence:

### 1. 🔥 Fire alert fires live
The camera feed gets a red tint overlay, a `CRITICAL` alert pulses in the sidebar with an audio tone, and an annotated snapshot auto-saves to `/snapshots/`.
*"Separate YOLOv8n fine-tuned on the D-Fire dataset (~21k images). Smoke detected first as early warning — fire confirms it. No cooldown on fire alerts."*

### 2. 🔎 Click an ID — see its full history
Click any bounding box on the live canvas. A detail panel slides in: name or UNKNOWN, which cameras have seen this person, zone enter/exit history, current dwell time, and a fading trail of the last 20 positions. For vehicles: colour, class, first/last seen, full camera timeline.

### 3. 🚗 Vehicle search in under 50ms
Open the Vehicle Search page, select colour `white` or enter a partial plate. The results table loads under 50ms backed by SQLite. Click any row for the full timeline. Every entry is timestamped and camera-attributed.

---

## 📊 Performance

| Metric | Value |
|---|---|
| Detection FPS (1 camera) | 15–20 FPS |
| Detection FPS (4 cameras, shared model) | 8–10 FPS effective total |
| CPU usage (4 cameras active) | < 70% |
| API response time (vehicle search) | < 50ms |
| Face recognition (cache hit) | ~2ms |
| Fire detection overhead | ~15–20ms every 3 frames |

> Benchmarked on Intel Core i5-12th Gen, 16GB RAM, no GPU.

---

## 📁 Project Structure

```
smart-ai-surveillance/
│
├── main.py                    # Entry point, camera threads, OpenCV grid display
├── api_main.py                # FastAPI app, JWT middleware, lifespan, CORS
├── config.py / config.json    # System-wide configuration + zone definitions
├── database.py                # SQLite schema, connection setup
├── security.py                # JWT auth, password hashing
├── schemas.py                 # Pydantic models for all API responses
│
├── shared_model.py            # Single YOLOv8n instance shared across all cameras
├── camera_processor.py        # Per-camera orchestrator, staggered frame offsets
├── camera_worker.py           # Thread wrapper per camera source
├── camera_registry.py         # Active camera state registry
├── stream_bridge.py           # FrameBuffer ring buffer, WebSocket JPEG forwarding
├── demo_mode.py               # Video file sources + hardcoded event injection
│
├── detection.py               # YOLOv8 wrapper, BoundingBox/Detection dataclasses
├── tracking.py                # DeepSORT per-camera tracker, ghost-box fix
├── cross_camera_tracker.py    # OSNet gallery, G-xxx global IDs, cosine similarity
├── target_manager.py          # Click-to-lock target, trail display, info panel
│
├── face_recognition_module.py # FaceNet embeddings, per-track_id cache
├── vehicle_analysis.py        # Colour k-means, shape type, vehicle history
├── behavior_analysis.py       # Accident · Dwell · Zones · Crowd · Traffic · Ambulance
├── fire_detection.py          # D-Fire YOLOv8n + HSV fallback, CRITICAL alerts
├── alert_system.py            # Cooldown dict, severity levels, DB + log writer
│
├── routes/
│   ├── routes_alerts.py       # GET/POST /api/alerts, acknowledge endpoint
│   ├── routes_vehicles.py     # GET /api/vehicles, plate lookup, track history
│   ├── routes_camera.py       # GET /api/cameras, /api/stats, snapshot
│   ├── routes_stream.py       # WebSocket /ws/camera/{id}
│   ├── routes_tracking.py     # Re-ID matches, global track history
│   └── routes_auth.py         # POST /api/auth/login
│
├── frontend/
│   └── src/
│       ├── App.jsx            # Router, nav, auth guard
│       ├── AuthContext.jsx    # JWT token management
│       ├── Dashboard.jsx      # Live stats, recent alerts, FPS chart
│       ├── CamerasPage.jsx    # Canvas grid, expand mode
│       ├── CameraFeed.jsx     # Canvas rendering, useCamera WebSocket hook
│       ├── AlertsPage.jsx     # Alert ticker, severity chips, acknowledge
│       ├── StatsPage.jsx      # AreaChart, PieChart, zone activity panel
│       ├── VehiclesPage.jsx   # Vehicle search, results table, history
│       ├── TrackingPage.jsx   # Re-ID matches, cross-camera status
│       └── api.js             # REST client for all endpoints
│
├── zones.json                 # Named polygon zone definitions
├── known_faces/               # Registered face embeddings (pickle)
├── snapshots/                 # Auto-saved alert snapshots
├── requirements.txt
└── .env.example
```

---

## 🔐 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Get JWT bearer token |
| `GET` | `/api/alerts` | Paginated alerts — filter by type, severity, camera, since |
| `POST` | `/api/alerts/{id}/acknowledge` | Mark alert as seen |
| `GET` | `/api/vehicles` | Vehicle list — filter by colour, date range |
| `GET` | `/api/vehicles/{track_id}/history` | Full timeline for one vehicle |
| `GET` | `/api/vehicles/plate/{text}` | Instant plate lookup |
| `GET` | `/api/stats` | Live: person count, vehicle count, active alerts, traffic state |
| `GET` | `/api/cameras` | Camera list with status and live counts |
| `GET` | `/api/cameras/{id}/snapshot` | Latest annotated frame as JPEG |
| `WS`  | `/ws/camera/{id}` | Binary JPEG frames + JSON alert events on one socket |

Full interactive docs at **http://localhost:8000/docs**

---

## 🗺 Future Roadmap

Fully designed and sequenced. Each item below has detailed implementation notes ready — these are the natural next phases for this project.

### Phase 6 — Complete the Spec *(~2 days)*
- [ ] **Weather classifier** — MobileNetV2 6-class scene recognition (Clear / Cloudy / Rainy / Foggy / Night / Low-visibility); runs every 5s per camera on a 224×224 centre crop; auto-adjusts YOLO `conf` 0.5→0.35 and DeepSORT `max_age` under fog/rain; weather badge per camera tile in dashboard
- [ ] **Async plate OCR** — EasyOCR in a dedicated `multiprocessing.Process`; vehicle crops sent via Queue, results returned without blocking the main loop; plate text drawn on vehicle bboxes and stored in vehicle registry

### Phase 7 — Performance Hardening *(~3 days)*
- [ ] **Motion gate** — `cv2.absdiff` frame diff; skip YOLO inference entirely on static scenes; expected 40–60% CPU drop on idle cameras
- [ ] **INT8 quantisation** — Export YOLOv8n to ONNX, apply `quantize_dynamic` (QInt8) via `onnxruntime`; ~50% faster inference; model size 50MB → 13MB
- [ ] **SQLite WAL mode + batched writes** — `PRAGMA journal_mode=WAL`; reads never block writes; batch vehicle updates every 30 frames; seed `activity_log` table for heatmap

### Phase 8 — Standout Features *(~6 days)*
- [ ] **Configurable alert rules UI** — Zone polygon drag editor + threshold sliders in dashboard; operators change settings without touching code
- [ ] **Exportable incident report (PDF)** — One-click PDF per alert: annotated snapshot + track timeline + metadata via `reportlab`
- [ ] **Temporal activity heatmap** — 24-hour spatial density map of where people/vehicles appeared; Canvas 2D Gaussian accumulation; time scrubber by hour
- [ ] **Anomaly scoring** — `sklearn.IsolationForest` trained on normal-scene feature vectors (velocity, dwell, zone count, time-of-day encoding); `ANOMALY_DETECTED` alerts for statistical outliers
- [ ] **Person attribute recognition** — Age group (child/adult/elderly) + top/bottom clothing colour via MobileNetV2 on person crop; shown in ID focus panel and incident reports
- [ ] **Natural language vehicle search** — Local Ollama (Mistral) converts plain English to SQLite SELECT; type *"white vehicles in Zone B after 6pm"* in the search bar

### Phase 9 — Production Engineering *(~3 days)*
- [ ] **pytest suite + GitHub Actions CI** — Unit tests for AccidentDetector, ZoneManager, VehicleAnalyzer, all API endpoints; green CI badge in README
- [ ] **Docker Compose** — One-command deployment: `docker compose up`; backend (Python 3.11-slim) + frontend (nginx multi-stage); SQLite persisted via named volume
- [ ] **Prometheus metrics + Grafana** — `inference_latency_ms`, `active_track_count`, `alert_rate`, `cpu_percent` exposed at `/metrics`; optional Grafana dashboard

### Longer-term ideas
- [ ] Speed estimation with physical camera calibration
- [ ] Edge deployment — ONNX model on Raspberry Pi 5 / Jetson Nano
- [ ] Cloud storage — S3 snapshots, RDS vehicle registry
- [ ] Mobile push notifications for CRITICAL alerts
- [ ] Automatic licence plate recognition fine-tuned on Indian number plates (ALPR-India dataset)

---

## 💼 Use Cases

| Domain | Application |
|--------|-------------|
| 🏢 Corporate / Campus | Entry/exit monitoring, restricted zone enforcement |
| 🚦 Traffic Management | Congestion detection, wrong-direction alerts, accident response |
| 🏬 Retail Analytics | Foot traffic patterns, dwell time at displays, crowd management |
| 🏙 Smart City | Ambulance corridor clearing, public safety monitoring |
| 🏫 School / College | Unknown person flagging, after-hours zone alerts |

---

## 🤝 Interview Preparation

When asked *"how does your system handle X"*:

| Question | Answer |
|----------|--------|
| ID persistence across occlusion | Two-layer identity: DeepSORT (short-term IoU+motion) + OSNet-x0.25 embeddings (60s TTL gallery, cosine similarity > 0.75). Same person re-appears with same G-xxx ID. |
| Multi-camera efficiency on CPU | Single shared YOLOv8n model. Round-robin FrameQueues (maxsize=2 — always freshest frame). Heavy tasks (FaceNet) async-queued in background thread pool. 4 cameras at ~10 FPS total. |
| Accident detection | 3-gate logic: IoU overlap > 0.15, velocity near zero for both vehicles, condition held ≥ 2 seconds. Fully explainable — every alert has vehicle IDs, timestamp, and a snapshot. |
| Why SQLite not Postgres | At this scale (4 cameras, ~100 alerts/hr) all queries are < 50ms. Postgres is right at 10× scale; SQLite lets us demo with zero infrastructure setup. |
| What would you add next | Weather-adaptive thresholds (MobileNetV2 adjusting YOLO conf in fog/rain), async plate OCR via multiprocessing, and INT8 quantisation for 50% faster inference — all fully designed and ready to build. |

---

## 👨‍💻 Author

**Shivam**  
[GitHub: @mr-shivam06](https://github.com/mr-shivam06)

---

## 📄 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

If this project helped you or you found it interesting, please consider giving it a ⭐

*Built with purpose. Every alert is explainable. Every feature is demonstrable.*

</div>