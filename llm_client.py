"""
llm_client.py — Groq LLM client.
Model is configured via GROQ_MODEL in .env (default: llama-3.3-70b-versatile).

`chat_completion()` is the preferred entry point: it enforces the daily Groq
usage limit, retries on transient errors and per-minute 429s (honouring
retry-after), and records real token usage to usage_tracker.
"""
import logging
import re
import time

from groq import Groq, RateLimitError
from dotenv import load_dotenv

import os

load_dotenv()

logger = logging.getLogger(__name__)

_client = None

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (2.0, 4.0)
_MAX_RETRY_WAIT = 120.0


def get_client() -> Groq:
    """Return a lazily-initialised Groq client."""
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    return _client


def get_model() -> str:
    """Return the configured Groq model name."""
    return os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')


def _parse_retry_after(error: RateLimitError) -> tuple[bool, float]:
    """Parse a 429 into (is_daily_limit, retry_after_seconds)."""
    msg = str(error).lower()
    is_daily = 'per day' in msg or ' tpd' in msg or ' rpd' in msg
    retry_after = 10.0
    m = re.search(r'try again in (?:(\d+)m)?(\d+(?:\.\d+)?)s', msg)
    if m:
        retry_after = int(m.group(1) or 0) * 60 + float(m.group(2) or 0) + 1.0
    return is_daily, min(retry_after, _MAX_RETRY_WAIT)


def chat_completion(*, messages: list[dict], model: str | None = None,
                    temperature: float = 0.7,
                    response_format: dict | None = None,
                    max_tokens: int | None = None) -> str:
    """Run a Groq chat completion with usage limits, retry, and usage logging.

    Args:
        messages: Chat messages in OpenAI format.
        model: Model name; defaults to get_model().
        temperature: Sampling temperature.
        response_format: e.g. {'type': 'json_object'}.
        max_tokens: Optional completion cap.

    Returns:
        The first choice's message content (str).

    Raises:
        UsageLimitError: When today's Groq call budget or Groq's own daily
            quota is exhausted (retry_after_seconds says when to resume).
        Exception: The last underlying error after all retries fail.
    """
    from usage_tracker import UsageLimitError, check, record, seconds_until_reset

    if not check('groq'):
        raise UsageLimitError('groq', seconds_until_reset())

    kwargs: dict = {
        'model': model or get_model(),
        'messages': messages,
        'temperature': temperature,
    }
    if response_format is not None:
        kwargs['response_format'] = response_format
    if max_tokens is not None:
        kwargs['max_tokens'] = max_tokens

    last_error: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = get_client().chat.completions.create(**kwargs)
        except RateLimitError as exc:
            is_daily, retry_after = _parse_retry_after(exc)
            record('groq', success=False, detail=f'429 attempt {attempt}: {exc}'[:500])
            if is_daily:
                logger.error('Groq daily quota exhausted: %s', exc)
                raise UsageLimitError('groq', seconds_until_reset()) from exc
            last_error = exc
            if attempt < _MAX_ATTEMPTS:
                logger.warning('Groq 429 — sleeping %.0fs (attempt %d/%d)',
                               retry_after, attempt, _MAX_ATTEMPTS)
                time.sleep(retry_after)
        except Exception as exc:
            record('groq', success=False, detail=f'error attempt {attempt}: {exc}'[:500])
            last_error = exc
            if attempt < _MAX_ATTEMPTS:
                backoff = _BACKOFF_SECONDS[min(attempt - 1, len(_BACKOFF_SECONDS) - 1)]
                logger.warning('Groq call failed (%s) — retrying in %.0fs (attempt %d/%d)',
                               exc, backoff, attempt, _MAX_ATTEMPTS)
                time.sleep(backoff)
        else:
            usage = getattr(response, 'usage', None)
            record('groq', tokens=getattr(usage, 'total_tokens', 0) or 0, success=True)
            return response.choices[0].message.content or ''

    logger.error('Groq call failed after %d attempts: %s', _MAX_ATTEMPTS, last_error)
    raise last_error  # type: ignore[misc]
