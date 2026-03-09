# Phoenix Solutions — Blog Marketing Automation
## Complete Product Documentation

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Technology Stack](#2-technology-stack)
3. [System Requirements](#3-system-requirements)
4. [Installation & Setup](#4-installation--setup)
5. [Environment Variables](#5-environment-variables)
6. [File & Folder Structure](#6-file--folder-structure)
7. [Module Reference](#7-module-reference)
8. [The GUI — Full Walkthrough](#8-the-gui--full-walkthrough)
9. [The Automated Pipeline](#9-the-automated-pipeline)
10. [Content Calendar](#10-content-calendar)
11. [tracker.csv Schema](#11-trackercsv-schema)
12. [Prompts & Customisation](#12-prompts--customisation)
13. [Website Integration](#13-website-integration)
14. [LinkedIn API](#14-linkedin-api)
15. [Unsplash Image API](#15-unsplash-image-api)
16. [Logging](#16-logging)
17. [Troubleshooting](#17-troubleshooting)
18. [External API Quick Reference](#18-external-api-quick-reference)

---

## 1. Product Overview

Phoenix Solutions Blog Marketing Automation is a desktop application that runs the complete content-to-publish pipeline with minimal manual work:

```
Topic selection
     |
     v
Blog generation  (Groq LLM — llama-3.3-70b-versatile)
     |
     v
LinkedIn post generation  (same LLM)
     |
     v
Image fetch  (Unsplash API — landscape, topic-relevant)
     |
     v
HTML rendering  (template-based, OG/Twitter/schema tags injected)
     |
     v
Website publish  (copy to git repo, update index.html + sitemap.xml, git push)
     |
     v
LinkedIn publish  (UGC post API, image upload via Assets API)
     |
     v
Tracker update  (tracker.csv — CSV, no database)
```

Everything is controlled from a single Tkinter GUI (`gui.py`). The system uses SQLite for post management and CSV files for content tracking.

---

## 2. Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| **Language** | Python 3.11+ | Core application |
| **GUI** | Tkinter | Desktop interface |
| **AI** | Groq API (llama-3.3-70b-versatile) | Content generation |
| **Database** | SQLite | Post management and scheduling |
| **Tracking** | CSV files | Content status tracking |
| **APIs** | Requests library | External service integration |
| **Scheduling** | APScheduler | Background job management |
| **Deployment** | Git + PyInstaller | Version control and distribution |

---

## 3. System Requirements

| Requirement | Minimum |
|---|---|
| Python | 3.8+ |
| OS | Windows 10/11 (GUI uses `os.startfile` and `webbrowser`) |
| Git | Installed and authenticated (SSH or credential manager) for website push |
| Internet | Required for Groq, Unsplash, LinkedIn APIs |
| Website repo | Local clone of the phoenixsolution git repository |

---

## 4. Installation & Setup

### 3.1 Clone / open the project

```
c:\Projects\BlogMarketing\
```

### 3.2 Create a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3.3 Install dependencies

```bash
pip install -r requirements.txt
```

Dependencies installed:

| Package | Version | Purpose |
|---|---|---|
| `groq` | >=0.9.0 | Groq LLM client (blog + LinkedIn generation) |
| `python-dotenv` | >=1.0.0 | Load `.env` into `os.environ` |
| `requests` | >=2.31.0 | Unsplash image fetch, LinkedIn API calls |
| `APScheduler` | >=3.10.4 | Optional background scheduler (scheduler.py) |

### 3.4 Configure environment

```bash
copy .env.example .env
```

Edit `.env` with your API keys — see [Section 5](#5-environment-variables).

### 3.5 Run the application

```bash
python gui.py
```

---

## 5. Environment Variables

All configuration lives in `.env` in the project root. Copy `.env.example` to get started.

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Groq API key. Free at https://console.groq.com |
| `GROQ_MODEL` | No | Default: `llama-3.3-70b-versatile`. Alternative: `llama-3.1-8b-instant` |
| `LINKEDIN_ACCESS_TOKEN` | Yes (for publish) | OAuth 2.0 Bearer token. Expires every ~60 days. |
| `LINKEDIN_PERSON_URN` | No | Format: `urn:li:person:<id>`. Auto-resolved via `/userinfo` if blank. |
| `LINKEDIN_CLIENT_ID` | No | LinkedIn app Client ID (used by `linkedin_auth.py` to get a fresh token) |
| `LINKEDIN_CLIENT_SECRET` | No | LinkedIn app Client Secret |
| `UNSPLASH_ACCESS_KEY` | No | Free key from https://unsplash.com/developers. 50 req/hour. Leave blank to skip images. |
| `WEBSITE_REPO_PATH` | No | Absolute path to the local phoenixsolution repo. Default: `C:\Projects\phoenixsolution` |

### Example `.env`

```env
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile

LINKEDIN_ACCESS_TOKEN=AQU...
LINKEDIN_PERSON_URN=urn:li:person:xxxxxxxx

UNSPLASH_ACCESS_KEY=eo18...

WEBSITE_REPO_PATH=C:\Projects\phoenixsolution
```

---

## 6. File & Folder Structure

```
c:\Projects\BlogMarketing\
|
|-- gui.py                      Main application (Tkinter GUI)
|-- blog_generator.py           Blog content generation via Groq
|-- linkedin_generator.py       LinkedIn caption + hashtag generation
|-- linkedin_publisher.py       LinkedIn UGC API publish (text + image)
|-- linkedin_auth.py            OAuth token helper (standalone)
|-- html_renderer.py            Template rendering: fills placeholders, injects sections/TOC
|-- image_fetcher.py            Unsplash image search + download
|-- website_publisher.py        Website repo sync: copy files, update index, sitemap, git push
|-- tracker.py                  CSV read/write for all content entries
|-- trend_research.py           Trending topic suggestions via Groq
|-- topic_researcher.py         Reddit/LinkedIn topic research
|-- smart_scheduler.py          Intelligent auto-posting scheduler
|-- llm_client.py               Groq client singleton
|-- paths.py                    Path resolution for dev/frozen builds
|-- scheduler.py                APScheduler-based daily job (optional CLI tool)
|-- main.py                     CLI entry point (generate / publish / schedule)
|-- database.py                 SQLite CRUD for post management and scheduling
|-- requirements.txt
|-- .env                        Your credentials (never commit)
|-- .env.example                Template for credentials
|-- tracker.csv                 Content log — auto-created on first run
|-- scheduler_config.json       Smart scheduler configuration
|-- blog_marketing.db           SQLite database — auto-created on first run
|-- Log.txt                     Activity log — auto-created on first run
|
|-- Blogs/
|   |-- _new-post.html          HTML template for all blog posts
|   |-- YYYY-MM-DD-slug.html    Generated blog HTML files
|   |-- images/
|       |-- {slug}.jpg          Downloaded Unsplash images
|
|-- LinkedIn Posts/
|   |-- YYYY-MM-DD-slug.txt     Generated LinkedIn post text files
|
|-- MarketingSchedule/
|   |-- Calender.json           30-day content calendar
|   |-- ResearchTopics.json     Latest topic research output
|
|-- Prompts/
    |-- blog_prompt.txt         System prompt for blog generation
    |-- Linkedin_prompt.txt     System prompt for LinkedIn generation
    |-- Hashtags.txt            Approved hashtag list (one per line)

c:\Projects\phoenixsolution\       (separate website repo)
|-- blog/
|   |-- index.html              Blog listing page (auto-updated)
|   |-- images/
|   |   |-- {slug}.jpg          Published post images (copied from Blogs/images/)
|   |-- {slug}.html             Published blog posts (copied from Blogs/)
|-- sitemap.xml                 Auto-updated with each new post
```

---

## 7. Module Reference

### 6.1 `llm_client.py`

Groq client singleton. Initialised lazily on first use.

| Function | Returns | Description |
|---|---|---|
| `get_client()` | `groq.Groq` | Returns the shared Groq client instance |
| `get_model()` | `str` | Returns `GROQ_MODEL` from env (default: `llama-3.3-70b-versatile`) |

---

### 6.2 `paths.py`

Centralised path resolution for development and PyInstaller frozen builds.

| Function | Returns | Description |
|---|---|---|
| `app_dir()` | `str` | Directory containing user data (.env, tracker.csv, Blogs/, LinkedIn Posts/, Log.txt) |
| `resource_dir()` | `str` | Directory containing read-only assets (Prompts/, Blogs/_new-post.html, MarketingSchedule/) |

---

### 6.3 `database.py`

SQLite database operations for post management and scheduling.

| Function | Parameters | Returns | Description |
|---|---|---|---|
| `init_db()` | — | — | Creates the posts table if it doesn't exist |
| `insert_post(topic, blog_path, linkedin_text, hashtags, status, publish_date)` | `str`, `str`, `str`, `str`, `str`, `str or None` | `int` | Inserts a new post record, returns the ID |
| `update_post_status(post_id, status)` | `int`, `str` | — | Updates the status of a post |
| `get_post_by_id(post_id)` | `int` | `sqlite3.Row or None` | Returns a single post by ID |
| `get_scheduled_posts()` | — | `list[sqlite3.Row]` | Returns all posts with status 'scheduled' |
| `get_all_posts()` | — | `list[sqlite3.Row]` | Returns all posts ordered by creation date |

**Database schema (posts table):**

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PRIMARY KEY | Auto-incremented ID |
| `topic` | TEXT | Blog topic |
| `blog_path` | TEXT | Path to generated HTML file |
| `linkedin_text` | TEXT | LinkedIn post text |
| `hashtags` | TEXT | Hashtag string |
| `status` | TEXT | 'draft', 'scheduled', or 'posted' |
| `publish_date` | TEXT | When the post was published |
| `created_at` | TEXT | When the record was created |

---

### 6.4 `tracker.py`

CSV-based content log. Auto-creates `tracker.csv` on first run.

Generates structured blog content as a JSON dict via Groq.

| Function | Parameters | Returns | Description |
|---|---|---|---|
| `load_calendar()` | — | `list` | Full 30-day calendar from `Calender.json` |
| `get_calendar_entry(day)` | `day: int` | `dict or None` | Single calendar entry by day number |
| `generate_blog(topic, content_angle, keywords)` | `topic: str`, `content_angle: str`, `keywords: list` | `dict` | Full blog data from Groq LLM |

**Blog data dict keys:**

| Key | Type | Description |
|---|---|---|
| `title` | str | Article headline |
| `slug` | str | URL-safe slug (lowercase, hyphens, max 60 chars) |
| `meta_description` | str | 150-160 character SEO description |
| `category` | str | e.g. `Power BI`, `Strategy`, `Analytics` |
| `tag_emoji` | str | Single emoji for the category label |
| `keywords` | list[str] | 4 focus keywords |
| `intro` | str | 2-3 opening paragraphs (double-newline separated) |
| `sections` | list[dict] | Each: `{"heading": str, "body": str}` — 3 to 5 sections |
| `conclusion` | str | Closing paragraph |
| `cta_headline` | str | Call-to-action heading |
| `cta_subtext` | str | CTA supporting text |
| `related_service_url` | str | e.g. `/services/business-intelligence` |
| `related_service_name` | str | e.g. `BI & Dashboards` |
| `related_service_desc` | str | One-sentence service description |

---

### 6.3 `html_renderer.py`

Fills the `Blogs/_new-post.html` template with blog data.

| Function | Parameters | Returns | Description |
|---|---|---|---|
| `render_blog(blog_data, publish_date, image_url)` | `blog_data: dict`, `publish_date: str` (YYYY-MM-DD), `image_url: str or None` | `str` | Full rendered HTML string |
| `save_blog(blog_data, publish_date, image_url)` | same | `str` | Renders and saves to `Blogs/YYYY-MM-DD-{slug}.html`. Returns the file path. |

**Template notes:**
- Placeholders use `[BRACKET STYLE]` — not `{{ }}`.
- Sections are injected between `<!-- ── SECTION 1 ──` and `<!-- ── Closing section`.
- TOC links are injected between `<!-- Add one link per h2 section -->` and `<!-- Add more as needed -->`.
- If `image_url` is provided, the following tags are replaced via regex:
  - `<meta property="og:image" content="...">`
  - `<meta name="twitter:image" content="...">`
  - Schema.org `"image": "..."` field

---

### 6.4 `linkedin_generator.py`

Generates LinkedIn captions and hashtags via Groq.

| Function | Parameters | Returns | Description |
|---|---|---|---|
| `load_hashtags()` | — | `list[str]` | Reads `Prompts/Hashtags.txt`, returns tag words (no `#`) |
| `generate_linkedin_post(topic, blog_data)` | `topic: str`, `blog_data: dict or None` | `dict` | Caption + hashtags from Groq. Dual mode: blog-linked (with blog_data) or standalone (blog_data=None) |
| `save_linkedin_post(li_data, topic, calendar_day, publish_date, blog_url)` | see below | `str` | Saves TXT file, returns path |

**LinkedIn data dict keys:**

| Key | Description |
|---|---|
| `caption` | Post body text (80-150 words, no hashtags) |
| `hashtags` | Space-separated string of `#Tag` items (6 tags) |
| `full_post` | `caption + "\n\n" + hashtags` (ready to publish) |
| `blog_url` | Populated by caller after website publish |

**Saved TXT file format:**
```
TOPIC        : <topic>
DATE         : <YYYY-MM-DD>
CALENDAR DAY : <N>   (if applicable)

============================================================

<caption>

Read the full article: <blog_url>

<hashtags>
```

---

### 6.5 `image_fetcher.py`

Downloads a landscape image from Unsplash for a given blog.

| Function | Parameters | Returns | Description |
|---|---|---|---|
| `fetch_image(keywords, slug)` | `keywords: list[str]`, `slug: str` | `dict or None` | Searches Unsplash, downloads JPEG. Returns `None` if no key or error. |

**Return dict keys:**

| Key | Description |
|---|---|
| `local_path` | Absolute path to `Blogs/images/{slug}.jpg` |
| `public_url` | `https://www.phoenixsolution.in/blog/images/{slug}.jpg` |
| `photographer` | Credit name from Unsplash |
| `photographer_url` | Unsplash profile URL |

**Search strategy:**
1. Use first 2 keywords joined as a query string.
2. If no results: fall back to `"business technology"`.
3. If still no results: fall back to `"data analytics office"`.
4. If all three fail: log a warning and return `None`.

Images are saved to `Blogs/images/{slug}.jpg`.

---

### 6.6 `website_publisher.py`

Syncs a generated blog post to the local phoenixsolution website repository.

| Function | Parameters | Returns | Description |
|---|---|---|---|
| `copy_blog_to_website(src_html_path, slug)` | `str`, `str` | `str` (dest path) | Copies HTML to `phoenixsolution/blog/{slug}.html` |
| `copy_image_to_website(local_path, slug)` | `str`, `str` | `str` (public URL) | Copies image to `phoenixsolution/blog/images/{slug}.jpg` |
| `update_blog_index(blog_data, slug, publish_date)` | `dict`, `str`, `str` | — | Inserts a new blog card at the top of `.blog-grid` in `blog/index.html` |
| `update_sitemap(slug, iso_date)` | `str`, `str` | — | Inserts a `<url>` entry before `</urlset>` in `sitemap.xml` |
| `git_push_website(slug, title)` | `str`, `str` | `tuple(rc, stdout, stderr)` | Runs `git add`, `git commit`, `git push` with timeouts |
| `wait_for_live(url, retries, delay)` | `str`, `int`, `int` | `bool` | Polls URL until HTTP 200. Not called in pipeline by default. |
| `publish_to_website(blog_data, src_html_path, publish_date, image_local)` | `dict`, `str`, `str`, `str or None` | `dict` | Orchestrates steps 1-4. Returns `{"blog_url": str, "image_public_url": str or None}` |

**Blog index card injected into `blog/index.html`:**
```html
<!-- ── ARTICLE N ── -->
<a href="/blog/{slug}" class="blog-card reveal">
  <div class="blog-card-header">
    <span class="blog-tag">{emoji} {category}</span>
    <div class="blog-title">{title}</div>
    <p class="blog-excerpt">{meta_description}</p>
  </div>
  <div class="blog-card-footer">
    <span class="blog-meta">{N} min read · {Mon YYYY}</span>
    <span class="blog-read-link">Read <span>→</span></span>
  </div>
</a>
```

**Sitemap entry inserted into `sitemap.xml`:**
```xml
<url>
  <loc>https://www.phoenixsolution.in/blog/{slug}</loc>
  <lastmod>YYYY-MM-DD</lastmod>
  <changefreq>monthly</changefreq>
  <priority>0.75</priority>
</url>
```

**Git timeouts:**
- `git add` / `git commit`: 30 seconds
- `git push`: 60 seconds (raises `TimeoutExpired` → returns error tuple, does not crash)

---

### 6.7 `linkedin_publisher.py`

Posts text + optional image to LinkedIn via the UGC Posts API.

| Function | Parameters | Returns | Description |
|---|---|---|---|
| `authenticate()` | — | `str` (URN) | Returns person URN from env or resolves via `/userinfo` |
| `upload_image_asset(image_path, person_urn)` | `str`, `str` | `str or None` | 2-step LinkedIn Assets API image upload. Returns image URN or `None` on failure. |
| `publish_post(text, image_path)` | `str`, `str or None` | `dict` | Posts to LinkedIn. Uses `shareMediaCategory: IMAGE` if image upload succeeds, falls back to `NONE`. |

**Image upload flow (2-step LinkedIn Assets API):**
1. `POST /rest/images?action=initializeUpload` — get `uploadUrl` and `image` URN.
2. `PUT {uploadUrl}` — binary JPEG upload.
3. Use the returned URN in the UGC post payload.

**UGC post endpoint:** `POST https://api.linkedin.com/v2/ugcPosts`

**Required LinkedIn scopes:** `openid`, `profile`, `w_member_social`

---

### 6.15 `tracker.py`

CSV-based content log. Auto-creates `tracker.csv` on first run.

| Function | Parameters | Returns | Description |
|---|---|---|---|
| `read_all()` | — | `list[dict]` | All rows from CSV as dicts |
| `add_entry(topic, blog_path, linkedin_path, hashtags, calendar_day, content_angle, website_url)` | see below | `int` (new ID) | Appends a new row. Status defaults to `draft`. |
| `update_status(entry_id, status, published_date)` | `int`, `str`, `str or None` | — | Updates status (and optionally published_date) for a row |
| `get_entry(entry_id)` | `int` | `dict or None` | Returns a single row by ID |

---

### 6.16 `trend_research.py`

Returns 5 trending topic suggestions via Groq.

Called by the "Fetch Trending Topics" button in the Generate tab.

---

### 6.17 `topic_researcher.py`

Researches trending BI topics from Reddit and LinkedIn.

| Function | Parameters | Returns | Description |
|---|---|---|---|
| `run_research()` | — | `dict` | Fetches Reddit posts and generates LinkedIn topics via Groq, saves to `MarketingSchedule/ResearchTopics.json` |

**Research sources:**
- **Reddit**: Fetches hot posts from subreddits (PowerBI, businessintelligence, dataengineering, analytics, datascience) via public JSON API
- **LinkedIn**: Groq LLM synthesizes topics based on what BI professionals discuss (no direct API access)

**Output saved to:** `MarketingSchedule/ResearchTopics.json`

---

### 6.18 `scheduler.py` / `main.py`

Optional CLI tools. Not used by the GUI.

```bash
python main.py generate [--topic "..."] [--publish]
python main.py linkedin [--topic "..."] [--publish]
python main.py publish  [--id <n>]
python main.py schedule [--list] [--set-id <n> --status draft|scheduled|posted] [--hour h] [--minute m]
```

---

### 6.19 `smart_scheduler.py`

Intelligent auto-posting scheduler that scores posts using marketing signals.

| Function | Parameters | Returns | Description |
|---|---|---|---|
| `start_scheduler()` | — | — | Starts the background thread that monitors time slots |
| `stop_scheduler()` | — | — | Stops the scheduler thread |
| `score_post(post_data)` | `dict` | `float` | Scores a post 0-100 based on multiple marketing signals |
| `select_best_post()` | — | `dict or None` | Finds the highest-scoring draft/scheduled post |

**Scoring model (100 points total):**
- 25 pts — Sentiment quality (Groq rates tone: inspiring/authoritative/positive)
- 20 pts — Engagement hooks (questions, lists, stats, CTAs detected)
- 15 pts — Keyword relevance (hashtag quality + keyword density)
- 15 pts — Freshness (newer generated posts rank higher)
- 15 pts — Optimal length (LinkedIn sweet spot: 900-1500 chars)
- 10 pts — Has image (image posts get full bonus)

**Configuration file:** `scheduler_config.json`

Optional CLI tools. Not used by the GUI.

```bash
python main.py generate [--topic "..."] [--publish]
python main.py linkedin [--topic "..."] [--publish]
python main.py publish  [--id <n>]
python main.py schedule [--list] [--set-id <n> --status draft|scheduled|posted] [--hour h] [--minute m]
```

---

## 8. The GUI — Full Walkthrough

Launch with:
```bash
python gui.py
```

Window size: 1200 × 960. Minimum: 1000 × 800.

### 7.1 Header Bar

Always visible at the top.

- **Status indicator** (top-right): coloured dot + text showing what the app is doing.
  - Green dot = Ready
  - Orange dot = Working (async operation in progress)
  - Red dot = Error

### 7.2 Tab 1 — Generate

The main content creation tab. Split into a left control panel and a right preview panel.

#### Left panel

**CONTENT CALENDAR**
- Lists all 30 days from `MarketingSchedule/Calender.json`.
- Click a row to auto-fill the topic, content angle, and keywords.
- The info label below shows the selected day's angle and keywords.

**OR CUSTOM TOPIC**
- Free-text entry field. Overrides calendar selection.

**TRENDING TOPICS**
- Click **Fetch Trending Topics** to call Groq and populate 5 timely ideas.
- Click any topic to select it and fill the topic field.

**ACTIONS**

| Button | State | Description |
|---|---|---|
| Generate Blog + LinkedIn Post | Always active | Runs generation pipeline (Groq) |
| Edit Blog Sections | Active after generation | Opens the Edit dialog |
| Approve, Publish & Save | Active after generation | Runs the full publish pipeline |
| Clear | Always active | Resets all fields and previews |

**Progress bar** (below buttons): Animates during any async operation.

**Duplicate check:** Before generating, the topic is compared (case-insensitive) against all existing topics in `tracker.csv`. If a match is found, a warning dialog appears and generation is blocked.

#### Right panel

**BLOG PREVIEW** (read-only)
Shows: title, slug, category, meta description, keywords, intro, all sections, conclusion.
Click "Edit Blog Sections" to open the edit dialog.

**LINKEDIN POST** (editable directly)
The generated LinkedIn caption + hashtags. You can edit this text freely before approving. The blog URL is appended automatically when saved — do not add it manually here.

#### Edit Blog Sections dialog

Opens as a modal window (860 × 680). Contains:
- **TITLE** — single-line Entry field
- **INTRO** — ScrolledText (5 lines)
- **SECTION N HEADING** — Entry field (one per section)
- **SECTION N BODY** — ScrolledText (5 lines, one per section)
- **CONCLUSION** — ScrolledText (4 lines)

Click **Apply Changes** to rebuild `_blog_data` from the edited fields and refresh the blog preview. Changes to individual section headings and bodies are saved independently.

---

### 7.3 Tab 2 — Tracker

Displays all entries from `tracker.csv` in a sortable table.

**Columns:** ID | Date | Day | Topic | Status | Website URL

**Row colours:**
- White: `draft`
- Orange: `scheduled`
- Green: `posted`

**Controls:**
- **Refresh** — reloads the CSV
- **Open CSV** — opens `tracker.csv` in the default application (Excel / Notepad)
- **Change status** — select a row, pick a status from the dropdown, click Apply

**Detail panel** (bottom): Click any row to see full metadata — blog path, LinkedIn path, live URL, hashtags, content angle.

---

### 7.4 Tab 3 — Publish

Used to load a previously generated post and publish it to LinkedIn.

**Workflow:**
1. Enter a Tracker ID and click **Load**.
2. Left panel shows a stripped-text preview of the blog HTML.
3. Right panel shows the editable LinkedIn caption, editable hashtags, the blog link, and the image indicator.
4. Edit caption or hashtags as needed.
5. Click **Publish to LinkedIn** — a confirmation dialog shows the image filename and a 250-character preview.
6. On confirm: the post is sent to LinkedIn (with image if available), the tracker status is set to `posted`, and the published date is recorded.

**Open buttons (left panel):**
- **Open in Browser** — opens the local HTML file in the default browser.
- **Open Live URL** — opens the published website URL in the browser.

**Image detection:** The image is auto-resolved from `Blogs/images/{slug}.jpg` based on the blog filename in the tracker. The indicator shows "Image attached: {slug}.jpg" (cyan) or "No image for this post" (grey).

---

### 7.5 Tab 4 — Help

Inline documentation covering all tabs, file structure, and tips. Read-only.

---

### 7.6 Activity Log Panel (bottom)

Always visible below the tab panel. Shows real-time progress for every operation.

- **White text**: normal info messages
- **Orange text**: warnings (e.g. image fetch fallback, git push non-zero exit)
- **Red text**: errors (e.g. API failure)

Click **Clear** to empty the panel. The same messages are written to `Log.txt` (see Section 16).

---

## 9. The Automated Pipeline

Triggered by **Approve, Publish & Save** in the Generate tab. Runs in a background thread so the GUI stays responsive.

### Step-by-step

| Step | What happens | Log message |
|---|---|---|
| 1 | Fetch Unsplash image for the blog slug | `Fetching image from Unsplash for slug: {slug}` |
| 2 | If image found: save to `Blogs/images/{slug}.jpg` | `Image saved: {path}` |
| 2b | If no image: continue without one | `No image found — continuing without image.` (warning) |
| 3 | Render blog HTML with `image_url` set in OG/Twitter/schema tags | `Rendering and saving blog HTML...` |
| 4 | Save HTML to `Blogs/YYYY-MM-DD-{slug}.html` | `Blog HTML saved: {path}` |
| 5 | Copy HTML and image to `phoenixsolution/blog/` | `Copying to website repo and updating index + sitemap...` |
| 6 | Inject blog card into `blog/index.html` | (included in step 5 log) |
| 7 | Insert `<url>` into `sitemap.xml` | (included in step 5 log) |
| 8 | `git add` + `git commit "Add blog: {title}"` + `git push` | `Running git add / commit / push...` |
| 9 | Save LinkedIn TXT with blog URL appended | `Saving LinkedIn post TXT with blog URL...` |
| 10 | Write row to `tracker.csv` with status `draft` | `Writing tracker entry...` |
| 11 | Show success dialog + switch Approve button to disabled | `Pipeline complete — Tracker #{id}` |

**The site goes live within ~1 minute of git push** (GitHub Pages / Netlify auto-deploy). The pipeline does not poll for liveness — it completes immediately after the push.

### On success

A popup shows:
```
Post saved and pushed live (Tracker #N).

Blog  : C:\Projects\BlogMarketing\Blogs\YYYY-MM-DD-slug.html
Live  : https://www.phoenixsolution.in/blog/slug
LinkedIn TXT: C:\Projects\BlogMarketing\LinkedIn Posts\YYYY-MM-DD-slug.txt
Image  : C:\Projects\BlogMarketing\Blogs\images\slug.jpg

Go to Publish tab to post to LinkedIn.
```

---

## 10. Content Calendar

**File:** `MarketingSchedule/Calender.json`

**Format:**
```json
{
  "content_calendar": [
    {
      "day": 1,
      "topic": "Topic string",
      "content_angle": "Angle description",
      "keywords": ["kw1", "kw2", "kw3", "kw4"]
    }
  ]
}
```

- 30 entries (day 1 through day 30).
- Selecting a calendar day auto-fills the topic, stores the content angle, and passes keywords to the blog generator.
- Keywords influence Unsplash image search (first 2 used).

---

## 11. tracker.csv Schema

Auto-created at `c:\Projects\BlogMarketing\tracker.csv` on first entry.

| Column | Type | Description |
|---|---|---|
| `id` | int | Auto-incremented integer ID |
| `generated_date` | str | `YYYY-MM-DD HH:MM` — when the entry was created |
| `calendar_day` | str | Calendar day number, or blank for custom/trending topics |
| `topic` | str | The blog topic string |
| `content_angle` | str | Content angle from calendar, or blank |
| `blog_path` | str | Absolute path to the generated HTML file |
| `linkedin_path` | str | Absolute path to the LinkedIn TXT file |
| `hashtags` | str | Space-separated hashtag string |
| `status` | str | `draft` / `scheduled` / `posted` |
| `published_date` | str | `YYYY-MM-DD HH:MM` — set when LinkedIn post is published |
| `website_url` | str | Full live URL e.g. `https://www.phoenixsolution.in/blog/slug` |

**Status lifecycle:**
```
draft  →  scheduled  →  posted
```
Status is changed manually from the Tracker tab, or set to `posted` automatically when published from the Publish tab.

---

## 12. Prompts & Customisation

### 11.1 Blog prompt

**File:** `Prompts/blog_prompt.txt`

Contains the user-facing instructions for Groq. The placeholder `{topic}` is replaced at runtime. Append `\n\nContent angle: ...` and `\nFocus keywords: ...` are added programmatically when available.

The system prompt (hardcoded in `blog_generator.py`) enforces:
- JSON output format
- Slug format (lowercase, hyphens, max 60 chars)
- Meta description length (150-160 chars)
- 3-5 sections, 900-1,200 total words
- Tone: insightful, authoritative, practical
- Audience: business leaders and consultants

### 11.2 LinkedIn prompt

**File:** `Prompts/Linkedin_prompt.txt`

User prompt for LinkedIn generation. `{topic}` is replaced at runtime. Blog title and intro excerpt are appended automatically when blog data is available.

### 11.3 Hashtag list

**File:** `Prompts/Hashtags.txt`

One hashtag per line. The `#` prefix is optional — it is stripped and re-added programmatically.

Example:
```
#PowerBI
#BusinessIntelligence
DataAnalytics
ERPModernisation
```

Groq is instructed to select exactly 6 tags from this approved list. The list constrains the LLM to brand-consistent hashtags.

---

## 13. Website Integration

The website is the separate git repository at `WEBSITE_REPO_PATH` (default: `C:\Projects\phoenixsolution`).

### Required structure in the website repo

```
phoenixsolution/
|-- blog/
|   |-- index.html       Must contain: <div class="blog-grid">
|-- sitemap.xml          Must contain: </urlset>  (closing tag)
```

### What is modified per publish

| File | Change |
|---|---|
| `blog/{slug}.html` | New file — copied from `Blogs/YYYY-MM-DD-{slug}.html` |
| `blog/images/{slug}.jpg` | New file — copied from `Blogs/images/{slug}.jpg` (if image exists) |
| `blog/index.html` | New `<a class="blog-card">` block inserted after `<div class="blog-grid">` |
| `sitemap.xml` | New `<url>` block inserted before `</urlset>` |

### Git commit message format

```
Add blog: {title}
```

### Base URL

`https://www.phoenixsolution.in` — hardcoded in `website_publisher.py`. To change:
```python
BASE_URL = 'https://www.phoenixsolution.in'   # line 35 of website_publisher.py
```

---

## 14. LinkedIn API

### Token generation

1. Go to https://www.linkedin.com/developers/
2. Create an app (or use existing).
3. Required scopes: `openid`, `profile`, `w_member_social`.
4. Generate an OAuth 2.0 access token.
5. Paste into `.env` as `LINKEDIN_ACCESS_TOKEN`.

Tokens expire after approximately 60 days. Regenerate and update `.env` when expired.

### Person URN

If `LINKEDIN_PERSON_URN` is blank, the app resolves it automatically via:
```
GET https://api.linkedin.com/v2/userinfo
```

To find your URN manually: it is in the format `urn:li:person:<alphanumeric-id>`. You can also check `Log.txt` after the first successful publish — the resolved URN is logged.

### Post format (UGC API)

**Endpoint:** `POST https://api.linkedin.com/v2/ugcPosts`

**With image:**
```json
{
  "author": "urn:li:person:...",
  "lifecycleState": "PUBLISHED",
  "specificContent": {
    "com.linkedin.ugc.ShareContent": {
      "shareCommentary": {"text": "..."},
      "shareMediaCategory": "IMAGE",
      "media": [{"status": "READY", "media": "urn:li:image:..."}]
    }
  },
  "visibility": {
    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
  }
}
```

**Text only:** `shareMediaCategory: "NONE"`, no `media` field.

---

## 15. Unsplash Image API

**Endpoint:** `GET https://api.unsplash.com/search/photos`

**Parameters used:**
- `query` — first 2 blog keywords joined by space
- `orientation=landscape`
- `per_page=1`

**Auth:** `Authorization: Client-ID {UNSPLASH_ACCESS_KEY}`

**Free tier limits:** 50 requests/hour, no cost.

**Fallback chain** (in order, stops at first result):
1. First 2 blog keywords
2. `business technology`
3. `data analytics office`

**Downloaded to:** `Blogs/images/{slug}.jpg`

**Published to website at:** `phoenixsolution/blog/images/{slug}.jpg`

**Public URL pattern:** `https://www.phoenixsolution.in/blog/images/{slug}.jpg`

This URL is injected into:
- `og:image` meta tag
- `twitter:image` meta tag
- Schema.org `"image"` field

in the rendered blog HTML.

---

## 16. Logging

### GUI Activity Log panel

Visible at the bottom of every window. Shows all activity in real time. Color-coded:
- **Grey/White** — INFO: normal progress messages
- **Orange** — WARNING: non-fatal issues (image fallback, git push warnings)
- **Red** — ERROR: failures (API errors, file not found, etc.)

Click **Clear** to empty the panel.

### Log.txt file

**Location:** `c:\Projects\BlogMarketing\Log.txt`

Auto-created on first run. Appended on each run (never overwritten).

**File format (one line per event):**
```
2026-03-06 14:23:01,123  INFO      gui           Starting publish pipeline for: "Cloud ERP for SMBs"
2026-03-06 14:23:01,456  INFO      image_fetcher  Image saved: C:\Projects\BlogMarketing\Blogs\images\cloud-erp-smbs.jpg
2026-03-06 14:23:04,789  INFO      gui           Blog HTML saved: C:\Projects\BlogMarketing\Blogs\2026-03-06-cloud-erp-smbs.html
2026-03-06 14:23:05,012  INFO      website_publisher  Updated blog/index.html with card for cloud-erp-smbs
2026-03-06 14:23:05,234  INFO      website_publisher  git push: rc=0
2026-03-06 14:23:05,456  INFO      gui           Pipeline complete — Tracker #3
```

**Modules that write to the log:**

| Module | Logger name |
|---|---|
| `gui.py` | `gui` |
| `website_publisher.py` | `website_publisher` |
| `image_fetcher.py` | `image_fetcher` |
| `linkedin_publisher.py` | `linkedin_publisher` |

All module logs appear in both `Log.txt` and the GUI panel because the root logger is configured with both handlers at startup.

---

## 17. Troubleshooting

### "Generation failed. Check GROQ_API_KEY in your .env file."

- Verify `GROQ_API_KEY` is set correctly in `.env`.
- Check https://console.groq.com for quota or key status.
- Check `Log.txt` for the full error message.

### "LinkedIn publish failed. Check LINKEDIN_ACCESS_TOKEN in .env."

- Token has expired (expires every ~60 days). Generate a new one at https://www.linkedin.com/developers/
- Verify required scopes: `openid`, `profile`, `w_member_social`.
- Check `Log.txt` for the HTTP status code returned.

### Unsplash image not found

- If all three queries in the fallback chain return no results, the pipeline continues without an image. This is non-fatal.
- Verify `UNSPLASH_ACCESS_KEY` is set in `.env`.
- Check that the key has not exceeded 50 req/hour.

### "Could not find `<div class=\"blog-grid\">` in index.html"

- The `blog/index.html` in the website repo does not contain the expected `<div class="blog-grid">` element.
- Open the file and confirm the div exists exactly as written.

### Git push times out or fails

- Confirm git credentials are cached (SSH key or Windows Credential Manager).
- Run `git push` manually in `c:\Projects\phoenixsolution` to diagnose.
- Check `Log.txt` — the `git push` stderr is logged when return code is non-zero.

### Approve button hangs / progress bar spins indefinitely

- Previously caused by `wait_for_live()` polling. This is no longer called in the pipeline.
- If the progress bar is still spinning, check `Log.txt` for the last logged step to identify where it stalled.

### Duplicate topic blocked

- The system checks `tracker.csv` before generating. If the topic already exists (case-insensitive), a warning is shown.
- To regenerate the same topic: either delete the row from `tracker.csv` or choose a differently worded topic.

### `ModuleNotFoundError: No module named 'groq'`

- The virtual environment packages are not installed.
- Run: `.venv\Scripts\activate` then `pip install -r requirements.txt`

---

## 18. External API Quick Reference

| API | Purpose | Auth method | Free tier | Docs |
|---|---|---|---|---|
| Groq | Blog + LinkedIn generation | `GROQ_API_KEY` in header | Yes (generous) | https://console.groq.com/docs |
| Unsplash | Image search + download | `Client-ID` header | 50 req/hour | https://unsplash.com/documentation |
| LinkedIn UGC Posts | Publish text + image post | Bearer token | Standard | https://docs.microsoft.com/linkedin |
| LinkedIn Assets (REST) | Upload image for post | Bearer token + `LinkedIn-Version: 202305` header | Standard | https://docs.microsoft.com/linkedin |
| LinkedIn /userinfo | Resolve person URN | Bearer token | Standard | https://docs.microsoft.com/linkedin |

---

*Phoenix Solutions — info@phoenixsolution.in — https://www.phoenixsolution.in*
