#!/usr/bin/env python3
"""
Phoenix Solutions — Blog Marketing Automation GUI
Run:  python gui.py
"""

import os
import sys
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# ── Colours ────────────────────────────────────────────────────────────────────
NAVY        = '#0B1F3A'
NAVY_MID    = '#122B4A'
NAVY_LIGHT  = '#1A3A5C'
CYAN        = '#00C9DB'
CYAN_HOVER  = '#00E8FC'
WHITE       = '#F0F2F5'
WHITE60     = '#99A4B0'
WHITE40     = '#6B7A8D'
BORDER      = '#1E3D5F'
RED         = '#FF4D6A'
GREEN       = '#22D68A'
ORANGE      = '#FFB347'
FONT        = 'Segoe UI'

# ── GUI Log Handler ────────────────────────────────────────────────────────────

class _GUILogHandler(logging.Handler):
    """Forwards log records to a Tkinter ScrolledText widget (thread-safe)."""

    def __init__(self, widget):
        super().__init__()
        self._widget = widget
        self.setFormatter(logging.Formatter('%(asctime)s  %(levelname)-8s  %(message)s',
                                            datefmt='%H:%M:%S'))

    def emit(self, record):
        msg = self.format(record)
        level = record.levelno

        def _append():
            try:
                w = self._widget
                w.configure(state='normal')
                tag = 'err' if level >= logging.ERROR else ('warn' if level >= logging.WARNING else 'info')
                w.insert('end', msg + '\n', tag)
                w.see('end')
                w.configure(state='disabled')
            except Exception:
                pass

        try:
            self._widget.after(0, _append)
        except Exception:
            pass


# ── Lazy imports ───────────────────────────────────────────────────────────────
_mods = {}


def _m():
    if not _mods:
        from blog_generator     import generate_blog, load_calendar, get_calendar_entry
        from html_renderer      import save_blog
        from linkedin_generator import (generate_linkedin_post, save_linkedin_post,
                                        load_hashtags)
        from linkedin_publisher import publish_post as li_pub
        from trend_research     import get_trending_topics
        from tracker            import add_entry, update_status, read_all, get_entry
        from image_fetcher      import fetch_image
        from website_publisher  import publish_to_website, git_push_website, wait_for_live
        _mods.update(
            generate_blog=generate_blog,
            load_calendar=load_calendar, get_calendar_entry=get_calendar_entry,
            save_blog=save_blog,
            generate_linkedin_post=generate_linkedin_post,
            save_linkedin_post=save_linkedin_post,
            load_hashtags=load_hashtags,
            li_pub=li_pub,
            get_trending_topics=get_trending_topics,
            tracker_add=add_entry, tracker_update=update_status,
            tracker_read=read_all, tracker_get=get_entry,
            fetch_image=fetch_image,
            publish_to_website=publish_to_website,
            git_push_website=git_push_website,
            wait_for_live=wait_for_live,
        )
    return _mods


# ══════════════════════════════════════════════════════════════════════════════
class PhoenixApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title('Phoenix Solutions — Blog Marketing Automation')
        self.geometry('1200x960')
        self.minsize(1000, 800)
        self.configure(bg=NAVY)
        self.protocol('WM_DELETE_WINDOW', self._on_close)

        self._blog_data     = None
        self._li_data       = None
        self._cal_day       = None
        self._content_angle = ''
        self._image_info    = None   # dict from fetch_image or None
        self._blog_url      = ''
        self._log_widget    = None

        self._build_ui()
        self._setup_logging()
        threading.Thread(target=_m, daemon=True).start()

    # ── Top-level layout ──────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        tk.Frame(self, bg=BORDER, height=1).pack(fill='x')
        self._build_log_panel()   # must be packed before notebook (side='bottom')
        self._build_notebook()

    def _build_header(self):
        bar = tk.Frame(self, bg=NAVY_MID, height=56)
        bar.pack(fill='x')
        bar.pack_propagate(False)

        tk.Label(bar, text=' P ', font=(FONT, 14, 'bold'),
                 bg=CYAN, fg=NAVY, padx=6).pack(side='left', padx=(18, 8), pady=10)
        tk.Label(bar, text='Phoenix Solutions', font=(FONT, 15, 'bold'),
                 bg=NAVY_MID, fg=WHITE).pack(side='left')
        tk.Label(bar, text='  |  Blog Marketing Automation',
                 font=(FONT, 10), bg=NAVY_MID, fg=WHITE60).pack(side='left')

        self._status_dot = tk.Label(bar, text='\u25CF', font=(FONT, 11),
                                    bg=NAVY_MID, fg=GREEN)
        self._status_dot.pack(side='right', padx=(0, 10))
        self._status_lbl = tk.Label(bar, text='Ready', font=(FONT, 9),
                                    bg=NAVY_MID, fg=WHITE60)
        self._status_lbl.pack(side='right')

    def _build_notebook(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure('TNotebook', background=NAVY, borderwidth=0)
        s.configure('TNotebook.Tab', background=NAVY_MID, foreground=WHITE60,
                    font=(FONT, 10, 'bold'), padding=[20, 8], borderwidth=0)
        s.map('TNotebook.Tab',
              background=[('selected', NAVY_LIGHT)],
              foreground=[('selected', CYAN)])
        s.configure('Phoenix.Horizontal.TProgressbar',
                    troughcolor=NAVY_MID, background=CYAN,
                    borderwidth=0, thickness=4)
        s.configure('Phoenix.Treeview',
                    background=NAVY_MID, foreground=WHITE,
                    fieldbackground=NAVY_MID, font=(FONT, 10), rowheight=28)
        s.configure('Phoenix.Treeview.Heading',
                    background=NAVY_LIGHT, foreground=CYAN,
                    font=(FONT, 10, 'bold'))
        s.map('Phoenix.Treeview',
              background=[('selected', NAVY_LIGHT)],
              foreground=[('selected', CYAN)])

        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True)
        self._nb = nb

        tabs = {
            'generate': tk.Frame(nb, bg=NAVY),
            'tracker':  tk.Frame(nb, bg=NAVY),
            'publish':  tk.Frame(nb, bg=NAVY),
            'help':     tk.Frame(nb, bg=NAVY),
        }
        nb.add(tabs['generate'], text='  Generate  ')
        nb.add(tabs['tracker'],  text='  Tracker  ')
        nb.add(tabs['publish'],  text='  Publish  ')
        nb.add(tabs['help'],     text='  Help  ')

        self._build_generate_tab(tabs['generate'])
        self._build_tracker_tab(tabs['tracker'])
        self._build_publish_tab(tabs['publish'])
        self._build_help_tab(tabs['help'])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — GENERATE
    # ══════════════════════════════════════════════════════════════════════════

    def _build_generate_tab(self, tab):
        left = tk.Frame(tab, bg=NAVY, width=370)
        left.pack(side='left', fill='y', padx=(16, 8), pady=16)
        left.pack_propagate(False)

        # Content Calendar
        self._lbl(left, 'CONTENT CALENDAR  (30-day plan)')
        self._cal_list = tk.Listbox(
            left, height=10, bg=NAVY_MID, fg=WHITE, font=(FONT, 9),
            selectbackground=CYAN, selectforeground=NAVY,
            borderwidth=0, highlightthickness=1,
            highlightcolor=BORDER, highlightbackground=BORDER,
            activestyle='none', exportselection=False,
        )
        self._cal_list.pack(fill='x')
        self._cal_list.bind('<<ListboxSelect>>', self._on_cal_select)

        self._cal_info = tk.Label(
            left, text='', font=(FONT, 8), bg=NAVY_LIGHT, fg=CYAN,
            wraplength=350, justify='left', anchor='w', padx=8, pady=6,
        )
        self._cal_info.pack(fill='x', pady=(4, 0))

        # Custom topic
        self._lbl(left, 'OR CUSTOM TOPIC')
        self._topic_var = tk.StringVar()
        self._topic_entry = tk.Entry(
            left, textvariable=self._topic_var,
            bg=NAVY_MID, fg=WHITE, font=(FONT, 11), insertbackground=WHITE,
            borderwidth=0, highlightthickness=1,
            highlightcolor=CYAN, highlightbackground=BORDER,
        )
        self._topic_entry.pack(fill='x')

        # Trending Topics
        self._lbl(left, 'TRENDING TOPICS')
        self._trend_list = tk.Listbox(
            left, height=5, bg=NAVY_MID, fg=WHITE, font=(FONT, 9),
            selectbackground=CYAN, selectforeground=NAVY,
            borderwidth=0, highlightthickness=1,
            highlightcolor=BORDER, highlightbackground=BORDER,
            activestyle='none', exportselection=False,
        )
        self._trend_list.pack(fill='x')
        self._trend_list.bind('<<ListboxSelect>>', self._on_trend_select)

        self._btn(left, 'Fetch Trending Topics', self._on_fetch_trending,
                  style='ghost').pack(fill='x', pady=(4, 0))

        # Action buttons
        self._lbl(left, 'ACTIONS')
        self._btn_gen = self._btn(left, 'Generate Blog + LinkedIn Post', self._on_generate)
        self._btn_gen.pack(fill='x', pady=(0, 4))

        self._btn_edit = self._btn(left, 'Edit Blog Sections', self._on_edit_blog,
                                   style='ghost')
        self._btn_edit.pack(fill='x', pady=(0, 4))
        self._btn_edit.configure(state='disabled', fg=WHITE40)

        self._btn_approve = self._btn(left, 'Approve, Publish & Save', self._on_approve,
                                      style='ghost')
        self._btn_approve.pack(fill='x', pady=(0, 4))
        self._btn_approve.configure(state='disabled', fg=WHITE40)

        self._btn_clear = self._btn(left, 'Clear', self._on_clear, style='ghost')
        self._btn_clear.pack(fill='x')

        self._progress = ttk.Progressbar(
            left, mode='indeterminate', style='Phoenix.Horizontal.TProgressbar')
        self._progress.pack(fill='x', pady=(10, 0))

        # Right panel
        right = tk.Frame(tab, bg=NAVY)
        right.pack(side='left', fill='both', expand=True, padx=(8, 16), pady=16)

        self._lbl(right, 'BLOG PREVIEW  (click "Edit Blog Sections" to change content)')
        self._blog_prev = scrolledtext.ScrolledText(
            right, height=14, bg=NAVY_MID, fg=WHITE, font=(FONT, 10),
            wrap='word', insertbackground=WHITE, state='disabled',
            borderwidth=0, highlightthickness=1,
            highlightcolor=BORDER, highlightbackground=BORDER, padx=10, pady=8,
        )
        self._blog_prev.pack(fill='both', expand=True, pady=(0, 10))

        li_hdr = tk.Frame(right, bg=NAVY)
        li_hdr.pack(fill='x')
        self._lbl(li_hdr, 'LINKEDIN POST  (editable — blog URL added automatically on save)')

        self._li_prev = scrolledtext.ScrolledText(
            right, height=8, bg=NAVY_MID, fg=WHITE, font=(FONT, 10),
            wrap='word', insertbackground=WHITE,
            borderwidth=0, highlightthickness=1,
            highlightcolor=CYAN, highlightbackground=BORDER, padx=10, pady=8,
        )
        self._li_prev.pack(fill='both', expand=False)

        self.after(100, self._load_calendar_list)

    def _load_calendar_list(self):
        try:
            calendar = _m()['load_calendar']()
            self._cal_list.delete(0, 'end')
            for e in calendar:
                self._cal_list.insert('end', 'Day {:02d}  {}'.format(e['day'], e['topic']))
        except Exception as exc:
            self._cal_list.insert('end', 'Error loading calendar: {}'.format(exc))

    def _on_cal_select(self, _):
        sel = self._cal_list.curselection()
        if not sel:
            return
        day   = sel[0] + 1
        entry = _m()['get_calendar_entry'](day)
        if entry:
            self._cal_day       = day
            self._content_angle = entry.get('content_angle', '')
            self._topic_var.set(entry['topic'])
            kw = ', '.join(entry.get('keywords', []))
            self._cal_info.configure(
                text='Angle: {}\nKeywords: {}'.format(entry.get('content_angle', ''), kw)
            )

    def _on_trend_select(self, _):
        sel = self._trend_list.curselection()
        if sel:
            self._topic_var.set(self._trend_list.get(sel[0]))
            self._cal_day       = None
            self._content_angle = ''
            self._cal_info.configure(text='')

    def _on_fetch_trending(self):
        self._trend_list.delete(0, 'end')
        self._log('Fetching trending topics from Groq...')
        self._run_async(
            fn=lambda: _m()['get_trending_topics'](),
            callback=lambda topics: [self._trend_list.insert('end', t) for t in topics],
            label='Fetching trending topics...',
            err='Could not fetch trending topics.',
        )

    def _on_generate(self):
        topic = self._topic_var.get().strip()
        if not topic:
            messagebox.showwarning('No topic',
                'Select a calendar day, a trending topic, or enter a custom topic.')
            return

        self._log('Generate requested: "{}"'.format(topic))
        # Duplicate check
        existing_topics = [r['topic'].lower() for r in _m()['tracker_read']()]
        if topic.lower() in existing_topics:
            messagebox.showwarning('Duplicate topic',
                'Topic "{}" already exists in the tracker.\n'
                'Choose a different topic to avoid duplicates.'.format(topic))
            return

        entry  = _m()['get_calendar_entry'](self._cal_day) if self._cal_day else None
        angle  = entry.get('content_angle', '') if entry else self._content_angle
        kwords = entry.get('keywords', [])       if entry else []

        def _work():
            m    = _m()
            self._log('Calling Groq API — blog generation...')
            blog = m['generate_blog'](topic, angle, kwords)
            self._log('Blog generated: "{}" ({} sections)'.format(
                blog.get('title', topic), len(blog.get('sections', []))))
            self._log('Generating LinkedIn post...')
            li   = m['generate_linkedin_post'](topic, blog)
            self._log('LinkedIn post generated.')
            return blog, li

        self._run_async(
            fn=_work,
            callback=self._on_generate_done,
            label='Generating via Groq...',
            err='Generation failed. Check GROQ_API_KEY in your .env file.',
        )

    def _on_generate_done(self, result):
        blog, li = result
        self._blog_data = blog
        self._li_data   = li
        self._image_info = None
        self._blog_url   = ''

        sections = ''.join(
            '\n\n--- {} ---\n{}'.format(s['heading'], s['body'])
            for s in blog['sections']
        )
        blog_text = (
            'TITLE    : {}\n'
            'SLUG     : {}\n'
            'CATEGORY : {} {}\n'
            'META     : {}\n'
            'KEYWORDS : {}\n'
            '\n{}\n\n'
            '{}'
            '{}\n\n'
            '--- Conclusion ---\n{}'
        ).format(
            blog['title'], blog['slug'],
            blog.get('tag_emoji', ''), blog.get('category', ''),
            blog['meta_description'],
            ', '.join(blog.get('keywords', [])),
            '=' * 60,
            blog['intro'],
            sections,
            blog['conclusion'],
        )
        self._set_text(self._blog_prev, blog_text, readonly=True)
        self._set_text(self._li_prev, self._li_data['full_post'])

        for btn, fg in [(self._btn_approve, WHITE), (self._btn_edit, WHITE)]:
            btn.configure(state='normal', fg=fg, cursor='hand2')
        self._set_status('Generated: {}'.format(blog['title'][:50]), GREEN)

    # ── Edit blog dialog ──────────────────────────────────────────────────────

    def _on_edit_blog(self):
        if not self._blog_data:
            return
        blog = self._blog_data
        dlg  = tk.Toplevel(self)
        dlg.title('Edit Blog Sections')
        dlg.configure(bg=NAVY)
        dlg.geometry('860x680')
        dlg.grab_set()

        canvas = tk.Canvas(dlg, bg=NAVY, borderwidth=0, highlightthickness=0)
        vsb    = ttk.Scrollbar(dlg, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner = tk.Frame(canvas, bg=NAVY)
        win   = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _on_configure(_):
            canvas.configure(scrollregion=canvas.bbox('all'))
            canvas.itemconfig(win, width=canvas.winfo_width())

        inner.bind('<Configure>', _on_configure)
        canvas.bind('<Configure>', _on_configure)

        def _field(parent, label, value, height=2):
            tk.Label(parent, text=label, font=(FONT, 9, 'bold'),
                     bg=NAVY, fg=WHITE40, anchor='w').pack(fill='x', pady=(8, 2), padx=16)
            widget = scrolledtext.ScrolledText(
                parent, height=height, bg=NAVY_MID, fg=WHITE, font=(FONT, 10),
                wrap='word', insertbackground=WHITE,
                borderwidth=0, highlightthickness=1,
                highlightcolor=CYAN, highlightbackground=BORDER, padx=8, pady=6,
            )
            widget.pack(fill='x', padx=16)
            widget.insert('1.0', value)
            return widget

        # Title
        title_lbl = tk.Label(inner, text='TITLE', font=(FONT, 9, 'bold'),
                             bg=NAVY, fg=WHITE40, anchor='w')
        title_lbl.pack(fill='x', pady=(12, 2), padx=16)
        title_var = tk.StringVar(value=blog['title'])
        title_entry = tk.Entry(inner, textvariable=title_var,
                               bg=NAVY_MID, fg=WHITE, font=(FONT, 11),
                               insertbackground=WHITE, borderwidth=0,
                               highlightthickness=1, highlightcolor=CYAN,
                               highlightbackground=BORDER)
        title_entry.pack(fill='x', padx=16)

        intro_w = _field(inner, 'INTRO', blog['intro'], height=5)

        section_widgets = []
        for i, sec in enumerate(blog['sections']):
            tk.Label(inner, text='SECTION {} HEADING'.format(i + 1),
                     font=(FONT, 9, 'bold'), bg=NAVY, fg=WHITE40, anchor='w'
                     ).pack(fill='x', pady=(10, 2), padx=16)
            h_var = tk.StringVar(value=sec['heading'])
            h_ent = tk.Entry(inner, textvariable=h_var,
                             bg=NAVY_MID, fg=WHITE, font=(FONT, 11),
                             insertbackground=WHITE, borderwidth=0,
                             highlightthickness=1, highlightcolor=CYAN,
                             highlightbackground=BORDER)
            h_ent.pack(fill='x', padx=16)
            b_w = _field(inner, 'SECTION {} BODY'.format(i + 1), sec['body'], height=5)
            section_widgets.append((h_var, b_w))

        conclusion_w = _field(inner, 'CONCLUSION', blog['conclusion'], height=4)

        def _apply():
            self._blog_data['title'] = title_var.get().strip()
            self._blog_data['intro'] = intro_w.get('1.0', 'end').strip()
            for idx, (h_var, b_w) in enumerate(section_widgets):
                self._blog_data['sections'][idx]['heading'] = h_var.get().strip()
                self._blog_data['sections'][idx]['body']    = b_w.get('1.0', 'end').strip()
            self._blog_data['conclusion'] = conclusion_w.get('1.0', 'end').strip()
            # Refresh blog preview
            self._on_generate_done((self._blog_data, self._li_data))
            dlg.destroy()

        btn_row = tk.Frame(inner, bg=NAVY)
        btn_row.pack(fill='x', padx=16, pady=16)
        self._btn(btn_row, 'Apply Changes', _apply).pack(side='left', padx=(0, 8))
        self._btn(btn_row, 'Cancel', dlg.destroy, style='ghost').pack(side='left')

    # ── Approve & full pipeline ───────────────────────────────────────────────

    def _on_approve(self):
        if not self._blog_data:
            return

        topic        = self._topic_var.get().strip()
        blog         = self._blog_data
        li_text      = self._li_prev.get('1.0', 'end').strip()
        parts        = li_text.rsplit('\n\n', 1)
        caption      = parts[0] if len(parts) == 2 else li_text
        hashtags     = parts[1] if len(parts) == 2 else ''
        li_data      = {'caption': caption, 'hashtags': hashtags, 'full_post': li_text}
        cal_day      = self._cal_day
        cal_entry    = _m()['get_calendar_entry'](cal_day) if cal_day else None
        content_angle = cal_entry.get('content_angle', '') if cal_entry else ''
        publish_date  = datetime.now().strftime('%Y-%m-%d')

        def _work():
            m = _m()

            # 1. Fetch Unsplash image
            self._log('Fetching image from Unsplash for slug: ' + blog['slug'])
            img          = m['fetch_image'](blog.get('keywords', []), blog['slug'])
            image_local  = img['local_path']  if img else None
            image_public = img['public_url']  if img else None
            if img:
                self._log('Image saved: ' + image_local)
            else:
                self._log('No image found — continuing without image.', 'warning')

            # 2. Save blog HTML (with social image tags)
            self._log('Rendering and saving blog HTML...')
            blog_path = m['save_blog'](blog, publish_date, image_url=image_public)
            self._log('Blog HTML saved: ' + blog_path)

            # 3. Publish to website (copy + update index + sitemap)
            self._log('Copying to website repo and updating index + sitemap...')
            result   = m['publish_to_website'](blog, blog_path, publish_date, image_local)
            blog_url = result['blog_url']
            self._log('Website updated. Live URL: ' + blog_url)

            # 4. Git push (fire and forget — site goes live within ~1 min)
            self._log('Running git add / commit / push...')
            rc, out, err = m['git_push_website'](blog['slug'], blog['title'])
            if rc == 0:
                self._log('Git push successful.')
            else:
                self._log('Git push returned code {}: {}'.format(rc, err.strip()), 'warning')

            # 5. Save LinkedIn TXT with blog URL
            self._log('Saving LinkedIn post TXT with blog URL...')
            li_path = m['save_linkedin_post'](
                li_data, topic, cal_day, publish_date, blog_url=blog_url)
            self._log('LinkedIn TXT saved: ' + li_path)

            # 6. Tracker CSV
            self._log('Writing tracker entry...')
            tracker_id = m['tracker_add'](
                topic=topic, blog_path=blog_path, linkedin_path=li_path,
                hashtags=hashtags, calendar_day=cal_day,
                content_angle=content_angle, website_url=blog_url,
            )
            self._log('Pipeline complete — Tracker #{}'.format(tracker_id))
            return tracker_id, blog_path, li_path, blog_url, image_local

        self._log('Starting publish pipeline for: "{}"'.format(topic))
        self._run_async(
            fn=_work,
            callback=self._on_approve_done,
            label='Saving, publishing to website & waiting for live URL...',
            err='Publish pipeline failed.',
        )

    def _on_approve_done(self, result):
        tid, blog_path, li_path, blog_url, image_local = result
        self._blog_url    = blog_url
        self._image_info  = {'local_path': image_local} if image_local else None

        self._set_status('Saved — Tracker #{}'.format(tid), GREEN)
        img_line = '\nImage  : {}'.format(image_local) if image_local else ''
        messagebox.showinfo(
            'Published to Website',
            'Post saved and pushed live (Tracker #{}).\n\n'
            'Blog  : {}\n'
            'Live  : {}\n'
            'LinkedIn TXT: {}{}\n\n'
            'Go to Publish tab to post to LinkedIn.'.format(
                tid, blog_path, blog_url, li_path, img_line),
        )
        for btn, fg in [(self._btn_approve, WHITE40), (self._btn_edit, WHITE40)]:
            btn.configure(state='disabled', fg=fg, cursor='')

    def _on_clear(self):
        self._blog_data = self._li_data = self._image_info = None
        self._cal_day = None
        self._content_angle = ''
        self._blog_url = ''
        self._topic_var.set('')
        self._cal_info.configure(text='')
        self._set_text(self._blog_prev, '', readonly=True)
        self._set_text(self._li_prev,   '')
        self._cal_list.selection_clear(0, 'end')
        self._trend_list.selection_clear(0, 'end')
        for btn, fg in [(self._btn_approve, WHITE40), (self._btn_edit, WHITE40)]:
            btn.configure(state='disabled', fg=fg, cursor='')
        self._set_status('Ready', GREEN)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — TRACKER (CSV)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tracker_tab(self, tab):
        toolbar = tk.Frame(tab, bg=NAVY)
        toolbar.pack(fill='x', padx=16, pady=(14, 6))

        self._btn(toolbar, 'Refresh', self._on_tracker_refresh,
                  style='ghost').pack(side='left', padx=(0, 6))
        self._btn(toolbar, 'Open CSV', self._on_open_csv,
                  style='ghost').pack(side='left', padx=(0, 18))

        tk.Label(toolbar, text='Change status:', font=(FONT, 10),
                 bg=NAVY, fg=WHITE60).pack(side='left', padx=(0, 6))
        self._trk_status_var = tk.StringVar(value='scheduled')
        self._trk_status_combo = ttk.Combobox(
            toolbar, textvariable=self._trk_status_var,
            values=['draft', 'scheduled', 'posted'],
            state='readonly', width=11, font=(FONT, 10),
        )
        self._trk_status_combo.pack(side='left', padx=(0, 6))
        self._btn(toolbar, 'Apply', self._on_tracker_set_status,
                  style='ghost').pack(side='left')

        cols = ('id', 'date', 'day', 'topic', 'status', 'website_url')
        self._trk_tree = ttk.Treeview(tab, columns=cols, show='headings',
                                      style='Phoenix.Treeview', selectmode='browse')
        for col, w in [('id', 40), ('date', 120), ('day', 45),
                       ('topic', 300), ('status', 90), ('website_url', 260)]:
            self._trk_tree.heading(col, text=col.replace('_', ' ').capitalize(), anchor='w')
            self._trk_tree.column(col, width=w, stretch=(col == 'topic'))

        vsb = ttk.Scrollbar(tab, orient='vertical', command=self._trk_tree.yview)
        self._trk_tree.configure(yscrollcommand=vsb.set)
        self._trk_tree.pack(fill='both', expand=True, padx=16, pady=(0, 6))
        vsb.place(relx=1.0, rely=0.08, relheight=0.8, anchor='ne', x=-16)
        self._trk_tree.bind('<<TreeviewSelect>>', self._on_trk_select)

        detail = tk.Frame(tab, bg=NAVY_MID, height=130)
        detail.pack(fill='x', padx=16, pady=(0, 14))
        detail.pack_propagate(False)
        self._trk_detail = scrolledtext.ScrolledText(
            detail, bg=NAVY_MID, fg=WHITE, font=(FONT, 9),
            wrap='word', borderwidth=0, highlightthickness=0, padx=10, pady=8,
        )
        self._trk_detail.pack(fill='both', expand=True)

        self.after(200, self._on_tracker_refresh)

    def _on_tracker_refresh(self):
        rows = _m()['tracker_read']()
        self._trk_tree.delete(*self._trk_tree.get_children())
        for r in rows:
            tag = r.get('status', 'draft')
            self._trk_tree.insert('', 'end', iid=r['id'], values=(
                r['id'], r.get('generated_date', ''), r.get('calendar_day', ''),
                r['topic'][:55], r.get('status', ''), r.get('website_url', ''),
            ), tags=(tag,))
        self._trk_tree.tag_configure('posted',    foreground=GREEN)
        self._trk_tree.tag_configure('scheduled', foreground=ORANGE)
        self._trk_tree.tag_configure('draft',     foreground=WHITE60)
        self._set_status('{} entries in tracker'.format(len(rows)), GREEN)

    def _on_trk_select(self, _):
        sel = self._trk_tree.selection()
        if not sel:
            return
        row = _m()['tracker_get'](int(sel[0]))
        if row:
            self._set_text(self._trk_detail,
                'ID {}  |  {}  |  Day: {}\n'
                'Topic   : {}\n'
                'Angle   : {}\n'
                'Blog    : {}\n'
                'LinkedIn: {}\n'
                'Live URL: {}\n'
                'Tags    : {}'.format(
                    row['id'], row.get('status', '').upper(),
                    row.get('calendar_day') or 'custom',
                    row['topic'], row.get('content_angle', ''),
                    row.get('blog_path', ''), row.get('linkedin_path', ''),
                    row.get('website_url', ''), row.get('hashtags', ''),
                )
            )

    def _on_tracker_set_status(self):
        sel = self._trk_tree.selection()
        if not sel:
            messagebox.showwarning('No row selected', 'Click a row first.')
            return
        new_status = self._trk_status_var.get()
        m = _m()
        for iid in sel:
            m['tracker_update'](int(iid), new_status)
        self._on_tracker_refresh()

    def _on_open_csv(self):
        from tracker import TRACKER_PATH
        if os.path.exists(TRACKER_PATH):
            os.startfile(TRACKER_PATH)
        else:
            messagebox.showinfo('No CSV', 'tracker.csv has not been created yet.')

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — PUBLISH
    # ══════════════════════════════════════════════════════════════════════════

    def _build_publish_tab(self, tab):
        # ── Toolbar row ───────────────────────────────────────────────────────
        toolbar = tk.Frame(tab, bg=NAVY)
        toolbar.pack(fill='x', padx=16, pady=(14, 8))

        tk.Label(toolbar, text='Tracker ID:', font=(FONT, 11, 'bold'),
                 bg=NAVY, fg=WHITE).pack(side='left', padx=(0, 6))
        self._pub_id_var = tk.StringVar()
        tk.Entry(
            toolbar, textvariable=self._pub_id_var, width=7,
            bg=NAVY_MID, fg=WHITE, font=(FONT, 12), insertbackground=WHITE,
            borderwidth=0, highlightthickness=1,
            highlightcolor=CYAN, highlightbackground=BORDER,
        ).pack(side='left', padx=(0, 8))
        self._btn(toolbar, 'Load', self._on_pub_load,
                  style='ghost').pack(side='left', padx=(0, 18))

        self._pub_status_lbl = tk.Label(toolbar, text='No post loaded',
                                        font=(FONT, 9), bg=NAVY, fg=WHITE40)
        self._pub_status_lbl.pack(side='left')

        # ── Two-panel body ────────────────────────────────────────────────────
        body = tk.Frame(tab, bg=NAVY)
        body.pack(fill='both', expand=True, padx=16, pady=(0, 8))

        # Left — Blog preview
        left = tk.Frame(body, bg=NAVY, width=480)
        left.pack(side='left', fill='both', expand=True, padx=(0, 8))
        left.pack_propagate(False)

        self._lbl(left, 'BLOG POST PREVIEW')

        # Meta chip
        self._pub_meta = tk.Label(
            left, text='', font=(FONT, 9), bg=NAVY_LIGHT, fg=CYAN,
            wraplength=460, justify='left', anchor='w', padx=10, pady=6,
        )
        self._pub_meta.pack(fill='x', pady=(0, 6))

        # Open buttons row
        btn_row = tk.Frame(left, bg=NAVY)
        btn_row.pack(fill='x', pady=(0, 6))
        self._btn(btn_row, 'Open in Browser', self._on_open_blog_browser,
                  style='ghost').pack(side='left', padx=(0, 6))
        self._btn(btn_row, 'Open Live URL', self._on_open_live_url,
                  style='ghost').pack(side='left')

        # Blog content text (read-only)
        self._pub_blog_txt = scrolledtext.ScrolledText(
            left, bg=NAVY_MID, fg=WHITE, font=(FONT, 10),
            wrap='word', state='disabled', insertbackground=WHITE,
            borderwidth=0, highlightthickness=1,
            highlightcolor=BORDER, highlightbackground=BORDER, padx=10, pady=8,
        )
        self._pub_blog_txt.pack(fill='both', expand=True)

        # Right — LinkedIn editor
        right = tk.Frame(body, bg=NAVY, width=440)
        right.pack(side='left', fill='both', expand=True, padx=(8, 0))
        right.pack_propagate(False)

        self._lbl(right, 'LINKEDIN CAPTION  (editable)')
        self._pub_caption = scrolledtext.ScrolledText(
            right, height=10, bg=NAVY_MID, fg=WHITE, font=(FONT, 10),
            wrap='word', insertbackground=WHITE,
            borderwidth=0, highlightthickness=1,
            highlightcolor=CYAN, highlightbackground=BORDER, padx=10, pady=8,
        )
        self._pub_caption.pack(fill='both', expand=True, pady=(0, 8))

        self._lbl(right, 'HASHTAGS  (editable)')
        self._pub_hashtags = scrolledtext.ScrolledText(
            right, height=3, bg=NAVY_MID, fg=WHITE, font=(FONT, 10),
            wrap='word', insertbackground=WHITE,
            borderwidth=0, highlightthickness=1,
            highlightcolor=BORDER, highlightbackground=BORDER, padx=10, pady=8,
        )
        self._pub_hashtags.pack(fill='x', pady=(0, 6))

        self._lbl(right, 'BLOG LINK  (appended automatically)')
        self._pub_link_lbl = tk.Label(
            right, text='—', font=(FONT, 9), bg=NAVY_LIGHT, fg=CYAN,
            wraplength=420, justify='left', anchor='w', padx=10, pady=6,
        )
        self._pub_link_lbl.pack(fill='x', pady=(0, 8))

        # Image indicator
        self._pub_img_lbl = tk.Label(right, text='', font=(FONT, 8),
                                     bg=NAVY, fg=WHITE40, wraplength=420)
        self._pub_img_lbl.pack(fill='x')

        # ── Action bar ────────────────────────────────────────────────────────
        act = tk.Frame(tab, bg=NAVY_MID, height=56)
        act.pack(fill='x', side='bottom')
        act.pack_propagate(False)

        self._btn_publish = self._btn(act, '  Publish to LinkedIn  ', self._on_publish)
        self._btn_publish.pack(side='right', padx=16, pady=10)

        self._pub_image_path = None
        self._pub_blog_url   = ''
        self._pub_tracker_id = None

    # ── Load post into Publish tab ────────────────────────────────────────────

    def _on_pub_load(self):
        raw = self._pub_id_var.get().strip()
        if not raw.isdigit():
            messagebox.showwarning('Invalid ID', 'Enter a numeric Tracker ID.')
            return
        row = _m()['tracker_get'](int(raw))
        if not row:
            messagebox.showerror('Not found', 'Tracker ID {} does not exist.'.format(raw))
            return

        self._pub_tracker_id = int(raw)
        self._pub_blog_url   = row.get('website_url', '')

        # ── Blog meta chip ────────────────────────────────────────────────────
        self._pub_meta.configure(
            text='Topic: {}\nBlog : {}\nURL  : {}'.format(
                row.get('topic', ''),
                row.get('blog_path', ''),
                self._pub_blog_url or '(not published yet)',
            )
        )

        # ── Blog HTML content → text preview ─────────────────────────────────
        blog_content = ''
        blog_path = row.get('blog_path', '')
        try:
            with open(blog_path, encoding='utf-8') as f:
                raw_html = f.read()
            # Strip tags for readable preview
            import re as _re
            text = _re.sub(r'<style[^>]*>.*?</style>', '', raw_html, flags=_re.DOTALL)
            text = _re.sub(r'<script[^>]*>.*?</script>', '', text, flags=_re.DOTALL)
            text = _re.sub(r'<[^>]+>', '', text)
            text = _re.sub(r'\n{3,}', '\n\n', text.strip())
            blog_content = text[:6000]
        except Exception as exc:
            blog_content = 'Could not load blog file:\n{}\n\n{}'.format(blog_path, exc)
        self._set_text(self._pub_blog_txt, blog_content, readonly=True)

        # ── LinkedIn TXT → split caption / hashtags ───────────────────────────
        caption_text  = ''
        hashtag_text  = ''
        try:
            with open(row['linkedin_path'], encoding='utf-8') as f:
                content = f.read()
            parts = content.split('=' * 60)
            post  = parts[-1].strip() if len(parts) > 1 else content

            # Remove the blog URL line so user edits only caption + hashtags
            lines = post.splitlines()
            body_lines, tag_lines, link_lines = [], [], []
            for line in lines:
                if line.startswith('#'):
                    tag_lines.append(line)
                elif line.startswith('Read the full article:'):
                    link_lines.append(line)
                else:
                    body_lines.append(line)
            caption_text = '\n'.join(body_lines).strip()
            hashtag_text = ' '.join(tag_lines).strip()
        except Exception:
            caption_text = row.get('topic', '')

        self._set_text(self._pub_caption,  caption_text)
        self._set_text(self._pub_hashtags, hashtag_text)
        self._pub_link_lbl.configure(
            text=self._pub_blog_url or '(no URL — post was not published to website yet)',
            fg=CYAN if self._pub_blog_url else WHITE40,
        )

        # ── Image ─────────────────────────────────────────────────────────────
        blog_file = os.path.basename(blog_path)              # 2026-03-06-slug.html
        parts_    = blog_file.replace('.html', '').split('-')
        slug      = '-'.join(parts_[3:]) if len(parts_) > 3 else blog_file.replace('.html', '')
        image_path = os.path.join(os.path.dirname(__file__), 'Blogs', 'images', slug + '.jpg')
        if os.path.exists(image_path):
            self._pub_image_path = image_path
            self._pub_img_lbl.configure(text='Image attached: ' + slug + '.jpg', fg=CYAN)
        else:
            self._pub_image_path = None
            self._pub_img_lbl.configure(text='No image for this post', fg=WHITE40)

        self._pub_status_lbl.configure(
            text='Loaded #{} — {}'.format(raw, row['topic'][:50]), fg=WHITE60)

    def _on_open_blog_browser(self):
        row = _m()['tracker_get'](self._pub_tracker_id) if self._pub_tracker_id else None
        path = row.get('blog_path', '') if row else ''
        if path and os.path.exists(path):
            import webbrowser
            webbrowser.open('file:///' + path.replace('\\', '/'))
        else:
            messagebox.showinfo('No file', 'Load a post first.')

    def _on_open_live_url(self):
        if self._pub_blog_url:
            import webbrowser
            webbrowser.open(self._pub_blog_url)
        else:
            messagebox.showinfo('No URL', 'This post has no live URL yet.')

    def _on_publish(self):
        if not self._pub_tracker_id:
            messagebox.showwarning('No post loaded', 'Load a post first.')
            return

        caption   = self._pub_caption.get('1.0', 'end').strip()
        hashtags  = self._pub_hashtags.get('1.0', 'end').strip()
        blog_url  = self._pub_blog_url

        if not caption:
            messagebox.showwarning('Empty post', 'Caption cannot be empty.')
            return

        # Build final post text
        parts = [caption]
        if blog_url:
            parts.append('Read the full article: ' + blog_url)
        if hashtags:
            parts.append(hashtags)
        li_text = '\n\n'.join(parts)

        img      = self._pub_image_path
        img_line = '\nImage: ' + os.path.basename(img) if img else '\n(text only)'
        post_id  = self._pub_tracker_id

        if not messagebox.askyesno(
            'Confirm Publish',
            'Publish to LinkedIn?\n{}\n\nPreview:\n{}...'.format(img_line, li_text[:250]),
        ):
            return

        def _work():
            _m()['li_pub'](li_text, image_path=img)
            pub_date = datetime.now().strftime('%Y-%m-%d %H:%M')
            _m()['tracker_update'](post_id, 'posted', pub_date)
            return post_id

        self._log('Publishing Tracker #{} to LinkedIn...'.format(post_id))
        self._pub_status_lbl.configure(text='Publishing...', fg=ORANGE)
        self._run_async(
            fn=_work,
            callback=lambda pid: self._on_publish_done(pid),
            label='Publishing to LinkedIn...',
            err='LinkedIn publish failed. Check LINKEDIN_ACCESS_TOKEN in .env.',
        )

    def _on_publish_done(self, post_id):
        self._log('LinkedIn publish successful — Tracker #{}'.format(post_id))
        self._pub_status_lbl.configure(text='Published #{}'.format(post_id), fg=GREEN)
        self._set_status('Published Tracker #{}'.format(post_id), GREEN)
        self._on_tracker_refresh()

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — HELP
    # ══════════════════════════════════════════════════════════════════════════

    def _build_help_tab(self, tab):
        help_text = """
PHOENIX SOLUTIONS — BLOG MARKETING AUTOMATION
Help Guide
══════════════════════════════════════════════════════════════════════

GETTING STARTED
───────────────
1. Copy .env.example to .env and fill in your credentials:
     GROQ_API_KEY           — your Groq API key (https://console.groq.com)
     GROQ_MODEL             — default: llama-3.3-70b-versatile
     LINKEDIN_ACCESS_TOKEN  — your LinkedIn OAuth2 bearer token
     LINKEDIN_PERSON_URN    — optional; auto-resolved if left blank
     UNSPLASH_ACCESS_KEY    — free key from https://unsplash.com/developers
     WEBSITE_REPO_PATH      — local path to your website repo (default: C:\\Projects\\phoenixsolution)

2. Run the app:
     python gui.py

────────────────────────────────────────────────────────────────────
TAB 1 — GENERATE
────────────────────────────────────────────────────────────────────
CONTENT CALENDAR
  • 30 pre-planned topics loaded from MarketingSchedule/Calender.json.
  • Click a day to auto-fill topic, content angle, and keywords.

TRENDING TOPICS
  • Click "Fetch Trending Topics" to get 5 timely ideas from Groq.
  • Click a topic to select it.
  • Duplicate check: if the topic already exists in the tracker, you'll be warned.

GENERATE
  • Calls Groq API to produce a full blog post + LinkedIn caption + 6 hashtags.

EDIT BLOG SECTIONS
  • Opens a dialog to edit title, intro, each section heading/body, and conclusion.
  • Click "Apply Changes" to update the preview.
  • LinkedIn post is directly editable in the lower preview panel.

APPROVE, PUBLISH & SAVE
  Full automated pipeline:
  1. Fetches a relevant image from Unsplash (if UNSPLASH_ACCESS_KEY is set)
  2. Renders blog HTML with topic-specific og:image / twitter:image
  3. Copies HTML to phoenixsolution/blog/{slug}.html
  4. Copies image to phoenixsolution/blog/images/{slug}.jpg
  5. Updates blog/index.html — new card inserted at the top
  6. Updates sitemap.xml — new URL entry added
  7. Git commit + push in the website repo
  8. Waits for the URL to go live (polls up to ~3 min)
  9. Saves LinkedIn TXT with the live blog URL appended
  10. Records everything in tracker.csv

────────────────────────────────────────────────────────────────────
TAB 2 — TRACKER
────────────────────────────────────────────────────────────────────
  • Shows all entries from tracker.csv.
  • Columns: ID | Date | Day | Topic | Status | Live URL
  • Colour: White = draft | Orange = scheduled | Green = posted
  • Click a row to see full paths, hashtags, and live URL.
  • Change status: select row → pick status → Apply.
  • Open CSV: opens tracker.csv in Excel/Notepad.

────────────────────────────────────────────────────────────────────
TAB 3 — PUBLISH
────────────────────────────────────────────────────────────────────
  1. Enter Tracker ID → Load Post.
  2. Review/edit the LinkedIn post text (blog URL is already included).
  3. Image indicator shows whether an image will be attached.
  4. Click "Publish to LinkedIn" — confirmation dialog appears.
  5. Post is sent to LinkedIn with image + blog link.
  6. Tracker status updates to "posted" automatically.

────────────────────────────────────────────────────────────────────
FILE STRUCTURE
────────────────────────────────────────────────────────────────────
  BlogMarketing/
  ├── Blogs/                  — generated HTML blog posts
  │   └── images/             — downloaded Unsplash images
  ├── LinkedIn Posts/         — generated LinkedIn TXT files
  ├── MarketingSchedule/
  │   └── Calender.json       — 30-day content plan
  ├── Prompts/
  │   ├── blog_prompt.txt
  │   ├── Linkedin_prompt.txt
  │   └── Hashtags.txt
  ├── tracker.csv             — master content log (no database)
  ├── .env                    — your API keys (never commit this)
  └── gui.py                  — this application

  phoenixsolution/            — your website repo (separate)
  ├── blog/
  │   ├── index.html          — blog listing (auto-updated)
  │   ├── images/             — published post images
  │   └── {slug}.html         — published blog posts
  └── sitemap.xml             — auto-updated

────────────────────────────────────────────────────────────────────
TIPS
────────────────────────────────────────────────────────────────────
  • Add hashtags to Prompts/Hashtags.txt (one per line, with #).
  • Edit Prompts/blog_prompt.txt to change the writing style.
  • Set WEBSITE_REPO_PATH in .env to point to your website git repo.
  • LinkedIn tokens expire after ~60 days — regenerate at:
    https://www.linkedin.com/developers/

────────────────────────────────────────────────────────────────────
SUPPORT
────────────────────────────────────────────────────────────────────
  Phoenix Solutions
  info@phoenixsolution.in
  https://www.phoenixsolution.in
"""
        self._lbl(tab, 'DOCUMENTATION')
        help_area = scrolledtext.ScrolledText(
            tab, bg=NAVY_MID, fg=WHITE, font=('Consolas', 10),
            wrap='word', state='disabled',
            borderwidth=0, highlightthickness=0, padx=20, pady=16,
        )
        help_area.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        self._set_text(help_area, help_text.strip(), readonly=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIVITY LOG PANEL
    # ══════════════════════════════════════════════════════════════════════════

    def _build_log_panel(self):
        """Fixed-height panel at the bottom of the window showing activity log."""
        wrap = tk.Frame(self, bg=NAVY_MID)
        wrap.pack(side='bottom', fill='x')

        # Header bar
        hdr = tk.Frame(wrap, bg=NAVY_MID)
        hdr.pack(fill='x', padx=10, pady=(4, 0))
        tk.Label(hdr, text='ACTIVITY LOG', font=(FONT, 8, 'bold'),
                 bg=NAVY_MID, fg=WHITE40).pack(side='left')
        tk.Label(
            hdr, text='Clear', font=(FONT, 8), bg=NAVY_MID, fg=WHITE40,
            cursor='hand2',
        ).pack(side='right').bind('<Button-1>', lambda _: self._log_clear())

        self._log_widget = scrolledtext.ScrolledText(
            wrap, height=6, bg=NAVY_MID, fg=WHITE60,
            font=('Consolas', 8), wrap='word', state='disabled',
            borderwidth=0, highlightthickness=0, padx=10, pady=4,
        )
        self._log_widget.pack(fill='x')
        self._log_widget.tag_configure('err',  foreground=RED)
        self._log_widget.tag_configure('warn', foreground=ORANGE)
        self._log_widget.tag_configure('info', foreground=WHITE60)

        # Thin border at top
        tk.Frame(wrap, bg=BORDER, height=1).place(relx=0, rely=0, relwidth=1)

    def _setup_logging(self):
        """Wire root logger to both Log.txt and the GUI log panel."""
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Log.txt')
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # Avoid adding duplicate handlers on re-init
        root_logger.handlers = []

        # File handler
        fh = logging.FileHandler(log_path, encoding='utf-8')
        fh.setFormatter(logging.Formatter(
            '%(asctime)s  %(levelname)-8s  %(name)s  %(message)s'))
        root_logger.addHandler(fh)

        # GUI handler
        if self._log_widget:
            gh = _GUILogHandler(self._log_widget)
            root_logger.addHandler(gh)

        self._logger = logging.getLogger('gui')
        self._logger.info('Phoenix Blog Marketing started')

    def _log(self, msg, level='info'):
        """Convenience: log a message from the GUI layer."""
        getattr(self._logger, level.lower(), self._logger.info)(msg)

    def _log_clear(self):
        if self._log_widget:
            self._log_widget.configure(state='normal')
            self._log_widget.delete('1.0', 'end')
            self._log_widget.configure(state='disabled')

    # ══════════════════════════════════════════════════════════════════════════
    # SHARED HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _lbl(self, parent, text):
        tk.Label(parent, text=text, font=(FONT, 9, 'bold'),
                 bg=NAVY, fg=WHITE40, anchor='w').pack(fill='x', pady=(10, 3))

    def _btn(self, parent, text, command, style='primary'):
        bg, fg, hbg = (CYAN, NAVY, CYAN_HOVER) if style == 'primary' \
                   else (NAVY_LIGHT, WHITE, NAVY_MID)
        w = tk.Label(parent, text=text, font=(FONT, 10, 'bold'),
                     bg=bg, fg=fg, padx=16, pady=8, cursor='hand2')
        w.bind('<Button-1>', lambda _: command())
        w.bind('<Enter>',    lambda _: w.configure(bg=hbg))
        w.bind('<Leave>',    lambda _: w.configure(bg=bg))
        w._base_bg = bg
        return w

    def _set_text(self, widget, text, readonly=False):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        if readonly:
            widget.configure(state='disabled')

    def _set_status(self, text, colour=GREEN):
        self._status_lbl.configure(text=text)
        self._status_dot.configure(fg=colour)

    def _run_async(self, fn, callback, label='Working...', err='Error'):
        self._progress.start(12)
        self._set_status(label, ORANGE)

        def _worker():
            try:
                result = fn()
                self.after(0, lambda r=result: self._async_done(callback, r))
            except Exception as exc:
                self.after(0, lambda e=exc: self._async_fail(err, e))

        threading.Thread(target=_worker, daemon=True).start()

    def _async_done(self, callback, result):
        self._progress.stop()
        self._set_status('Ready', GREEN)
        callback(result)

    def _async_fail(self, msg, exc):
        self._progress.stop()
        self._set_status('Error', RED)
        self._log('{} — {}'.format(msg, exc), 'error')
        messagebox.showerror('Error', '{}\n\n{}'.format(msg, exc))

    def _on_close(self):
        self.destroy()
        sys.exit(0)


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    PhoenixApp().mainloop()
