"""
topic_researcher.py — Research trending BI topics from Reddit and LinkedIn.

Reddit:   fetches real hot posts via public JSON API (no auth needed).
LinkedIn: Groq LLM synthesises topics based on what BI professionals discuss
          on LinkedIn (no public read API available without OAuth).

Results are saved to MarketingSchedule/ResearchTopics.json.
"""

import os
import json
import logging
import requests
from datetime import datetime

from dotenv import load_dotenv
from llm_client import get_client, get_model

load_dotenv()

logger = logging.getLogger(__name__)

SUBREDDITS = [
    'PowerBI',
    'businessintelligence',
    'dataengineering',
    'analytics',
    'datascience',
]

from paths import app_dir
RESEARCH_PATH = os.path.join(app_dir(), 'MarketingSchedule', 'ResearchTopics.json')


# ── Reddit (real data) ────────────────────────────────────────────────────────

def fetch_reddit_posts(subreddit, limit=15):
    """
    Fetch hot posts from a subreddit via the public JSON API.
    Returns list of {title, score, num_comments, url, subreddit}.
    Returns [] on any error.
    """
    url = 'https://www.reddit.com/r/{}/hot.json'.format(subreddit)
    try:
        resp = requests.get(
            url,
            params={'limit': limit},
            headers={'User-Agent': 'PhoenixBlogBot/1.0'},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning('Reddit r/%s returned HTTP %d', subreddit, resp.status_code)
            return []
        data = resp.json()
        posts = []
        for child in data.get('data', {}).get('children', []):
            p = child.get('data', {})
            title = p.get('title', '').strip()
            if not title or p.get('stickied'):
                continue
            posts.append({
                'title':        title,
                'score':        p.get('score', 0),
                'num_comments': p.get('num_comments', 0),
                'url':          'https://www.reddit.com' + p.get('permalink', ''),
                'subreddit':    subreddit,
            })
        logger.info('Reddit r/%s: fetched %d posts', subreddit, len(posts))
        return posts
    except Exception as exc:
        logger.warning('Reddit r/%s fetch failed: %s', subreddit, exc)
        return []


def synthesise_from_reddit(posts):
    """
    Pass Reddit post titles to Groq and extract blog topic ideas.
    Returns list of topic dicts with keys:
      pain_point, generated_title, keywords, source, reddit_score
    """
    if not posts:
        return []

    # Build input for LLM — include score so it can weight popular topics
    lines = []
    for p in posts:
        lines.append('[r/{subreddit} score:{score}] {title}'.format(**p))
    post_block = '\n'.join(lines)

    system_prompt = (
        'You are a content strategist for a Business Intelligence consulting firm. '
        'Analyse Reddit posts from BI communities and identify consulting pain points '
        'that business leaders actually face. '
        'Return ONLY valid JSON:\n'
        '{"topics": [\n'
        '  {"pain_point": "...", "generated_title": "...", '
        '"keywords": ["kw1","kw2","kw3"], "source": "r/subreddit", "reddit_score": 123}\n'
        ']}\n'
        'Rules:\n'
        '- pain_point: the underlying business problem (1 sentence)\n'
        '- generated_title: a compelling consulting blog title (max 65 chars)\n'
        '- keywords: 3-4 SEO keywords\n'
        '- source: the subreddit the idea came from (e.g. "r/PowerBI")\n'
        '- reddit_score: the score of the source post\n'
        '- Generate 8 to 12 distinct topics\n'
        '- Prioritise posts with higher scores\n'
        '- Target audience: CFOs, IT managers, operations leaders'
    )

    user_prompt = (
        'Here are recent hot posts from BI-related Reddit communities.\n'
        'Extract the most valuable consulting blog topic ideas:\n\n'
        + post_block
    )

    try:
        resp = get_client().chat.completions.create(
            model=get_model(),
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': user_prompt},
            ],
            response_format={'type': 'json_object'},
            temperature=0.7,
        )
        result = json.loads(resp.choices[0].message.content)
        topics = result.get('topics', [])
        logger.info('Reddit synthesis: %d topics generated', len(topics))
        return topics
    except Exception as exc:
        logger.error('Reddit topic synthesis failed: %s', exc)
        return []


# ── LinkedIn (LLM-synthesised) ────────────────────────────────────────────────

def synthesise_linkedin_topics(n=8):
    """
    Use Groq to generate blog topic ideas based on what LinkedIn BI professionals
    are actively discussing. LinkedIn has no public read API without OAuth, so the
    LLM simulates this based on its training knowledge of LinkedIn BI discussions.
    Returns list of topic dicts.
    """
    system_prompt = (
        'You are a LinkedIn content analyst specialising in Business Intelligence '
        'and enterprise analytics consulting. '
        'Return ONLY valid JSON:\n'
        '{"topics": [\n'
        '  {"pain_point": "...", "generated_title": "...", '
        '"keywords": ["kw1","kw2","kw3"], "source": "LinkedIn", "reddit_score": 0}\n'
        ']}\n'
        'Rules:\n'
        '- pain_point: a real business pain point BI/analytics professionals discuss on LinkedIn\n'
        '- generated_title: a compelling consulting blog title (max 65 chars)\n'
        '- keywords: 3-4 SEO keywords\n'
        '- source: always "LinkedIn"\n'
        '- reddit_score: always 0\n'
        '- Target audience: CFOs, IT managers, operations leaders\n'
        '- Focus on ERP reporting, Power BI, KPIs, data strategy, digital transformation'
    )

    user_prompt = (
        'Generate {} blog topic ideas based on the consulting pain points '
        'that Business Intelligence and analytics professionals are actively '
        'discussing on LinkedIn right now. '
        'Focus on practical, decision-maker-level challenges.'.format(n)
    )

    try:
        resp = get_client().chat.completions.create(
            model=get_model(),
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',   'content': user_prompt},
            ],
            response_format={'type': 'json_object'},
            temperature=0.75,
        )
        result = json.loads(resp.choices[0].message.content)
        topics = result.get('topics', [])
        logger.info('LinkedIn synthesis: %d topics generated', len(topics))
        return topics
    except Exception as exc:
        logger.error('LinkedIn topic synthesis failed: %s', exc)
        return []


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_research(subreddits=None, include_linkedin=True):
    """
    Full research run.
    1. Fetch Reddit posts from selected subreddits and synthesise topics.
    2. If include_linkedin, synthesise LinkedIn topics via LLM.
    3. Merge, deduplicate by title, save, return.
    """
    if subreddits is None:
        subreddits = SUBREDDITS

    all_topics = []

    # Reddit
    if subreddits:
        logger.info('Fetching Reddit posts from: %s', subreddits)
        all_posts = []
        for sub in subreddits:
            all_posts.extend(fetch_reddit_posts(sub))
        if all_posts:
            reddit_topics = synthesise_from_reddit(all_posts)
            all_topics.extend(reddit_topics)

    # LinkedIn
    if include_linkedin:
        logger.info('Synthesising LinkedIn topics via Groq...')
        li_topics = synthesise_linkedin_topics(n=8)
        all_topics.extend(li_topics)

    # Deduplicate by generated_title (case-insensitive)
    seen = set()
    unique = []
    for t in all_topics:
        key = t.get('generated_title', '').lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(t)

    save_research(unique)
    logger.info('Research complete: %d unique topics saved', len(unique))
    return unique


# ── Persistence ───────────────────────────────────────────────────────────────

def save_research(topics):
    """Write topics to MarketingSchedule/ResearchTopics.json."""
    os.makedirs(os.path.dirname(RESEARCH_PATH), exist_ok=True)
    data = {
        'last_run': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'topics':   topics,
    }
    with open(RESEARCH_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info('Saved %d research topics to %s', len(topics), RESEARCH_PATH)


def load_saved_research():
    """
    Load topics from the last saved research run.
    Returns list of topic dicts, or [] if file does not exist.
    """
    if not os.path.exists(RESEARCH_PATH):
        return []
    try:
        with open(RESEARCH_PATH, encoding='utf-8') as f:
            data = json.load(f)
        topics = data.get('topics', [])
        logger.info('Loaded %d saved research topics', len(topics))
        return topics
    except Exception as exc:
        logger.warning('Could not load research topics: %s', exc)
        return []


def get_last_run_date():
    """Return the last_run string from the JSON, or None."""
    if not os.path.exists(RESEARCH_PATH):
        return None
    try:
        with open(RESEARCH_PATH, encoding='utf-8') as f:
            return json.load(f).get('last_run')
    except Exception:
        return None
