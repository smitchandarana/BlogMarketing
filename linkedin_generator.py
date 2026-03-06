import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from llm_client import get_client, get_model

load_dotenv()

PROMPT_PATH   = os.path.join(os.path.dirname(__file__), 'Prompts', 'Linkedin_prompt.txt')
HASHTAGS_PATH = os.path.join(os.path.dirname(__file__), 'Prompts', 'Hashtags.txt')
LI_POSTS_DIR  = os.path.join(os.path.dirname(__file__), 'LinkedIn Posts')


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
    Generate a LinkedIn caption + hashtags via ChatGPT.
    Hashtags are selected from the approved list in Prompts/Hashtags.txt.

    Returns:
        caption   -- post text without hashtags (80-150 words)
        hashtags  -- space-separated '#Tag' string
        full_post -- caption + blank line + hashtags (ready to publish)
    """
    user_prompt = _load_prompt().replace('{topic}', topic)

    if blog_data:
        user_prompt += (
            f'\n\nBlog title: {blog_data["title"]}'
            f'\nBlog intro excerpt: {blog_data["intro"][:300]}'
        )

    approved_tags = load_hashtags()
    tags_list_str = ', '.join(f'#{t}' for t in approved_tags)

    system_prompt = (
        'You are a LinkedIn content strategist for Phoenix Solutions, a BI consulting firm.\n'
        'Return ONLY valid JSON:\n'
        '{\n'
        '  "caption": "Post body - hook, key insight, call-to-action. 80-150 words. No hashtags in this field.",\n'
        '  "selected_hashtags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5", "Tag6"]\n'
        '}\n'
        'Rules:\n'
        '- caption: compelling hook on line 1 -> key insight -> call to action. No # symbols inside caption.\n'
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
