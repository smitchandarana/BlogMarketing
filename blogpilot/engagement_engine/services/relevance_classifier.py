"""Relevance Classifier — uses Groq to score post relevance to the user's niche.

Uses a fast, cheap model (llama-3.1-8b-instant) for batch classification.
Returns a 0-1 score; posts >= threshold are considered relevant.
"""

from __future__ import annotations

import json
import logging
import os

from blogpilot.engagement_engine.models.engagement_model import (
    ClassificationResult,
    LinkedInPost,
)

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = float(os.environ.get("ENGAGEMENT_RELEVANCE_THRESHOLD", "0.6"))
_CLASSIFIER_MODEL = "llama-3.1-8b-instant"


def _get_niche_keywords() -> str:
    """Load niche keywords from scheduler_config.json or fall back to a sensible default."""
    try:
        import sys
        _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        config_path = os.path.join(_root, "scheduler_config.json")
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        keywords = cfg.get("niche_keywords", [])
        if keywords:
            return ", ".join(keywords)
    except Exception:
        pass
    return "digital marketing, AI automation, LinkedIn growth, content marketing, SaaS"


def classify(post: LinkedInPost, threshold: float | None = None) -> ClassificationResult:
    """Score a single post for relevance to the user's niche.

    Args:
        post: The LinkedIn post to classify.
        threshold: Relevance threshold (default: ENGAGEMENT_RELEVANCE_THRESHOLD env var or 0.6).

    Returns:
        ClassificationResult with relevant flag, score, and reason.
    """
    effective_threshold = threshold if threshold is not None else _DEFAULT_THRESHOLD

    try:
        from llm_client import get_client, get_model  # type: ignore[import]
        client = get_client()
    except Exception as exc:
        logger.warning("Relevance classifier: could not get LLM client: %s", exc)
        return ClassificationResult(relevant=False, score=0.0, reason="LLM unavailable")

    niche = _get_niche_keywords()
    prompt = f"""You are a LinkedIn engagement assistant. Score the relevance of this post to the niche: [{niche}].

Post text:
\"\"\"{post.text[:500]}\"\"\"

Return ONLY valid JSON with this shape:
{{"score": <float 0.0-1.0>, "reason": "<one sentence>"}}

Score 1.0 = directly on topic. Score 0.0 = completely off topic. No extra text."""

    try:
        response = client.chat.completions.create(
            model=_CLASSIFIER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=80,
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        score = float(data.get("score", 0.0))
        reason = str(data.get("reason", ""))
        return ClassificationResult(
            relevant=score >= effective_threshold,
            score=score,
            reason=reason,
        )
    except Exception as exc:
        logger.error("Relevance classifier failed for post %s: %s", post.post_urn, exc)
        return ClassificationResult(relevant=False, score=0.0, reason=str(exc))
