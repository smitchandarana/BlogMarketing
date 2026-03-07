import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from llm_client import get_client, get_model

load_dotenv()

from paths import app_dir, resource_dir
PROMPT_PATH   = os.path.join(resource_dir(), 'Prompts', 'Linkedin_prompt.txt')
HASHTAGS_PATH = os.path.join(resource_dir(), 'Prompts', 'Hashtags.txt')
LI_POSTS_DIR  = os.path.join(app_dir(),      'LinkedIn Posts')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_prompt() -> str:
    with open(PROMPT_PATH, encoding='utf-8') as f:
        return f.read()


def load_hashtags() -> list:
    """Return list of tag words (without #) from Prompts/Hashtags.txt."""
    with open(HASHTAGS_PATH, encoding='utf-8') as f:
        lines = f.read().splitlines()
    return [line.strip().lstrip('#') for line in lines if line.strip()]


# ── Generation ────────────────────────────────────────────────────────────────

def generate_linkedin_post(topic: str, blog_data: dict = None) -> dict:
    """
    Generate a LinkedIn post + hashtags via Groq LLM.

    Standalone mode (blog_data=None):
        Full self-contained post (300-500 words) with real insight and context.
        Ends with a CTA to phoenixsolution.in — no blog link needed.

    Blog-linked mode (blog_data provided):
        Short summary caption (80-150 words) that teases the blog and invites
        readers to visit the full article link.

    Returns:
        caption   -- post body without hashtags
        hashtags  -- space-separated '#Tag' string
        full_post -- caption + blank line + hashtags (ready to publish)
        blog_url  -- empty string; populated by caller after website publish
    """
    approved_tags = load_hashtags()
    tags_list_str = ', '.join(f'#{t}' for t in approved_tags)

    if blog_data:
        # ── Blog-linked: short teaser that drives to the article ──────────────
        user_prompt = _load_prompt().replace('{topic}', topic)
        user_prompt += (
            f'\n\nBlog title: {blog_data["title"]}'
            f'\nBlog intro excerpt: {blog_data["intro"][:300]}'
        )
        system_prompt = (
            'You are a LinkedIn content strategist for Phoenix Solutions, a BI consulting firm.\n'
            'Return ONLY valid JSON:\n'
            '{\n'
            '  "caption": "Post body - hook, key insight, call-to-action. 80-150 words. No hashtags in this field.",\n'
            '  "selected_hashtags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5", "Tag6"]\n'
            '}\n'
            'Rules:\n'
            '- caption: compelling hook on line 1 -> key insight -> invite to read the full article. No # symbols.\n'
            f'- selected_hashtags: pick 6 MOST RELEVANT tags from this approved list ONLY: {tags_list_str}\n'
            '  Return just the tag word without the # symbol.\n'
            '- Total post length including hashtags must stay under 3000 LinkedIn characters.'
        )
    else:
        # ── Standalone: full value post, no blog link needed ──────────────────
        user_prompt = (
            f'Write a standalone LinkedIn post about: {topic}\n\n'
            'This post must deliver complete, actionable value on its own — '
            'no external article is being linked. The reader should finish the '
            'post feeling informed and ready to act.'
        )
        system_prompt = (
            'You are a LinkedIn content strategist for Phoenix Solutions, a BI consulting firm.\n'
            'Return ONLY valid JSON:\n'
            '{\n'
            '  "caption": "Full self-contained post. 300-500 words. No hashtags in this field.",\n'
            '  "selected_hashtags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5", "Tag6"]\n'
            '}\n'
            'Rules:\n'
            '- caption structure:\n'
            '    Line 1: bold hook or provocative question (standalone line)\n'
            '    Lines 2-N: 3-5 short paragraphs delivering real insight, practical tips, or a '
            'framework your audience (CFOs, IT managers, ops leaders) can use immediately\n'
            '    Final paragraph: soft CTA — "Explore more at www.phoenixsolution.in" or similar\n'
            '- Use short paragraphs (2-4 lines). Add blank lines between sections for readability.\n'
            '- No # symbols inside caption.\n'
            f'- selected_hashtags: pick 6 MOST RELEVANT tags from this approved list ONLY: {tags_list_str}\n'
            '  Return just the tag word without the # symbol.\n'
            '- Total post length including hashtags must stay under 3000 LinkedIn characters.'
        )

    response = get_client().chat.completions.create(
        model=get_model(),
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': user_prompt},
        ],
        response_format={'type': 'json_object'},
        temperature=0.7,
    )

    result      = json.loads(response.choices[0].message.content)
    caption     = result.get('caption', '').strip()
    sel_tags    = result.get('selected_hashtags', approved_tags[:6])
    hashtag_str = ' '.join(f'#{t}' for t in sel_tags)

    return {
        'caption':   caption,
        'hashtags':  hashtag_str,
        'full_post': f'{caption}\n\n{hashtag_str}',
        'blog_url':  '',  # populated by caller after website publish
    }


# ── File persistence ──────────────────────────────────────────────────────────

def save_linkedin_post(li_data: dict, topic: str,
                       calendar_day: int = None, publish_date: str = None,
                       blog_url: str = None) -> str:
    """
    Save the LinkedIn post as a TXT file in 'LinkedIn Posts/' folder.
    Returns the saved file path.
    """
    os.makedirs(LI_POSTS_DIR, exist_ok=True)

    if publish_date is None:
        publish_date = datetime.now().strftime('%Y-%m-%d')

    slug    = re.sub(r'[^a-z0-9]+', '-', topic.lower())[:45].strip('-')
    day_str = f'-day{calendar_day:02d}' if calendar_day else ''
    path    = os.path.join(LI_POSTS_DIR, f'{publish_date}{day_str}-{slug}.txt')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(f'TOPIC        : {topic}\n')
        f.write(f'DATE         : {publish_date}\n')
        if calendar_day:
            f.write(f'CALENDAR DAY : {calendar_day}\n')
        f.write(f'\n{"=" * 60}\n\n')
        # Build final post text: caption + optional blog link + hashtags
        caption     = li_data.get('caption', '')
        hashtags    = li_data.get('hashtags', '')
        url         = blog_url or li_data.get('blog_url', '')
        if url:
            post_text = f'{caption}\n\nRead the full article: {url}\n\n{hashtags}'
        else:
            post_text = li_data.get('full_post', f'{caption}\n\n{hashtags}')
        f.write(post_text)
        f.write('\n')

    return path
