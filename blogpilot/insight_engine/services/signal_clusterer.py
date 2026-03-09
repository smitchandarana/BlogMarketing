"""Signal Clusterer — groups related signals into topic clusters.

Two-pass algorithm (zero external dependencies):
  Pass 1: group by category tag (already on every signal from Phase 2)
  Pass 2: within each category, sub-cluster by keyword Jaccard similarity

Each cluster is a dict:
    {
        "category": str,
        "keywords": set[str],
        "signals": list[Signal],
    }
"""

from __future__ import annotations

import logging
import re
from blogpilot.signal_engine.models.signal import Signal

logger = logging.getLogger(__name__)

# Words that carry no topical meaning — excluded from keyword sets
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "it", "its", "this", "that", "how", "why", "what", "when", "who",
    "will", "can", "new", "top", "best", "more", "most", "get", "use",
    "using", "used", "your", "our", "their", "has", "have", "had",
    "not", "no", "as", "up", "do", "did", "about", "into", "than",
}

_MIN_CLUSTER_SIZE = 2       # Clusters smaller than this are kept but low-priority
_JACCARD_THRESHOLD = 0.15   # Min keyword overlap to merge two signals


def _extract_keywords(text: str) -> set[str]:
    """Lowercase, strip punctuation, remove stopwords."""
    tokens = re.findall(r"[a-z]{3,}", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster(signals: list[Signal]) -> list[dict]:
    """Group signals into topic clusters.

    Args:
        signals: List of Signal objects (any status).

    Returns:
        List of cluster dicts, each with 'category', 'keywords', 'signals'.
        Sorted by cluster size descending.
    """
    if not signals:
        return []

    # Pass 1: group by category
    by_category: dict[str, list[Signal]] = {}
    for sig in signals:
        by_category.setdefault(sig.category, []).append(sig)

    clusters: list[dict] = []

    for category, group in by_category.items():
        # Attach keyword set to each signal (transient, not persisted)
        kw_map: dict[int, set[str]] = {
            i: _extract_keywords(sig.title + " " + sig.summary)
            for i, sig in enumerate(group)
        }

        visited = [False] * len(group)

        # Pass 2: greedy keyword-similarity sub-clustering
        for i in range(len(group)):
            if visited[i]:
                continue
            visited[i] = True
            cluster_indices = [i]
            cluster_kw = set(kw_map[i])

            for j in range(i + 1, len(group)):
                if visited[j]:
                    continue
                if _jaccard(kw_map[i], kw_map[j]) >= _JACCARD_THRESHOLD:
                    visited[j] = True
                    cluster_indices.append(j)
                    cluster_kw |= kw_map[j]

            clusters.append({
                "category": category,
                "keywords": cluster_kw,
                "signals": [group[idx] for idx in cluster_indices],
            })

    # Sort: largest clusters first (more signals = stronger trend signal)
    clusters.sort(key=lambda c: len(c["signals"]), reverse=True)
    logger.info(
        "Clusterer: %d signals → %d clusters (categories: %s).",
        len(signals),
        len(clusters),
        list(by_category.keys()),
    )
    return clusters
