# Phoenix Marketing Intelligence Engine
## Product Capabilities Reference

**Version:** 1.0.0
**Platform:** Local-first, Windows / Linux / macOS
**Prepared for:** Phoenix Solutions
**Document date:** 2026-03-09

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [The Eight-Step Automation Pipeline](#3-the-eight-step-automation-pipeline)
4. [Engine Capabilities — Module Reference](#4-engine-capabilities--module-reference)
   - 4.1 [Signal Engine](#41-signal-engine)
   - 4.2 [Insight Engine](#42-insight-engine)
   - 4.3 [Content Engine](#43-content-engine)
   - 4.4 [Distribution Engine](#44-distribution-engine)
   - 4.5 [Analytics Engine](#45-analytics-engine)
   - 4.6 [LinkedIn Growth Engine (Engagement Engine)](#46-linkedin-growth-engine-engagement-engine)
5. [Legacy Pipeline Modules](#5-legacy-pipeline-modules)
6. [User Interfaces](#6-user-interfaces)
7. [REST API Reference](#7-rest-api-reference)
8. [Configuration and Customisation](#8-configuration-and-customisation)
9. [Database Schema](#9-database-schema)
10. [Packaging and Deployment](#10-packaging-and-deployment)
11. [Technical Specifications](#11-technical-specifications)
12. [What to Expect — Realistic Outcomes and KPIs](#12-what-to-expect--realistic-outcomes-and-kpis)

---

## 1. Executive Summary

The Phoenix Marketing Intelligence Engine is a locally-hosted, AI-powered marketing automation system built exclusively for Phoenix Solutions. It removes the manual effort from content marketing by connecting real-time industry intelligence to published blog posts and LinkedIn content, and then measuring what works — all without relying on third-party SaaS platforms or paying per-seat subscription fees.

### What the system does

The engine monitors configurable industry signal sources (RSS feeds, Reddit communities), identifies trending topics relevant to Phoenix Solutions' market, generates full-length blog posts and LinkedIn posts using a large-language model, publishes them directly to the Phoenix Solutions website and LinkedIn account on a schedule, and then collects performance metrics to continuously improve future content decisions.

In addition to outbound publishing, the engine includes an opt-in LinkedIn Growth module that scans the LinkedIn feed, identifies relevant posts from target audiences and tracked influencers, and autonomously places AI-generated likes and thoughtful comments to build profile visibility and network engagement.

### Who it is for

The system is designed for internal use by the Phoenix Solutions marketing and content team. It is operated from either a browser-based web dashboard or a native desktop application (Windows EXE), with no coding required for day-to-day use.

### Core value proposition

| Without this system | With this system |
|---|---|
| Manual topic research taking hours per week | Automated signal collection running every 6 hours |
| Blog posts written from scratch per piece | Full blog posts generated and published in one pipeline run |
| LinkedIn posts crafted individually | AI-generated captions linked to live blog content |
| No systematic engagement strategy | Autonomous feed monitoring and commenting on a 2-hour cycle |
| No feedback loop between content and results | Analytics-driven scoring that improves scheduling decisions over time |
| Paid SaaS tools for scheduling and analytics | Self-contained local system with no per-use cost beyond LLM API calls |

The entire system runs on the local machine. Data never leaves the Phoenix Solutions environment except for the outbound API calls to Groq (LLM inference), LinkedIn (publishing and engagement), and Unsplash (image fetching), all of which are controlled by Phoenix Solutions' own API keys.

---

## 2. System Architecture Overview

The system is composed of six specialised engines, each with its own isolated codebase, worker process, database tables, and REST API router. The engines are chained into a single automation pipeline that runs on a configurable schedule.

```
signal_sources.json
        |
        v
[1. Signal Engine]   — collects & scores raw industry signals
        |
        v
[2. Insight Engine]  — clusters signals into ranked content insights
        |
        v
[3. Content Engine]  — generates blogs and LinkedIn posts from insights
        |
        v
[4. Distribution Engine] — schedules & publishes to website + LinkedIn
        |
        v
[5. Analytics Engine]    — collects LinkedIn & website performance metrics
        |
        v
[6. Feedback Loop]       — updates schedule preferences from performance data
        |
        v
[7. Engagement Engine]   — optional: scans feed, likes, comments (LinkedIn Growth)
```

All six engines share a single SQLite database (`blog_marketing.db`). The FastAPI server (`api/main.py`) exposes every engine via a versioned REST API. A browser-based web dashboard and a legacy Tkinter desktop GUI both connect to this API.

---

## 3. The Eight-Step Automation Pipeline

The pipeline is defined in `automation/pipeline.py` and can be invoked on-demand, on a schedule, or per individual step via the API. Each step is fully isolated — a failure in any single step is logged and the pipeline continues rather than aborting.

### Step 1 — Collect Signals

**Worker:** Signal Engine (`blogpilot/signal_engine/`)
**Default interval:** every 6 hours

The signal collector reads `signal_sources.json`, instantiates the appropriate source adapter for each entry (RSS or Reddit), fetches new articles and posts, deduplicates against already-stored URLs, and persists new records to the `signals` table. The Groq LLM then scores each signal for relevance to Phoenix Solutions' business on a scale of 0.0 to 1.0 using a fast, low-cost model (`llama-3.1-8b-instant`) in batches of 10. Scores are written back to the database immediately.

**Output:** New rows in the `signals` table with `relevance_score` populated.

### Step 2 — Generate Insights

**Worker:** Insight Engine (`blogpilot/insight_engine/`)
**Default interval:** every 12 hours

The insight engine reads signals with status `new` or `processed`, groups them by category and semantic similarity (signal clustering), then calls Groq to synthesise each cluster into a named insight with a summary, confidence score, and a list of recommended action items. Insights are ranked by confidence and freshness. Only insights above the configured confidence threshold are eligible for content generation.

**Output:** New rows in the `insights` table.

### Step 3 — Generate Content

**Worker:** Content Engine (`blogpilot/content_engine/`)
**Default interval:** every 24 hours

The content planner selects approved insights and decides what type of content to generate: a full HTML blog post, a LinkedIn post (blog-linked or standalone), or a comment-style response. It calls the appropriate generator service for each:

- **Blog posts** are generated as structured JSON (title, sections, TOC, metadata) by Groq, then rendered into the `Blogs/_new-post.html` template using bracket-style placeholder replacement (`[TITLE]`, `[CONTENT]`, etc.). Section content and the table of contents are injected via regex markers.
- **LinkedIn posts** are generated in one of two modes: an 80–150 word blog-linked teaser that drives traffic to the published article, or a 300–500 word standalone post with a soft call-to-action pointing to phoenixsolution.in.
- **Images** are fetched from Unsplash using relevant keywords extracted from the blog content if an `UNSPLASH_ACCESS_KEY` is configured. Image fetching is skipped gracefully if no key is present.

**Output:** New rows in the `content` table with `status = draft`. HTML files written to `Blogs/`. Images written to `Blogs/images/`.

### Step 4 — Schedule Distribution

**Orchestrated by:** `automation/pipeline.py`

The distribution planner reads all draft content that does not yet have a queue entry, runs the planning logic for each item (determines which channels to publish to and calculates the optimal time based on historical schedule preferences from the analytics feedback loop), and inserts jobs into the `distribution_queue` table with `status = scheduled` or `queued`.

**Output:** New rows in the `distribution_queue` table.

### Step 5 — Publish Content

**Worker:** Distribution Engine (`blogpilot/distribution_engine/`)
**Default interval:** every 30 minutes

The distribution worker polls the queue for items whose scheduled time is due. For each due item:

- **Blog channel:** copies the HTML and image files into the phoenixsolution website repository, injects a new card at the top of the blog grid on `blog/index.html`, updates the XML sitemap, then executes `git add / commit / push` to deploy the post live.
- **LinkedIn channel:** calls the LinkedIn UGC API (`https://api.linkedin.com/v2/ugcPosts`) to publish the post. If an image is associated, a 2-step image upload process is executed first via `https://api.linkedin.com/rest/images?action=initializeUpload`. The system falls back to text-only if image upload fails (HTTP 426 is handled gracefully).

**Output:** Queue items updated to `status = published`. `external_url` stored on each completed job.

### Step 6 — Collect Analytics

**Worker:** Analytics Engine (`blogpilot/analytics_engine/`)
**Default interval:** every 24 hours

The analytics worker fetches performance metrics for all recently published content from LinkedIn and the website. Metrics collected include impressions, clicks, likes, comments, shares, and a computed engagement score. All data is stored in the `metrics` table.

**Output:** New rows in the `metrics` table. `performance_score` updated on the `content` table.

### Step 7 — Update Feedback Signals

**Service:** `analytics_engine/services/performance_analyzer.py`

The performance analyser examines the collected metrics, identifies which posting hours and days consistently produce higher engagement, and writes updated records to the `schedule_preferences` table. On the next pipeline run, the Distribution Planner reads these preferences to select optimal publication times for new content. This closes the feedback loop between content performance and future scheduling decisions.

**Output:** `schedule_preferences` table updated. Highest-performing topics identified for the Content Planner.

### Step 8 — LinkedIn Engagement (Optional)

**Worker:** Engagement Engine (`blogpilot/engagement_engine/`)
**Default interval:** every 2 hours
**Activation:** requires `ENABLE_ENGAGEMENT=true` in the environment

The engagement worker scans the LinkedIn feed, identifies relevant posts from the target niche, checks tracked influencer profiles for new activity, and executes AI-generated likes and comments. This step is documented in full detail in section 4.6.

**Output:** New rows in `engagement_log`. `influencer_targets.last_checked` updated.

---

## 4. Engine Capabilities — Module Reference

### 4.1 Signal Engine

**Location:** `blogpilot/signal_engine/`

The Signal Engine is the data intake layer of the system. It monitors external content sources continuously to maintain a live feed of industry signals.

#### Source Adapters

| Adapter | Description |
|---|---|
| `sources/rss.py` | Fetches articles from any RSS or Atom feed. Extracts title, URL, and summary. |
| `sources/reddit.py` | Fetches hot posts from configured subreddits via the Reddit API. Extracts title, URL, score, and body text. |

Both adapters implement a standard `.fetch(config)` interface, making it straightforward to add new source types (Twitter/X, Hacker News, industry newsletters) by registering a new adapter class.

#### Signal Collector (`services/collector.py`)

- Reads source definitions from `signal_sources.json`
- Validates each source definition before attempting to fetch
- Loads all known source URLs from the database in a single query to avoid per-signal round-trips
- Deduplicates within a single run as well as against the database
- Persists each new unique signal immediately
- Returns the list of newly inserted `Signal` objects for the scorer

#### Signal Scorer (`services/scorer.py`)

- Uses `llama-3.1-8b-instant` (the fast Groq model) to minimise cost for bulk scoring
- Batches up to 10 signals per API call
- Prompts the model to rate relevance on a 0–10 scale aligned to Phoenix Solutions' business categories: AI, digital marketing, web development, SEO, social media, Indian SMB market
- Normalises scores to 0.0–1.0
- Falls back to a neutral score of 0.5 if the model response cannot be parsed
- Persists scores back to the database immediately via `signal_repo.update_score()`

#### Signal Data Model

| Field | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-increment primary key |
| `source` | TEXT | Source name (e.g., "rss", "reddit") |
| `source_url` | TEXT | Deduplication key |
| `title` | TEXT | Article or post headline |
| `summary` | TEXT | Excerpt or body text |
| `relevance_score` | REAL | 0.0–1.0, assigned by scorer |
| `category` | TEXT | Topic category from source config |
| `status` | TEXT | new / processed / dismissed |

---

### 4.2 Insight Engine

**Location:** `blogpilot/insight_engine/`

The Insight Engine transforms raw signals into actionable content intelligence. It does not generate content — it produces the strategic brief that the Content Engine works from.

#### Signal Clusterer (`services/signal_clusterer.py`)

Groups signals by category and semantic similarity. Each cluster represents a coherent topic area that the market is actively discussing. Clusters are formed from unprocessed signals accumulated since the last insight run.

#### Insight Generator (`services/insight_generator.py`)

For each signal cluster, calls Groq to synthesise:

- A concise insight title suitable for use as a content angle
- A summary paragraph explaining the trend and its relevance to Phoenix Solutions' audience
- A confidence score (0.0–1.0) representing how strongly the signals support the insight
- A list of recommended action items (e.g., "write a comparison article", "create a LinkedIn tip post")

The insight is stored with `status = draft` and the IDs of the contributing signals.

#### Insight Ranker (`services/insight_ranker.py`)

Ranks stored insights by confidence score and recency. The Content Engine reads only insights above the configured confidence threshold (default: 0.5, adjustable via the runtime config API).

#### Insight Data Model

| Field | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-increment primary key |
| `signal_ids` | TEXT | JSON array of contributing signal IDs |
| `title` | TEXT | Insight title / content angle |
| `summary` | TEXT | Synthesised trend summary |
| `category` | TEXT | Topic category |
| `confidence` | REAL | 0.0–1.0 confidence score |
| `action_items` | TEXT | JSON array of recommended content actions |
| `status` | TEXT | draft / approved / dismissed |

---

### 4.3 Content Engine

**Location:** `blogpilot/content_engine/`

The Content Engine is the creative layer. It takes approved insights and produces publication-ready content assets.

#### Content Planner (`services/content_planner.py`)

Selects insights eligible for content generation (above threshold, not already processed). Decides the content type for each insight based on the action_items list. Enforces a configurable maximum number of content items generated per cycle (`content_max_per_cycle`, default: 20) to prevent runaway API usage.

#### Blog Service (`services/blog_service.py`)

Generates a complete blog post for a given topic or insight. The process:

1. Calls Groq with the prompt from `Prompts/blog_prompt.txt`
2. Receives a structured JSON response containing title, slug, meta description, sections (each with h2 heading and body paragraphs), and a list of TOC entries
3. Renders the JSON into the `Blogs/_new-post.html` template by replacing bracket-style placeholders (`[TITLE]`, `[AUTHOR]`, `[DATE]`, `[META_DESCRIPTION]`, etc.)
4. Injects section HTML between the `<!-- ── SECTION 1 ──` and `<!-- ── Closing section` template markers via regex
5. Injects TOC anchor links between the `<!-- Add one link per h2 section -->` markers
6. Saves the rendered file as `Blogs/YYYY-MM-DD-{slug}.html`

#### LinkedIn Service (`services/linkedin_service.py`)

Generates a LinkedIn post in one of two modes:

- **Blog-linked mode** (when blog content exists): 80–150 word teaser that hooks the reader, highlights one key insight, and closes with a link to the published article. Uses `Prompts/Linkedin_prompt.txt` and the approved hashtag list from `Prompts/Hashtags.txt`.
- **Standalone mode** (no blog): 300–500 word self-contained post structured as hook, 3–5 insight paragraphs, and a soft call-to-action to phoenixsolution.in. No external article link.

#### Image Service (`services/image_service.py`)

Fetches a relevant hero image from the Unsplash API using keywords extracted from the blog content. Downloads and saves the image to `Blogs/images/{slug}.jpg`. Returns `None` gracefully if `UNSPLASH_ACCESS_KEY` is not configured, allowing the rest of the pipeline to continue without an image.

#### Comment Service (`services/comment_service.py`)

Generates short-form comment-style content for use in community engagement contexts outside of LinkedIn (future extension point).

#### Content Data Model

| Field | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-increment primary key |
| `insight_id` | INTEGER | Foreign key to insights table |
| `content_type` | TEXT | blog_post / linkedin_post / comment |
| `topic` | TEXT | The topic string used for generation |
| `title` | TEXT | Blog post title |
| `body` | TEXT | Full content body |
| `file_path` | TEXT | Path to saved HTML file |
| `hashtags` | TEXT | Space-separated hashtag string |
| `status` | TEXT | draft / scheduled / published |
| `performance_score` | REAL | Updated by analytics feedback loop |

---

### 4.4 Distribution Engine

**Location:** `blogpilot/distribution_engine/`

The Distribution Engine handles all outbound publishing. It operates on a 30-minute polling cycle to ensure timely delivery of scheduled content.

#### Distribution Planner (`services/distribution_planner.py`)

Determines which channels to publish each content item to and calculates the optimal scheduled time. For blog posts, channels are `website` and optionally `linkedin` (for the linked teaser). For standalone LinkedIn posts, the channel is `linkedin` only. The planner reads the `schedule_preferences` table to select hours with historically high engagement.

#### Blog Publisher Service (`services/blog_publisher_service.py`)

Executes the full website publishing sequence for a blog post:

1. Copies the HTML file from `Blogs/YYYY-MM-DD-{slug}.html` to the phoenixsolution website repository
2. Copies the image from `Blogs/images/{slug}.jpg` to the website's images directory
3. Injects a new blog card at the top of `<div class="blog-grid">` in `blog/index.html`
4. Appends a new `<url>` entry to the XML sitemap (`sitemap.xml`)
5. Executes `git add`, `git commit`, and `git push` to deploy the changes live

The website repository path is configured via `WEBSITE_REPO_PATH` (default: `C:\Projects\phoenixsolution`).

#### LinkedIn Publisher Service (`services/linkedin_publisher_service.py`)

Publishes content to LinkedIn via the official UGC API:

- **Text-only post:** single API call to `POST https://api.linkedin.com/v2/ugcPosts`
- **Post with image:** 2-step process — initialises an upload via `POST https://api.linkedin.com/rest/images?action=initializeUpload`, uploads the image binary, then creates the post referencing the uploaded asset ID
- Supports both personal profile posting (using `LINKEDIN_PERSON_URN`) and company page posting (using `LINKEDIN_ORG_URN`)
- Falls back to text-only if image upload fails
- Requires scopes: `openid profile w_member_social`

#### Distribution Queue Data Model

| Field | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-increment primary key |
| `content_id` | INTEGER | Foreign key to content table |
| `channel` | TEXT | website / linkedin |
| `scheduled_at` | TEXT | ISO 8601 scheduled publish time |
| `published_at` | TEXT | Actual publish timestamp |
| `status` | TEXT | queued / scheduled / published / failed |
| `error_message` | TEXT | Populated on failure |
| `external_url` | TEXT | Live URL after publication |

---

### 4.5 Analytics Engine

**Location:** `blogpilot/analytics_engine/`

The Analytics Engine closes the feedback loop by measuring what was published and feeding performance data back into future scheduling and content decisions.

#### Metrics Collector (`services/metrics_collector.py`)

Fetches performance data for all recently published content:

- **LinkedIn metrics:** impressions, clicks, likes, comments, shares — retrieved via the LinkedIn API for each published post
- **Website metrics:** page views and clicks fetched from website analytics (configurable source)

All metrics are stored in the `metrics` table with a `recorded_at` timestamp, allowing trend analysis over time.

#### Performance Analyser (`services/performance_analyzer.py`)

Examines accumulated metrics to produce two categories of intelligence:

1. **Schedule preferences:** aggregates engagement by hour of day per channel. Identifies which hours consistently produce higher engagement. Writes results to the `schedule_preferences` table. The Distribution Planner reads this table on every planning run to select optimal times.

2. **Content performance scoring:** computes a `performance_score` for each piece of content based on a weighted combination of impressions, engagements, and click-through rate. Updates the score on the `content` table. The highest-scoring topics and content types inform the Content Planner on subsequent cycles.

#### Dashboard Data

The analytics API exposes an aggregated dashboard view containing:
- Total impressions, clicks, engagements, shares across all channels
- Top-performing content items by performance_score
- Per-content metric history

#### Metrics Data Model

| Field | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-increment primary key |
| `content_id` | INTEGER | Foreign key to content table |
| `channel` | TEXT | linkedin / website |
| `impressions` | INTEGER | Total impressions |
| `clicks` | INTEGER | Click-throughs |
| `likes` | INTEGER | LinkedIn reactions |
| `comments` | INTEGER | LinkedIn comments |
| `engagements` | INTEGER | Total engagement actions |
| `shares` | INTEGER | Reposts / shares |
| `engagement_score` | REAL | Computed composite score |

---

### 4.6 LinkedIn Growth Engine (Engagement Engine)

**Location:** `blogpilot/engagement_engine/`
**Activation:** Set `ENABLE_ENGAGEMENT=true` in `.env`

The LinkedIn Growth Engine is an autonomous engagement module that builds Phoenix Solutions' LinkedIn presence by identifying relevant conversations and participating in them through AI-generated, contextually appropriate comments and likes. It operates independently of the content publishing pipeline and runs on a separate 2-hour cycle.

#### Feed Scanner (`services/feed_scanner.py`)

Scrolls the LinkedIn feed using a headless Playwright-controlled Chromium browser session authenticated with stored session cookies (`LINKEDIN_COOKIES_PATH`). For each configured scroll:

- Extracts all visible post cards from the DOM
- Parses post URN (unique identifier), author name, author profile URL, full post text, reaction count, comment count, and share count
- Deduplicates posts by URN across scrolls
- Detects session expiration (redirect to login page) and raises `PlaywrightLoginRequired` for clean error handling

Default scroll depth: 3 scrolls yielding approximately 30 posts per cycle.

A randomised delay of 1.5–5.0 seconds is inserted between scroll actions to mimic natural human browsing behaviour.

#### Influencer Monitor (`services/influencer_monitor.py`)

Maintains a database-backed list of target influencer LinkedIn profiles. For each active influencer:

- Visits their profile's recent activity page (`/recent-activity/shares/`) using the same Playwright session
- Extracts their most recent posts
- Returns these posts with high-priority designation so the engagement strategy gives them preferential treatment
- Records the `last_checked` timestamp to avoid redundant profile visits

Influencer targets are managed via the API (add, list, remove) without requiring any code changes.

#### Relevance Classifier (`services/relevance_classifier.py`)

Calls the Groq API (using `llama-3.1-8b-instant`) to score each post's relevance to Phoenix Solutions' niche on a 0.0–1.0 scale. The niche keyword list is read from `scheduler_config.json` and defaults to `digital marketing, AI automation, LinkedIn growth, content marketing, SaaS`.

The classifier returns:
- `score`: float 0.0–1.0
- `relevant`: boolean (true if score >= threshold)
- `reason`: one-sentence explanation of the scoring rationale

The default relevance threshold is 0.6, configurable via the `ENGAGEMENT_RELEVANCE_THRESHOLD` environment variable.

#### Viral Detector (`services/viral_detector.py`)

Determines whether a post is performing significantly above normal for its author. The detection logic:

- Computes the author's historical average likes and comments from the `engagement_log` table
- Flags a post as viral if likes exceed 3x the author's average, or comments exceed 2x the average
- For authors with fewer than 3 historical records, applies absolute thresholds: 100+ likes or 20+ comments
- Returns a `viral_score` (0.0–1.0) reflecting the degree of above-average performance

Viral posts receive elevated engagement priority regardless of their relevance score.

#### Engagement Strategy (`services/engagement_strategy.py`)

Applies a deterministic decision table to select an action for each post. The rules, in priority order:

| Condition | Action |
|---|---|
| Relevance score < 0.6 | Skip |
| Post already in engagement_log (non-skip) | Skip |
| Daily like limit reached (default: 50) | Skip |
| Influencer post AND daily limits not reached | Like + Comment |
| Viral post AND daily limits not reached | Like + Comment |
| Relevance score >= 0.75 AND daily limits not reached | Like + Comment |
| Relevance score 0.6–0.75 AND likes not at limit | Like only |
| Comment limit reached but likes remaining | Like only (fallback) |

Daily limits are enforced by counting rows in `engagement_log` for the current calendar day. Both the like limit (50) and comment limit (20) are configurable via environment variables `ENGAGEMENT_MAX_LIKES` and `ENGAGEMENT_MAX_COMMENTS`.

#### Comment Generator (`services/comment_generator.py`)

Generates a 2–4 sentence LinkedIn comment for each post selected for the `comment` action. The prompt:

- Uses the full Groq generation model (not the fast model) for quality
- Provides brand context loaded from `Prompts/brand_context.txt` (falls back to a default Phoenix Solutions description)
- Instructs the model to add genuine insight or a thought-provoking perspective
- Explicitly prohibits generic filler phrases, brand mentions within the comment, and hashtags
- Aims for a human, conversational tone that reflects well on the Phoenix Solutions profile

#### Engagement Log Data Model

| Field | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-increment primary key |
| `post_urn` | TEXT | LinkedIn post unique identifier |
| `author_name` | TEXT | Post author display name |
| `post_text` | TEXT | First 500 characters of post content |
| `action` | TEXT | like / comment / skip |
| `comment_text` | TEXT | Generated comment (if applicable) |
| `relevance_score` | REAL | Score from relevance classifier |
| `viral_score` | REAL | Score from viral detector |
| `engaged_at` | TEXT | ISO 8601 timestamp |
| `status` | TEXT | done / error |

#### Influencer Target Data Model

| Field | Type | Description |
|---|---|---|
| `id` | INTEGER | Auto-increment primary key |
| `name` | TEXT | Display name |
| `linkedin_url` | TEXT | Profile URL (unique) |
| `category` | TEXT | e.g., "competitor", "partner", "thought leader" |
| `priority` | INTEGER | 1–5 priority for queue ordering |
| `last_checked` | TEXT | ISO 8601 timestamp of last profile visit |
| `active` | INTEGER | 1 = active, 0 = soft-deleted |

---

## 5. Legacy Pipeline Modules

These modules predate the engine architecture and remain fully operational. They are used by the CLI (`main.py`) and Tkinter GUI and can also be invoked directly.

| Module | Responsibility |
|---|---|
| `llm_client.py` | Groq client singleton — `get_client()`, `get_model()` |
| `paths.py` | `app_dir()` / `resource_dir()` — resolves correct paths in both development and PyInstaller frozen contexts |
| `database.py` | SQLite CRUD for the legacy `posts` table — `init_db`, `insert_post`, `update_post_status`, `get_post_by_id`, `get_scheduled_posts`, `get_all_posts` |
| `tracker.py` | CSV post tracker (`tracker.csv`) — `add_entry`, `update_status`, `get_entry`, `read_all`; used by the smart scheduler |
| `blog_generator.py` | `generate_blog(topic)` — Groq JSON blog generation (legacy interface) |
| `html_renderer.py` | `render_blog()` / `save_blog()` — template rendering and file output |
| `image_fetcher.py` | `fetch_image(keywords, slug)` — Unsplash download |
| `website_publisher.py` | `publish_to_website()` and `git_push_website()` — website deployment |
| `linkedin_generator.py` | `generate_linkedin_post(topic, blog_data)` — dual-mode generation |
| `linkedin_publisher.py` | `publish_post(text, image_path, org_urn)` — LinkedIn UGC API |
| `linkedin_auth.py` | OAuth 2.0 flow — opens browser, captures callback, saves token to `.env` |
| `trend_research.py` | `get_trending_topics()` — Groq-generated topic suggestions |
| `topic_researcher.py` | `run_research()` — Reddit + Groq topics saved to `MarketingSchedule/ResearchTopics.json` |
| `scheduler.py` | APScheduler blocking daily job — publishes scheduled posts from SQLite |
| `smart_scheduler.py` | Thread-based scheduler — scores `tracker.csv` posts across five dimensions (sentiment, hooks, freshness, image presence, length, keywords) and auto-posts the highest-scoring eligible item to LinkedIn |
| `main.py` | CLI entry point |
| `gui.py` | Tkinter desktop GUI |

### Smart Scheduler Scoring System

The smart scheduler selects the best post from `tracker.csv` for automated LinkedIn publishing by scoring each eligible post across five dimensions:

- Sentiment analysis of the LinkedIn post text
- Presence and quality of engagement hooks
- Content freshness (how recently the post was generated)
- Whether a hero image is attached
- Post length and keyword density

The highest-scoring post is published. This ensures automated posts are always the best available content, not simply the oldest.

### CLI Commands

```
python main.py generate [--topic "topic text"] [--publish]
python main.py publish  [--id N]
python main.py schedule [--list]
python main.py schedule [--set-id N --status draft|scheduled|posted]
python main.py schedule [--hour H] [--minute M]
```

---

## 6. User Interfaces

### Web Dashboard (Browser GUI)

**Location:** `api/web_gui.py` and `api/static/index.html`
**URL:** `http://localhost:8000/` (or `http://127.0.0.1:8000/`)

The web dashboard is a single-page application served directly by the FastAPI server. It is accessible from any browser on the same machine (or network, with appropriate firewall configuration). No installation is required — the dashboard loads automatically when the API server starts.

**Capabilities available through the web dashboard:**

- View real-time system status (last pipeline run, counts per step)
- Start, stop, and restart individual engine workers with custom intervals
- Trigger the full pipeline immediately (all steps or a selected subset)
- Trigger individual engine collection cycles on-demand
- Browse database tables (signals, insights, content, distribution_queue, metrics)
- View and edit content items (body, hashtags, status)
- View distribution queue with per-item status and external URLs
- View analytics dashboard with aggregate performance metrics
- View top-performing content ranked by performance score
- Manage signal sources (add, remove, view count)
- Update runtime configuration (confidence threshold, max content per cycle, active Groq model)
- View engagement log, engagement statistics, and viral post detections
- Manage influencer target list (add, view, remove)
- Trigger individual engagement cycles on-demand
- View the LinkedIn feed scan preview (without executing engagement actions)

### Desktop GUI (Tkinter)

**Location:** `gui.py`
**Executable:** `dist/PhoenixMarketing/PhoenixMarketing.exe`

The Tkinter desktop application provides a native Windows interface for users who prefer not to use a browser. It communicates with the same FastAPI backend and exposes equivalent functionality. The desktop GUI is the recommended interface for users running the system in fully offline or restricted network environments.

---

## 7. REST API Reference

The FastAPI server exposes interactive API documentation at `http://localhost:8000/docs` (Swagger UI). All endpoints are grouped by tag.

### System Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check — returns version and status |
| `GET` | `/api/system/status` | Last pipeline run summary with step counts and elapsed time |
| `GET` | `/api/system/workers` | Running state and current interval for all 5 core workers |
| `POST` | `/api/system/workers/{engine}/stop` | Stop a named engine worker |
| `POST` | `/api/system/workers/{engine}/start` | Start a named engine worker at current interval |
| `POST` | `/api/system/workers/{engine}/restart` | Restart with a new `interval_hours` or `interval_minutes` |
| `GET` | `/api/system/config` | Read runtime configuration and signal source count |
| `POST` | `/api/system/config` | Update confidence threshold, max content per cycle, or active model |
| `GET` | `/api/sources` | List configured signal sources |
| `POST` | `/api/sources` | Replace the full signal sources configuration |
| `GET` | `/api/db/browse` | Browse any allowed database table (limit, filter by table name) |
| `POST` | `/api/pipeline/run` | Run all or selected pipeline steps, with optional dry-run mode |

Valid engine names for worker control: `signal`, `insight`, `content`, `distribution`, `analytics`, `engagement`.

### Signal Engine Endpoints (`/api/signals`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/signals` | List signals (filter by status, limit up to 500) |
| `GET` | `/api/signals/{id}` | Retrieve a single signal by ID |
| `GET` | `/api/signals/worker` | Worker running state |
| `POST` | `/api/signals/collect` | Trigger immediate signal collection and optional scoring |

### Insight Engine Endpoints (`/api/insights`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/insights` | List insights (filter by status, limit up to 200) |
| `GET` | `/api/insights/{id}` | Retrieve a single insight by ID |
| `GET` | `/api/insights/worker` | Worker running state |
| `POST` | `/api/insights/generate` | Trigger immediate insight generation cycle |

### Content Engine Endpoints (`/api/content`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/content` | List content items (filter by status, type, limit up to 200) |
| `GET` | `/api/content/{id}` | Retrieve a single content item |
| `GET` | `/api/content/worker` | Worker running state |
| `POST` | `/api/content/generate` | Generate content from eligible insights, or for a specific topic/type |
| `PUT` | `/api/content/{id}` | Edit content body, hashtags, or status |

### Distribution Engine Endpoints (`/api/distribution`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/distribution/distribute` | Queue a content item for publishing (planner selects channel and time) |
| `GET` | `/api/distribution/queue` | List queue items (filter by status, channel, limit up to 200) |
| `POST` | `/api/distribution/schedule` | Reschedule an existing queue item to a new time |
| `POST` | `/api/distribution/run` | Trigger an immediate distribution cycle |
| `GET` | `/api/distribution/worker` | Worker running state |

### Analytics Engine Endpoints (`/api/analytics`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/analytics/dashboard` | Aggregated performance data for all channels |
| `GET` | `/api/analytics/content/{id}` | All metric records for a specific content item |
| `GET` | `/api/analytics/top-content` | Top N content items ranked by performance score |
| `POST` | `/api/analytics/collect` | Trigger immediate metrics collection and performance analysis |
| `GET` | `/api/analytics/worker` | Worker running state |

### Engagement Engine Endpoints (`/api/engagement`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/engagement/worker` | Worker running state and current interval |
| `POST` | `/api/engagement/run` | Trigger one full engagement cycle immediately |
| `GET` | `/api/engagement/feed` | Scan LinkedIn feed and return extracted posts (no engagement action taken) |
| `GET` | `/api/engagement/log` | List engagement log entries (filter by status, limit) |
| `GET` | `/api/engagement/stats` | Cumulative and today's engagement stats (likes, comments, rate) |
| `GET` | `/api/engagement/viral` | Posts detected as viral in the last N days |
| `GET` | `/api/engagement/influencers` | List all active influencer targets |
| `POST` | `/api/engagement/influencers` | Add a new influencer target (name, URL, category, priority) |
| `DELETE` | `/api/engagement/influencers/{id}` | Soft-delete an influencer target |

---

## 8. Configuration and Customisation

### Environment Variables (`.env` file)

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | LLM API key for all generation and classification |
| `GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Primary model for content generation |
| `GROQ_MODEL_FAST` | No | `llama-3.1-8b-instant` | Fast model for scoring and classification |
| `UNSPLASH_ACCESS_KEY` | No | — | Image fetching (skipped if absent) |
| `LINKEDIN_ACCESS_TOKEN` | Yes | — | Bearer token for LinkedIn UGC API |
| `LINKEDIN_PERSON_URN` | No | — | Resolved via `/userinfo` if absent |
| `LINKEDIN_ORG_URN` | No | — | Company page posting (optional) |
| `LINKEDIN_CLIENT_ID` | No | — | Required for OAuth flow (`linkedin_auth.py`) |
| `LINKEDIN_CLIENT_SECRET` | No | — | Required for OAuth flow |
| `LINKEDIN_COOKIES_PATH` | No | `linkedin_session.json` | Path to stored session cookies for Playwright |
| `WEBSITE_REPO_PATH` | No | `C:\Projects\phoenixsolution` | Local path to the website Git repository |
| `ENABLE_ENGAGEMENT` | No | `false` | Set to `true` to activate the Engagement Engine |
| `ENGAGEMENT_RELEVANCE_THRESHOLD` | No | `0.6` | Minimum relevance score for engagement |
| `ENGAGEMENT_MAX_LIKES` | No | `50` | Daily like cap for the engagement worker |
| `ENGAGEMENT_MAX_COMMENTS` | No | `20` | Daily comment cap for the engagement worker |
| `API_HOST` | No | `127.0.0.1` | API server bind address |
| `API_PORT` | No | `8000` | API server port |

### Runtime Configuration (`runtime_config.json`)

The following settings can be changed without restarting the server via `POST /api/system/config`:

| Setting | Default | Description |
|---|---|---|
| `content_confidence_threshold` | `0.5` | Minimum insight confidence for content generation |
| `content_max_per_cycle` | `20` | Maximum content items generated per cycle |
| `groq_model` | `llama-3.3-70b-versatile` | Active generation model (overrides env var) |

### Signal Sources Configuration (`signal_sources.json`)

Defines which RSS feeds and subreddits to monitor. Each entry specifies:

```json
{
  "sources": [
    {
      "type": "rss",
      "url": "https://example.com/feed.xml",
      "category": "ai_marketing"
    },
    {
      "type": "reddit",
      "subreddit": "digitalmarketing",
      "category": "social_media"
    }
  ]
}
```

The full sources list can be updated at runtime via `POST /api/sources` without restarting any worker.

### Prompt Customisation

All LLM prompts are plain text files and can be edited without touching code:

| File | Purpose |
|---|---|
| `Prompts/blog_prompt.txt` | Blog generation prompt |
| `Prompts/Linkedin_prompt.txt` | LinkedIn blog-linked post prompt |
| `Prompts/Hashtags.txt` | Approved hashtag list (one per line) |
| `Prompts/brand_context.txt` | Brand context for engagement comment generator |

### Scheduler Configuration (`scheduler_config.json`)

Controls the legacy smart scheduler and the relevance classifier's niche keywords:

| Field | Description |
|---|---|
| `slots` | Number of LinkedIn posts to schedule per day |
| `days` | Days of the week to post |
| `mode` | Scheduling mode (`auto` or `manual`) |
| `dry_run` | If true, simulates actions without posting |
| `niche_keywords` | List of keywords for the relevance classifier |

### Worker Interval Customisation

All worker intervals can be changed at runtime via the API without a restart:

```
POST /api/system/workers/signal/restart      {"interval_hours": 4}
POST /api/system/workers/distribution/restart {"interval_minutes": 15}
POST /api/system/workers/engagement/restart  {"interval_hours": 3}
```

---

## 9. Database Schema

All data is stored in a single SQLite file: `blog_marketing.db`. The schema is managed by an idempotent migration runner (`blogpilot/db/migrations.py`) that applies versioned migrations on startup.

### Migration History

| Version | Tables added / modified |
|---|---|
| 1 | `schema_version`, `signals`, `insights`, `content`, `distribution_queue`, `metrics` |
| 2 | Extended `metrics` with `likes`, `comments`, `engagement_score`, `raw_payload`; extended `content` with `performance_score`; added `schedule_preferences` |
| 3 | Added `engagement_log`, `influencer_targets` |

### Allowed Tables for Database Browser (`/api/db/browse`)

`signals`, `insights`, `content`, `distribution_queue`, `metrics`, `posts`, `schema_version`, `schedule_preferences`

### Legacy `posts` Table (created by `database.py`)

| Field | Description |
|---|---|
| `id` | Auto-increment primary key |
| `topic` | Blog topic |
| `blog_path` | Path to generated HTML file |
| `linkedin_text` | Generated LinkedIn post text |
| `hashtags` | Hashtag string |
| `status` | draft / scheduled / posted |
| `publish_date` | Scheduled publication date |
| `created_at` | Record creation timestamp |

---

## 10. Packaging and Deployment

### PyInstaller Windows Executable

The system is packaged as a standalone Windows EXE using PyInstaller. The executable bundles the Python runtime, all dependencies, and all static assets. No Python installation is required on the target machine.

**Build output:** `dist/PhoenixMarketing/PhoenixMarketing.exe`

**Bundled assets:**
- `Blogs/_new-post.html` — blog HTML template
- `Prompts/*.txt` — all prompt and hashtag files
- `MarketingSchedule/*.json` — topic research output
- `api/static/*` — web dashboard static files

The `paths.py` module provides a `PyInstaller`-aware resolver that correctly locates bundled resources whether running from source or from the frozen EXE:

- `app_dir()` — returns the writable runtime directory (user data, database, logs)
- `resource_dir()` — returns the directory containing bundled read-only assets

### Python Package (development / server deployment)

The project is structured as an installable Python package via `pyproject.toml`:

```
name = "phoenix-marketing-engine"
version = "1.0.0"
requires-python = ">=3.11"
```

**Registered entry points:**
- `phoenix-gui` — launches the Tkinter desktop GUI
- `phoenix-api` — starts the FastAPI server

**Included packages:** `blogpilot`, `api`, `automation`

### Starting the API Server

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

On startup, the server:
1. Initialises the legacy `posts` table via `database.init_db()`
2. Runs all pending database migrations via `blogpilot.db.migrations.run_migrations()`
3. Starts the Signal worker (every 6 hours)
4. Starts the Insight worker (every 12 hours)
5. Starts the Content worker (every 24 hours)
6. Starts the Distribution worker (every 30 minutes)
7. Starts the Analytics worker (every 24 hours)
8. Starts the Engagement worker (every 2 hours) if `ENABLE_ENGAGEMENT=true`

On shutdown, all workers are stopped gracefully.

### Running the Pipeline Standalone

The pipeline can be run without the API server:

```bash
python automation/pipeline.py                          # single run
python automation/pipeline.py --schedule               # recurring (every 24h)
python automation/pipeline.py --interval 6 --schedule  # recurring (every 6h)
python automation/pipeline.py --dry-run                # log steps, no execution
```

---

## 11. Technical Specifications

| Specification | Detail |
|---|---|
| **Language** | Python 3.11+ |
| **LLM Provider** | Groq |
| **Primary generation model** | `llama-3.3-70b-versatile` (configurable) |
| **Fast classification model** | `llama-3.1-8b-instant` |
| **Database** | SQLite 3 (via `sqlite3` stdlib) |
| **Database file** | `blog_marketing.db` |
| **API framework** | FastAPI 0.111+ |
| **API server** | Uvicorn (with standard extras) |
| **Task scheduling** | APScheduler 3.10+ |
| **Browser automation** | Playwright (Chromium) |
| **Feed parsing** | feedparser 6.0+ |
| **Data validation** | Pydantic v2 |
| **HTTP client** | requests 2.31+ |
| **Environment management** | python-dotenv |
| **LinkedIn API** | v2 UGC Posts + REST Images |
| **LinkedIn required scopes** | `openid profile w_member_social` |
| **Image source** | Unsplash API |
| **Website deployment** | Git (add / commit / push via subprocess) |
| **Desktop GUI** | Tkinter (stdlib) |
| **Packaging** | PyInstaller (Windows EXE) |
| **Package build** | setuptools 68+ / wheel |
| **CORS** | Enabled for `localhost:3000` and `127.0.0.1:3000` |
| **Log file** | `blog_marketing.log` |
| **Schema migration** | Versioned, idempotent, append-only |
| **Data residency** | All data stored locally; API calls only to Groq, LinkedIn, Unsplash |

### Worker Schedule Summary

| Worker | Default Interval | Rationale |
|---|---|---|
| Signal | Every 6 hours | Frequent enough to capture breaking trends |
| Insight | Every 12 hours | Runs after signals have accumulated |
| Content | Every 24 hours | One generation cycle per day prevents API overuse |
| Distribution | Every 30 minutes | Ensures timely delivery of scheduled posts |
| Analytics | Every 24 hours | Metrics stabilise within 24 hours of publication |
| Engagement | Every 2 hours | Maintains active presence across the LinkedIn day |

---

## 12. What to Expect — Realistic Outcomes and KPIs

### Content Volume

Under default configuration (one content cycle per 24 hours, confidence threshold 0.5, max 20 items per cycle), the system can produce:

| Output type | Expected volume |
|---|---|
| Blog posts generated | 3–7 per week (driven by insight confidence) |
| LinkedIn blog-linked posts | 1 per blog post published |
| Standalone LinkedIn posts | 2–5 per week (when insights are available) |
| Signal records collected | 50–200 per week depending on source configuration |
| Insights synthesised | 10–30 per week |

Actual volume depends entirely on the number and quality of configured signal sources, the pace of industry activity, and the confidence threshold setting.

### LinkedIn Engagement (Engagement Engine)

At default settings (50 likes and 20 comments per day, 2-hour cycle):

| Metric | Expected daily output |
|---|---|
| LinkedIn feed posts scanned | 60–120 |
| Posts engaged (liked or commented) | Up to 50 |
| AI-generated comments posted | Up to 20 |
| Influencer profiles checked | All active targets (visited once per cycle) |

The quality of comments is bounded by the Groq model quality. Comments are generated to be substantive and topically relevant. No comment will be posted unless the post clears the 0.6 relevance threshold and the daily cap has not been reached.

### Performance Feedback Loop

The analytics feedback loop improves scheduling precision over time. After approximately 4–6 weeks of operation with consistent daily publishing:

- The `schedule_preferences` table will contain statistically meaningful hour-of-day engagement data
- The Distribution Planner will begin selecting posting times that reflect the actual engagement patterns of the Phoenix Solutions audience
- The Content Planner will begin weighting topic categories that have historically produced high-performing content

### What the system does not do

- It does not guarantee specific engagement rates, follower growth, or lead generation outcomes
- It does not replace human review of generated content before publication (though publication can be configured to require manual approval by setting content to `draft` status and using the web dashboard to approve and queue items individually)
- It does not generate images from scratch — it downloads matching photographs from Unsplash
- The Engagement Engine's browser actions are dependent on LinkedIn's DOM structure remaining stable; changes to LinkedIn's front-end may require selector updates
- LinkedIn API rate limits apply to all publishing and metrics collection operations; the system does not circumvent platform limits

### Recommended Initial Setup

1. Configure 5–10 RSS sources and 2–3 subreddits in `signal_sources.json` covering the target topic areas
2. Set `GROQ_API_KEY`, `LINKEDIN_ACCESS_TOKEN`, and `WEBSITE_REPO_PATH` in `.env`
3. Start the API server and allow one full 24-hour pipeline cycle to complete
4. Review generated insights and content in the web dashboard before enabling automated publishing
5. Enable `ENABLE_ENGAGEMENT=true` and add influencer targets after the core pipeline is operating stably
6. Revisit `runtime_config.json` thresholds after two weeks of data collection to tune quality vs. volume

---

*This document covers Phoenix Marketing Intelligence Engine version 1.0.0. All module locations, API paths, and configuration keys reflect the codebase as of the document date.*
