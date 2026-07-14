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
