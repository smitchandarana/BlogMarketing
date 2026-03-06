import os
import re
import math
from datetime import datetime

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'Blogs', '_new-post.html')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'Blogs')


def _estimate_read_time(text: str) -> str:
    minutes = max(1, math.ceil(len(text.split()) / 200))
    return f'{minutes} min read'


def _build_sections_html(sections: list) -> str:
    parts = []
    for i, sec in enumerate(sections, 1):
        parts.append(f'    <!-- \u2500\u2500 SECTION {i} \u2500\u2500 -->')
        parts.append(f'    <h2 id="section-{i}">{sec["heading"]}</h2>')
        for para in sec['body'].strip().split('\n\n'):
            para = para.strip()
            if para:
                parts.append(f'    <p>{para}</p>')
        parts.append('')
    return '\n'.join(parts)


def _build_toc_html(sections: list) -> str:
    return '\n'.join(
        f'      <a href="#section-{i}" class="sidebar-toc-link">{sec["heading"]}</a>'
        for i, sec in enumerate(sections, 1)
    )


def render_blog(blog_data: dict, publish_date: str = None, image_url: str = None) -> str:
    if publish_date is None:
        publish_date = datetime.now().strftime('%Y-%m-%d')

    display_date = datetime.strptime(publish_date, '%Y-%m-%d').strftime('%B %d, %Y')
    all_text = ' '.join([
        blog_data['intro'],
        *[s['heading'] + ' ' + s['body'] for s in blog_data['sections']],
        blog_data['conclusion'],
    ])
    read_time = _estimate_read_time(all_text)
    keywords_str = ', '.join(blog_data.get('keywords', []))
    _default_emoji = '\U0001f4a1'
    tag = "{} {}".format(
        blog_data.get('tag_emoji', _default_emoji),
        blog_data.get('category', 'Analytics'),
    )

    with open(TEMPLATE_PATH, encoding='utf-8') as f:
        html = f.read()

    # Replace social / schema image tags with topic-specific image
    if image_url:
        html = re.sub(
            r'(<meta property="og:image"\s+content=")[^"]*(")',
            r'\g<1>' + image_url + r'\2',
            html,
        )
        html = re.sub(
            r'(<meta name="twitter:image"\s+content=")[^"]*(")',
            r'\g<1>' + image_url + r'\2',
            html,
        )
        html = re.sub(
            r'("image":\s*")[^"]*(")',
            r'\g<1>' + image_url + r'\2',
            html,
        )

    # --- Simple one-for-one replacements ---
    simple = {
        '[ARTICLE TITLE]': blog_data['title'],
        '[ARTICLE SLUG]': blog_data['slug'],
        '[META DESCRIPTION \u2014 150-160 characters describing the article]': blog_data['meta_description'],
        '[META DESCRIPTION]': blog_data['meta_description'],
        '[keyword1, keyword2, keyword3, keyword4]': keywords_str,
        '[keyword1, keyword2, keyword3]': keywords_str,
        '[TAG EMOJI + CATEGORY]': tag,
        '[PUBLISH DATE]': display_date,
        '[ISO DATE]': publish_date,
        '[READ TIME]': read_time,
        '[ARTICLE INTRO \u2014 2-3 opening paragraphs that set context and explain why this topic matters to your reader.]': blog_data['intro'],
        '[CLOSING PARAGRAPH \u2014 Summarize the key takeaway and transition to CTA.]': blog_data['conclusion'],
        '[RELATED SERVICE URL]': blog_data.get('related_service_url', '/services/business-intelligence'),
        '[RELATED SERVICE NAME]': blog_data.get('related_service_name', 'Our Services'),
        '[RELATED SERVICE DESC]': blog_data.get('related_service_desc', 'We build data solutions for your business.'),
        '[CTA HEADLINE \u2014 e.g. \u201cWant this applied to your business?\u201d]': blog_data.get('cta_headline', 'Want this applied to your business?'),
        '[CTA SUBTEXT \u2014 1-2 sentences connecting the article topic to booking a call.]': blog_data.get('cta_subtext', 'Book a free 30-minute call to discuss how we can help.'),
    }
    for placeholder, value in simple.items():
        html = html.replace(placeholder, value)

    # --- Sections block: replace from SECTION 1 comment to just before Closing section ---
    sections_html = _build_sections_html(blog_data['sections'])
    html = re.sub(
        r'<!-- \u2500\u2500 SECTION 1 \u2500\u2500.*?(?=\s*<!-- \u2500\u2500 Closing section)',
        sections_html + '\n\n    ',
        html,
        flags=re.DOTALL,
    )

    # --- TOC: replace links between the two comments ---
    toc_html = _build_toc_html(blog_data['sections'])
    html = re.sub(
        r'(<!-- Add one link per h2 section -->).*?(<!-- Add more as needed -->)',
        f'<!-- Add one link per h2 section -->\n{toc_html}\n      <!-- Add more as needed -->',
        html,
        flags=re.DOTALL,
    )

    return html


def save_blog(blog_data: dict, publish_date: str = None, image_url: str = None) -> str:
    if publish_date is None:
        publish_date = datetime.now().strftime('%Y-%m-%d')

    html = render_blog(blog_data, publish_date, image_url=image_url)
    filename = f'{publish_date}-{blog_data["slug"]}.html'
    output_path = os.path.join(OUTPUT_DIR, filename)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path
