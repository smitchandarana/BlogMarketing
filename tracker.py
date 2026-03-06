"""
tracker.py — CSV-based content tracker.
Every generated blog/LinkedIn post is logged here and updated on status change.
File: tracker.csv in the project root.
"""
import csv
import os
from datetime import datetime

TRACKER_PATH = os.path.join(os.path.dirname(__file__), 'tracker.csv')

FIELDNAMES = [
    'id', 'generated_date', 'calendar_day', 'topic', 'content_angle',
    'blog_path', 'linkedin_path', 'hashtags', 'status', 'published_date', 'website_url',
]


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
              calendar_day=None, content_angle='', website_url=''):
    """Append a new row and return the new entry id."""
    rows   = read_all()
    new_id = (max(int(r['id']) for r in rows) + 1) if rows else 1
    rows.append({
        'id':             new_id,
        'generated_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'calendar_day':   calendar_day or '',
        'topic':          topic,
        'content_angle':  content_angle or '',
        'blog_path':      blog_path,
        'linkedin_path':  linkedin_path,
        'hashtags':       hashtags,
        'status':         'draft',
        'published_date': '',
        'website_url':    website_url or '',
    })
    _rewrite(rows)
    return new_id


def update_status(entry_id: int, status: str, published_date: str = None):
    rows = read_all()
    for row in rows:
        if int(row['id']) == entry_id:
            row['status'] = status
            if published_date:
                row['published_date'] = published_date
    _rewrite(rows)


def get_entry(entry_id: int):
    for row in read_all():
        if int(row['id']) == entry_id:
            return row
    return None
