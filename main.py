#!/usr/bin/env python3
"""
Blog Marketing Automation — CLI entry point.

Commands:
    python main.py generate [--topic "..."] [--publish]
    python main.py publish  [--id <post_id>]
    python main.py schedule [--list] [--set-id <id> --status <status>]
                            [--hour <h>] [--minute <m>]
"""

import argparse
import logging
import sqlite3
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('blog_marketing.log', encoding='utf-8'),
    ],
)
logger = logging.getLogger(__name__)


# ── Lazy imports keep startup fast ──────────────────────────────────────────

def _imports():
    from database import init_db, insert_post, update_post_status, get_post_by_id, get_scheduled_posts, get_all_posts
    from blog_generator import generate_blog
    from html_renderer import save_blog
    from linkedin_generator import generate_linkedin_post, save_linkedin_post
    from linkedin_publisher import publish_post
    from scheduler import start_scheduler
    from trend_research import get_trending_topics
    from image_fetcher import fetch_image
    from website_publisher import publish_to_website, git_push_website
    from tracker import add_entry as tracker_add_entry
    return {
        'init_db': init_db,
        'insert_post': insert_post,
        'update_post_status': update_post_status,
        'get_post_by_id': get_post_by_id,
        'get_scheduled_posts': get_scheduled_posts,
        'get_all_posts': get_all_posts,
        'generate_blog': generate_blog,
        'save_blog': save_blog,
        'generate_linkedin_post': generate_linkedin_post,
        'save_linkedin_post': save_linkedin_post,
        'publish_post': publish_post,
        'start_scheduler': start_scheduler,
        'get_trending_topics': get_trending_topics,
        'fetch_image': fetch_image,
        'publish_to_website': publish_to_website,
        'git_push_website': git_push_website,
        'tracker_add_entry': tracker_add_entry,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _do_publish(m, post_id: int, full_text: str, image_path=None):
    import os
    try:
        print(f'  Publishing post ID {post_id} to LinkedIn...')
        org_urn = os.getenv('LINKEDIN_ORG_URN', '').strip() or None
        m['publish_post'](full_text, image_path=image_path, org_urn=org_urn)
        m['update_post_status'](post_id, 'posted')
        logger.info('Published post ID %d', post_id)
        print('  Done — post is live.')
    except Exception as exc:
        logger.error('Publish failed for post ID %d: %s', post_id, exc)
        print(f'  Publish failed: {exc}')


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_generate(args, m):
    topic = args.topic

    if not topic:
        print('Fetching trending topic ideas...')
        topics = m['get_trending_topics']()
        print()
        for i, t in enumerate(topics, 1):
            print(f'  {i}. {t}')
        print()
        choice = input('Select a number or type your own topic: ').strip()
        if choice.isdigit() and 1 <= int(choice) <= len(topics):
            topic = topics[int(choice) - 1]
        else:
            topic = choice

    if not topic:
        print('No topic provided. Exiting.')
        return

    print(f'\nGenerating blog: "{topic}"')
    blog_data = m['generate_blog'](topic)
    slug = blog_data['slug']
    print(f'  Title   : {blog_data["title"]}')
    print(f'  Slug    : {slug}')

    publish_date = datetime.now().strftime('%Y-%m-%d')
    blog_path = m['save_blog'](blog_data, publish_date)
    print(f'  Saved   : {blog_path}')

    # Fetch image from Unsplash
    print('  Fetching image...')
    image_info = m['fetch_image'](blog_data.get('keywords', []), slug)
    image_local = image_info['local_path'] if image_info else None
    if image_info:
        print(f'  Image   : {image_info["public_url"]}')
    else:
        print('  Image   : none (UNSPLASH_ACCESS_KEY not set or fetch failed)')

    # Publish to website: copy HTML + image, update blog grid, update sitemap
    print('  Publishing to website...')
    pub_result = m['publish_to_website'](blog_data, blog_path, publish_date, image_local)
    blog_url = pub_result['blog_url']
    print(f'  Blog URL: {blog_url}')

    # Git push to deploy
    print('  Pushing to GitHub...')
    rc, out, err = m['git_push_website'](slug, blog_data['title'])
    if rc == 0:
        print('  Deployed.')
    else:
        print(f'  Git push failed (rc={rc}): {err[:200]}')

    # Generate LinkedIn post
    print('  Generating LinkedIn post...')
    li = m['generate_linkedin_post'](topic, blog_data)
    print(f'  Caption : {len(li["caption"].split())} words  |  Hashtags: {li["hashtags"]}')

    # Save LinkedIn post TXT file
    li_path = m['save_linkedin_post'](li, topic, publish_date=publish_date, blog_url=blog_url)
    print(f'  LI file : {li_path}')

    # Store in SQLite database
    post_id = m['insert_post'](
        topic=topic,
        blog_path=blog_path,
        linkedin_text=li['caption'],
        hashtags=li['hashtags'],
        status='draft',
        publish_date=publish_date,
    )

    # Store in tracker.csv so smart_scheduler can pick it up
    m['tracker_add_entry'](
        topic=topic,
        blog_path=blog_path,
        linkedin_path=li_path,
        hashtags=li['hashtags'],
        website_url=blog_url,
    )

    li_full = f'{li["caption"]}\n\nRead the full article: {blog_url}\n\n{li["hashtags"]}'
    print(f'\nStored as post ID {post_id} (status: draft)')
    print('\n--- LinkedIn Preview ---')
    print(li_full)
    print('------------------------\n')

    if args.publish:
        _do_publish(m, post_id, li_full, image_local)


def cmd_publish(args, m):
    if args.id:
        post = m['get_post_by_id'](args.id)
        if not post:
            print(f'Post ID {args.id} not found.')
            return
        posts = [post]
    else:
        posts = m['get_scheduled_posts']()

    if not posts:
        print('No posts to publish. Use --id <n> or set a post status to "scheduled".')
        return

    for post in posts:
        full_text = f"{post['linkedin_text']}\n\n{post['hashtags']}"
        _do_publish(m, post['id'], full_text)


def cmd_schedule(args, m):
    if args.list:
        posts = m['get_all_posts']()
        if not posts:
            print('No posts in database.')
            return
        print(f'\n{"ID":<5} {"Status":<12} {"Date":<12} {"Topic"}')
        print('-' * 72)
        for p in posts:
            print(f'{p["id"]:<5} {p["status"]:<12} {(p["publish_date"] or ""):<12} {p["topic"][:45]}')
        print()
        return

    if args.set_id is not None and args.status:
        m['update_post_status'](args.set_id, args.status)
        print(f'Post {args.set_id} status updated to: {args.status}')
        return

    hour = args.hour if args.hour is not None else 9
    minute = args.minute if args.minute is not None else 0
    print(f'Starting scheduler (daily at {hour:02d}:{minute:02d} IST). Press Ctrl+C to stop.')
    m['start_scheduler'](hour=hour, minute=minute)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Blog Marketing Automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest='command', required=True)

    # generate
    gen = sub.add_parser('generate', help='Generate blog + LinkedIn post')
    gen.add_argument('--topic', '-t', help='Blog topic (omit to pick from trending list)')
    gen.add_argument('--publish', '-p', action='store_true', help='Publish to LinkedIn immediately')

    # publish
    pub = sub.add_parser('publish', help='Publish post(s) to LinkedIn')
    pub.add_argument('--id', type=int, help='Publish a specific post by ID (otherwise publishes all scheduled)')

    # schedule
    sch = sub.add_parser('schedule', help='Manage scheduled posts or run the scheduler')
    sch.add_argument('--list', '-l', action='store_true', help='List all posts')
    sch.add_argument('--set-id', type=int, dest='set_id', help='Post ID to update status')
    sch.add_argument('--status', choices=['draft', 'scheduled', 'posted'], help='New status for --set-id')
    sch.add_argument('--hour', type=int, help='Scheduler run hour, 0-23 (default: 9)')
    sch.add_argument('--minute', type=int, help='Scheduler run minute, 0-59 (default: 0)')

    args = parser.parse_args()

    m = _imports()
    m['init_db']()

    if args.command == 'generate':
        cmd_generate(args, m)
    elif args.command == 'publish':
        cmd_publish(args, m)
    elif args.command == 'schedule':
        cmd_schedule(args, m)


if __name__ == '__main__':
    main()
