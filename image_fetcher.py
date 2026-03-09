"""
Unsplash image fetcher.
Searches Unsplash by topic keywords, downloads the best result.
Falls back gracefully if no API key or network error.
"""

import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

UNSPLASH_API  = 'https://api.unsplash.com/search/photos'
from paths import app_dir
IMAGES_DIR    = os.path.join(app_dir(), 'Blogs', 'images')
BASE_PUB_URL  = 'https://www.phoenixsolution.in/blog/images'


def fetch_image(keywords, slug, blog_data=None):
    """
    Search Unsplash for a landscape image matching keywords, download it.

    Args:
        keywords:  List of SEO keyword strings from blog_data.
        slug:      URL slug used as the local filename ({slug}.jpg).
        blog_data: Optional full blog data dict — used to build a richer search query
                   from title + keywords combined.

    Returns dict with keys:
        local_path    -- absolute path to downloaded JPEG on disk
        public_url    -- URL the image will have once published to website
        photographer  -- credit name
        photographer_url -- Unsplash profile URL

    Returns None if UNSPLASH_ACCESS_KEY not set, or any error occurs.
    Skips the download (returns cached result) if the image already exists on disk.
    """
    access_key = os.getenv('UNSPLASH_ACCESS_KEY', '').strip()
    if not access_key:
        logger.info('UNSPLASH_ACCESS_KEY not set — skipping image fetch')
        return None

    # Return cached result if image already downloaded
    dest = os.path.join(IMAGES_DIR, slug + '.jpg')
    if os.path.exists(dest):
        logger.info('Image already exists — reusing: %s', dest)
        return {
            'local_path':       dest,
            'public_url':       BASE_PUB_URL + '/' + slug + '.jpg',
            'photographer':     'cached',
            'photographer_url': '',
        }

    # Build fallback query chain (most specific → most generic)
    kw = keywords or []
    category = (blog_data or {}).get('category', '') if blog_data else ''
    title_words = (blog_data or {}).get('title', '') if blog_data else ''

    # Attempt 1: title-level (most specific)
    q1_parts = [w for w in title_words.split() if len(w) > 4][:4] if title_words else []
    q1 = ' '.join(q1_parts) if q1_parts else None

    # Attempt 2: keyword-based
    q2 = ' '.join(kw[:3]) + ' business' if kw else None

    # Attempt 3: category-level
    q3 = (category + ' data analytics').strip() if category else 'data analytics office'

    # Attempt 4: reliable generic fallback
    q4 = 'business intelligence dashboard'

    fallback_queries = [q for q in [q1, q2, q3, q4] if q]

    def _search(q):
        r = requests.get(
            UNSPLASH_API,
            params={'query': q, 'orientation': 'landscape', 'per_page': 3},
            headers={'Authorization': 'Client-ID ' + access_key},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get('results', [])

    try:
        results = []
        used_query = ''
        for attempt_query in fallback_queries:
            results = _search(attempt_query)
            if results:
                used_query = attempt_query
                break
            logger.info('No Unsplash results for "%s" — trying next fallback', attempt_query)

        if not results:
            logger.warning('Unsplash returned no results after all fallbacks')
            return None

        photo     = results[0]
        image_url = photo['urls']['regular']
        photographer     = photo['user']['name']
        photographer_url = photo['user']['links']['html']

        # Download the image
        os.makedirs(IMAGES_DIR, exist_ok=True)
        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        with open(dest, 'wb') as f:
            f.write(img_resp.content)

        logger.info('Image saved: %s (query: "%s", by %s)', dest, used_query, photographer)
        return {
            'local_path':       dest,
            'public_url':       BASE_PUB_URL + '/' + slug + '.jpg',
            'photographer':     photographer,
            'photographer_url': photographer_url,
        }

    except Exception as exc:
        logger.warning('Image fetch failed: %s', exc)
        return None
