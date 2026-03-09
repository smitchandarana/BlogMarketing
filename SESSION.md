# Session State — Phoenix Marketing Intelligence Engine

Quick-reference for resuming development. Read this at the start of every session.

---

## Current Status

**Last completed:** Phase 8 — ALL PHASES COMPLETE
**Next task:** Testing, tuning, EXE packaging
**API version:** 0.8.0
**Python:** C:/Users/DESKTOP/AppData/Local/Programs/Python/Python314/python.exe

---

## How to Start the Server

```bash
"C:/Users/DESKTOP/AppData/Local/Programs/Python/Python314/python.exe" -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Verify: `GET http://127.0.0.1:8000/health` → `{"status":"ok","version":"0.3.0"}`

---

## Live Endpoints

| Method | URL | Status |
|---|---|---|
| GET | /health | ✅ Working |
| GET | /api/signals | ✅ Working |
| POST | /api/signals/collect | ✅ Working (needs GROQ_API_KEY for scoring) |
| GET | /api/signals/worker | ✅ Working |
| GET | /api/insights | ✅ Working |
| POST | /api/insights/generate | ✅ Working (needs GROQ_API_KEY) |
| GET | /api/insights/worker | ✅ Working |
| GET | /api/content | ✅ Working |
| POST | /api/content/generate | ✅ Working |
| POST | /api/distribution/distribute | ✅ Working |
| GET | /api/distribution/queue | ✅ Working |
| POST | /api/distribution/schedule | ✅ Working |
| POST | /api/distribution/run | ✅ Working |
| GET | /api/analytics/dashboard | 🔲 Phase 6 |

---

## Phase Completion

| Phase | Status | Key files |
|---|---|---|
| 1 — Foundation | ✅ Done | blogpilot/config/, blogpilot/common/, blogpilot/db/, api/main.py |
| 2 — Signal Engine | ✅ Done | blogpilot/signal_engine/, blogpilot/db/repositories/signals.py |
| 3 — Insight Engine | ✅ Done | blogpilot/insight_engine/, blogpilot/db/repositories/insights.py |
| 4 — Content Engine | ✅ Done | blogpilot/content_engine/, blogpilot/db/repositories/content.py |
| 5 — Distribution Engine | ✅ Done | blogpilot/distribution_engine/, blogpilot/db/repositories/distribution.py |
| 6 — Analytics Engine | 🔲 Planned | blogpilot/analytics_engine/ (scaffold only) |
| 7 — Dashboard UI | 🔲 Planned | frontend/ (not created yet) |

---

## Phase 4 — Content Engine (IMPLEMENT THIS NEXT)

**Goal:** Generate blog posts and LinkedIn content from Insight Engine output.

**Files to create:**
```
blogpilot/content_engine/
  models/content_model.py
  services/content_planner.py      ← insight → [(type, topic, angle)]
  services/blog_service.py         ← wraps blog_generator.py + html_renderer.py
  services/linkedin_service.py     ← wraps linkedin_generator.py
  services/comment_service.py      ← wraps LinkedINGrowth/ai/comment_generator.py
  services/image_service.py        ← Stable Diffusion → fallback image_fetcher.py
  workers/content_worker.py        ← auto-draft from insights confidence >= 0.6
  schemas.py
  router.py
blogpilot/db/repositories/content.py
```

**Planner rules:**
| Category | Blog posts | LinkedIn posts |
|---|---|---|
| digital-marketing | 1 | 2 |
| ai-tech | 1 | 1 |
| marketing | 1 | 3 |
| reddit | 0 | 2 |
| default | 1 | 1 |

**External dependencies to wrap (do NOT duplicate):**
- `blog_generator.generate_blog(topic, content_angle, keywords)` → from BlogMarketing root
- `html_renderer.save_blog(blog_data, date)` → from BlogMarketing root
- `linkedin_generator.generate_linkedin_post(topic, blog_data)` → from BlogMarketing root
- `LinkedINGrowth/ai/comment_generator.generate_comment(post_text, author, topic)` → via sys.path

**DB table:** `content` (already exists from Phase 1 migration)
- id, insight_id, content_type, topic, title, body, file_path, hashtags, status, created_at

---

## Phase 5 — Distribution Engine (AFTER Phase 4)

Wraps: `website_publisher.py`, `linkedin_publisher.py`, `smart_scheduler.py`
LinkedINGrowth integration: `automation/`, `growth/`, `core/`

---

## Installed Packages

```
groq, python-dotenv, requests, APScheduler,
fastapi, uvicorn[standard], feedparser,
pydantic, starlette, httptools, watchfiles, websockets
```

Install command:
```bash
"C:/Users/DESKTOP/AppData/Local/Programs/Python/Python314/python.exe" -m pip install -r requirements.txt
```

---

## Important File Locations

| File | Purpose |
|---|---|
| `ROADMAP.md` | Full phase plan with file lists |
| `api/main.py` | FastAPI app — add new routers here |
| `signal_sources.json` | RSS feeds + subreddits (edit to add sources) |
| `blogpilot/db/migrations.py` | Add new DB tables here |
| `Blogs/_new-post.html` | Blog HTML template |
| `Prompts/blog_prompt.txt` | Blog generation prompt |
| `Prompts/Linkedin_prompt.txt` | LinkedIn post prompt |
| `.env.example` | Environment variable reference |
| `d:/Projects/LinkedINGrowth/` | LinkedIn automation repo (imported via sys.path) |

---

## Architecture Rule

- **Prefer editing existing modules** over creating new wrappers when direct modification is cleaner
- **LinkedINGrowth modules:** import via sys.path; modify only if needed for integration
- **One file per session state update** — keep this file current
