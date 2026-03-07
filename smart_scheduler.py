"""
smart_scheduler.py — Intelligent auto-posting scheduler.

Scores all draft/scheduled posts using multiple marketing signals,
selects the highest-scoring post for each time slot, and publishes
automatically via LinkedIn API.

Scoring model (100 pts total):
  25 pts — Sentiment quality   (Groq rates tone: inspiring/authoritative/positive)
  20 pts — Engagement hooks    (questions, lists, stats, CTAs detected)
  15 pts — Keyword relevance   (hashtag quality + keyword density)
  15 pts — Freshness           (newer generated posts rank higher)
  15 pts — Optimal length      (LinkedIn sweet spot: 900-1500 chars)
  10 pts — Has image           (image posts get full bonus)
"""

import os
import re
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Callable

# Scoring uses the small fast model to avoid burning the TPM quota
_SCORE_MODEL = 'llama-3.1-8b-instant'
# Minimum seconds to wait between consecutive Groq scoring calls
_SCORE_DELAY = 1.5

from dotenv import load_dotenv

from paths import app_dir

load_dotenv(os.path.join(app_dir(), '.env'), override=True)

logger = logging.getLogger(__name__)

# ── Scheduler state file ───────────────────────────────────────────────────
SCHED_CONFIG_PATH = os.path.join(app_dir(), 'scheduler_config.json')

DEFAULT_CONFIG = {
    'enabled':      False,
    'slots':        ['09:00', '17:00'],   # HH:MM 24h slots
    'mode':         'auto',               # 'auto' | 'manual'
    'manual_id':    None,                 # tracker ID when mode=manual
    'post_target':  'personal',           # always personal (company posting disabled)
    'dry_run':      False,
    'days':         ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
    'last_posted':  None,
    'day_content_type': {                 # per-day content type
        'Mon': 'blog_and_li',
        'Tue': 'li_only',
        'Wed': 'blog_and_li',
        'Thu': 'li_only',
        'Fri': 'li_only',
        'Sat': 'li_only',
        'Sun': 'li_only',
    },
}

_scheduler_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_pause_event = threading.Event()          # set = paused


# ══════════════════════════════════════════════════════════════════════════════
# Config persistence
# ══════════════════════════════════════════════════════════════════════════════

def load_config() -> dict:
    try:
        with open(SCHED_CONFIG_PATH, encoding='utf-8') as f:
            cfg = json.load(f)
        # Fill any missing keys with defaults
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    with open(SCHED_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
# Scoring engine
# ══════════════════════════════════════════════════════════════════════════════

def _score_length(text: str) -> float:
    """15 pts: peaks at 900-1500 chars, falls off outside that range."""
    n = len(text)
    if 900 <= n <= 1500:
        return 15.0
    elif n < 900:
        return max(0.0, 15.0 * (n / 900))
    else:                                    # > 1500
        return max(0.0, 15.0 * (1 - (n - 1500) / 2000))


def _score_hooks(text: str) -> float:
    """20 pts: count engagement signals."""
    score = 0.0
    if re.search(r'\?', text):                               score += 5   # question
    if re.search(r'\b(you|your|you\'re)\b', text, re.I):    score += 3   # direct address
    if re.search(r'^\s*[\u2022\-\*\d+\.]', text, re.M):     score += 4   # list/bullet
    if re.search(r'\b\d+[\%x]\b|\b\d{2,}\b', text):         score += 3   # stats/numbers
    if re.search(r'\b(comment|share|follow|tag|click|dm)\b', text, re.I): score += 3  # CTA
    if re.search(r'[\U0001F300-\U0001FFFF]', text):          score += 2   # emoji
    return min(score, 20.0)


def _score_keywords(hashtags: str) -> float:
    """15 pts: good hashtag coverage (4-8 hashtags is optimal)."""
    tags = re.findall(r'#\w+', hashtags)
    n = len(tags)
    if 4 <= n <= 8:
        return 15.0
    elif n < 4:
        return max(0.0, 15.0 * n / 4)
    else:
        return max(5.0, 15.0 - (n - 8) * 1.5)


def _score_freshness(generated_date: str) -> float:
    """15 pts: posts generated in last 7 days score full points."""
    try:
        d = datetime.strptime(generated_date[:10], '%Y-%m-%d')
        age_days = (datetime.now() - d).days
        return max(0.0, 15.0 * (1 - age_days / 30))
    except Exception:
        return 7.5


def _score_image(blog_path: str) -> float:
    """10 pts: check if a matching image exists next to the blog."""
    if not blog_path:
        return 0.0
    slug = os.path.basename(blog_path).replace('.html', '')
    parts = slug.split('-')
    slug_part = '-'.join(parts[3:]) if len(parts) > 3 else slug
    img = os.path.join(app_dir(), 'Blogs', 'images', slug_part + '.jpg')
    return 10.0 if os.path.exists(img) else 0.0


def _score_sentiment_groq(caption: str) -> float:
    """
    25 pts: ask Groq to rate the post's marketing sentiment.
    Uses the small 8b model to conserve TPM quota.
    Returns 0-25. Falls back to 12.5 on error.
    """
    try:
        from llm_client import get_client
        client = get_client()
        prompt = (
            'Rate this LinkedIn post caption 0-100 for marketing quality '
            '(authoritative tone, value delivery, professional appeal). '
            'Reply with ONLY the integer score.\n\nCAPTION:\n' + caption[:600]
        )
        resp = client.chat.completions.create(
            model=_SCORE_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=5,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        groq_score = min(100, max(0, int(re.sub(r'\D', '', raw) or '50')))
        return round(groq_score / 100 * 25, 1)
    except Exception as exc:
        logger.warning('Sentiment scoring failed (using neutral): %s', exc)
        return 12.5


def score_post(row: dict, use_ai: bool = True) -> dict:
    """
    Score a single tracker row. Returns row + score breakdown dict.
    Set use_ai=False to skip the Groq sentiment call (faster, offline scoring).
    """
    # Load the LinkedIn text from the saved TXT file
    caption = ''
    hashtags = row.get('hashtags', '')
    li_path  = row.get('linkedin_path', '')
    if li_path and os.path.exists(li_path):
        try:
            with open(li_path, encoding='utf-8') as f:
                content = f.read()
            parts = content.split('=' * 60)
            post  = parts[-1].strip() if len(parts) > 1 else content
            lines = post.splitlines()
            body_lines = [l for l in lines
                          if not l.startswith('#')
                          and not l.startswith('Read the full article:')]
            caption = '\n'.join(body_lines).strip()
        except Exception:
            caption = row.get('topic', '')
    else:
        caption = row.get('topic', '')

    full_text = caption + '\n\n' + hashtags

    s_sentiment  = _score_sentiment_groq(caption) if use_ai else 12.5
    s_hooks      = _score_hooks(full_text)
    s_keywords   = _score_keywords(hashtags)
    s_freshness  = _score_freshness(row.get('generated_date', ''))
    s_length     = _score_length(full_text)
    s_image      = _score_image(row.get('blog_path', ''))
    total        = s_sentiment + s_hooks + s_keywords + s_freshness + s_length + s_image

    return {
        **row,
        'score':         round(total, 1),
        's_sentiment':   s_sentiment,
        's_hooks':       s_hooks,
        's_keywords':    s_keywords,
        's_freshness':   s_freshness,
        's_length':      s_length,
        's_image':       s_image,
        '_caption':      caption,
    }


def score_all_pending(use_ai: bool = True, cancel_event=None) -> List[dict]:
    """
    Load all draft/scheduled tracker rows, score each one, return sorted list.
    If cancel_event is provided and gets set, scoring stops early and returns
    whatever has been scored so far.
    """
    from tracker import read_all
    rows = [r for r in read_all() if r.get('status') in ('draft', 'scheduled')]
    if not rows:
        return []
    scored = []
    for i, r in enumerate(rows):
        if cancel_event and cancel_event.is_set():
            break
        scored.append(score_post(r, use_ai=use_ai))
        if use_ai and i < len(rows) - 1:
            time.sleep(_SCORE_DELAY)
    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored


def pick_best(use_ai: bool = True, content_type: str = 'li_only') -> Optional[dict]:
    """Return the highest-scoring pending post, filtered by content_type.

    content_type:
        'li_only'     — posts with linkedin_path (any post qualifies)
        'blog_and_li' — posts that have both blog_path AND linkedin_path
    """
    scored = score_all_pending(use_ai=use_ai)
    if content_type == 'blog_and_li':
        scored = [s for s in scored if s.get('blog_path')]
    return scored[0] if scored else None


# ══════════════════════════════════════════════════════════════════════════════
# Posting action
# ══════════════════════════════════════════════════════════════════════════════

def _do_post(row: dict, cfg: dict, on_log: Optional[Callable] = None):
    """Execute the actual LinkedIn post for a given tracker row."""
    def log(msg, lvl='info'):
        logger.info(msg) if lvl == 'info' else logger.warning(msg)
        if on_log:
            on_log(msg, lvl)

    caption    = row.get('_caption') or row.get('topic', '')
    hashtags   = row.get('hashtags', '')
    blog_url   = row.get('website_url', '') or 'https://www.phoenixsolution.in'
    blog_path  = row.get('blog_path', '')
    post_id    = int(row['id'])

    # Build full post text
    parts = [caption]
    if blog_url:
        parts.append('Read the full article: ' + blog_url)
    if hashtags:
        parts.append(hashtags)
    li_text = '\n\n'.join(parts)

    # Image
    slug = os.path.basename(blog_path).replace('.html', '')
    slug_part = '-'.join(slug.split('-')[3:]) if len(slug.split('-')) > 3 else slug
    image_path = os.path.join(app_dir(), 'Blogs', 'images', slug_part + '.jpg')
    image_path = image_path if os.path.exists(image_path) else None

    org_urn = None  # company posting disabled — personal profile only

    if cfg.get('dry_run'):
        log('[DRY RUN] Would post Tracker #{}: "{}" — score {}'.format(
            post_id, row.get('topic', '')[:60], row.get('score', '?')))
        return

    log('Auto-posting Tracker #{} — "{}" (score: {})'.format(
        post_id, row.get('topic', '')[:60], row.get('score', '?')))

    from linkedin_publisher import publish_post
    publish_post(li_text, image_path=image_path, org_urn=org_urn)

    # Update tracker
    from tracker import update_status
    pub_date = datetime.now().strftime('%Y-%m-%d %H:%M')
    update_status(post_id, 'posted', pub_date)
    log('Tracker #{} marked as posted.'.format(post_id))


# ══════════════════════════════════════════════════════════════════════════════
# Scheduler loop
# ══════════════════════════════════════════════════════════════════════════════

def _next_fire_times(cfg: dict) -> List[datetime]:
    """Return list of upcoming datetime objects for configured slots today/tomorrow."""
    day_map = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
    active_days = {day_map[d] for d in cfg.get('days', []) if d in day_map}
    slots = cfg.get('slots', [])
    now   = datetime.now()
    fires = []
    for offset in range(8):                              # look ahead up to 8 days
        candidate = now + timedelta(days=offset)
        if candidate.weekday() not in active_days:
            continue
        for slot in slots:
            try:
                h, m = map(int, slot.split(':'))
                dt = candidate.replace(hour=h, minute=m, second=0, microsecond=0)
                if dt > now:
                    fires.append(dt)
            except Exception:
                pass
    fires.sort()
    return fires


def get_next_fire(cfg: dict) -> Optional[datetime]:
    fires = _next_fire_times(cfg)
    return fires[0] if fires else None


def _scheduler_loop(on_log: Optional[Callable] = None,
                    on_status_change: Optional[Callable] = None):
    """Background thread: sleep until next slot, then fire."""
    def log(msg, lvl='info'):
        logger.info(msg) if lvl == 'info' else logger.warning(msg)
        if on_log:
            on_log(msg, lvl)

    day_names = {0: 'Mon', 1: 'Tue', 2: 'Wed', 3: 'Thu', 4: 'Fri', 5: 'Sat', 6: 'Sun'}

    log('Scheduler started.')
    while not _stop_event.is_set():
        # ── Handle pause ────────────────────────────────────────────────
        if _pause_event.is_set():
            log('Scheduler paused.')
            if on_status_change:
                on_status_change('paused', None)
            while _pause_event.is_set() and not _stop_event.is_set():
                _stop_event.wait(5)
            if _stop_event.is_set():
                break
            log('Scheduler resumed.')
            if on_status_change:
                on_status_change('resumed', None)

        cfg  = load_config()
        if not cfg.get('enabled'):
            log('Scheduler disabled — stopping.')
            break

        next_dt = get_next_fire(cfg)
        if not next_dt:
            log('No upcoming slots found — stopping scheduler.', 'warning')
            break

        log('Next auto-post: {}'.format(next_dt.strftime('%a %d %b %Y  %H:%M')))
        if on_status_change:
            on_status_change('next', next_dt)

        # Sleep in 30-second increments so we can detect stop/config/pause changes
        while not _stop_event.is_set() and not _pause_event.is_set():
            remaining = (next_dt - datetime.now()).total_seconds()
            if remaining <= 0:
                break
            _stop_event.wait(min(30, remaining))

        if _stop_event.is_set() or _pause_event.is_set():
            continue  # re-enter loop top to handle pause or stop

        # Fire!
        cfg = load_config()                              # reload in case changed
        if not cfg.get('enabled'):
            break

        # Determine content type for today
        day_types = cfg.get('day_content_type', {})
        today_name = day_names.get(datetime.now().weekday(), 'Mon')
        content_type = day_types.get(today_name, 'li_only')

        try:
            if cfg.get('mode') == 'manual' and cfg.get('manual_id'):
                from tracker import get_entry
                row = get_entry(int(cfg['manual_id']))
                if row:
                    row = score_post(row, use_ai=False)
                    _do_post(row, cfg, on_log)
                else:
                    log('Manual post ID {} not found.'.format(cfg['manual_id']), 'warning')
            else:
                best = pick_best(use_ai=True, content_type=content_type)
                if best:
                    _do_post(best, cfg, on_log)
                else:
                    log('No pending posts to publish — skipping slot.', 'warning')
        except Exception as exc:
            log('Auto-post failed: {}'.format(exc), 'warning')

        if on_status_change:
            on_status_change('fired', datetime.now())

        # Brief pause to avoid double-firing in the same minute
        _stop_event.wait(90)

    log('Scheduler stopped.')
    if on_status_change:
        on_status_change('stopped', None)


# ══════════════════════════════════════════════════════════════════════════════
# Public start / stop
# ══════════════════════════════════════════════════════════════════════════════

def start_scheduler(on_log=None, on_status_change=None):
    global _scheduler_thread, _stop_event, _pause_event
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    _stop_event = threading.Event()
    _pause_event = threading.Event()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        args=(on_log, on_status_change),
        daemon=True,
        name='PhoenixScheduler',
    )
    _scheduler_thread.start()


def stop_scheduler():
    global _stop_event, _pause_event
    _pause_event.clear()
    _stop_event.set()


def pause_scheduler():
    """Pause the scheduler — thread stays alive but skips firing."""
    _pause_event.set()


def resume_scheduler():
    """Resume a paused scheduler."""
    _pause_event.clear()


def is_running() -> bool:
    return bool(_scheduler_thread and _scheduler_thread.is_alive())


def is_paused() -> bool:
    return _pause_event.is_set() and is_running()
