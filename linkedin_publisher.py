import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

LINKEDIN_API_BASE = 'https://api.linkedin.com/v2'
LINKEDIN_REST_BASE = 'https://api.linkedin.com/rest'


def _get_headers():
    token = os.getenv('LINKEDIN_ACCESS_TOKEN')
    if not token:
        raise EnvironmentError('LINKEDIN_ACCESS_TOKEN is not set in .env')
    return {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0',
    }


def authenticate():
    """
    Resolve and return the LinkedIn person URN.
    Uses LINKEDIN_PERSON_URN from .env if set; otherwise calls /userinfo.
    """
    urn = os.getenv('LINKEDIN_PERSON_URN', '').strip()
    if urn:
        logger.info('Using person URN from env: %s', urn)
        return urn

    resp = requests.get(
        LINKEDIN_API_BASE + '/userinfo',
        headers=_get_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    sub = resp.json().get('sub', '')
    if not sub:
        raise ValueError('Could not resolve LinkedIn person URN from /userinfo')
    urn = 'urn:li:person:' + sub
    logger.info('Resolved person URN: %s', urn)
    return urn


def upload_image_asset(image_path, person_urn):
    """
    Upload an image to LinkedIn via the Assets API (2-step).
    Returns the image URN string, or None on failure.
    """
    token = os.getenv('LINKEDIN_ACCESS_TOKEN', '')
    headers_upload = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
        'LinkedIn-Version': '202305',
    }

    # Step 1: register the upload
    try:
        reg_resp = requests.post(
            LINKEDIN_REST_BASE + '/images?action=initializeUpload',
            headers=headers_upload,
            json={'initializeUploadRequest': {'owner': person_urn}},
            timeout=15,
        )
        reg_resp.raise_for_status()
        data       = reg_resp.json().get('value', {})
        upload_url = data.get('uploadUrl', '')
        image_urn  = data.get('image', '')

        if not upload_url or not image_urn:
            logger.warning('Image upload init returned unexpected data: %s', reg_resp.text[:300])
            return None

        # Step 2: upload the image bytes
        with open(image_path, 'rb') as f:
            img_bytes = f.read()

        put_resp = requests.put(
            upload_url,
            data=img_bytes,
            headers={
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'image/jpeg',
            },
            timeout=30,
        )
        put_resp.raise_for_status()
        logger.info('Image uploaded to LinkedIn: %s', image_urn)
        return image_urn

    except Exception as exc:
        if hasattr(exc, 'response') and getattr(exc.response, 'status_code', None) == 426:
            logger.warning('LinkedIn Images API requires additional access (426) — posting text-only.')
        else:
            logger.warning('Image upload failed (will post text-only): %s', exc)
        return None


def publish_post(text, image_path=None, org_urn=None):
    """
    Post text (with optional image) to LinkedIn as a public UGC share.
    If org_urn is provided (e.g. 'urn:li:organization:12345'), also posts
    to that company page using the same content.
    Returns the personal profile API response dict.
    Falls back to text-only if image upload fails.
    """
    author_urn = authenticate()
    headers    = _get_headers()

    # Try image upload (owned by personal profile)
    image_urn = None
    if image_path and os.path.exists(image_path):
        image_urn = upload_image_asset(image_path, author_urn)

    def _build_payload(author):
        if image_urn:
            share_content = {
                'shareCommentary':    {'text': text},
                'shareMediaCategory': 'IMAGE',
                'media': [{
                    'status':      'READY',
                    'description': {'text': ''},
                    'media':       image_urn,
                    'title':       {'text': ''},
                }],
            }
        else:
            share_content = {
                'shareCommentary':    {'text': text},
                'shareMediaCategory': 'NONE',
            }
        return {
            'author':          author,
            'lifecycleState':  'PUBLISHED',
            'specificContent': {
                'com.linkedin.ugc.ShareContent': share_content,
            },
            'visibility': {
                'com.linkedin.ugc.MemberNetworkVisibility': 'PUBLIC',
            },
        }

    # Post to personal profile
    resp = requests.post(
        LINKEDIN_API_BASE + '/ugcPosts',
        headers=headers,
        json=_build_payload(author_urn),
        timeout=15,
    )
    if not resp.ok:
        logger.error('LinkedIn personal post failed %d: %s', resp.status_code, resp.text[:600])
        resp.raise_for_status()
    log_response(resp)
    personal_result = resp.json()

    # Optionally post to company page
    if org_urn:
        try:
            org_resp = requests.post(
                LINKEDIN_API_BASE + '/ugcPosts',
                headers=headers,
                json=_build_payload(org_urn),
                timeout=15,
            )
            if not org_resp.ok:
                logger.warning('Company page post failed %d: %s',
                               org_resp.status_code, org_resp.text[:600])
                org_resp.raise_for_status()
            log_response(org_resp)
            logger.info('Posted to company page: %s', org_urn)
        except Exception as exc:
            logger.warning('Company page post failed (personal post succeeded): %s', exc)

    return personal_result


def log_response(response):
    logger.info(
        'LinkedIn API %s %s — status %d — %s',
        response.request.method,
        response.request.url,
        response.status_code,
        response.text[:300],
    )
