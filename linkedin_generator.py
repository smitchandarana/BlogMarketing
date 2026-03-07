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
            'You are a LinkedIn content strategist for Phoenix Solution (phoenixsolution.in), '
            'a BI, data analytics, and ERP consulting firm.\n\n'
            'Return ONLY valid JSON:\n'
            '{\n'
            '  "caption": "Post body. 80-150 words. No hashtags in this field.",\n'
            '  "selected_hashtags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5", "Tag6"]\n'
            '}\n\n'
            'CAPTION STRUCTURE:\n'
            '- LINE 1: Bold hook that stops the scroll. Use one of these formulas:\n'
            '  * Curiosity gap: "Most companies get [X] wrong. Here\'s what they miss."\n'
            '  * Contrarian: "Unpopular opinion: [bold claim]."\n'
            '  * Story: "A client came to us with [problem]. What we found surprised us."\n'
            '  * Value: "How to [outcome] without [pain]:"\n'
            '  * Stat: "[Surprising number] — and most companies don\'t know it."\n'
            '- BODY (3-5 short lines): Tease 1-2 key insights from the blog WITHOUT giving the full answer. '
            'Create an information gap. Use arrows (→) or short bullets for scanability. '
            'Keep paragraphs to 1-2 lines. Address reader with "you/your".\n'
            '- CTA (final line): "Full breakdown in the article below" or "Link in comments" — '
            'optionally end with an engagement question.\n\n'
            'FORMATTING RULES:\n'
            '- Line break after hook. Blank line between paragraphs.\n'
            '- NO generic openers like "In today\'s fast-paced world" or "It\'s no secret".\n'
            '- NO emojis unless they add real meaning (max 1-2).\n'
            '- NO # symbols inside caption.\n'
            '- Voice: trusted senior consultant sharing a key insight — confident, direct.\n\n'
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
            'You are a LinkedIn thought leadership writer for Phoenix Solution (phoenixsolution.in), '
            'a BI, data analytics, and ERP consulting firm that helps mid-market companies '
            'turn raw data into actionable business intelligence.\n\n'
            'Return ONLY valid JSON:\n'
            '{\n'
            '  "caption": "Full self-contained post. 300-500 words. No hashtags in this field.",\n'
            '  "selected_hashtags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5", "Tag6"]\n'
            '}\n\n'
            'CAPTION STRUCTURE:\n'
            '- LINE 1: Bold hook that stops the scroll. Use ONE of these formulas:\n'
            '  * Curiosity: "Most companies get [X] completely wrong."\n'
            '  * Contrarian: "Unpopular opinion: [bold claim about topic]."\n'
            '  * Story: "A client came to us with [relatable problem]. Here\'s what we found."\n'
            '  * Value: "How to [desirable outcome] without [common pain]:"\n'
            '  * Stat: "[Surprising percentage or number] — and most teams don\'t even know it."\n\n'
            '- BODY (3-5 paragraphs): Follow this flow:\n'
            '  1. PROBLEM AGITATION: Paint the pain your audience feels (data silos, manual reporting, '
            'spreadsheet chaos, lack of real-time dashboards, ERP data locked away)\n'
            '  2. INSIGHT/FRAMEWORK: Share a concrete framework, mental model, or step-by-step approach. '
            'Use numbered steps or arrows (→) for scanability.\n'
            '  3. PROOF: Reference a real-world scenario (e.g., "We helped a manufacturing firm cut '
            'reporting time by 70%") — be specific, not generic.\n\n'
            '- CTA (final paragraph): Rotate between these styles:\n'
            '  * "We help mid-market companies turn data chaos into clarity. Learn more at phoenixsolution.in"\n'
            '  * "Want to stop guessing with your data? DM us or visit phoenixsolution.in"\n'
            '  * "Phoenix Solution builds the dashboards and pipelines that make this possible. '
            'See how at phoenixsolution.in"\n'
            '  THEN end with an engagement question: "What\'s your biggest data challenge right now?" '
            'or "Have you seen this in your org?"\n\n'
            'FORMATTING RULES:\n'
            '- Short paragraphs: 2-3 lines max. Blank line between every paragraph.\n'
            '- Use → arrows or bullet points for lists and steps.\n'
            '- Line break after hook line.\n'
            '- NO generic openers ("In today\'s fast-paced world", "It\'s no secret", "As we all know").\n'
            '- NO filler sentences. Every line must deliver value or advance the argument.\n'
            '- NO emojis unless they add real meaning (max 2).\n'
            '- NO # symbols inside caption.\n\n'
            'AUDIENCE: IT directors, CFOs, ops leaders at companies with 50-500 employees.\n'
            'TONE: Like a senior consultant sharing hard-won wisdom over coffee — authoritative, '
            'conversational, generous with insight. NOT a vendor pitch.\n\n'
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
