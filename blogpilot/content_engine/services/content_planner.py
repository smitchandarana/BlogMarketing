"""Content Planner — maps an insight to a list of content generation tasks.

Returns a list of plan items, each describing one piece of content to create:
    {"content_type": "blog_post"|"linkedin_post", "topic": str, "angle": str}

Adding a new rule: extend _PLAN_RULES with a new category key.
"""

from __future__ import annotations

import logging
from blogpilot.insight_engine.models.insight import Insight

logger = logging.getLogger(__name__)

# category → (blog_count, linkedin_count)
_PLAN_RULES: dict[str, tuple[int, int]] = {
    "digital-marketing": (1, 2),
    "ai-tech":           (1, 1),
    "marketing":         (1, 3),
    "reddit":            (0, 2),
    "industry":          (1, 1),
    "general":           (1, 1),
}
_DEFAULT_RULE = (1, 1)


def plan(insight: Insight) -> list[dict]:
    """Produce a list of content tasks for a given insight.

    Args:
        insight: A ranked Insight with title, summary, category, action_items.

    Returns:
        List of dicts: [{"content_type": str, "topic": str, "angle": str}, ...]
    """
    blog_count, li_count = _PLAN_RULES.get(insight.category, _DEFAULT_RULE)

    topic = insight.title
    angle = insight.action_items[0] if insight.action_items else insight.summary[:120]

    items: list[dict] = []

    for _ in range(blog_count):
        items.append({
            "content_type": "blog_post",
            "topic": topic,
            "angle": angle,
        })

    for i in range(li_count):
        # Vary the angle for multiple LinkedIn posts from the same insight
        li_angle = insight.action_items[i] if i < len(insight.action_items) else angle
        items.append({
            "content_type": "linkedin_post",
            "topic": topic,
            "angle": li_angle,
        })

    logger.info(
        "Planner: insight '%s' → %d blog(s), %d LinkedIn post(s).",
        insight.title[:60], blog_count, li_count,
    )
    return items
