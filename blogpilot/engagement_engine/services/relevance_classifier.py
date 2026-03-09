"""Relevance Classifier — multi-factor scoring for LinkedIn post relevance.

Combines four independent signals (weights sum to 1.0):

  1. LLM semantic score  (weight 0.45) — Groq llama-3.1-8b-instant
  2. Keyword overlap     (weight 0.25) — niche keyword match ratio
  3. Engagement velocity (weight 0.15) — normalised like/comment counts
  4. Author influence    (weight 0.15) — author_metrics rolling average

Posts with combined_score >= threshold are classified as relevant.
If the Groq call fails the classifier falls back to the remaining three factors.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re

from blogpilot.engagement_engine.models.engagement_model import (
    ClassificationResult,
    LinkedInPost,
)

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = float(os.environ.get("ENGAGEMENT_RELEVANCE_THRESHOLD", "0.6"))
_CLASSIFIER_MODEL = "llama-3.1-8b-instant"

# Factor weights — must sum to 1.0
_W_LLM = 0.45
_W_KEYWORD = 0.25
_W_VELOCITY = 0.15
_W_INFLUENCE = 0.15

# Normalisation caps
_MAX_LIKES_NORM = 500
_MAX_COMMENTS_NORM = 100

# Cache niche keywords so we read the config only once per process
_niche_keywords: list[str] | None = None


def _get_niche_keywords() -> list[str]:
    """Load niche keywords from scheduler_config.json or fall back to a sensible default."""
    global _niche_keywords
    if _niche_keywords is not None:
        return _niche_keywords

    try:
        _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        config_path = os.path.join(_root, "scheduler_config.json")
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        keywords = cfg.get("niche_keywords", [])
        if keywords:
            _niche_keywords = [k.lower() for k in keywords]
            return _niche_keywords
    except Exception:
        pass

    _niche_keywords = [
        "digital marketing", "ai automation", "linkedin growth",
        "content marketing", "saas", "data analytics", "business intelligence",
        "marketing automation", "lead generation", "b2b",
    ]
    return _niche_keywords


# ── Factor 1: LLM semantic score ──────────────────────────────────────────────

def _llm_score(post: LinkedInPost, niche: str) -> float | None:
    """Call Groq to get a 0-1 semantic relevance score.

    Returns None on failure so the caller can fall back gracefully.
    """
    try:
        from llm_client import get_client  # type: ignore[import]
        client = get_client()
    except Exception as exc:
        logger.debug("LLM client unavailable: %s", exc)
        return None

    prompt = (
        f"Score the relevance of this LinkedIn post to the niche: [{niche}].\n\n"
        f"Post:\n\"\"\"{post.text[:500]}\"\"\"\n\n"
        "Return ONLY valid JSON: {\"score\": <float 0.0-1.0>, \"reason\": \"<one sentence>\"}\n"
        "Score 1.0 = directly on topic. Score 0.0 = completely off topic. No extra text."
    )
    try:
        response = client.chat.completions.create(
            model=_CLASSIFIER_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=80,
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        return float(data.get("score", 0.0))
    except Exception as exc:
        logger.debug("LLM scoring failed for post %s: %s", post.post_urn, exc)
        return None


# ── Factor 2: Keyword overlap score ───────────────────────────────────────────

def _keyword_score(post: LinkedInPost, keywords: list[str]) -> float:
    """Fraction of niche keywords present in the post text (case-insensitive)."""
    if not keywords or not post.text:
        return 0.0
    text_lower = post.text.lower()
    matched = sum(1 for kw in keywords if kw in text_lower)
    # Diminishing returns: log scale so 3/10 keywords → ~0.5, not 0.3
    raw = matched / len(keywords)
    return min(1.0, math.log1p(matched) / math.log1p(max(len(keywords), 5)))


# ── Factor 3: Engagement velocity score ───────────────────────────────────────

def _velocity_score(post: LinkedInPost) -> float:
    """Normalised engagement count — higher likes/comments → higher score."""
    like_score = min(1.0, post.likes / _MAX_LIKES_NORM)
    comment_score = min(1.0, post.comments / _MAX_COMMENTS_NORM)
    # Comments weighted more than likes (harder to get)
    return like_score * 0.4 + comment_score * 0.6


# ── Factor 4: Author influence score ──────────────────────────────────────────

def _influence_score(post: LinkedInPost, db_path: str | None = None) -> float:
    """Score based on author's rolling average engagement from author_metrics table.

    Authors with no history return 0.5 (neutral — we don't penalise unknown authors).
    """
    if not post.author_name:
        return 0.5
    try:
        from blogpilot.db.connection import get_connection  # type: ignore[import]
        with get_connection(db_path) as conn:
            row = conn.execute(
                "SELECT avg_likes, avg_comments, post_count FROM author_metrics WHERE author_name = ?",
                (post.author_name,),
            ).fetchone()
        if row and row["post_count"] >= 3:
            avg = (row["avg_likes"] + row["avg_comments"] * 2) / 3
            # Normalise against moderate engagement baseline
            return min(1.0, avg / 50.0)
    except Exception as exc:
        logger.debug("Author influence query failed: %s", exc)
    return 0.5  # Neutral for unknown authors


# ── Public API ─────────────────────────────────────────────────────────────────

def classify(
    post: LinkedInPost,
    threshold: float | None = None,
    db_path: str | None = None,
) -> ClassificationResult:
    """Score a post using multi-factor relevance analysis.

    Args:
        post: The LinkedIn post to classify.
        threshold: Relevance threshold (default: ENGAGEMENT_RELEVANCE_THRESHOLD env var or 0.6).
        db_path: Optional DB path override (for author_metrics lookup).

    Returns:
        ClassificationResult with relevant flag, combined score, and breakdown reason.
    """
    effective_threshold = threshold if threshold is not None else _DEFAULT_THRESHOLD
    keywords = _get_niche_keywords()
    niche_str = ", ".join(keywords)

    # Factor 2 + 3 + 4 are always computed (no external calls)
    f_keyword = _keyword_score(post, keywords)
    f_velocity = _velocity_score(post)
    f_influence = _influence_score(post, db_path)

    # Factor 1: LLM (may return None on failure)
    f_llm = _llm_score(post, niche_str)

    if f_llm is not None:
        combined = (
            _W_LLM * f_llm
            + _W_KEYWORD * f_keyword
            + _W_VELOCITY * f_velocity
            + _W_INFLUENCE * f_influence
        )
        reason = (
            f"llm={f_llm:.2f} kw={f_keyword:.2f} "
            f"vel={f_velocity:.2f} inf={f_influence:.2f} => {combined:.2f}"
        )
    else:
        # LLM unavailable — redistribute its weight across the other factors
        total_other_weight = _W_KEYWORD + _W_VELOCITY + _W_INFLUENCE
        combined = (
            (_W_KEYWORD / total_other_weight) * f_keyword
            + (_W_VELOCITY / total_other_weight) * f_velocity
            + (_W_INFLUENCE / total_other_weight) * f_influence
        )
        reason = (
            f"llm=unavailable kw={f_keyword:.2f} "
            f"vel={f_velocity:.2f} inf={f_influence:.2f} => {combined:.2f}"
        )

    logger.debug(
        "Classify post %s: %s (threshold=%.2f)", post.post_urn, reason, effective_threshold
    )
    return ClassificationResult(
        relevant=combined >= effective_threshold,
        score=round(combined, 4),
        reason=reason,
    )
