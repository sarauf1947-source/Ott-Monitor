# 📡 OTT/IPTV Monitor

**Production-grade real-time monitoring platform for HLS and MPEG-DASH live streams.**

Supports 300–350 concurrent streams with QoS/QoE metrics, NOC-style dashboard, alerting, and reporting.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     NGINX (reverse proxy)                    │
│              HTTP :80 / HTTPS :443                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┴────────────┐
          ▼                        ▼
  ┌───────────────┐      ┌──────────────────┐
  │  React SPA    │      │  FastAPI Backend  │
  │  (port 3000)  │◄────►│  (port 8000)      │
  └───────────────┘      └────────┬──────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
             ┌──────────┐ ┌──────────┐ ┌──────────────┐
             │TimescaleDB│ │  Redis   │ │  15× Workers  │
             │ (PG 15)   │ │  Cache   │ │  (ffprobe)    │
             └──────────┘ └──────────┘ └──────────────┘
```

**Stack:**

| Layer | Technology |
|-------|-----------|
| API | Python 3.11 + FastAPI + Uvicorn |
| Database | PostgreSQL 15 + TimescaleDB |
| Cache | Redis 7 |
| Workers | Asyncio + ffprobe |
| Frontend | React 18 + Vite + Tailwind CSS |
| Container | Docker + Docker Compose v2 |

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/yourorg/ott_monitor.git
cd ott_monitor
cp .env.example .env
nano .env    # Set DB_PASSWORD and other values
```

### 2. Start with Docker Compose

```bash
# Build all images
docker compose -f deployment/docker-compose.yml build

# Start infrastructure (DB + Redis)
docker compose -f deployment/docker-compose.yml up -d timescaledb redis

# Wait for healthy (watch until both show "healthy")
watch docker compose -f deployment/docker-compose.yml ps

# Start API
docker compose -f deployment/docker-compose.yml up -d api

# Seed 300 sample channels
docker compose -f deployment/docker-compose.yml exec api python scripts/seed_data.py

# Start 15 workers (covers 300 streams at 20 per worker)
docker compose -f deployment/docker-compose.yml up -d --scale worker=15

# Start frontend
docker compose -f deployment/docker-compose.yml up -d frontend
```

### 3. Access

| Service | URL |
|---------|-----|
| NOC Dashboard | http://localhost:3000 |
| API Docs (Swagger) | http://localhost:8000/api/docs |
| API Health | http://localhost:8000/api/v1/health |
| Dashboard Summary | http://localhost:8000/api/v1/dashboard/summary |

---

## Development

### Backend (local Python)

```bash
# Create virtualenv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start supporting services
docker compose -f deployment/docker-compose.yml up -d timescaledb redis

# Run API with hot-reload
uvicorn api.main:app --reload --port 8000

# Run a single worker
SIMULATE_MODE=true WORKER_ID=0 TOTAL_WORKERS=1 python -m workers.monitor_worker
```

### Frontend (local Node)

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

### Run Tests

```bash
# Install test deps
pip install -r requirements.txt

# Run all tests
pytest -v

# Run specific test file
pytest tests/api/test_channels.py -v

# With coverage
pytest --cov=. --cov-report=html
```

---

## Configuration

All configuration is driven by environment variables (`.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `SIMULATE_MODE` | `true` | Use simulated data — no real streams needed |
| `MONITOR_INTERVAL` | `300` | Seconds between stream checks |
| `STREAMS_PER_WORKER` | `20` | Channels handled per worker replica |
| `TOTAL_WORKERS` | `15` | Total worker replicas (must match `--scale worker=N`) |
| `DB_PASSWORD` | — | PostgreSQL password (required) |
| `REDIS_URL` | `redis://redis:6379` | Redis connection URL |
| `WEBHOOK_URL` | — | Slack/webhook URL for alerts |
| `SMTP_USER` | — | Email address for alert emails |

See `.env.example` for the full reference.

---

## API Reference

### Channels

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/channels` | List channels (filterable, paginated) |
| `POST` | `/api/v1/channels` | Register new channel |
| `GET` | `/api/v1/channels/{id}` | Get single channel |
| `PATCH` | `/api/v1/channels/{id}` | Update channel |
| `DELETE` | `/api/v1/channels/{id}` | Delete channel |

### Metrics & Errors

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/channels/{id}/metrics` | Time-series metrics |
| `GET` | `/api/v1/channels/{id}/metrics/summary` | Aggregated stats |
| `GET` | `/api/v1/channels/{id}/errors` | Error history |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/dashboard/summary` | NOC KPI summary (cached 30s) |
| `GET` | `/api/v1/dashboard/channels` | Per-channel status grid |

### Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/alerts` | List alerts |
| `PATCH` | `/api/v1/alerts/{id}/acknowledge` | Acknowledge alert |
| `PATCH` | `/api/v1/alerts/{id}/resolve` | Resolve alert |

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/reports/generate` | Generate JSON report |
| `POST` | `/api/v1/reports/export/csv` | Download CSV report |

---

## Error Classification

| Severity | Color | Error Types |
|----------|-------|-------------|
| CRITICAL | 🔴 Red | `STREAM_DOWN`, `BLACK_FRAME`, `VIDEO_JITTER` |
| MAJOR | 🟡 Yellow | `VIDEO_FREEZE`, `AUDIO_SILENCE`, `AUDIO_JITTER` |
| WARNING | 🟣 Purple | `LIP_SYNC_OUT`, `HLS_SEGMENT_DELAY`, `BITRATE_DROP` |
| INFO | 🔵 Blue | `HIGH_LATENCY`, `RESOLUTION_CHANGE` |

---

## Importing Your Own Channels

```bash
# Via CSV (columns: name, stream_url, protocol, group, description, expected_bitrate, expected_resolution)
docker compose exec api python scripts/import_channels.py /path/to/channels.csv

# Via API
curl -X POST http://localhost:8000/api/v1/channels \
  -H "Content-Type: application/json" \
  -d '{"name":"My Channel","stream_url":"https://cdn.example.com/live/stream.m3u8","protocol":"HLS"}'
```

---

## Production Deployment

See the `OTT_Monitor_Ubuntu_Setup_Guide.docx` in this repo for the complete step-by-step Ubuntu 22.04/24.04 setup guide covering:

- OS hardening, firewall, SSH security
- Docker Engine installation
- ffmpeg/Python/Node installation
- System limits tuning
- Nginx reverse proxy + SSL (Let's Encrypt)
- Systemd auto-restart service
- TimescaleDB retention policies
- Log management
- Automated backup

### Quick scale reference

```bash
# 300 streams → 15 workers
docker compose up -d --scale worker=15

# 150 streams → 8 workers  
docker compose up -d --scale worker=8

# Check all services
docker compose ps
docker compose logs -f api
docker compose logs -f worker
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| API returns 500 | `docker compose logs timescaledb` — check DB connectivity |
| Workers not updating | Verify `SIMULATE_MODE=false` for real streams; check `TOTAL_WORKERS` matches replicas |
| Dashboard shows 0 channels | Run seed script: `docker compose exec api python scripts/seed_data.py` |
| ffprobe not found | Rebuild worker: `docker compose build worker` |
| Redis connection refused | Ensure `REDIS_URL=redis://redis:6379` (not localhost) |
| DB disk full | Check retention policy; run `docker system prune` |
| High CPU on workers | Reduce `STREAMS_PER_WORKER` or increase `MONITOR_INTERVAL` |

---

## License

MIT — see LICENSE file.
