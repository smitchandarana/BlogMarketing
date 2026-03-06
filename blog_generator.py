import os
import json
from dotenv import load_dotenv
from llm_client import get_client, get_model

load_dotenv()

PROMPT_PATH   = os.path.join(os.path.dirname(__file__), 'Prompts', 'blog_prompt.txt')
CALENDAR_PATH = os.path.join(os.path.dirname(__file__), 'MarketingSchedule', 'Calender.json')


# ── Calendar helpers ──────────────────────────────────────────────────────────

def load_calendar() -> list:
    """Return the full 30-day content calendar from Calender.json."""
    with open(CALENDAR_PATH, encoding='utf-8') as f:
        return json.load(f)['content_calendar']


def get_calendar_entry(day: int):
    """Return a single calendar entry by day number, or None if not found."""
    for entry in load_calendar():
        if entry['day'] == day:
            return entry
    return None


# ── Blog generation ───────────────────────────────────────────────────────────

def _load_prompt() -> str:
    with open(PROMPT_PATH, encoding='utf-8') as f:
        return f.read()


def generate_blog(topic: str, content_angle: str = '', keywords: list = None) -> dict:
    """
    Generate structured blog content via ChatGPT.

    Returns a dict with keys:
        title, slug, meta_description, category, tag_emoji, keywords,
        intro, sections, conclusion, cta_headline, cta_subtext,
        related_service_url, related_service_name, related_service_desc
    """
    base_prompt = _load_prompt().replace('{topic}', topic)
    if content_angle:
        base_prompt += f'\n\nContent angle: {content_angle}'
    if keywords:
        base_prompt += f'\nFocus keywords: {", ".join(keywords)}'

    system_prompt = """You are a professional blog writer for Phoenix Solutions, a Business Intelligence consulting firm.
Return ONLY valid JSON with this exact structure:
{
  "title": "Full article title",
  "slug": "lowercase-hyphenated-slug-max-60-chars",
  "meta_description": "150-160 character SEO description",
  "category": "e.g. Power BI / Strategy / Data Engineering / Integration / Analytics",
  "tag_emoji": "one of: \U0001F4CA \U0001F3AF \u2699\ufe0f \U0001F517 \U0001F4A1",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4"],
  "intro": "2-3 opening paragraphs separated by double newlines",
  "sections": [
    {"heading": "Section heading", "body": "Section body \u2014 multiple paragraphs separated by double newlines"},
    {"heading": "Section heading", "body": "..."},
    {"heading": "Section heading", "body": "..."}
  ],
  "conclusion": "Closing paragraph summarising key takeaway",
  "cta_headline": "CTA headline connecting the topic to a booking",
  "cta_subtext": "1-2 sentences connecting topic to booking a call",
  "related_service_url": "/services/business-intelligence",
  "related_service_name": "BI & Dashboards",
  "related_service_desc": "One sentence describing the related service"
}
Rules:
- slug: lowercase, hyphens only, no special chars, max 60 chars
- meta_description: exactly 150-160 characters
- 3-5 sections
- total word count 900-1200 words across intro + sections + conclusion
- tone: insightful, authoritative, practical
- audience: business leaders and consultants"""

    response = get_client().chat.completions.create(
        model=get_model(),
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': base_prompt},
        ],
        response_format={'type': 'json_object'},
        temperature=0.7,
    )

    return json.loads(response.choices[0].message.content)
