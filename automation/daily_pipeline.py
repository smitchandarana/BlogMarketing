"""
daily_pipeline.py — The primary daily content automation workflow.

One call drives the full Research → Generate → Publish pipeline:

    from automation.daily_pipeline import run

    run()                               # auto-pick topic, full publish
    run(topic="Power BI dashboards")    # specific topic
    run(content_types=["li_only"])      # standalone LinkedIn only
    run(dry_run=True)                   # generate but don't push/post

Steps (blog_and_linkedin mode):
  1. Research topics — refresh if cache older than 24 h
  2. Pick best unused topic from research (or use provided topic)
  3. Generate blog post via Groq (blog_generator)
  4. Render HTML and save to Blogs/ (html_renderer)
  5. Fetch Unsplash hero image (image_fetcher)
  6. Publish blog to phoenixsolution website + git push (website_publisher)
  7. Generate LinkedIn teaser post linked to the blog (linkedin_generator)
  8. Publish LinkedIn post via UGC API (linkedin_publisher)
  9. Log to tracker.csv + blog_marketing.db

Steps (li_only mode):
  1. Research topics — same refresh logic
  2. Pick best unused topic
  3. Generate standalone LinkedIn post (300-500 words, no blog link)
  4. Publish LinkedIn post
  5. Log to tracker.csv + blog_marketing.db
"""

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Callable

logger = logging.getLogger(__name__)

# ── Ensure root-level modules are importable ──────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ═════════════════════════════════════════════════════════════════════════════
# Topic picking
# ═════════════════════════════════════════════════════════════════════════════

def _slugify(text: str) -> str:
    """Simple slug — lowercase, replace non-alnum with hyphens."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')[:60]


def _load_used_slugs() -> set[str]:
    """Return set of topic slugs already in tracker.csv."""
    try:
        from tracker import read_all
        rows = read_all()
        used: set[str] = set()
        for r in rows:
            topic = r.get('topic', '')
            if topic:
                used.add(_slugify(topic))
            # Also check via blog_path filename
            bp = r.get('blog_path', '')
            if bp:
                base = os.path.basename(bp).replace('.html', '')
                parts = base.split('-')
                if len(parts) > 3:
                    used.add('-'.join(parts[3:]))
        return used
    except Exception as exc:
        logger.warning('Could not load tracker slugs: %s', exc)
        return set()


def _research_is_fresh(max_age_hours: int = 24) -> bool:
    """Return True if ResearchTopics.json was updated within max_age_hours."""
    try:
        from topic_researcher import get_last_run_date
        last_run = get_last_run_date()
        if not last_run:
            return False
        last_dt = datetime.strptime(last_run[:16], '%Y-%m-%d %H:%M')
        return datetime.now() - last_dt < timedelta(hours=max_age_hours)
    except Exception:
        return False


def pick_best_topic() -> str | None:
    """
    Return the best unused topic title from the latest research.

    Scoring: reddit_score (higher = better) + keyword count,
    minus topics already covered in tracker.csv.
    """
    try:
        from topic_researcher import load_saved_research
        topics = load_saved_research()
        if not topics:
            return None

        used = _load_used_slugs()

        candidates = []
        for t in topics:
            title = t.get('generated_title', '').strip()
            if not title:
                continue
            slug = _slugify(title)
            if slug in used:
                continue
            score = (t.get('reddit_score', 0) or 0) + len(t.get('keywords', []))
            candidates.append((score, title))

        if not candidates:
            logger.info('All researched topics already covered — re-using top topic.')
            # Fall back to the highest-scoring topic regardless of coverage
            candidates = [
                ((t.get('reddit_score', 0) or 0) + len(t.get('keywords', [])),
                 t.get('generated_title', ''))
                for t in topics if t.get('generated_title')
            ]

        candidates.sort(key=lambda x: x[0], reverse=True)
        best = candidates[0][1] if candidates else None
        logger.info('Picked topic: %s', best)
        return best
    except Exception as exc:
        logger.error('Topic picking failed: %s', exc)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Pipeline
# ═════════════════════════════════════════════════════════════════════════════

def run(
    topic: str | None = None,
    content_types: list[str] | None = None,
    publish: bool = True,
    dry_run: bool = False,
    on_log: Callable[[str], None] | None = None,
) -> dict:
    """
    Run the daily content pipeline.

    Args:
        topic: Topic string. None = auto-pick from research.
        content_types: List containing 'blog_and_linkedin', 'li_only', 'blog_only'.
                       Defaults to ['blog_and_linkedin'].
        publish: If False, generate content but skip website push and LinkedIn post.
        dry_run: Alias for publish=False (backwards compat with scheduler config).
        on_log: Optional callback for progress messages — called with a string.

    Returns:
        dict with keys: topic, blog_path, blog_url, linkedin_path,
                        published_website, published_linkedin, error, timestamp, dry_run.
    """
    if dry_run:
        publish = False

    content_types = content_types or ['blog_and_linkedin']
    mode = content_types[0] if content_types else 'blog_and_linkedin'

    result: dict = {
        'topic': topic or '',
        'blog_path': None,
        'blog_url': None,
        'linkedin_path': None,
        'published_website': False,
        'published_linkedin': False,
        'error': None,
        'timestamp': datetime.now().isoformat(),
        'dry_run': not publish,
    }

    def log(msg: str) -> None:
        logger.info(msg)
        if on_log:
            on_log(msg)

    try:
        # ── Step 1: Research topics ─────────────────────────────────────────
        log('Step 1/9  Checking topic research cache...')
        if not _research_is_fresh():
            log('Research cache older than 24 h — running fresh research...')
            try:
                from topic_researcher import run_research
                run_research()
                log('Research complete.')
            except Exception as exc:
                log(f'Research failed ({exc}) — continuing with cached topics.')
        else:
            log('Research cache is fresh.')

        # ── Step 2: Pick topic ──────────────────────────────────────────────
        if not topic:
            log('Step 2/9  Picking best unused topic from research...')
            topic = pick_best_topic()
            if not topic:
                result['error'] = 'No topics available. Run research first.'
                log(f"ERROR: {result['error']}")
                return result
            result['topic'] = topic
        log(f'Topic: {topic}')

        # ══════════════════════════════════════════════════════════════════
        # BLOG + LINKEDIN MODE
        # ══════════════════════════════════════════════════════════════════
        if mode in ('blog_and_linkedin', 'blog_only'):

            # ── Step 3: Generate blog ───────────────────────────────────
            log('Step 3/9  Generating blog post...')
            from blog_generator import generate_blog
            blog_data = generate_blog(topic)
            if not blog_data:
                result['error'] = 'Blog generation failed — Groq returned empty data.'
                log(f"ERROR: {result['error']}")
                return result
            log(f"Blog generated: {blog_data.get('title', topic)}")

            # ── Step 4: Render HTML and save ────────────────────────────
            log('Step 4/9  Rendering blog HTML...')
            from html_renderer import save_blog
            publish_date = datetime.now().strftime('%Y-%m-%d')
            blog_path = save_blog(blog_data, publish_date, image_url=None)
            result['blog_path'] = blog_path
            log(f'Blog saved: {blog_path}')

            # ── Step 5: Fetch image ─────────────────────────────────────
            log('Step 5/9  Fetching hero image from Unsplash...')
            from image_fetcher import fetch_image
            keywords = blog_data.get('keywords', [])
            slug = blog_data.get('slug', _slugify(topic))
            image_info = fetch_image(keywords, slug, blog_data=blog_data)
            image_url = image_info['public_url'] if image_info else None
            if image_url:
                log(f"Image fetched: {image_info['local_path']}")
                # Re-render with the image URL now that we have it
                blog_path = save_blog(blog_data, publish_date, image_url=image_url)
                result['blog_path'] = blog_path
            else:
                log('No image available — proceeding without hero image.')

            # ── Step 6: Publish blog to website ─────────────────────────
            blog_url = None
            if publish:
                log('Step 6/9  Publishing blog to phoenixsolution.in...')
                from website_publisher import publish_to_website, git_push_website
                try:
                    blog_url = publish_to_website(
                        blog_path=blog_path,
                        image_path=image_info['local_path'] if image_info else None,
                        blog_data=blog_data,
                        publish_date=publish_date,
                    )
                    result['blog_url'] = blog_url
                    result['published_website'] = True
                    log(f'Website published: {blog_url}')

                    log('Step 6b/9  Git pushing website...')
                    git_push_website(
                        slug=blog_data.get('slug', slug),
                        title=blog_data.get('title', topic),
                    )
                    log('Git push complete.')
                except Exception as exc:
                    log(f'Website publish failed: {exc} — continuing.')
                    result['blog_url'] = (
                        'https://www.phoenixsolution.in/blog/'
                        + blog_data.get('slug', slug) + '.html'
                    )
                    blog_url = result['blog_url']
            else:
                log('Step 6/9  [SKIPPED — dry run] Website publish.')
                blog_url = (
                    'https://www.phoenixsolution.in/blog/'
                    + blog_data.get('slug', slug) + '.html'
                )
                result['blog_url'] = blog_url

            if mode == 'blog_only':
                _log_to_tracker(topic, blog_path, None, '', website_url=blog_url or '')
                log('Pipeline complete (blog only).')
                return result

            # ── Step 7: Generate LinkedIn teaser ────────────────────────
            log('Step 7/9  Generating LinkedIn teaser post...')
            from linkedin_generator import generate_linkedin_post, save_linkedin_post
            li_data = generate_linkedin_post(topic, blog_data=blog_data)
            li_path = save_linkedin_post(
                li_data, topic, publish_date, blog_url or ''
            )
            result['linkedin_path'] = li_path
            log(f'LinkedIn post saved: {li_path}')

            # ── Step 8: Publish LinkedIn ─────────────────────────────────
            if publish:
                log('Step 8/9  Publishing to LinkedIn...')
                _publish_linkedin(li_data, image_info, log)
                result['published_linkedin'] = True
            else:
                log('Step 8/9  [SKIPPED — dry run] LinkedIn publish.')

            # ── Step 9: Log ──────────────────────────────────────────────
            log('Step 9/9  Logging to tracker and database...')
            hashtags = ' '.join(li_data.get('hashtags', []))
            _log_to_tracker(topic, blog_path, li_path, hashtags, website_url=blog_url or '')
            _log_to_db(topic, blog_path, li_path, hashtags, publish_date, blog_url or '')

        # ══════════════════════════════════════════════════════════════════
        # LINKEDIN ONLY MODE
        # ══════════════════════════════════════════════════════════════════
        else:
            # ── Step 3: Generate standalone LinkedIn post ────────────────
            log('Step 3/9  Generating standalone LinkedIn post (300-500 words)...')
            from linkedin_generator import generate_linkedin_post, save_linkedin_post
            li_data = generate_linkedin_post(topic, blog_data=None)
            publish_date = datetime.now().strftime('%Y-%m-%d')
            li_path = save_linkedin_post(li_data, topic, publish_date, '')
            result['linkedin_path'] = li_path
            log(f'LinkedIn post saved: {li_path}')

            # ── Step 4: Publish LinkedIn ─────────────────────────────────
            if publish:
                log('Step 4/9  Publishing to LinkedIn...')
                _publish_linkedin(li_data, None, log)
                result['published_linkedin'] = True
            else:
                log('Step 4/9  [SKIPPED — dry run] LinkedIn publish.')

            # ── Step 5: Log ──────────────────────────────────────────────
            log('Step 5/9  Logging to tracker...')
            hashtags = ' '.join(li_data.get('hashtags', []))
            _log_to_tracker(topic, '', li_path, hashtags)
            _log_to_db(topic, '', li_path, hashtags, publish_date, '')

        log('Pipeline complete.')

    except Exception as exc:
        logger.exception('Daily pipeline failed: %s', exc)
        result['error'] = str(exc)

    return result


# ═════════════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════════════

def _publish_linkedin(li_data: dict, image_info: dict | None, log: Callable) -> None:
    """Publish a LinkedIn post via the UGC API."""
    caption = li_data.get('caption', '')
    hashtags_list = li_data.get('hashtags', [])
    blog_url = li_data.get('blog_url', '')

    parts = [caption]
    if blog_url:
        parts.append(f'\nRead the full article: {blog_url}')
    if hashtags_list:
        parts.append('\n' + ' '.join(hashtags_list))
    full_text = '\n'.join(parts)

    image_path = image_info['local_path'] if image_info else None

    try:
        from linkedin_publisher import publish_post
        publish_post(full_text, image_path=image_path, org_urn=None)
        log('LinkedIn post published.')
    except Exception as exc:
        log(f'LinkedIn publish failed: {exc}')
        raise


def _log_to_tracker(
    topic: str,
    blog_path: str,
    linkedin_path: str | None,
    hashtags: str,
    website_url: str = '',
) -> None:
    """Append a row to tracker.csv."""
    try:
        from tracker import add_entry
        add_entry(
            topic=topic,
            blog_path=blog_path or '',
            linkedin_path=linkedin_path or '',
            hashtags=hashtags,
            content_angle='',
            website_url=website_url,
            status='posted',
        )
    except Exception as exc:
        logger.warning('Tracker log failed: %s', exc)


def _log_to_db(
    topic: str,
    blog_path: str,
    linkedin_path: str | None,
    hashtags: str,
    publish_date: str,
    blog_url: str,
) -> None:
    """Insert a record into blog_marketing.db."""
    try:
        from database import insert_post
        # Read linkedin text from file if available
        li_text = ''
        if linkedin_path and os.path.exists(linkedin_path):
            with open(linkedin_path, encoding='utf-8') as f:
                li_text = f.read()
        insert_post(
            topic=topic,
            blog_path=blog_path or '',
            linkedin_text=li_text,
            hashtags=hashtags,
            status='posted',
            publish_date=publish_date,
        )
    except Exception as exc:
        logger.warning('DB log failed: %s', exc)
