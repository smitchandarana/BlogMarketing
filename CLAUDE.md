# CLAUDE.md

## Purpose

Local automation system that generates blog posts, publishes them to the phoenixsolution website, and creates + schedules LinkedIn posts — all from the CLI or GUI.

---

## Technology Stack

- Python 3.11+
- groq (LLM — NOT OpenAI; use GROQ_API_KEY + GROQ_MODEL)
- requests, python-dotenv, apscheduler, sqlite3

---

## Architecture Rules

- One responsibility per module. Never merge concerns across files.
- Prefer editing existing modules over creating new ones.
- No partial implementations — always wire imports and verify integration.

---

## Module Map

| File | Responsibility |
|---|---|
| `llm_client.py` | Groq client singleton — `get_client()`, `get_model()` |
| `paths.py` | `app_dir()` / `resource_dir()` — dev + PyInstaller frozen support |
| `database.py` | SQLite CRUD — `init_db`, `insert_post`, `update_post_status`, `get_post_by_id`, `get_scheduled_posts`, `get_all_posts` |
| `tracker.py` | CSV tracker (`tracker.csv`) — `add_entry`, `update_status`, `get_entry`, `read_all`; used by smart_scheduler |
| `blog_generator.py` | `generate_blog(topic)` — Groq JSON blog data |
| `html_renderer.py` | `render_blog()` / `save_blog()` — template `[PLACEHOLDER]` replacement + section/TOC injection |
| `image_fetcher.py` | `fetch_image(keywords, slug)` — Unsplash download to `Blogs/images/{slug}.jpg`; returns None if no key |
| `website_publisher.py` | `publish_to_website()`, `git_push_website()` — copy files to phoenixsolution, update blog-grid, update sitemap, git push |
| `linkedin_generator.py` | `generate_linkedin_post(topic, blog_data)` — dual mode (see below); `save_linkedin_post()` saves TXT |
| `linkedin_publisher.py` | `publish_post(text, image_path, org_urn)` — LinkedIn UGC API with optional 2-step image upload |
| `linkedin_auth.py` | OAuth 2.0 flow — opens browser, captures callback, saves token to `.env` |
| `trend_research.py` | `get_trending_topics()` — Groq topic suggestions |
| `topic_researcher.py` | `run_research()` — Reddit + Groq topics → `MarketingSchedule/ResearchTopics.json` |
| `scheduler.py` | APScheduler blocking daily job — publishes scheduled posts from SQLite |
| `smart_scheduler.py` | Thread-based scheduler — scores tracker.csv posts (sentiment, hooks, freshness, image, length, keywords), picks best, auto-posts to LinkedIn |
| `main.py` | CLI entry point — `generate`, `publish`, `schedule` commands |
| `gui.py` | Tkinter GUI |

---

## Full Generate Pipeline (main.py cmd_generate)

```
generate_blog(topic)
  → save_blog(blog_data, date)           # Blogs/YYYY-MM-DD-{slug}.html
  → fetch_image(keywords, slug)          # Blogs/images/{slug}.jpg (optional)
  → publish_to_website(...)              # copy to phoenixsolution, inject blog-grid card, update sitemap
  → git_push_website(slug, title)        # git add/commit/push to deploy live
  → generate_linkedin_post(topic, blog_data)   # Groq caption + hashtags (blog-linked mode)
  → save_linkedin_post(li, topic, date, blog_url)  # LinkedIn Posts/YYYY-MM-DD-{slug}.txt
  → insert_post(...)                     # SQLite record (status: draft)
  → tracker_add_entry(...)               # tracker.csv record for smart_scheduler
```

---

## LinkedIn Post Modes (linkedin_generator.py)

**Blog-linked** (`blog_data` provided):
- 80-150 word teaser caption
- Hooks reader, highlights key insight, invites to read the full article link
- Used by `cmd_generate` after a blog is published

**Standalone** (`blog_data=None`):
- 300-500 word full self-contained post
- Structure: hook → 3-5 insight paragraphs → soft CTA to `www.phoenixsolution.in`
- No external article link — delivers complete value on its own

---

## Key File Paths

| Path | Description |
|---|---|
| `Blogs/_new-post.html` | Blog HTML template (placeholders use `[BRACKET STYLE]`) |
| `Blogs/YYYY-MM-DD-{slug}.html` | Generated blog output |
| `Blogs/images/{slug}.jpg` | Downloaded Unsplash image |
| `LinkedIn Posts/YYYY-MM-DD-{slug}.txt` | Saved LinkedIn post |
| `Prompts/blog_prompt.txt` | Blog generation prompt |
| `Prompts/Linkedin_prompt.txt` | LinkedIn blog-linked post prompt |
| `Prompts/Hashtags.txt` | Approved hashtag list (one per line) |
| `blog_marketing.db` | SQLite database |
| `tracker.csv` | CSV post tracker for smart_scheduler |
| `scheduler_config.json` | smart_scheduler config (slots, days, mode, dry_run) |
| `MarketingSchedule/ResearchTopics.json` | Latest topic research output |
| `blog_marketing.log` | Runtime log |

---

## Website Publisher (website_publisher.py)

- `WEBSITE_REPO` = env `WEBSITE_REPO_PATH` (default: `C:\Projects\phoenixsolution`)
- `publish_to_website()` does steps 1-4 (copy HTML, copy image, update blog-grid, update sitemap) — does NOT git push
- `git_push_website()` is called separately in `main.py` after `publish_to_website()`
- `update_blog_index()` injects new card at top of `<div class="blog-grid">` in `blog/index.html`
- `wait_for_live(url)` polls the live URL until HTTP 200 (optional, call manually)

---

## Database Schema

**posts table**: `id, topic, blog_path, linkedin_text, hashtags, status (draft/scheduled/posted), publish_date, created_at`

**tracker.csv**: `id, generated_date, calendar_day, topic, content_angle, blog_path, linkedin_path, hashtags, status, published_date, website_url`

---

## Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `GROQ_API_KEY` | Yes | LLM for all generation — NOT OpenAI |
| `GROQ_MODEL` | No | Default: `llama-3.3-70b-versatile` |
| `UNSPLASH_ACCESS_KEY` | No | Image fetch skipped if missing |
| `LINKEDIN_ACCESS_TOKEN` | Yes | Bearer token for UGC API |
| `LINKEDIN_PERSON_URN` | No | Resolved via `/userinfo` if missing |
| `LINKEDIN_ORG_URN` | No | Company page posting |
| `LINKEDIN_CLIENT_ID` | No | Required for `linkedin_auth.py` OAuth flow |
| `LINKEDIN_CLIENT_SECRET` | No | Required for `linkedin_auth.py` OAuth flow |
| `WEBSITE_REPO_PATH` | No | Default: `C:\Projects\phoenixsolution` |

---

## CLI Commands

```bash
python main.py generate [--topic "..."] [--publish]
python main.py publish  [--id <n>]
python main.py schedule [--list]
python main.py schedule [--set-id <n> --status draft|scheduled|posted]
python main.py schedule [--hour <h>] [--minute <m>]
```

---

## Validation Checklist (run after every code change)

1. Verify all imports resolve (no missing modules)
2. Verify `_imports()` in main.py includes any new functions used in commands
3. Confirm env vars exist in `.env` before using them
4. Confirm database schema matches `init_db()` in `database.py`
5. Confirm `tracker.csv` fieldnames match `FIELDNAMES` in `tracker.py`
6. Confirm `<div class="blog-grid">` exists in `phoenixsolution/blog/index.html`

---

## LinkedIn API Notes

- Endpoint: `https://api.linkedin.com/v2/ugcPosts`
- Image upload: 2-step via `https://api.linkedin.com/rest/images?action=initializeUpload`
- Falls back to text-only if image upload fails (426 handled gracefully)
- Required scopes: `openid profile w_member_social`

---

## HTML Template Notes

- Placeholders: `[BRACKET STYLE]` (not `{{}}`)
- Sections injected via regex between `<!-- ── SECTION 1 ──` and `<!-- ── Closing section`
- TOC injected between `<!-- Add one link per h2 section -->` and `<!-- Add more as needed -->`
