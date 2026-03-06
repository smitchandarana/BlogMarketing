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
IMAGES_DIR    = os.path.join(os.path.dirname(__file__), 'Blogs', 'images')
BASE_PUB_URL  = 'https://www.phoenixsolution.in/blog/images'


def fetch_image(keywords, slug):
    """
    Search Unsplash for a landscape image matching keywords, download it.

    Returns dict with keys:
        local_path    -- absolute path to downloaded JPEG on disk
        public_url    -- URL the image will have once published to website
        photographer  -- credit name
        photographer_url -- Unsplash profile URL

    Returns None if UNSPLASH_ACCESS_KEY not set, or any error occurs.
    """
    access_key = os.getenv('UNSPLASH_ACCESS_KEY', '').strip()
    if not access_key:
        logger.info('UNSPLASH_ACCESS_KEY not set — skipping image fetch')
        return None

    # Use first 2 keywords, fall back to category-based generic terms
    kw    = keywords[:2] if keywords else []
    query = ' '.join(kw) if kw else slug.replace('-', ' ')[:40]

    # Fallback chain: specific → generic business → data analytics
    fallback_queries = [query, 'business technology', 'data analytics office']

    def _search(q):
        r = requests.get(
            UNSPLASH_API,
            params={'query': q, 'orientation': 'landscape', 'per_page': 1},
            headers={'Authorization': 'Client-ID ' + access_key},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get('results', [])

    try:
        results = []
        for attempt_query in fallback_queries:
            results = _search(attempt_query)
            if results:
                break
            logger.info('No Unsplash results for "%s", trying fallback', attempt_query)

        if not results:
            logger.warning('Unsplash returned no results after all fallbacks')
            return None

        photo     = results[0]
        image_url = photo['urls']['regular']
        photographer     = photo['user']['name']
        photographer_url = photo['user']['links']['html']

        # Download the image
        os.makedirs(IMAGES_DIR, exist_ok=True)
        dest = os.path.join(IMAGES_DIR, slug + '.jpg')

        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        with open(dest, 'wb') as f:
            f.write(img_resp.content)

        logger.info('Image saved: %s (by %s)', dest, photographer)
        return {
            'local_path':       dest,
            'public_url':       BASE_PUB_URL + '/' + slug + '.jpg',
            'photographer':     photographer,
            'photographer_url': photographer_url,
        }

    except Exception as exc:
        logger.warning('Image fetch failed: %s', exc)
        return None
