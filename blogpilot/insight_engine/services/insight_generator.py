"""Insight Generator — converts signal clusters into structured insights via Groq.

One Groq call per cluster. Returns a structured Insight for each cluster.
Uses the main generation model (llama-3.3-70b-versatile) for quality.
"""

from __future__ import annotations

import json
import logging
import os
import sys

from blogpilot.insight_engine.models.insight import Insight
from blogpilot.signal_engine.models.signal import Signal

logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

_SYSTEM_PROMPT = """\
You are a marketing intelligence analyst for Phoenix Solutions — an IT services, \
web development, and digital marketing agency based in India serving SMBs.

Analyze the provided industry signals and extract a structured insight that Phoenix \
Solutions can use to create relevant content and offer services.

Respond ONLY with valid JSON matching this exact structure:
{
  "title": "Short problem headline (max 12 words)",
  "core_problem": "The core industry problem these signals reveal (2-3 sentences)",
  "decision_implication": "What this means for businesses like Phoenix Solutions clients (2 sentences)",
  "recommended_action": "One specific content or service action Phoenix Solutions should take",
  "confidence": 7
}

confidence is an integer 1-10 reflecting how strong and consistent the signal pattern is.
"""


def _build_cluster_prompt(cluster: dict) -> str:
    signals: list[Signal] = cluster["signals"]
    keywords = ", ".join(sorted(cluster["keywords"])[:15])
    lines = [
        f"Category: {cluster['category']}",
        f"Key topics: {keywords}",
        "",
        "Signals:",
    ]
    for i, sig in enumerate(signals, 1):
        lines.append(f"{i}. [{sig.source}] {sig.title}")
        if sig.summary:
            lines.append(f"   {sig.summary[:250]}")
    return "\n".join(lines)


def _parse_response(raw: str, cluster: dict) -> dict | None:
    text = raw.strip()
    # Strip markdown fences
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Insight parse failed for cluster '%s': %s", cluster["category"], raw[:200])
        return None


def generate(clusters: list[dict], db_path: str | None = None) -> list[Insight]:
    """Generate one Insight per cluster using Groq.

    Args:
        clusters: Output of signal_clusterer.cluster().
        db_path:  Unused here — passed through for future use.

    Returns:
        List of Insight objects (not yet persisted).
    """
    if not clusters:
        return []

    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

    try:
        from llm_client import get_client, get_model  # type: ignore[import]
    except ImportError as exc:
        logger.error("Cannot import llm_client: %s", exc)
        return []

    client = get_client()
    model = get_model()
    insights: list[Insight] = []

    for cluster in clusters:
        signals: list[Signal] = cluster["signals"]
        if not signals:
            continue

        prompt = _build_cluster_prompt(cluster)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""
            parsed = _parse_response(raw, cluster)

            if not parsed:
                continue

            action = parsed.get("recommended_action", "")
            insight = Insight(
                title=parsed.get("title", cluster["category"])[:120],
                summary=(
                    parsed.get("core_problem", "")
                    + " "
                    + parsed.get("decision_implication", "")
                ).strip(),
                category=cluster["category"],
                signal_ids=[s.id for s in signals if s.id is not None],
                confidence=max(0.0, min(1.0, float(parsed.get("confidence", 5)) / 10.0)),
                action_items=[action] if action else [],
            )
            insights.append(insight)
            logger.info("Generated insight: '%s' (confidence=%.2f)", insight.title, insight.confidence)

        except Exception as exc:
            logger.error("Insight generation failed for cluster '%s': %s", cluster["category"], exc)

    logger.info("Generator: %d clusters → %d insights.", len(clusters), len(insights))
    return insights
