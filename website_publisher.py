"""
Website publisher — syncs a generated blog post to the phoenixsolution repo.

Steps:
  1. copy_blog_to_website   — copies HTML file to /blog/{slug}.html
  2. copy_image_to_website  — copies image to /blog/images/{slug}.jpg
  3. update_blog_index      — injects card at top of .blog-grid in blog/index.html
  4. update_sitemap         — adds <url> entry to sitemap.xml
  5. git_push_website       — git add / commit / push
  6. wait_for_live          — polls URL until HTTP 200 (or timeout)

publish_to_website() orchestrates steps 1-4 and returns {'blog_url', 'image_public_url'}.
"""

import os
import re
import math
import shutil
import logging
import subprocess
import time

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

WEBSITE_REPO = os.getenv('WEBSITE_REPO_PATH', r'C:\Projects\phoenixsolution')
BLOG_DIR     = os.path.join(WEBSITE_REPO, 'blog')
IMAGES_DIR   = os.path.join(WEBSITE_REPO, 'blog', 'images')
INDEX_HTML   = os.path.join(WEBSITE_REPO, 'blog', 'index.html')
SITEMAP_XML  = os.path.join(WEBSITE_REPO, 'sitemap.xml')
BASE_URL     = 'https://www.phoenixsolution.in'


# ── helpers ───────────────────────────────────────────────────────────────────

def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def _write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def _read_time(blog_data):
    words = ' '.join([
        blog_data.get('intro', ''),
        *[s['body'] for s in blog_data.get('sections', [])],
        blog_data.get('conclusion', ''),
    ]).split()
    mins = max(1, math.ceil(len(words) / 200))
    return '{} min read'.format(mins)


def _month_year(iso_date):
    from datetime import datetime
    try:
        return datetime.strptime(iso_date, '%Y-%m-%d').strftime('%b %Y')
    except Exception:
        return iso_date


# ── step 1 ────────────────────────────────────────────────────────────────────

def copy_blog_to_website(src_html_path, slug):
    """Copy dated blog HTML to website blog dir as {slug}.html."""
    os.makedirs(BLOG_DIR, exist_ok=True)
    dest = os.path.join(BLOG_DIR, slug + '.html')
    shutil.copy2(src_html_path, dest)
    logger.info('Copied blog: %s -> %s', src_html_path, dest)
    return dest


# ── step 2 ────────────────────────────────────────────────────────────────────

def copy_image_to_website(local_path, slug):
    """Copy image to website blog/images dir, return public URL."""
    os.makedirs(IMAGES_DIR, exist_ok=True)
    dest = os.path.join(IMAGES_DIR, slug + '.jpg')
    shutil.copy2(local_path, dest)
    logger.info('Copied image: %s -> %s', local_path, dest)
    return BASE_URL + '/blog/images/' + slug + '.jpg'


# ── step 3 ────────────────────────────────────────────────────────────────────

def update_blog_index(blog_data, slug, publish_date):
    """Insert a new blog card at the top of .blog-grid in blog/index.html."""
    html = _read(INDEX_HTML)

    # Count existing article cards for numbering
    article_count = len(re.findall(r'<!--\s*──\s*ARTICLE\s+\d+', html))
    article_num   = article_count + 1

    tag_emoji = blog_data.get('tag_emoji', '')
    category  = blog_data.get('category', 'Analytics')
    title     = blog_data.get('title', '')
    excerpt   = blog_data.get('meta_description', '')
    read_time = _read_time(blog_data)
    mon_year  = _month_year(publish_date)

    card = (
        '\n      <!-- \u2500\u2500 ARTICLE {num} \u2500\u2500 -->\n'
        '      <a href="/blog/{slug}" class="blog-card reveal">\n'
        '        <div class="blog-card-header">\n'
        '          <span class="blog-tag">{tag} {cat}</span>\n'
        '          <div class="blog-title">{title}</div>\n'
        '          <p class="blog-excerpt">{excerpt}</p>\n'
        '        </div>\n'
        '        <div class="blog-card-footer">\n'
        '          <span class="blog-meta">{rt} \u00b7 {my}</span>\n'
        '          <span class="blog-read-link">Read <span>\u2192</span></span>\n'
        '        </div>\n'
        '      </a>\n'
    ).format(
        num=article_num, slug=slug, tag=tag_emoji, cat=category,
        title=title, excerpt=excerpt, rt=read_time, my=mon_year,
    )

    # Inject after <div class="blog-grid">
    updated = html.replace('<div class="blog-grid">', '<div class="blog-grid">' + card, 1)
    if updated == html:
        logger.warning('Could not find <div class="blog-grid"> in index.html')
    _write(INDEX_HTML, updated)
    logger.info('Updated blog/index.html with card for %s', slug)


# ── step 4 ────────────────────────────────────────────────────────────────────

def update_sitemap(slug, iso_date):
    """Insert a new <url> entry into sitemap.xml before </urlset>."""
    xml = _read(SITEMAP_XML)
    entry = (
        '\n  <url>\n'
        '    <loc>{base}/blog/{slug}</loc>\n'
        '    <lastmod>{date}</lastmod>\n'
        '    <changefreq>monthly</changefreq>\n'
        '    <priority>0.75</priority>\n'
        '  </url>\n'
    ).format(base=BASE_URL, slug=slug, date=iso_date)

    updated = xml.replace('</urlset>', entry + '</urlset>')
    _write(SITEMAP_XML, updated)
    logger.info('Updated sitemap.xml with %s/blog/%s', BASE_URL, slug)


# ── step 5 ────────────────────────────────────────────────────────────────────

def git_push_website(slug, title):
    """git add + commit + push in the website repo. Returns (returncode, out, err)."""
    files = [
        os.path.join('blog', slug + '.html'),
        os.path.join('blog', 'index.html'),
        'sitemap.xml',
    ]
    image_rel = os.path.join('blog', 'images', slug + '.jpg')
    if os.path.exists(os.path.join(WEBSITE_REPO, image_rel)):
        files.append(image_rel)

    def _run(args, timeout=30):
        return subprocess.run(
            args, cwd=WEBSITE_REPO,
            capture_output=True, text=True, timeout=timeout,
        )

    add = _run(['git', 'add'] + files)
    if add.returncode != 0:
        logger.error('git add failed: %s', add.stderr)
        return add.returncode, add.stdout, add.stderr

    commit = _run(['git', 'commit', '-m', 'Add blog: ' + title])
    if commit.returncode != 0:
        logger.error('git commit failed: %s', commit.stderr)
        return commit.returncode, commit.stdout, commit.stderr

    try:
        push = _run(['git', 'push'], timeout=60)
        logger.info('git push: rc=%d  %s', push.returncode, push.stdout.strip())
        return push.returncode, push.stdout, push.stderr
    except subprocess.TimeoutExpired:
        logger.error('git push timed out after 60 seconds')
        return 1, '', 'git push timed out'


# ── step 6 ────────────────────────────────────────────────────────────────────

def wait_for_live(url, retries=10, delay=20):
    """
    Poll GET url every delay seconds up to retries times.
    Returns True when HTTP 200 received, False on timeout.
    """
    logger.info('Waiting for %s to go live...', url)
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                logger.info('URL is live after %d attempt(s)', attempt)
                return True
        except Exception:
            pass
        logger.info('Attempt %d/%d — not live yet, retrying in %ds', attempt, retries, delay)
        time.sleep(delay)
    logger.warning('URL did not go live within timeout: %s', url)
    return False


# ── orchestrator ──────────────────────────────────────────────────────────────

def publish_to_website(blog_data, src_html_path, publish_date, image_local=None):
    """
    Full website sync: copy HTML, copy image, update index, update sitemap.
    Returns {'blog_url': str, 'image_public_url': str | None}
    """
    slug = blog_data['slug']

    copy_blog_to_website(src_html_path, slug)

    image_public_url = None
    if image_local and os.path.exists(image_local):
        image_public_url = copy_image_to_website(image_local, slug)

    update_blog_index(blog_data, slug, publish_date)
    update_sitemap(slug, publish_date)

    blog_url = BASE_URL + '/blog/' + slug
    return {'blog_url': blog_url, 'image_public_url': image_public_url}
