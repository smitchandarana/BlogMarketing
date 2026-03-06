import os
import json
from dotenv import load_dotenv
from llm_client import get_client, get_model

load_dotenv()

DEFAULT_INDUSTRY = 'business intelligence, data analytics, and ERP consulting'


def get_trending_topics(industry: str = DEFAULT_INDUSTRY, n: int = 5) -> list:
    """
    Return n trending blog topic ideas for the given industry.
    Each topic is a specific, ready-to-use blog title.
    """
    response = get_client().chat.completions.create(
        model=get_model(),
        messages=[
            {
                'role': 'system',
                'content': (
                    'You are a content strategist. '
                    'Return ONLY valid JSON: {"topics": ["topic1", "topic2", ...]}. '
                    'Each topic must be a specific, compelling blog title (not a category).'
                ),
            },
            {
                'role': 'user',
                'content': (
                    f'Give me {n} trending blog topic ideas for {industry} relevant to 2025. '
                    'Target audience: business leaders and consultants. '
                    'Each topic should support a 900-1200 word professional article.'
                ),
            },
        ],
        response_format={'type': 'json_object'},
        temperature=0.85,
    )

    result = json.loads(response.choices[0].message.content)
    return result.get('topics', [])
