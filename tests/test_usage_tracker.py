"""
Unit tests for usage_tracker, llm_client.chat_completion retry behaviour,
daily_pipeline status honesty, and distribution_worker failure handling.

These are pure unit tests — they do NOT need the live API server that
conftest.py's `api` fixture requires.
"""
from __future__ import annotations

import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Point database.DB_PATH (used by usage_tracker) at a throwaway file."""
    import database
    import usage_tracker

    monkeypatch.setattr(database, 'DB_PATH', str(tmp_path / 'test.db'))
    monkeypatch.setattr(usage_tracker, '_table_ready', False)
    return database


# ── usage_tracker ─────────────────────────────────────────────────────────────

def test_record_and_get_usage(temp_db):
    import usage_tracker as ut

    ut.record('groq', tokens=100, success=True)
    ut.record('groq', tokens=50, success=True)
    ut.record('groq', tokens=0, success=False)  # failures don't count vs limit

    snap = ut.get_usage('groq')
    row = snap['services']['groq']
    assert row['used'] == 2
    assert row['tokens'] == 150
    assert row['limit'] == 500
    assert row['remaining'] == 498


def test_check_blocks_at_limit(temp_db, monkeypatch):
    import usage_tracker as ut

    monkeypatch.setattr(ut, 'get_limits', lambda: {'linkedin': 2})
    assert ut.check('linkedin')
    ut.record('linkedin', event='post', success=True)
    ut.record('linkedin', event='post', success=True)
    assert not ut.check('linkedin')


def test_seconds_until_reset_bounds(temp_db):
    import usage_tracker as ut

    s = ut.seconds_until_reset()
    assert 0 < s <= 86400


def test_usage_limit_error_fields(temp_db):
    import usage_tracker as ut

    err = ut.UsageLimitError('groq', 3600)
    assert err.service == 'groq'
    assert err.retry_after_seconds == 3600
    assert 'groq' in str(err)


# ── llm_client.chat_completion ────────────────────────────────────────────────

class _FakeUsage:
    total_tokens = 42


class _FakeResponse:
    usage = _FakeUsage()

    class _Choice:
        class _Msg:
            content = '{"ok": true}'
        message = _Msg()
    choices = [_Choice()]


def test_chat_completion_records_usage(temp_db, monkeypatch):
    import llm_client
    import usage_tracker as ut

    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(
            completions=types.SimpleNamespace(create=lambda **kw: _FakeResponse())
        )
    )
    monkeypatch.setattr(llm_client, 'get_client', lambda: fake_client)

    out = llm_client.chat_completion(messages=[{'role': 'user', 'content': 'hi'}])
    assert out == '{"ok": true}'
    assert ut.get_usage('groq')['services']['groq']['tokens'] == 42


def test_chat_completion_retries_on_429_then_succeeds(temp_db, monkeypatch):
    import llm_client

    class FakeRateLimitError(Exception):
        pass

    monkeypatch.setattr(llm_client, 'RateLimitError', FakeRateLimitError)
    monkeypatch.setattr(llm_client.time, 'sleep', lambda s: None)

    calls = {'n': 0}

    def create(**kw):
        calls['n'] += 1
        if calls['n'] == 1:
            raise FakeRateLimitError('rate limit — please try again in 1.0s')
        return _FakeResponse()

    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    monkeypatch.setattr(llm_client, 'get_client', lambda: fake_client)

    out = llm_client.chat_completion(messages=[{'role': 'user', 'content': 'hi'}])
    assert out == '{"ok": true}'
    assert calls['n'] == 2


def test_chat_completion_daily_quota_raises_usage_limit(temp_db, monkeypatch):
    import llm_client
    from usage_tracker import UsageLimitError

    class FakeRateLimitError(Exception):
        pass

    monkeypatch.setattr(llm_client, 'RateLimitError', FakeRateLimitError)

    def create(**kw):
        raise FakeRateLimitError('tokens per day limit exceeded, try again in 120m0s')

    fake_client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    monkeypatch.setattr(llm_client, 'get_client', lambda: fake_client)

    with pytest.raises(UsageLimitError):
        llm_client.chat_completion(messages=[{'role': 'user', 'content': 'hi'}])


def test_chat_completion_blocked_when_local_limit_hit(temp_db, monkeypatch):
    import llm_client
    import usage_tracker as ut
    from usage_tracker import UsageLimitError

    monkeypatch.setattr(ut, 'get_limits', lambda: {'groq': 0})
    with pytest.raises(UsageLimitError):
        llm_client.chat_completion(messages=[{'role': 'user', 'content': 'hi'}])


# ── daily_pipeline status honesty ─────────────────────────────────────────────

def test_dry_run_does_not_log_posted(temp_db, monkeypatch, tmp_path):
    import automation.daily_pipeline as dp
    import tracker
    import database

    monkeypatch.setattr(dp, '_research_is_fresh', lambda *a, **k: True)

    fake_ligen = types.ModuleType('linkedin_generator')
    fake_ligen.generate_linkedin_post = lambda topic, blog_data=None: {
        'caption': 'body', 'hashtags': '#A #B', 'full_post': 'x', 'blog_url': ''
    }
    li_file = tmp_path / 'post.txt'
    li_file.write_text('body', encoding='utf-8')
    fake_ligen.save_linkedin_post = lambda *a, **k: str(li_file)
    monkeypatch.setitem(sys.modules, 'linkedin_generator', fake_ligen)

    captured: dict = {}

    def fake_add_entry(**kwargs):
        captured['tracker_status'] = kwargs.get('status')
        return 1

    def fake_insert_post(**kwargs):
        captured['db_status'] = kwargs.get('status')
        return 1

    monkeypatch.setattr(tracker, 'add_entry', fake_add_entry)
    monkeypatch.setattr(database, 'insert_post', fake_insert_post)

    result = dp.run(topic='Test Topic', content_types=['li_only'], dry_run=True)

    assert result['error'] is None
    assert result['published_linkedin'] is False
    assert captured['tracker_status'] == 'draft'
    assert captured['db_status'] == 'draft'


def test_hashtags_str_handles_string_and_list():
    from automation.daily_pipeline import _hashtags_str

    assert _hashtags_str({'hashtags': '#A #B'}) == '#A #B'
    assert _hashtags_str({'hashtags': ['#A', '#B']}) == '#A #B'
    assert _hashtags_str({}) == ''


def test_blog_and_linkedin_publish_stores_string_blog_url(monkeypatch, tmp_path):
    """publish_to_website() returns {'blog_url': ..., 'image_public_url': ...} —
    daily_pipeline must unpack the 'blog_url' key, not store the whole dict.

    Regression test: the pipeline used to assign the raw dict returned by
    publish_to_website() straight into `blog_url` / result['blog_url'], which
    then got written into tracker.csv's website_url column and into the saved
    LinkedIn post text as the "Read the full article" link — corrupting both
    with a stringified Python dict instead of a real URL.
    """
    import automation.daily_pipeline as dp
    import blog_generator
    import html_renderer
    import image_fetcher
    import website_publisher
    import linkedin_generator
    import linkedin_publisher
    import tracker
    import database

    monkeypatch.setattr(dp, '_research_is_fresh', lambda *a, **k: True)

    fake_blog_data = {
        'title': 'Test Title', 'slug': 'test-slug',
        'meta_description': 'x' * 20, 'category': 'Analytics', 'tag_emoji': '\U0001F4A1',
        'keywords': ['a', 'b'], 'intro': 'intro text',
        'sections': [{'heading': 'H1', 'body': 'body1'}],
        'conclusion': 'the end', 'cta_headline': 'CTA', 'cta_subtext': 'sub',
        'related_service_url': '/x', 'related_service_name': 'X', 'related_service_desc': 'd',
    }
    monkeypatch.setattr(blog_generator, 'generate_blog', lambda topic, **k: fake_blog_data)

    blog_html_path = tmp_path / 'blog.html'
    blog_html_path.write_text('<html></html>', encoding='utf-8')
    monkeypatch.setattr(html_renderer, 'save_blog', lambda *a, **k: str(blog_html_path))
    monkeypatch.setattr(image_fetcher, 'fetch_image', lambda *a, **k: None)

    real_blog_url = 'https://www.phoenixsolution.in/blog/test-slug'
    monkeypatch.setattr(
        website_publisher, 'publish_to_website',
        lambda *a, **k: {'blog_url': real_blog_url, 'image_public_url': None},
    )
    monkeypatch.setattr(website_publisher, 'git_push_website', lambda *a, **k: (0, '', ''))

    li_file = tmp_path / 'post.txt'
    li_file.write_text('body', encoding='utf-8')
    captured_save_blog_url = {}

    def fake_save_linkedin_post(li_data, topic, calendar_day=None, publish_date=None, blog_url=None):
        captured_save_blog_url['blog_url'] = blog_url
        return str(li_file)

    monkeypatch.setattr(
        linkedin_generator, 'generate_linkedin_post',
        lambda topic, blog_data=None: {
            'caption': 'body', 'hashtags': '#A #B', 'full_post': 'x', 'blog_url': ''
        },
    )
    monkeypatch.setattr(linkedin_generator, 'save_linkedin_post', fake_save_linkedin_post)
    monkeypatch.setattr(linkedin_publisher, 'publish_post', lambda *a, **k: {'id': 'urn:li:share:1'})

    captured: dict = {}
    monkeypatch.setattr(
        tracker, 'add_entry',
        lambda **kw: captured.setdefault('tracker_website_url', kw.get('website_url')) or 1,
    )
    monkeypatch.setattr(
        database, 'insert_post',
        lambda **kw: captured.setdefault('db_status', kw.get('status')) or 1,
    )

    result = dp.run(topic='Test Topic', content_types=['blog_and_linkedin'], publish=True)

    assert result['error'] is None
    assert result['blog_url'] == real_blog_url
    assert isinstance(result['blog_url'], str)
    assert captured_save_blog_url['blog_url'] == real_blog_url
    assert captured['tracker_website_url'] == real_blog_url


# ── topic_researcher now routes through the shared usage-limited client ───────

def test_synthesise_from_reddit_respects_daily_groq_limit(temp_db, monkeypatch):
    """synthesise_from_reddit/synthesise_linkedin_topics used to call
    llm_client.get_client() directly, bypassing chat_completion()'s daily
    usage-limit check, retry/backoff, and token-usage recording. Now that
    they route through chat_completion(), a call made after the daily Groq
    budget is exhausted must be blocked (no live API call) instead of
    silently going straight to Groq.
    """
    import usage_tracker as ut
    import topic_researcher as tr

    monkeypatch.setattr(ut, 'get_limits', lambda: {'groq': 0})

    calls = {'n': 0}

    def fake_create(**kw):
        calls['n'] += 1
        raise AssertionError('Groq API should not be called once the daily limit is hit')

    import llm_client
    monkeypatch.setattr(
        llm_client, 'get_client',
        lambda: types.SimpleNamespace(
            chat=types.SimpleNamespace(
                completions=types.SimpleNamespace(create=fake_create)
            )
        ),
    )

    topics = tr.synthesise_from_reddit([{'subreddit': 'PowerBI', 'score': 10, 'title': 'x'}])
    assert topics == []
    assert calls['n'] == 0

    topics2 = tr.synthesise_linkedin_topics(n=3)
    assert topics2 == []
    assert calls['n'] == 0


# ── distribution_queue.get_due() timestamp-format bug ─────────────────────────

def test_get_due_finds_past_due_iso_timestamp(tmp_path):
    """distribution_planner stores scheduled_at as datetime.isoformat() + "Z"
    (e.g. "2026-07-18T07:01:27.741835Z"). SQLite's datetime('now') returns
    "2026-07-18 07:01:27" (space separator, no fractional seconds, no 'Z').
    A raw string comparison ('T' sorts after ' ' in ASCII) makes same-day
    scheduled items compare as "in the future" no matter their actual time,
    so get_due() silently skipped every item scheduled for later "today"
    until the calendar date rolled over. This regression test inserts a job
    scheduled 1 hour in the past and asserts get_due() returns it.
    """
    from datetime import datetime, timedelta
    import blogpilot.db.migrations as migrations
    import blogpilot.db.repositories.content as content_repo
    import blogpilot.db.repositories.distribution as dist_repo
    from blogpilot.content_engine.models.content_model import Content
    from blogpilot.distribution_engine.models.distribution_queue_model import DistributionQueue

    db_path = str(tmp_path / 'dist_test.db')
    migrations.run_migrations(db_path)

    content_ids = [
        content_repo.insert(Content(content_type='linkedin_post', topic='t'), db_path=db_path)
        for _ in range(3)
    ]

    past_due = (datetime.utcnow() - timedelta(hours=1)).isoformat() + 'Z'
    future = (datetime.utcnow() + timedelta(hours=1)).isoformat() + 'Z'

    dist_repo.insert(
        DistributionQueue(content_id=content_ids[0], channel='linkedin', scheduled_time=past_due),
        db_path=db_path,
    )
    dist_repo.insert(
        DistributionQueue(content_id=content_ids[1], channel='linkedin', scheduled_time=future),
        db_path=db_path,
    )
    dist_repo.insert(
        DistributionQueue(content_id=content_ids[2], channel='website', scheduled_time=None),
        db_path=db_path,
    )

    due = dist_repo.get_due(db_path=db_path)
    due_content_ids = {d.content_id for d in due}

    assert content_ids[0] in due_content_ids, 'past-due ISO-timestamp job must be returned as due'
    assert content_ids[2] in due_content_ids, 'NULL scheduled_at (ASAP job) must be returned as due'
    assert content_ids[1] not in due_content_ids, 'future job must not be returned as due'


# ── distribution_planner no longer double-queues a broken LinkedIn promo job ──

def test_distribution_planner_does_not_duplicate_linkedin_for_blog_post():
    """distribution_planner used to queue a second 'linkedin' job that reused
    the blog_post's own content_id. distribution_worker then posted that
    content's raw `body` (the blog's intro paragraph — no hook, no hashtags,
    no article link) straight to LinkedIn as if it were a ready-made caption.
    content_planner already creates a dedicated, properly-captioned
    linkedin_post content row (and its own distribution job) for every
    insight, so the blog_post branch must only ever queue a 'website' job.
    """
    from blogpilot.distribution_engine.services.distribution_planner import plan

    jobs = plan(content_type='blog_post', content_id=42)

    assert len(jobs) == 1
    assert jobs[0]['channel'] == 'website'
    assert jobs[0]['content_id'] == 42
    assert not any(j['channel'] == 'linkedin' for j in jobs)


# ── distribution_worker failure handling ──────────────────────────────────────

def test_distribution_worker_marks_failed_on_publish_error(monkeypatch):
    import blogpilot.distribution_engine.workers.distribution_worker as dw
    import blogpilot.distribution_engine.services.linkedin_publisher_service as li_svc
    from blogpilot.distribution_engine.models.distribution_queue_model import (
        STATUS_FAILED, STATUS_PUBLISHED,
    )

    job = types.SimpleNamespace(id=1, content_id=10, channel='linkedin')
    content = types.SimpleNamespace(id=10, body='text', hashtags='#a',
                                    title='T', topic='t', file_path='',
                                    created_at='2026-07-14T00:00:00')

    statuses: list = []
    monkeypatch.setattr(dw.dist_repo, 'get_due', lambda db_path=None: [job])
    monkeypatch.setattr(dw.content_repo, 'get_by_id', lambda cid, db_path=None: content)
    monkeypatch.setattr(
        dw.dist_repo, 'update_status',
        lambda jid, status, **kw: statuses.append(('job', status)),
    )
    monkeypatch.setattr(
        dw.content_repo, 'update_status',
        lambda cid, status, db_path=None: statuses.append(('content', status)),
    )

    def failing_publish(text, image_path=None, org_urn=None):
        raise RuntimeError('LinkedIn API 401')

    monkeypatch.setattr(li_svc, 'publish', failing_publish)

    summary = dw.run_now()

    assert summary['jobs_failed'] == 1
    assert summary['jobs_published'] == 0
    assert ('job', STATUS_FAILED) in statuses
    assert ('content', 'published') not in statuses
    assert ('job', STATUS_PUBLISHED) not in statuses
