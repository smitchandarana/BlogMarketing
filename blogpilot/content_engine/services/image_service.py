"""Image Service — local Stable Diffusion with fallback to Unsplash.

Priority:
  1. Stable Diffusion local API (http://127.0.0.1:7860) if running
  2. Unsplash via existing image_fetcher.py
  3. None (content generated without image — always safe)
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))
_SD_API = os.getenv("STABLE_DIFFUSION_URL", "http://127.0.0.1:7860")


def generate(keywords: list[str] | str, slug: str = "") -> str | None:
    """Generate or fetch an image for the given keywords.

    Args:
        keywords: Topic keywords for image generation/search.
        slug:     Blog slug used as filename base.

    Returns:
        Absolute path to saved image file, or None.
    """
    kw_list = [keywords] if isinstance(keywords, str) else keywords

    # Try Stable Diffusion first
    path = _try_stable_diffusion(kw_list, slug)
    if path:
        return path

    # Fallback to Unsplash
    return _try_unsplash(kw_list, slug)


def _try_stable_diffusion(keywords: list[str], slug: str) -> str | None:
    """Attempt image generation via local Stable Diffusion AUTOMATIC1111 API."""
    try:
        import requests  # already in requirements
        # Quick health check — fail fast if SD not running
        health = requests.get(f"{_SD_API}/sdapi/v1/progress", timeout=2)
        if health.status_code != 200:
            return None

        prompt = ", ".join(keywords[:5]) + ", professional marketing, clean, modern"
        payload = {
            "prompt": prompt,
            "negative_prompt": "text, watermark, blurry, low quality",
            "steps": 20,
            "width": 1200,
            "height": 630,
            "cfg_scale": 7,
        }
        resp = requests.post(f"{_SD_API}/sdapi/v1/txt2img", json=payload, timeout=60)
        resp.raise_for_status()

        import base64
        from pathlib import Path
        images = resp.json().get("images", [])
        if not images:
            return None

        if _ROOT not in sys.path:
            sys.path.insert(0, _ROOT)

        try:
            from paths import app_dir  # type: ignore[import]
            img_dir = Path(app_dir()) / "Blogs" / "images"
        except ImportError:
            img_dir = Path(_ROOT) / "Blogs" / "images"

        img_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{slug or 'generated'}-sd.jpg"
        out_path = img_dir / fname

        with open(out_path, "wb") as f:
            f.write(base64.b64decode(images[0]))

        logger.info("Stable Diffusion image saved: %s", out_path)
        return str(out_path)

    except Exception as exc:
        logger.debug("Stable Diffusion unavailable: %s", exc)
        return None


def _try_unsplash(keywords: list[str], slug: str) -> str | None:
    """Fallback: fetch image from Unsplash via existing image_fetcher module."""
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    try:
        from image_fetcher import fetch_image  # type: ignore[import]
        path = fetch_image(keywords=keywords, slug=slug)
        if path:
            logger.info("Unsplash image fetched: %s", path)
        return path
    except Exception as exc:
        logger.debug("Unsplash fetch failed: %s", exc)
        return None
