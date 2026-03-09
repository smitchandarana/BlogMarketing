"""Centralised Prompt Loader — single point of access for all LLM prompts.

Loads prompt templates from `Prompts/` directory, supports variable injection,
and provides a registry for inline prompts used across the codebase.

Usage:
    from blogpilot.ai.prompt_loader import load_prompt, render_prompt

    # Load from file
    template = load_prompt("blog_prompt")
    rendered = render_prompt("blog_prompt", topic="AI in marketing", date="2026-03-09")

    # Load inline registered prompt
    rendered = render_prompt("signal_score", signals_text="1. AI trends...")
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Root directory of the project (4 levels up from this file)
_ROOT = Path(__file__).resolve().parents[2]
_PROMPTS_DIR = _ROOT / "Prompts"

# Cache loaded templates to avoid repeated file reads
_cache: dict[str, str] = {}

# ── Inline prompt registry ───────────────────────────────────────────────────
# Prompts that don't have their own file live here. Modules register via
# register_prompt() or they're defined below.

_INLINE_PROMPTS: dict[str, str] = {
    "signal_score": """\
You are a marketing intelligence analyst for Phoenix Solutions — an IT services and digital marketing agency based in India.

Rate each signal's relevance to Phoenix Solutions' business on a scale of 0-10:
- 10 = directly relevant (AI, digital marketing, web dev, SEO, social media, Indian SMB market)
- 5  = tangentially relevant (general tech, business, startups)
- 0  = irrelevant (unrelated industries, sports, entertainment)

Respond ONLY with a valid JSON array of integers matching the input order.
Example input count 3 → respond: [7, 2, 9]

Signals:
{signals_text}
""",
    "relevance_classify": """\
You are a LinkedIn engagement assistant. Score the relevance of this post to the niche: [{niche}].

Post text:
\"\"\"{post_text}\"\"\"

Return ONLY valid JSON with this shape:
{{"score": <float 0.0-1.0>, "reason": "<one sentence>"}}

Score 1.0 = directly on topic. Score 0.0 = completely off topic. No extra text.
""",
    "comment_generate": """\
You are a LinkedIn engagement specialist for {brand_name}.

Write a thoughtful, human-quality comment on this LinkedIn post. The comment should:
- Be 2-4 sentences long
- Add genuine value or insight to the discussion
- Sound natural and conversational (NOT generic or salesy)
- Reference a specific point from the post
- Avoid phrases like "Great post!", "Love this!", "Couldn't agree more"

Brand context: {brand_context}

Post by {author_name}:
\"\"\"{post_text}\"\"\"

Write ONLY the comment text, nothing else.
""",
    "insight_generate": """\
You are a strategic marketing analyst for Phoenix Solutions.

Analyse these signals and generate actionable marketing insights:
{signals_summary}

For each insight, provide:
1. A concise title
2. A 2-3 sentence summary of the opportunity
3. Specific action items Phoenix Solutions should take
4. Confidence level (0.0-1.0)

Return valid JSON:
[{{"title": "...", "summary": "...", "action_items": ["..."], "confidence": 0.8}}]
""",
}


def load_prompt(name: str) -> str:
    """Load a prompt template by name.

    Searches in order:
      1. File cache (previously loaded)
      2. Prompts/{name}.txt file
      3. Inline prompt registry

    Args:
        name: Prompt identifier (e.g. 'blog_prompt', 'signal_score').

    Returns:
        Raw template string with {variable} placeholders.

    Raises:
        FileNotFoundError: If no prompt found by that name.
    """
    # Check cache first
    if name in _cache:
        return _cache[name]

    # Try file-based prompt
    file_path = _PROMPTS_DIR / f"{name}.txt"
    if file_path.exists():
        template = file_path.read_text(encoding="utf-8").strip()
        _cache[name] = template
        logger.debug("Loaded prompt '%s' from %s.", name, file_path)
        return template

    # Try inline registry
    if name in _INLINE_PROMPTS:
        template = _INLINE_PROMPTS[name]
        _cache[name] = template
        logger.debug("Loaded inline prompt '%s'.", name)
        return template

    raise FileNotFoundError(
        f"Prompt '{name}' not found in {_PROMPTS_DIR} or inline registry."
    )


def render_prompt(name: str, **variables: str) -> str:
    """Load a prompt template and inject variables.

    Uses Python str.format() for {variable} placeholders. Undefined variables
    are left as-is (no KeyError).

    Args:
        name: Prompt identifier.
        **variables: Key-value pairs to inject into the template.

    Returns:
        Rendered prompt string.
    """
    template = load_prompt(name)

    # Use format_map with a default dict to avoid KeyError on missing keys
    class _SafeDict(dict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    return template.format_map(_SafeDict(**variables))


def register_prompt(name: str, template: str) -> None:
    """Register an inline prompt template at runtime.

    Args:
        name: Unique prompt identifier.
        template: Template string with {variable} placeholders.
    """
    _INLINE_PROMPTS[name] = template
    # Invalidate cache if exists
    _cache.pop(name, None)
    logger.debug("Registered inline prompt '%s'.", name)


def list_prompts() -> dict[str, str]:
    """Return all available prompt names and their source (file/inline).

    Returns:
        Dict mapping prompt name → source ('file' or 'inline').
    """
    result: dict[str, str] = {}

    # File-based prompts
    if _PROMPTS_DIR.exists():
        for f in _PROMPTS_DIR.glob("*.txt"):
            result[f.stem] = "file"

    # Inline prompts
    for name in _INLINE_PROMPTS:
        if name not in result:
            result[name] = "inline"

    return result


def clear_cache() -> None:
    """Clear the prompt template cache."""
    _cache.clear()
