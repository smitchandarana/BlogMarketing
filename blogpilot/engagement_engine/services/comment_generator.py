"""Comment Generator — uses Groq to write insightful, human-quality LinkedIn comments."""

from __future__ import annotations

import logging
import os

from blogpilot.engagement_engine.models.engagement_model import LinkedInPost

logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
_BRAND_CONTEXT_PATH = os.path.join(_ROOT, "Prompts", "brand_context.txt")


def _load_brand_context() -> str:
    try:
        with open(_BRAND_CONTEXT_PATH, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return (
            "We are Phoenix Solutions, a digital marketing agency specialising in AI-powered "
            "content automation, LinkedIn growth, and SEO for B2B companies."
        )


def generate(post: LinkedInPost) -> str:
    """Generate a 2-4 sentence LinkedIn comment for the given post.

    Args:
        post: The LinkedIn post to comment on.

    Returns:
        Comment text string, or empty string on failure.
    """
    try:
        from llm_client import get_client, get_model  # type: ignore[import]
        client = get_client()
        model = get_model()
    except Exception as exc:
        logger.warning("Comment generator: could not get LLM client: %s", exc)
        return ""

    brand_context = _load_brand_context()
    prompt = f"""You are a LinkedIn engagement expert writing on behalf of: {brand_context}

Write a 2-4 sentence comment on this LinkedIn post by {post.author_name or "someone"}:

\"\"\"{post.text[:800]}\"\"\"

Requirements:
- Add genuine insight or a thought-provoking perspective (not just agreement)
- Sound human and conversational — no generic phrases like "Great post!" or "Totally agree!"
- Do NOT mention your company or brand
- Do NOT add hashtags
- Return ONLY the comment text, nothing else"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        comment = response.choices[0].message.content.strip()
        logger.debug("Comment generated (%d chars) for post %s.", len(comment), post.post_urn)
        return comment
    except Exception as exc:
        logger.error("Comment generator failed for post %s: %s", post.post_urn, exc)
        return ""
