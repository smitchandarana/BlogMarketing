"""
tracker.py — CSV-based content tracker.
Every generated blog/LinkedIn post is logged here and updated on status change.
File: tracker.csv in the project root.
"""
import csv
import os
from datetime import datetime

from paths import app_dir
TRACKER_PATH = os.path.join(app_dir(), 'tracker.csv')

FIELDNAMES = [
    'id', 'generated_date', 'calendar_day', 'topic', 'content_angle',
    'blog_path', 'linkedin_path', 'hashtags', 'status', 'published_date', 'website_url',
]

# Valid status values in workflow order
STATUSES = ['planning', 'drafting', 'draft', 'scheduled', 'posted']


def _ensure_csv():
    if not os.path.exists(TRACKER_PATH):
        with open(TRACKER_PATH, 'w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()


def read_all() -> list:
    _ensure_csv()
    with open(TRACKER_PATH, 'r', newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _rewrite(rows: list):
    with open(TRACKER_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def add_entry(topic, blog_path, linkedin_path, hashtags,
              calendar_day=None, content_angle='', website_url='',
              status='draft'):
    """Append a new row and return the new entry id."""
    rows      = read_all()
    valid_ids = [int(r['id']) for r in rows if r.get('id', '').strip().isdigit()]
    new_id    = (max(valid_ids) + 1) if valid_ids else 1
    rows.append({
        'id':             new_id,
        'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'calendar_day':   calendar_day or '',
        'topic':          topic,
        'content_angle':  content_angle or '',
        'blog_path':      blog_path,
        'linkedin_path':  linkedin_path,
        'hashtags':       hashtags,
        'status':         status,
        'published_date': '',
        'website_url':    website_url or '',
    })
    _rewrite(rows)
    return new_id


def add_idea(topic, content_angle='', calendar_day=None):
    """Add a raw idea (no content yet) with status 'planning'."""
    return add_entry(
        topic=topic, blog_path='', linkedin_path='', hashtags='',
        calendar_day=calendar_day, content_angle=content_angle,
        website_url='', status='planning',
    )


def delete_entry(entry_id: int) -> bool:
    """Delete a row by ID. Returns True if found and deleted."""
    rows = read_all()
    new_rows = [r for r in rows if not (r.get('id', '').strip().isdigit()
                                        and int(r['id']) == entry_id)]
    if len(new_rows) == len(rows):
        return False
    _rewrite(new_rows)
    return True


def delete_entries(entry_ids: list) -> int:
    """Delete multiple rows by ID. Returns count deleted."""
    id_set = set(entry_ids)
    rows = read_all()
    new_rows = [r for r in rows if not (r.get('id', '').strip().isdigit()
                                        and int(r['id']) in id_set)]
    deleted = len(rows) - len(new_rows)
    _rewrite(new_rows)
    return deleted


def update_status(entry_id: int, status: str, published_date: str = None):
    rows = read_all()
    for row in rows:
        if row.get('id', '').strip().isdigit() and int(row['id']) == entry_id:
            row['status'] = status
            if published_date:
                row['published_date'] = published_date
    _rewrite(rows)


def get_entry(entry_id: int):
    for row in read_all():
        if row.get('id', '').strip().isdigit() and int(row['id']) == entry_id:
            return row
    return None
