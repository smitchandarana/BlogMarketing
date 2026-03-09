# Phoenix Marketing Intelligence Engine — Development Roadmap

## Project Goal
Local-first AI marketing automation system that collects industry signals, converts them into decision intelligence, generates content, and distributes it — all from a single platform. Runs as a standalone EXE, no environment setup required.

## Tech Stack
| Layer | Technology |
|---|---|
| Backend | Python 3.14, FastAPI, SQLite |
| AI | Groq API (llama-3.3-70b-versatile / llama-3.1-8b-instant) |
| Scheduler | APScheduler |
| LinkedIn automation | LinkedINGrowth (d:/Projects/LinkedINGrowth) |
| Frontend (future) | Next.js + Tailwind |

---

## Phase Status

### Phase 1 — Foundation & Scaffolding ✅ COMPLETE
- `blogpilot/` package created
- `blogpilot/config/settings.py` — centralized env-based config
- `blogpilot/common/exceptions.py` — error hierarchy
- `blogpilot/common/logging.py` — logger factory
- `blogpilot/db/connection.py` — SQLite WAL connection factory
- `blogpilot/db/migrations.py` — schema versioning (5 new tables)
- `api/main.py` — FastAPI app, lifespan hooks, CORS, /health
- All 5 engine directories scaffolded

### Phase 2 — Signal Engine ✅ COMPLETE
Collects and scores industry signals from RSS and Reddit.

Files:
- `blogpilot/signal_engine/models/signal.py`
- `blogpilot/signal_engine/sources/rss.py` (feedparser)
- `blogpilot/signal_engine/sources/reddit.py` (Reddit JSON API)
- `blogpilot/signal_engine/services/collector.py`
- `blogpilot/signal_engine/services/scorer.py` (Groq batch, 10/call)
- `blogpilot/signal_engine/workers/signal_worker.py` (APScheduler, every 6h)
- `blogpilot/signal_engine/router.py`
- `blogpilot/signal_engine/schemas.py`
- `blogpilot/db/repositories/signals.py`
- `signal_sources.json` — configurable feed list

Endpoints: `GET /api/signals`, `POST /api/signals/collect`, `GET /api/signals/worker`

### Phase 3 — Insight Engine ✅ COMPLETE
Clusters signals, generates decision intelligence insights via Groq.

Files:
- `blogpilot/insight_engine/models/insight.py`
- `blogpilot/insight_engine/services/signal_clusterer.py` (Jaccard keyword clustering)
- `blogpilot/insight_engine/services/insight_generator.py` (Groq, 1 call/cluster)
- `blogpilot/insight_engine/services/insight_ranker.py` (count×40 + relevance×40 + recency×20)
- `blogpilot/insight_engine/workers/insight_worker.py` (APScheduler, every 12h)
- `blogpilot/insight_engine/router.py`
- `blogpilot/insight_engine/schemas.py`
- `blogpilot/db/repositories/insights.py`

Endpoints: `GET /api/insights`, `POST /api/insights/generate`, `GET /api/insights/{id}`

### Phase 4 — Content Engine 🔲 NEXT
Generates blog posts and LinkedIn content from insights.
Wraps: BlogMarketing flat modules + LinkedINGrowth ai/ layer.

Planned files:
- `blogpilot/content_engine/models/content_model.py`
- `blogpilot/content_engine/services/content_planner.py`
- `blogpilot/content_engine/services/blog_service.py` (wraps blog_generator + html_renderer)
- `blogpilot/content_engine/services/linkedin_service.py` (wraps linkedin_generator)
- `blogpilot/content_engine/services/comment_service.py` (wraps LinkedINGrowth ai/)
- `blogpilot/content_engine/services/image_service.py` (Stable Diffusion → image_fetcher)
- `blogpilot/content_engine/workers/content_worker.py`
- `blogpilot/content_engine/router.py`
- `blogpilot/content_engine/schemas.py`
- `blogpilot/db/repositories/content.py`

Endpoints: `GET /api/content`, `POST /api/content/generate`, `GET /api/content/{id}`

### Phase 5 — Distribution Engine 🔲 PLANNED
Publishes content to website and LinkedIn.
Wraps: website_publisher, linkedin_publisher, smart_scheduler.
Integrates: LinkedINGrowth automation/ + growth/ + core/ layers.

Key integrations:
- `automation/browser.py`, `linkedin_login.py`, `feed_scanner.py`, `interaction_engine.py`
- `growth/viral_detector.py`, `engagement_strategy.py`
- `core/pipeline.py`, `worker_pool.py`, `rate_limiter.py`

Endpoints: `POST /api/distribute`, `GET /api/distribution/queue`

### Phase 6 — Analytics Engine 🔲 PLANNED
Tracks content performance, feeds learnings back into signal scoring.
Integrates: LinkedINGrowth analytics/metrics.py.

Endpoints: `GET /api/analytics/dashboard`, `GET /api/analytics/topics`

### Phase 7 — Dashboard UI 🔲 PLANNED
Next.js + Tailwind frontend.
Pages: Signal feed, Insight board, Content pipeline, Distribution queue, Analytics.

---

## Existing Flat Modules (Backward Compatible — Keep Unchanged)

These live in the project root and continue to power the CLI (`main.py`) and GUI (`gui.py`):

| Module | Purpose | Wrapped By (future) |
|---|---|---|
| `blog_generator.py` | Groq blog JSON generation | content_engine/services/blog_service.py |
| `html_renderer.py` | Template → HTML | content_engine/services/blog_service.py |
| `linkedin_generator.py` | LinkedIn post generation | content_engine/services/linkedin_service.py |
| `linkedin_publisher.py` | LinkedIn UGC API | distribution_engine/services/linkedin.py |
| `website_publisher.py` | Copy → phoenixsolution repo + git push | distribution_engine/services/website.py |
| `image_fetcher.py` | Unsplash image download | content_engine/services/image_service.py |
| `smart_scheduler.py` | Post scoring + scheduling | distribution_engine/services/scheduler.py |
| `database.py` | posts table CRUD | db/repositories/posts.py |
| `tracker.py` | tracker.csv CRUD | distribution_engine (kept for backward compat) |
| `llm_client.py` | Groq singleton | config/settings.get_groq_client() |
| `paths.py` | Dev/frozen path resolution | config/settings._app_dir() |
| `main.py` | CLI entry point | Unchanged forever |
| `gui.py` | Tkinter GUI | Unchanged (deprecated when dashboard ships) |

---

## Linked External Repository

**LinkedINGrowth** (`d:/Projects/LinkedINGrowth`)
- Standalone LinkedIn engagement automation (Selenium, Groq, APScheduler)
- Imported via sys.path — NOT copied or modified
- Phase 4 uses: `ai/comment_generator.py`, `ai/relevance_classifier.py`
- Phase 5 uses: `automation/`, `growth/`, `core/`
- Phase 6 uses: `analytics/`

---

## Running the System

```bash
# Install dependencies (one-time)
"C:/Users/DESKTOP/AppData/Local/Programs/Python/Python314/python.exe" -m pip install -r requirements.txt

# Start API server
"C:/Users/DESKTOP/AppData/Local/Programs/Python/Python314/python.exe" -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# Run existing CLI (unchanged)
"C:/Users/DESKTOP/AppData/Local/Programs/Python/Python314/python.exe" main.py generate --topic "AI in marketing"

# Run existing GUI (unchanged)
"C:/Users/DESKTOP/AppData/Local/Programs/Python/Python314/python.exe" gui.py
```

---

## Key Paths

| Path | Description |
|---|---|
| `blogpilot/` | New modular package |
| `api/main.py` | FastAPI entry point |
| `signal_sources.json` | RSS feeds + subreddits config |
| `scheduler_config.json` | Worker scheduling config |
| `blog_marketing.db` | Unified SQLite database |
| `Blogs/` | Generated HTML blog files |
| `LinkedIn Posts/` | Generated LinkedIn post TXT files |
| `Prompts/` | Groq prompt templates |
| `Blogs/_new-post.html` | Blog HTML template |
| `.env.example` | Environment variable template |
