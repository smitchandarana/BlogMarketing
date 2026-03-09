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
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime

from dotenv import load_dotenv

# ── Exe-aware base directory ────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(_APP_DIR, '.env'), override=True)

# ── Colours ────────────────────────────────────────────────────────────────────
NAVY        = '#0B1F3A'
NAVY_MID    = '#122B4A'
NAVY_LIGHT  = '#1A3A5C'
NAVY_CARD   = '#0F2845'
CYAN        = '#00C9DB'
CYAN_HOVER  = '#00E8FC'
CYAN_DIM    = '#007A87'
WHITE       = '#F0F2F5'
WHITE60     = '#99A4B0'
WHITE40     = '#6B7A8D'
BORDER      = '#1E3D5F'
RED         = '#FF4D6A'
GREEN       = '#22D68A'
GREEN_DIM   = '#0F6B40'
ORANGE      = '#FFB347'
REDDIT      = '#FF6B35'
LINKEDIN    = '#0A84FF'
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
        from tracker            import (add_entry, add_idea, update_status, read_all,
                                        get_entry, delete_entry, delete_entries, STATUSES)
        from image_fetcher      import fetch_image
        from website_publisher  import publish_to_website, git_push_website, wait_for_live
        from topic_researcher   import run_research, load_saved_research, get_last_run_date
        import smart_scheduler as _sched
        _mods.update(
            sched=_sched,
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
            run_research=run_research,
            load_research=load_saved_research,
            get_last_run=get_last_run_date,
        )
    return _mods


# ══════════════════════════════════════════════════════════════════════════════
class PhoenixApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title('Phoenix Solutions  \u00b7  Blog Marketing Automation  v2')
        self.geometry('1280x980')
        self.minsize(1100, 820)
        self.configure(bg=NAVY)
        self.protocol('WM_DELETE_WINDOW', self._on_close)

        self._blog_data      = None
        self._li_data        = None
        self._cal_day        = None
        self._content_angle  = ''
        self._image_info     = None   # dict from fetch_image or None
        self._blog_url       = ''
        self._log_widget     = None
        self._research_topics = []    # list of topic dicts from last research run
        self._cancel_event   = threading.Event()  # shared cancel for long operations

        self._build_ui()
        self._setup_logging()
        threading.Thread(target=_m, daemon=True).start()

    # ── Top-level layout ──────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_log_panel()   # must be packed before notebook (side='bottom')
        self._build_notebook()

    def _build_header(self):
        wrap = tk.Frame(self, bg=NAVY_MID)
        wrap.pack(fill='x')

        bar = tk.Frame(wrap, bg=NAVY_MID, height=58)
        bar.pack(fill='x')
        bar.pack_propagate(False)

        # Logo badge
        badge = tk.Frame(bar, bg=CYAN, padx=8, pady=4)
        badge.pack(side='left', padx=(18, 10), pady=10)
        tk.Label(badge, text='PS', font=(FONT, 12, 'bold'), bg=CYAN, fg=NAVY).pack()

        tk.Label(bar, text='Phoenix Solutions', font=(FONT, 15, 'bold'),
                 bg=NAVY_MID, fg=WHITE).pack(side='left')
        tk.Label(bar, text='  \u00b7  Blog Marketing Automation',
                 font=(FONT, 10), bg=NAVY_MID, fg=WHITE40).pack(side='left')

        # Right side — status
        right = tk.Frame(bar, bg=NAVY_MID)
        right.pack(side='right', padx=18)
        self._status_dot = tk.Label(right, text='\u25CF', font=(FONT, 13),
                                    bg=NAVY_MID, fg=GREEN)
        self._status_dot.pack(side='right', padx=(4, 0))
        self._status_lbl = tk.Label(right, text='Ready', font=(FONT, 9),
                                    bg=NAVY_MID, fg=WHITE60)
        self._status_lbl.pack(side='right')

        # Accent line at bottom of header
        tk.Frame(wrap, bg=CYAN_DIM, height=2).pack(fill='x')

    def _build_notebook(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure('TNotebook', background=NAVY, borderwidth=0)
        s.configure('TNotebook.Tab', background=NAVY_MID, foreground=WHITE40,
                    font=(FONT, 10, 'bold'), padding=[24, 10], borderwidth=0)
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
            'research':  tk.Frame(nb, bg=NAVY),
            'generate':  tk.Frame(nb, bg=NAVY),
            'tracker':   tk.Frame(nb, bg=NAVY),
            'publish':   tk.Frame(nb, bg=NAVY),
            'scheduler': tk.Frame(nb, bg=NAVY),
            'settings':  tk.Frame(nb, bg=NAVY),
            'help':      tk.Frame(nb, bg=NAVY),
        }
        nb.add(tabs['research'],  text='  Research  ')
        nb.add(tabs['generate'],  text='  Generate  ')
        nb.add(tabs['tracker'],   text='  Tracker  ')
        nb.add(tabs['publish'],   text='  Publish  ')
        nb.add(tabs['scheduler'], text='  Scheduler  ')
        nb.add(tabs['settings'],  text='  Settings  ')
        nb.add(tabs['help'],      text='  Help  ')

        self._build_research_tab(tabs['research'])
        self._build_generate_tab(tabs['generate'])
        self._build_tracker_tab(tabs['tracker'])
        self._build_publish_tab(tabs['publish'])
        self._build_scheduler_tab(tabs['scheduler'])
        self._build_settings_tab(tabs['settings'])
        self._build_help_tab(tabs['help'])

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — RESEARCH
    # ══════════════════════════════════════════════════════════════════════════

    def _build_research_tab(self, tab):
        # ── Left panel — source controls ──────────────────────────────────────
        left = tk.Frame(tab, bg=NAVY, width=300)
        left.pack(side='left', fill='y', padx=(16, 8), pady=16)
        left.pack_propagate(False)

        self._lbl(left, 'REDDIT SOURCES')
        reddit_card = self._card(left, pady=(0, 8))
        self._research_sub_vars = {}
        for sub in ['PowerBI', 'businessintelligence', 'dataengineering',
                    'analytics', 'datascience']:
            var = tk.BooleanVar(value=True)
            self._research_sub_vars[sub] = var
            tk.Checkbutton(
                reddit_card, text='r/' + sub, variable=var,
                bg=NAVY_MID, fg=WHITE, selectcolor=NAVY_LIGHT,
                activebackground=NAVY_MID, activeforeground=CYAN,
                font=(FONT, 9), anchor='w', borderwidth=0,
                highlightthickness=0,
            ).pack(fill='x', padx=10, pady=2)

        self._lbl(left, 'LINKEDIN')
        li_card = self._card(left, pady=(0, 8))
        self._research_linkedin_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            li_card, text='LinkedIn Trends (AI-synthesised)',
            variable=self._research_linkedin_var,
            bg=NAVY_MID, fg=WHITE, selectcolor=NAVY_LIGHT,
            activebackground=NAVY_MID, activeforeground=CYAN,
            font=(FONT, 9), anchor='w', borderwidth=0, highlightthickness=0,
        ).pack(fill='x', padx=10, pady=(6, 2))
        tk.Label(li_card, text='Uses Groq to simulate LinkedIn BI discussions',
                 font=(FONT, 7), bg=NAVY_MID, fg=WHITE40,
                 wraplength=260, justify='left').pack(fill='x', padx=10, pady=(0, 6))

        self._lbl(left, 'ACTIONS')
        self._btn_research = self._btn(left, 'Run Research', self._on_run_research)
        self._btn_research.pack(fill='x', pady=(0, 4))
        self._btn_research_stop = self._btn(left, 'Stop Research',
                                             self._on_stop_operation, style='ghost')
        self._btn_research_stop.pack(fill='x', pady=(0, 4))
        self._btn(left, 'Load Saved', self._on_load_saved_research,
                  style='ghost').pack(fill='x', pady=(0, 4))
        self._btn(left, 'Clear Results', self._on_clear_research,
                  style='ghost').pack(fill='x')

        self._research_progress = ttk.Progressbar(
            left, mode='indeterminate', style='Phoenix.Horizontal.TProgressbar')
        self._research_progress.pack(fill='x', pady=(10, 6))

        self._research_last_run_lbl = tk.Label(
            left, text='Last run: never', font=(FONT, 8),
            bg=NAVY, fg=WHITE40, anchor='w')
        self._research_last_run_lbl.pack(fill='x')

        # Preload last-run date
        self.after(300, self._refresh_research_last_run)

        # ── Right panel — results ─────────────────────────────────────────────
        right = tk.Frame(tab, bg=NAVY)
        right.pack(side='left', fill='both', expand=True, padx=(8, 16), pady=16)

        topic_hdr = tk.Frame(right, bg=NAVY)
        topic_hdr.pack(fill='x')
        self._research_count_lbl = tk.Label(
            topic_hdr, text='', font=(FONT, 9, 'bold'),
            bg=NAVY, fg=CYAN)
        self._research_count_lbl.pack(side='right', padx=4, pady=(12, 4))
        self._lbl(topic_hdr, 'DISCOVERED TOPICS')

        # Results treeview
        cols = ('source', 'title', 'pain_point', 'score')
        self._res_tree = ttk.Treeview(
            right, columns=cols, show='headings',
            style='Phoenix.Treeview', selectmode='browse', height=14,
        )
        for col, label, w, stretch in [
            ('source',     'Source',      110, False),
            ('title',      'Blog Title',  340, True),
            ('pain_point', 'Pain Point',  300, True),
            ('score',      'Score',        55, False),
        ]:
            self._res_tree.heading(col, text=label, anchor='w')
            self._res_tree.column(col, width=w, stretch=stretch, minwidth=50)

        res_vsb = ttk.Scrollbar(right, orient='vertical', command=self._res_tree.yview)
        self._res_tree.configure(yscrollcommand=res_vsb.set)
        self._res_tree.pack(fill='both', expand=True, pady=(0, 0))
        res_vsb.place(relx=1.0, rely=0, relheight=0.78, anchor='ne', x=-2)
        self._res_tree.bind('<<TreeviewSelect>>', self._on_research_select)

        # Source colour tags
        self._res_tree.tag_configure('reddit',   foreground=REDDIT)
        self._res_tree.tag_configure('linkedin', foreground=LINKEDIN)
        self._res_tree.tag_configure('other',    foreground=WHITE60)

        # Detail panel
        detail = tk.Frame(right, bg=NAVY_MID, highlightbackground=BORDER,
                          highlightthickness=1, height=100)
        detail.pack(fill='x', pady=(6, 0))
        detail.pack_propagate(False)
        self._res_detail = scrolledtext.ScrolledText(
            detail, bg=NAVY_MID, fg=WHITE60, font=(FONT, 9),
            wrap='word', state='disabled', borderwidth=0,
            highlightthickness=0, padx=10, pady=8,
        )
        self._res_detail.pack(fill='both', expand=True)

        # Action row
        act_row = tk.Frame(right, bg=NAVY)
        act_row.pack(fill='x', pady=(8, 0))
        self._btn_use_topic = self._btn(
            act_row, '  Use This Topic  \u2192', self._on_use_research_topic)
        self._btn_use_topic.pack(side='left', padx=(0, 8))
        self._btn_use_topic.configure(state='disabled', fg=WHITE40, cursor='')
        self._btn_send_to_sched = self._btn(
            act_row, 'Send All to Scheduler', self._on_send_research_to_scheduler,
            style='ghost')
        self._btn_send_to_sched.pack(side='left', padx=(0, 8))

    def _on_run_research(self):
        selected_subs = [sub for sub, var in self._research_sub_vars.items() if var.get()]
        include_li    = self._research_linkedin_var.get()
        if not selected_subs and not include_li:
            from tkinter import messagebox
            messagebox.showwarning('No sources', 'Select at least one source.')
            return

        self._cancel_event.clear()
        self._log('Starting research: {} subreddits + LinkedIn={}'.format(
            len(selected_subs), include_li))
        self._research_progress.start(12)
        self._set_status('Researching Reddit & LinkedIn...', ORANGE)

        def _work():
            return _m()['run_research'](selected_subs, include_li)

        def _done(topics):
            self._research_progress.stop()
            self._set_status('Ready', GREEN)
            self._on_research_done(topics)

        def _fail(err):
            self._research_progress.stop()
            self._set_status('Research error — will retry in 60s', RED)
            self._log('Research failed: {} — waiting 60s before allowing retry.'.format(err), 'error')

        def _worker():
            try:
                if self._cancel_event.is_set():
                    return
                result = _work()
                if self._cancel_event.is_set():
                    self.after(0, lambda: self._set_status('Cancelled', ORANGE))
                    return
                self.after(0, lambda r=result: _done(r))
            except Exception as exc:
                self.after(0, lambda e=exc: _fail(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_load_saved_research(self):
        self._log('Loading saved research topics...')
        topics = _m()['load_research']()
        if not topics:
            from tkinter import messagebox
            messagebox.showinfo('No saved data',
                'No saved research found.\nRun Research first.')
            return
        self._on_research_done(topics)

    def _on_research_done(self, topics):
        self._research_topics = topics
        self._res_tree.delete(*self._res_tree.get_children())

        for t in topics:
            src   = t.get('source', '')
            title = t.get('generated_title', '')
            pain  = t.get('pain_point', '')
            score = t.get('reddit_score', 0)

            tag = 'linkedin' if src == 'LinkedIn' else ('reddit' if src.startswith('r/') else 'other')
            self._res_tree.insert('', 'end', values=(src, title, pain, score or ''), tags=(tag,))

        count = len(topics)
        self._research_count_lbl.configure(
            text='{} idea{} found'.format(count, 's' if count != 1 else ''))
        self._log('Research results loaded: {} topics'.format(count))
        self._refresh_research_last_run()

    def _on_research_select(self, _):
        sel = self._res_tree.selection()
        if not sel:
            return
        vals = self._res_tree.item(sel[0], 'values')
        src, title, pain, score = vals[0], vals[1], vals[2], vals[3]

        # Find keywords from stored data
        keywords = []
        for t in self._research_topics:
            if t.get('generated_title', '') == title:
                keywords = t.get('keywords', [])
                break

        detail_text = (
            'Title    : {}\n'
            'Source   : {}  |  Score: {}\n'
            'Keywords : {}\n'
            'Pain     : {}'
        ).format(title, src, score or 'N/A', ', '.join(keywords), pain)

        self._set_text(self._res_detail, detail_text, readonly=True)
        self._btn_use_topic.configure(state='normal', fg=NAVY, cursor='hand2')

    def _on_use_research_topic(self):
        sel = self._res_tree.selection()
        if not sel:
            return
        vals = self._res_tree.item(sel[0], 'values')
        title, source = vals[1], vals[0]
        self._topic_var.set(title)
        self._cal_day       = None
        self._content_angle = ''
        self._topic_source_lbl.configure(
            text='From research: {}'.format(source), fg=REDDIT if source.startswith('r/') else LINKEDIN)
        # Switch to Generate tab (index 1)
        self._nb.select(1)
        self._log('Topic selected from research: "{}"'.format(title))

    def _on_clear_research(self):
        self._research_topics = []
        self._res_tree.delete(*self._res_tree.get_children())
        self._set_text(self._res_detail, '', readonly=True)
        self._research_count_lbl.configure(text='')
        self._btn_use_topic.configure(state='disabled', fg=WHITE40, cursor='')

    def _refresh_research_last_run(self):
        last = _m()['get_last_run']()
        self._research_last_run_lbl.configure(
            text='Last run: {}'.format(last) if last else 'Last run: never')

    def _on_stop_operation(self):
        """Cancel any in-progress long-running operation (research, batch gen, scoring)."""
        self._cancel_event.set()
        self._log('Operation cancelled by user.')
        self._progress.stop()
        self._research_progress.stop()
        self._sched_progress.stop()
        self._set_status('Cancelled', ORANGE)

    def _on_send_research_to_scheduler(self):
        """Carry research topics forward to scheduler batch generate."""
        if not self._research_topics:
            messagebox.showinfo('No topics', 'Run Research first to discover topics.')
            return
        # Switch to scheduler tab and set source to 'research'
        self._sched_gen_source.set('research')
        count = len(self._research_topics)
        self._nb.select(4)  # scheduler tab index
        self._log('{} research topics available for batch generate.'.format(count))

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — GENERATE
    # ══════════════════════════════════════════════════════════════════════════

    def _build_generate_tab(self, tab):
        left = tk.Frame(tab, bg=NAVY, width=370)
        left.pack(side='left', fill='y', padx=(16, 8), pady=16)
        left.pack_propagate(False)

        # Content Calendar
        self._lbl(left, 'CONTENT CALENDAR  (30-day plan)')
        cal_card = self._card(left)
        self._cal_list = tk.Listbox(
            cal_card, height=8, bg=NAVY_MID, fg=WHITE, font=(FONT, 9),
            selectbackground=CYAN, selectforeground=NAVY,
            borderwidth=0, highlightthickness=0,
            activestyle='none', exportselection=False,
        )
        self._cal_list.pack(fill='x', padx=2, pady=2)
        self._cal_list.bind('<<ListboxSelect>>', self._on_cal_select)

        self._cal_info = tk.Label(
            left, text='', font=(FONT, 8), bg=NAVY_LIGHT, fg=CYAN,
            wraplength=350, justify='left', anchor='w', padx=8, pady=6,
        )
        self._cal_info.pack(fill='x', pady=(2, 0))

        # Custom topic
        self._lbl(left, 'TOPIC')
        self._topic_var = tk.StringVar()
        topic_card = self._card(left)
        self._topic_entry = tk.Entry(
            topic_card, textvariable=self._topic_var,
            bg=NAVY_MID, fg=WHITE, font=(FONT, 11), insertbackground=WHITE,
            borderwidth=0, highlightthickness=0,
        )
        self._topic_entry.pack(fill='x', padx=6, pady=6)
        self._topic_source_lbl = tk.Label(
            left, text='', font=(FONT, 7), bg=NAVY, fg=WHITE40, anchor='w')
        self._topic_source_lbl.pack(fill='x', pady=(1, 0))

        # Trending Topics
        self._lbl(left, 'TRENDING TOPICS')
        trend_card = self._card(left)
        self._trend_list = tk.Listbox(
            trend_card, height=4, bg=NAVY_MID, fg=WHITE, font=(FONT, 9),
            selectbackground=CYAN, selectforeground=NAVY,
            borderwidth=0, highlightthickness=0,
            activestyle='none', exportselection=False,
        )
        self._trend_list.pack(fill='x', padx=2, pady=2)
        self._trend_list.bind('<<ListboxSelect>>', self._on_trend_select)

        self._btn(left, 'Fetch Trending Topics', self._on_fetch_trending,
                  style='ghost').pack(fill='x', pady=(4, 0))

        # Action buttons
        self._lbl(left, 'ACTIONS')
        self._btn_gen = self._btn(left, 'Generate Blog + LinkedIn Post', self._on_generate)
        self._btn_gen.pack(fill='x', pady=(0, 4))
        self._btn_li_only = self._btn(left, 'Generate LinkedIn Post Only',
                                       self._on_generate_li_only, style='ghost')
        self._btn_li_only.pack(fill='x', pady=(0, 4))

        self._btn_edit = self._btn(left, 'Edit Blog Sections', self._on_edit_blog,
                                   style='ghost')
        self._btn_edit.pack(fill='x', pady=(0, 4))
        self._btn_edit.configure(state='disabled', fg=WHITE40)

        # Publish mode selector
        self._lbl(left, 'PUBLISH MODE')
        mode_card = self._card(left, pady=(0, 4))
        self._publish_mode_var = tk.StringVar(value='blog_and_li')
        for label, val in [
            ('Blog + LinkedIn Post', 'blog_and_li'),
            ('Blog Only (no LinkedIn)', 'blog_only'),
            ('LinkedIn Post Only', 'li_only'),
        ]:
            tk.Radiobutton(
                mode_card, text=label, variable=self._publish_mode_var, value=val,
                bg=NAVY_MID, fg=WHITE, selectcolor=NAVY_LIGHT,
                activebackground=NAVY_MID, activeforeground=CYAN,
                font=(FONT, 9), anchor='w', borderwidth=0, highlightthickness=0,
            ).pack(fill='x', padx=10, pady=2)
        tk.Label(mode_card,
                 text='LinkedIn Only: uses phoenixsolution.in as the link',
                 font=(FONT, 7), bg=NAVY_MID, fg=WHITE40,
                 wraplength=260, justify='left').pack(fill='x', padx=10, pady=(0, 6))

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
            self._topic_source_lbl.configure(text='From calendar: Day {:02d}'.format(day), fg=CYAN)

    def _on_trend_select(self, _):
        sel = self._trend_list.curselection()
        if sel:
            self._topic_var.set(self._trend_list.get(sel[0]))
            self._cal_day       = None
            self._content_angle = ''
            self._cal_info.configure(text='')
            self._topic_source_lbl.configure(text='From trending topics', fg=ORANGE)

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

    # ── LinkedIn-only generation ────────────────────────────────────────────

    def _on_generate_li_only(self):
        """Generate a standalone LinkedIn post without a blog."""
        topic = self._topic_var.get().strip()
        if not topic:
            messagebox.showwarning('No topic',
                'Select a calendar day, a trending topic, or enter a custom topic.')
            return

        self._log('LinkedIn-only post requested: "{}"'.format(topic))

        def _work():
            m  = _m()
            self._log('Calling Groq API — standalone LinkedIn post...')
            li = m['generate_linkedin_post'](topic, None)  # standalone mode
            self._log('LinkedIn post generated ({} words).'.format(
                len(li['caption'].split())))

            # Save and track
            from datetime import datetime
            publish_date = datetime.now().strftime('%Y-%m-%d')
            li_path = m['save_linkedin_post'](li, topic, publish_date=publish_date)
            tid = m['tracker_add'](
                topic=topic, blog_path='', linkedin_path=li_path,
                hashtags=li['hashtags'], website_url='',
            )
            return li, li_path, tid

        self._run_async(
            fn=_work,
            callback=self._on_generate_li_only_done,
            label='Generating LinkedIn post via Groq...',
            err='LinkedIn generation failed. Check GROQ_API_KEY in your .env file.',
        )

    def _on_generate_li_only_done(self, result):
        li, li_path, post_id = result
        self._blog_data  = None
        self._li_data    = li
        self._image_info = None
        self._blog_url   = ''

        self._set_text(self._blog_prev,
                       '(No blog generated — LinkedIn-only post)\n\n'
                       'Post ID: {}\nSaved: {}'.format(post_id, li_path),
                       readonly=True)
        self._set_text(self._li_prev, li['full_post'])
        self._set_status('LinkedIn post generated (ID {})'.format(post_id), GREEN)

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

        mode         = self._publish_mode_var.get()
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

        # ── LinkedIn Only ─────────────────────────────────────────────────────
        if mode == 'li_only':
            def _work_li_only():
                m = _m()
                website_link = 'https://www.phoenixsolution.in'
                self._log('LinkedIn Only — using site link: ' + website_link)
                li_path = m['save_linkedin_post'](
                    li_data, topic, cal_day, publish_date, blog_url=website_link)
                self._log('LinkedIn TXT saved: ' + li_path)
                tracker_id = m['tracker_add'](
                    topic=topic, blog_path='', linkedin_path=li_path,
                    hashtags=hashtags, calendar_day=cal_day,
                    content_angle=content_angle, website_url=website_link,
                )
                self._log('Tracker entry created — #{}'.format(tracker_id))
                return tracker_id, '', li_path, website_link, None

            self._log('LinkedIn-only pipeline: "{}"'.format(topic))
            self._run_async(
                fn=_work_li_only,
                callback=self._on_approve_done,
                label='Saving LinkedIn post...',
                err='LinkedIn save failed.',
            )
            return

        # ── Blog Only ─────────────────────────────────────────────────────────
        if mode == 'blog_only':
            def _work_blog_only():
                m = _m()
                self._log('Blog Only — fetching Unsplash image...')
                img          = m['fetch_image'](blog.get('keywords', []), blog['slug'])
                image_local  = img['local_path'] if img else None
                image_public = img['public_url']  if img else None
                if img:
                    self._log('Image saved: ' + image_local)
                else:
                    self._log('No image — continuing without.', 'warning')
                self._log('Rendering and saving blog HTML...')
                blog_path = m['save_blog'](blog, publish_date, image_url=image_public)
                self._log('Blog HTML saved: ' + blog_path)
                self._log('Copying to website repo and updating index + sitemap...')
                result   = m['publish_to_website'](blog, blog_path, publish_date, image_local)
                blog_url = result['blog_url']
                self._log('Website updated. Live URL: ' + blog_url)
                self._log('Running git add / commit / push...')
                rc, out, err = m['git_push_website'](blog['slug'], blog['title'])
                if rc == 0:
                    self._log('Git push successful.')
                else:
                    self._log('Git push returned code {}: {}'.format(rc, err.strip()), 'warning')
                tracker_id = m['tracker_add'](
                    topic=topic, blog_path=blog_path, linkedin_path='',
                    hashtags=hashtags, calendar_day=cal_day,
                    content_angle=content_angle, website_url=blog_url,
                )
                self._log('Blog-only pipeline complete — Tracker #{}'.format(tracker_id))
                return tracker_id, blog_path, '', blog_url, image_local

            self._log('Blog-only pipeline: "{}"'.format(topic))
            self._run_async(
                fn=_work_blog_only,
                callback=self._on_approve_done,
                label='Publishing blog to website...',
                err='Blog publish failed.',
            )
            return

        # ── Blog + LinkedIn (full pipeline) ───────────────────────────────────
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

            # 4. Git push
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

        self._log('Starting full pipeline for: "{}"'.format(topic))
        self._run_async(
            fn=_work,
            callback=self._on_approve_done,
            label='Saving, publishing to website...',
            err='Publish pipeline failed.',
        )

    def _on_approve_done(self, result):
        tid, blog_path, li_path, blog_url, image_local = result
        self._blog_url    = blog_url
        self._image_info  = {'local_path': image_local} if image_local else None

        mode = self._publish_mode_var.get()
        self._set_status('Saved — Tracker #{}'.format(tid), GREEN)

        if mode == 'li_only':
            messagebox.showinfo(
                'LinkedIn Post Saved',
                'LinkedIn post saved (Tracker #{}).\n\n'
                'LinkedIn TXT: {}\n'
                'Site link   : {}\n\n'
                'Go to Publish tab to post to LinkedIn.'.format(tid, li_path, blog_url),
            )
        elif mode == 'blog_only':
            img_line = '\nImage : {}'.format(image_local) if image_local else ''
            messagebox.showinfo(
                'Blog Published',
                'Blog published to website (Tracker #{}).\n\n'
                'Blog  : {}\n'
                'Live  : {}{}'.format(tid, blog_path, blog_url, img_line),
            )
        else:
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
        self._topic_source_lbl.configure(text='', fg=WHITE40)
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

        # Company page checkbox — auto-checked if LINKEDIN_ORG_URN is set in .env
        self._pub_company_var = tk.BooleanVar(
            value=bool(os.getenv('LINKEDIN_ORG_URN', '').strip()))
        org_urn_set = bool(os.getenv('LINKEDIN_ORG_URN', '').strip())
        chk_label = 'Also post to Company Page' + ('' if org_urn_set else ' (set LINKEDIN_ORG_URN in .env)')
        tk.Checkbutton(
            act, text=chk_label, variable=self._pub_company_var,
            bg=NAVY_MID, fg=WHITE if org_urn_set else WHITE40,
            selectcolor=NAVY_LIGHT,
            activebackground=NAVY_MID, activeforeground=CYAN,
            font=(FONT, 9), borderwidth=0, highlightthickness=0,
        ).pack(side='right', padx=(0, 20), pady=14)

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
        image_path = os.path.join(_APP_DIR, 'Blogs', 'images', slug + '.jpg')
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

        org_urn_preview = os.getenv('LINKEDIN_ORG_URN', '').strip()
        company_line = ('\nCompany: ' + org_urn_preview) if (self._pub_company_var.get() and org_urn_preview) else ''

        if not messagebox.askyesno(
            'Confirm Publish',
            'Publish to LinkedIn?{}{}\n\nPreview:\n{}...'.format(
                img_line, company_line, li_text[:250]),
        ):
            return

        org_urn = None
        if self._pub_company_var.get():
            org_urn = os.getenv('LINKEDIN_ORG_URN', '').strip() or None
            if not org_urn:
                messagebox.showwarning(
                    'No Company URN',
                    'LINKEDIN_ORG_URN is not set in your .env file.\n'
                    'Add it as: urn:li:organization:YOUR_COMPANY_ID\n\n'
                    'Posting to personal profile only.')

        def _work():
            _m()['li_pub'](li_text, image_path=img, org_urn=org_urn)
            pub_date = datetime.now().strftime('%Y-%m-%d %H:%M')
            _m()['tracker_update'](post_id, 'posted', pub_date)
            return post_id

        target = 'LinkedIn profile + company page' if org_urn else 'LinkedIn'
        self._log('Publishing Tracker #{} to {}...'.format(post_id, target))
        self._pub_status_lbl.configure(text='Publishing...', fg=ORANGE)
        self._run_async(
            fn=_work,
            callback=lambda pid: self._on_publish_done(pid),
            label='Publishing to LinkedIn...',
            err='LinkedIn publish failed. See Activity Log below for the API error detail.',
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
    # TAB 5 — SCHEDULER
    # ══════════════════════════════════════════════════════════════════════════

    def _build_scheduler_tab(self, tab):
        import smart_scheduler as sched

        # ── Left panel — configuration ────────────────────────────────────────
        left = tk.Frame(tab, bg=NAVY, width=340)
        left.pack(side='left', fill='y', padx=(16, 8), pady=16)
        left.pack_propagate(False)

        # ── Mode ──────────────────────────────────────────────────────────────
        self._lbl(left, 'SELECTION MODE')
        mode_card = self._card(left, pady=(0, 4))
        self._sched_mode = tk.StringVar(value='auto')
        for label, val in [('Auto — AI picks best post', 'auto'),
                            ('Manual — I choose the post', 'manual')]:
            tk.Radiobutton(
                mode_card, text=label, variable=self._sched_mode, value=val,
                bg=NAVY_MID, fg=WHITE, selectcolor=NAVY_LIGHT,
                activebackground=NAVY_MID, activeforeground=CYAN,
                font=(FONT, 9), anchor='w', borderwidth=0, highlightthickness=0,
                command=self._on_sched_mode_change,
            ).pack(fill='x', padx=10, pady=3)

        # Manual ID entry (shown only in manual mode)
        self._sched_manual_row = tk.Frame(left, bg=NAVY)
        self._sched_manual_row.pack(fill='x', pady=(2, 0))
        tk.Label(self._sched_manual_row, text='Tracker ID:', font=(FONT, 9),
                 bg=NAVY, fg=WHITE60).pack(side='left')
        self._sched_manual_id = tk.StringVar()
        tk.Entry(self._sched_manual_row, textvariable=self._sched_manual_id,
                 width=7, bg=NAVY_MID, fg=WHITE, font=(FONT, 10),
                 insertbackground=WHITE, borderwidth=0,
                 highlightthickness=1, highlightcolor=CYAN,
                 highlightbackground=BORDER).pack(side='left', padx=(6, 0))
        self._sched_manual_row.pack_forget()   # hidden by default

        # ── Post target (personal only — company posting disabled) ────────────
        self._sched_target = tk.StringVar(value='personal')

        # ── Active days + content type per day ────────────────────────────────
        self._lbl(left, 'ACTIVE DAYS & CONTENT TYPE')
        days_card = self._card(left, pady=(0, 4))
        self._sched_day_vars = {}
        self._sched_day_type_vars = {}
        default_days = {'Mon', 'Tue', 'Wed', 'Thu', 'Fri'}
        default_blog_days = {'Mon', 'Wed'}
        for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
            row = tk.Frame(days_card, bg=NAVY_MID)
            row.pack(fill='x', padx=8, pady=1)
            var = tk.BooleanVar(value=day in default_days)
            self._sched_day_vars[day] = var
            tk.Checkbutton(
                row, text=day, variable=var, width=4,
                bg=NAVY_MID, fg=WHITE, selectcolor=NAVY_LIGHT,
                activebackground=NAVY_MID, activeforeground=CYAN,
                font=(FONT, 9), anchor='w', borderwidth=0, highlightthickness=0,
            ).pack(side='left')
            type_var = tk.StringVar(
                value='blog_and_li' if day in default_blog_days else 'li_only')
            self._sched_day_type_vars[day] = type_var
            ttk.Combobox(
                row, textvariable=type_var, width=15,
                values=['LinkedIn Only', 'Blog + LinkedIn'],
                state='readonly',
            ).pack(side='left', padx=(4, 0))

        # ── Options ───────────────────────────────────────────────────────────
        self._lbl(left, 'OPTIONS')
        opt_card = self._card(left, pady=(0, 4))
        self._sched_dry_run = tk.BooleanVar(value=False)
        tk.Checkbutton(opt_card, text='Dry Run (preview only — no actual posting)',
                       variable=self._sched_dry_run,
                       bg=NAVY_MID, fg=ORANGE, selectcolor=NAVY_LIGHT,
                       activebackground=NAVY_MID, activeforeground=ORANGE,
                       font=(FONT, 9), anchor='w', borderwidth=0,
                       highlightthickness=0).pack(fill='x', padx=10, pady=4)

        # ── Controls ──────────────────────────────────────────────────────────
        self._lbl(left, 'CONTROLS')
        self._btn_sched_start = self._btn(left, '  Start Scheduler  ',
                                          self._on_sched_start)
        self._btn_sched_start.pack(fill='x', pady=(0, 4))
        self._btn_sched_pause = self._btn(left, 'Pause Scheduler',
                                          self._on_sched_pause, style='ghost')
        self._btn_sched_pause.pack(fill='x', pady=(0, 4))
        self._btn_sched_stop = self._btn(left, 'Stop Scheduler',
                                         self._on_sched_stop, style='ghost')
        self._btn_sched_stop.pack(fill='x', pady=(0, 4))
        self._btn_sched_score = self._btn(left, 'Score All Pending Posts',
                                          self._on_sched_score, style='ghost')
        self._btn_sched_score.pack(fill='x', pady=(0, 8))

        # Dedicated progress bar for scheduler operations
        self._sched_progress = ttk.Progressbar(
            left, mode='indeterminate', style='Phoenix.Horizontal.TProgressbar')
        self._sched_progress.pack(fill='x', pady=(0, 6))

        self._sched_status_lbl = tk.Label(
            left, text='Scheduler: stopped', font=(FONT, 9, 'bold'),
            bg=NAVY, fg=WHITE40, anchor='w')
        self._sched_status_lbl.pack(fill='x')

        self._sched_next_lbl = tk.Label(
            left, text='', font=(FONT, 8), bg=NAVY, fg=CYAN, anchor='w',
            wraplength=300, justify='left')
        self._sched_next_lbl.pack(fill='x')

        # Load saved config
        self.after(400, self._sched_load_config)

        # ── Right panel — time slots + scored posts ───────────────────────────
        right = tk.Frame(tab, bg=NAVY)
        right.pack(side='left', fill='both', expand=True, padx=(8, 16), pady=16)

        # ── Time slots ────────────────────────────────────────────────────────
        slot_hdr = tk.Frame(right, bg=NAVY)
        slot_hdr.pack(fill='x')
        self._lbl(slot_hdr, 'POSTING TIMES  (add up to 5 slots per day, 24h format)')
        self._btn(slot_hdr, '+ Add Slot', self._on_sched_add_slot,
                  style='ghost').pack(side='right', pady=(12, 4))

        self._slot_frame = tk.Frame(right, bg=NAVY)
        self._slot_frame.pack(fill='x', pady=(0, 8))
        self._slot_widgets = []    # list of (frame, StringVar) tuples

        # ── Batch Generate ────────────────────────────────────────────────────
        self._lbl(right, 'BATCH GENERATE POSTS  (saved as drafts, scored automatically)')
        gen_card = self._card(right, pady=(0, 8))
        gen_inner = tk.Frame(gen_card, bg=NAVY_MID)
        gen_inner.pack(fill='x', padx=8, pady=6)

        # Row 1: Source
        src_row = tk.Frame(gen_inner, bg=NAVY_MID)
        src_row.pack(fill='x', pady=(0, 4))
        tk.Label(src_row, text='Source:', font=(FONT, 9), bg=NAVY_MID,
                 fg=WHITE60, width=10, anchor='w').pack(side='left')
        self._sched_gen_source = tk.StringVar(value='calendar')
        for lbl, val in [('Content Calendar', 'calendar'),
                          ('Research Topics',  'research')]:
            tk.Radiobutton(src_row, text=lbl, variable=self._sched_gen_source,
                           value=val, bg=NAVY_MID, fg=WHITE, selectcolor=NAVY_LIGHT,
                           activebackground=NAVY_MID, activeforeground=CYAN,
                           font=(FONT, 9), borderwidth=0,
                           highlightthickness=0).pack(side='left', padx=(0, 14))

        # Row 2: Content type
        ct_row = tk.Frame(gen_inner, bg=NAVY_MID)
        ct_row.pack(fill='x', pady=(0, 4))
        tk.Label(ct_row, text='Content:', font=(FONT, 9), bg=NAVY_MID,
                 fg=WHITE60, width=10, anchor='w').pack(side='left')
        self._sched_gen_mode = tk.StringVar(value='li_only')
        for lbl, val in [('LinkedIn Post Only', 'li_only'),
                          ('Blog + LinkedIn',    'blog_and_li')]:
            tk.Radiobutton(ct_row, text=lbl, variable=self._sched_gen_mode,
                           value=val, bg=NAVY_MID, fg=WHITE, selectcolor=NAVY_LIGHT,
                           activebackground=NAVY_MID, activeforeground=CYAN,
                           font=(FONT, 9), borderwidth=0,
                           highlightthickness=0).pack(side='left', padx=(0, 14))

        # Row 3: Count + button
        cnt_row = tk.Frame(gen_inner, bg=NAVY_MID)
        cnt_row.pack(fill='x', pady=(0, 2))
        tk.Label(cnt_row, text='Max posts:', font=(FONT, 9), bg=NAVY_MID,
                 fg=WHITE60, width=10, anchor='w').pack(side='left')
        self._sched_gen_count = tk.StringVar(value='5')
        tk.Entry(cnt_row, textvariable=self._sched_gen_count, width=5,
                 bg=NAVY_LIGHT, fg=WHITE, font=(FONT, 10), insertbackground=WHITE,
                 borderwidth=0, highlightthickness=1, highlightcolor=CYAN,
                 highlightbackground=BORDER).pack(side='left', padx=(0, 6))
        tk.Label(cnt_row, text='(0 = all)', font=(FONT, 8),
                 bg=NAVY_MID, fg=WHITE40).pack(side='left', padx=(0, 14))
        self._btn(cnt_row, 'Generate & Queue',
                  self._on_sched_generate_batch, style='ghost').pack(side='left')
        self._btn(cnt_row, 'Stop',
                  self._on_stop_operation, style='ghost').pack(side='left', padx=(4, 0))
        self._sched_gen_lbl = tk.Label(cnt_row, text='', font=(FONT, 8),
                                       bg=NAVY_MID, fg=CYAN)
        self._sched_gen_lbl.pack(side='left', padx=(10, 0))

        # ── Scored posts leaderboard ──────────────────────────────────────────
        score_hdr = tk.Frame(right, bg=NAVY)
        score_hdr.pack(fill='x')
        self._sched_score_count = tk.Label(score_hdr, text='', font=(FONT, 9, 'bold'),
                                           bg=NAVY, fg=CYAN)
        self._sched_score_count.pack(side='right', padx=4, pady=(12, 4))
        self._lbl(score_hdr, 'POST LEADERBOARD  (ranked by AI score)')

        cols = ('rank', 'id', 'topic', 'score', 'sentiment', 'hooks', 'length', 'image')
        self._score_tree = ttk.Treeview(
            right, columns=cols, show='headings',
            style='Phoenix.Treeview', selectmode='browse', height=10,
        )
        for col, label, w, stretch in [
            ('rank',      '#',         35,  False),
            ('id',        'ID',        40,  False),
            ('topic',     'Topic',    280,  True),
            ('score',     'Score',     60,  False),
            ('sentiment', 'Sentiment', 75,  False),
            ('hooks',     'Hooks',     55,  False),
            ('length',    'Length',    55,  False),
            ('image',     'Image',     50,  False),
        ]:
            self._score_tree.heading(col, text=label, anchor='w')
            self._score_tree.column(col, width=w, stretch=stretch, minwidth=30)

        score_vsb = ttk.Scrollbar(right, orient='vertical',
                                   command=self._score_tree.yview)
        self._score_tree.configure(yscrollcommand=score_vsb.set)
        self._score_tree.pack(fill='both', expand=True)
        score_vsb.place(relx=1.0, rely=0, relheight=0.7, anchor='ne', x=-2)

        self._score_tree.tag_configure('top',  foreground=GREEN)
        self._score_tree.tag_configure('mid',  foreground=CYAN)
        self._score_tree.tag_configure('low',  foreground=WHITE60)

        # Detail panel
        detail = tk.Frame(right, bg=NAVY_MID, highlightbackground=BORDER,
                          highlightthickness=1, height=80)
        detail.pack(fill='x', pady=(6, 0))
        detail.pack_propagate(False)
        self._score_detail = scrolledtext.ScrolledText(
            detail, bg=NAVY_MID, fg=WHITE60, font=(FONT, 9),
            wrap='word', state='disabled', borderwidth=0,
            highlightthickness=0, padx=10, pady=6,
        )
        self._score_detail.pack(fill='both', expand=True)
        self._score_tree.bind('<<TreeviewSelect>>', self._on_score_select)
        self._sched_scored_cache = []

        # Add default 2 slots
        self._on_sched_add_slot('09:00')
        self._on_sched_add_slot('17:00')

    def _on_sched_mode_change(self):
        if self._sched_mode.get() == 'manual':
            self._sched_manual_row.pack(fill='x', pady=(2, 0))
        else:
            self._sched_manual_row.pack_forget()

    def _on_sched_add_slot(self, default='12:00'):
        if len(self._slot_widgets) >= 5:
            return
        row = tk.Frame(self._slot_frame, bg=NAVY)
        row.pack(fill='x', pady=2)
        var = tk.StringVar(value=default if isinstance(default, str) else '12:00')
        tk.Label(row, text='Post at:', font=(FONT, 9), bg=NAVY,
                 fg=WHITE60).pack(side='left', padx=(0, 6))
        tk.Entry(row, textvariable=var, width=8,
                 bg=NAVY_MID, fg=WHITE, font=(FONT, 11), insertbackground=WHITE,
                 borderwidth=0, highlightthickness=1,
                 highlightcolor=CYAN, highlightbackground=BORDER,
                 ).pack(side='left', padx=(0, 6))
        tk.Label(row, text='(HH:MM  24h)', font=(FONT, 8),
                 bg=NAVY, fg=WHITE40).pack(side='left')

        def _remove(r=row, entry=(row, var)):
            r.destroy()
            if entry in self._slot_widgets:
                self._slot_widgets.remove(entry)

        rm = tk.Label(row, text='✕', font=(FONT, 10), bg=NAVY, fg=RED,
                      cursor='hand2', padx=6)
        rm.pack(side='right')
        rm.bind('<Button-1>', lambda _: _remove())
        self._slot_widgets.append((row, var))

    def _sched_load_config(self):
        """Load saved scheduler config into the UI."""
        import smart_scheduler as sched
        cfg = sched.load_config()
        self._sched_mode.set(cfg.get('mode', 'auto'))
        self._on_sched_mode_change()
        if cfg.get('manual_id'):
            self._sched_manual_id.set(str(cfg['manual_id']))
        self._sched_target.set('personal')  # always personal
        self._sched_dry_run.set(cfg.get('dry_run', False))
        days = set(cfg.get('days', []))
        day_types = cfg.get('day_content_type', {})
        for d, var in self._sched_day_vars.items():
            var.set(d in days)
        # Restore day content types
        for d, tvar in self._sched_day_type_vars.items():
            saved = day_types.get(d, 'li_only')
            tvar.set('Blog + LinkedIn' if saved == 'blog_and_li' else 'LinkedIn Only')
        # Restore saved slots
        saved_slots = cfg.get('slots', [])
        if saved_slots:
            # Remove default slots and re-add from config
            for w, _ in list(self._slot_widgets):
                w.destroy()
            self._slot_widgets.clear()
            for s in saved_slots:
                self._on_sched_add_slot(s)

    def _sched_build_config(self) -> dict:
        """Read UI state into a config dict."""
        slots = []
        for _, var in self._slot_widgets:
            val = var.get().strip()
            if val:
                slots.append(val)
        day_content_type = {}
        for d, tvar in self._sched_day_type_vars.items():
            day_content_type[d] = 'blog_and_li' if 'Blog' in tvar.get() else 'li_only'
        return {
            'enabled':           True,
            'slots':             slots,
            'mode':              self._sched_mode.get(),
            'manual_id':         self._sched_manual_id.get().strip() or None,
            'post_target':       'personal',
            'dry_run':           self._sched_dry_run.get(),
            'days':              [d for d, var in self._sched_day_vars.items() if var.get()],
            'day_content_type':  day_content_type,
        }

    # ── Scheduler-specific async runner ──────────────────────────────────────

    def _sched_run_async(self, fn, callback, label='Working...', err='Error'):
        """Like _run_async but drives the scheduler's own progress bar."""
        self._sched_progress.start(12)
        self._sched_status_lbl.configure(text=label, fg=ORANGE)

        def _worker():
            try:
                result = fn()
                self.after(0, lambda r=result: self._sched_async_done(callback, r))
            except Exception as exc:
                self.after(0, lambda e=exc: self._sched_async_fail(err, e))

        threading.Thread(target=_worker, daemon=True).start()

    def _sched_async_done(self, callback, result):
        self._sched_progress.stop()
        self._sched_status_lbl.configure(text='Scheduler: stopped', fg=WHITE40)
        callback(result)

    def _sched_async_fail(self, msg, exc):
        self._sched_progress.stop()
        self._sched_status_lbl.configure(text='Error', fg=RED)
        self._log('{} — {}'.format(msg, exc), 'error')
        messagebox.showerror('Scheduler Error', '{}\n\n{}'.format(msg, exc))

    def _on_sched_start(self):
        try:
            import smart_scheduler as sched
            cfg = self._sched_build_config()
            if not cfg['slots']:
                messagebox.showwarning('No slots', 'Add at least one posting time slot.')
                return
            if not cfg['days']:
                messagebox.showwarning('No days', 'Select at least one active day.')
                return
            sched.save_config(cfg)
            self._log('Scheduler config saved. Starting...')

            def _on_log(msg, lvl='info'):
                self.after(0, lambda m=msg, l=lvl: self._log(m, l))

            def _on_status(event, dt):
                def _update():
                    if event == 'next' and dt:
                        self._sched_status_lbl.configure(
                            text='Scheduler: RUNNING', fg=GREEN)
                        self._sched_next_lbl.configure(
                            text='Next post: {}'.format(
                                dt.strftime('%a %d %b  %H:%M')))
                    elif event == 'fired':
                        self._sched_next_lbl.configure(
                            text='Last fired: {}'.format(
                                dt.strftime('%H:%M') if dt else '—'))
                    elif event == 'paused':
                        self._sched_status_lbl.configure(
                            text='Scheduler: PAUSED', fg=ORANGE)
                        self._sched_next_lbl.configure(text='Paused — click Resume to continue')
                        self._btn_sched_pause.configure(text='Resume Scheduler')
                    elif event == 'resumed':
                        self._sched_status_lbl.configure(
                            text='Scheduler: RUNNING', fg=GREEN)
                        self._btn_sched_pause.configure(text='Pause Scheduler')
                    elif event == 'stopped':
                        self._sched_status_lbl.configure(
                            text='Scheduler: stopped', fg=WHITE40)
                        self._sched_next_lbl.configure(text='')
                        self._btn_sched_pause.configure(text='Pause Scheduler')
                self.after(0, _update)

            sched.start_scheduler(on_log=_on_log, on_status_change=_on_status)
            self._sched_status_lbl.configure(text='Scheduler: starting…', fg=ORANGE)
            next_dt = sched.get_next_fire(cfg)
            if next_dt:
                self._sched_next_lbl.configure(
                    text='Next post: {}'.format(next_dt.strftime('%a %d %b  %H:%M')))
        except Exception as exc:
            self._log('Scheduler start failed: {}'.format(exc), 'error')
            messagebox.showerror('Scheduler Error', str(exc))

    def _on_sched_stop(self):
        try:
            import smart_scheduler as sched
            cfg = self._sched_build_config()
            cfg['enabled'] = False
            sched.save_config(cfg)
            sched.stop_scheduler()
            self._sched_status_lbl.configure(text='Scheduler: stopped', fg=WHITE40)
            self._sched_next_lbl.configure(text='')
            self._btn_sched_pause.configure(text='Pause Scheduler')
            self._log('Scheduler stopped.')
        except Exception as exc:
            self._log('Scheduler stop failed: {}'.format(exc), 'error')
            messagebox.showerror('Scheduler Error', str(exc))

    def _on_sched_pause(self):
        try:
            import smart_scheduler as sched
            if sched.is_paused():
                sched.resume_scheduler()
                self._sched_status_lbl.configure(text='Scheduler: RUNNING', fg=GREEN)
                self._btn_sched_pause.configure(text='Pause Scheduler')
                self._log('Scheduler resumed.')
            elif sched.is_running():
                sched.pause_scheduler()
                self._sched_status_lbl.configure(text='Scheduler: PAUSED', fg=ORANGE)
                self._sched_next_lbl.configure(text='Paused — click Resume to continue')
                self._btn_sched_pause.configure(text='Resume Scheduler')
                self._log('Scheduler paused.')
            else:
                self._log('Scheduler is not running.', 'warning')
        except Exception as exc:
            self._log('Scheduler pause/resume failed: {}'.format(exc), 'error')
            messagebox.showerror('Scheduler Error', str(exc))

    def _on_sched_score(self):
        self._cancel_event.clear()
        self._log('Scoring all pending posts via Groq AI...')

        def _work():
            import smart_scheduler as sched
            return sched.score_all_pending(use_ai=True, cancel_event=self._cancel_event)

        def _done(scored):
            cancelled = self._cancel_event.is_set()
            self._score_tree.delete(*self._score_tree.get_children())
            self._sched_scored_cache = scored
            for i, row in enumerate(scored, 1):
                tag = 'top' if i == 1 else ('mid' if i <= 3 else 'low')
                self._score_tree.insert('', 'end', iid=str(row['id']), values=(
                    i,
                    row['id'],
                    row.get('topic', '')[:50],
                    '{:.1f}'.format(row.get('score', 0)),
                    '{:.1f}'.format(row.get('s_sentiment', 0)),
                    '{:.1f}'.format(row.get('s_hooks', 0)),
                    '{:.1f}'.format(row.get('s_length', 0)),
                    'Yes' if row.get('s_image', 0) > 0 else 'No',
                ), tags=(tag,))
            count = len(scored)
            self._sched_score_count.configure(
                text='{} post{} scored{}'.format(count, 's' if count != 1 else '',
                                                  ' (cancelled)' if cancelled else ''))
            if cancelled:
                self._log('Scoring cancelled — {} posts scored before stop.'.format(count))
            else:
                self._log('Scoring complete — {} posts ranked.'.format(count))
            if count == 0 and not cancelled:
                messagebox.showinfo('No posts', 'No draft/scheduled posts found.\nGenerate some posts first.')

        self._sched_run_async(fn=_work, callback=_done,
                              label='Scoring via Groq AI...',
                              err='Scoring failed.')

    def _on_sched_generate_batch(self):
        source = self._sched_gen_source.get()
        mode   = self._sched_gen_mode.get()
        try:
            max_count = int(self._sched_gen_count.get())
        except ValueError:
            max_count = 5

        self._cancel_event.clear()  # reset cancel flag
        self._log('Batch generate: source={}, mode={}, max={}'.format(
            source, mode, max_count or 'all'))
        self._sched_gen_lbl.configure(text='Working…', fg=ORANGE)

        def _work():
            m = _m()
            publish_date = datetime.now().strftime('%Y-%m-%d')
            existing = {r['topic'].lower() for r in m['tracker_read']()}

            # Build topic list
            if source == 'calendar':
                calendar = m['load_calendar']()
                topics_data = [
                    {'topic': e['topic'], 'angle': e.get('content_angle', ''),
                     'keywords': e.get('keywords', []), 'day': e['day']}
                    for e in calendar if e['topic'].lower() not in existing
                ]
            else:
                from topic_researcher import load_saved_research
                raw = load_saved_research()
                if not raw:
                    raise ValueError('No research topics saved. Run Research tab first.')
                topics_data = [
                    {'topic': t['generated_title'], 'angle': t.get('pain_point', ''),
                     'keywords': t.get('keywords', []), 'day': None}
                    for t in raw if t['generated_title'].lower() not in existing
                ]

            if max_count > 0:
                topics_data = topics_data[:max_count]

            if not topics_data:
                raise ValueError('No new topics to generate (all already in tracker).')

            generated = []
            import time as _time
            for i, td in enumerate(topics_data, 1):
                if self._cancel_event.is_set():
                    self._log('Batch generate cancelled by user.')
                    break
                topic = td['topic']
                self._log('Generating {}/{}: "{}"'.format(
                    i, len(topics_data), topic[:50]))
                try:
                    blog = m['generate_blog'](topic, td['angle'], td['keywords'])
                    _time.sleep(2)  # rate limit between API calls
                    if self._cancel_event.is_set():
                        break
                    li   = m['generate_linkedin_post'](topic, blog)
                    full_post = li.get('full_post', '')
                    parts_ = full_post.rsplit('\n\n', 1)
                    caption  = parts_[0] if len(parts_) == 2 else full_post
                    hashtags = parts_[1] if len(parts_) == 2 else li.get('hashtags', '')
                    li_data  = {'caption': caption, 'hashtags': hashtags,
                                'full_post': full_post}

                    if mode == 'li_only':
                        website_link = 'https://www.phoenixsolution.in'
                        li_path = m['save_linkedin_post'](
                            li_data, topic, td.get('day'),
                            publish_date, blog_url=website_link)
                        tid = m['tracker_add'](
                            topic=topic, blog_path='', linkedin_path=li_path,
                            hashtags=hashtags, calendar_day=td.get('day'),
                            content_angle=td['angle'], website_url=website_link)
                    else:
                        blog_path = m['save_blog'](blog, publish_date)
                        li_path   = m['save_linkedin_post'](
                            li_data, topic, td.get('day'), publish_date, blog_url='')
                        tid = m['tracker_add'](
                            topic=topic, blog_path=blog_path, linkedin_path=li_path,
                            hashtags=hashtags, calendar_day=td.get('day'),
                            content_angle=td['angle'], website_url='')

                    generated.append({'id': tid, 'topic': topic})
                    self._log('Queued as Tracker #{}: "{}"'.format(tid, topic[:50]))
                    # Rate limit between posts
                    if i < len(topics_data):
                        _time.sleep(2)
                except Exception as exc:
                    self._log('Failed "{}": {} — waiting 60s before next attempt.'.format(
                        topic[:40], exc), 'warning')
                    _time.sleep(60)  # wait 60s on failure before continuing

            return generated

        def _done(generated):
            count = len(generated)
            self._sched_gen_lbl.configure(
                text='{} post{} queued'.format(count, 's' if count != 1 else ''),
                fg=GREEN if count > 0 else ORANGE)
            self._log('Batch complete: {} posts saved as drafts.'.format(count))
            self._on_tracker_refresh()
            if count > 0:
                self.after(300, self._on_sched_score)

        self._sched_run_async(fn=_work, callback=_done,
                              label='Generating posts…',
                              err='Batch generation failed.')

    def _on_score_select(self, _):
        sel = self._score_tree.selection()
        if not sel:
            return
        cache = getattr(self, '_sched_scored_cache', [])
        row = next((r for r in cache if str(r['id']) == sel[0]), None)
        if not row:
            return
        detail = (
            'Topic     : {}\n'
            'Total     : {:.1f} / 100\n'
            'Sentiment : {:.1f}/25   Hooks: {:.1f}/20   Keywords: {:.1f}/15\n'
            'Freshness : {:.1f}/15   Length: {:.1f}/15  Image: {:.1f}/10\n'
            'Status    : {}   Generated: {}'
        ).format(
            row.get('topic', ''),
            row.get('score', 0),
            row.get('s_sentiment', 0), row.get('s_hooks', 0),
            row.get('s_keywords', 0), row.get('s_freshness', 0),
            row.get('s_length', 0),   row.get('s_image', 0),
            row.get('status', ''),    row.get('generated_date', ''),
        )
        self._set_text(self._score_detail, detail, readonly=True)
        # Auto-fill manual ID when user clicks a post
        self._sched_manual_id.set(str(row['id']))

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 6 — SETTINGS
    # ══════════════════════════════════════════════════════════════════════════

    def _build_settings_tab(self, tab):
        self._settings_vars = {}

        # ── Action bar (packed first so it anchors to bottom) ─────────────────
        act = tk.Frame(tab, bg=NAVY_MID, height=56)
        act.pack(fill='x', side='bottom')
        act.pack_propagate(False)
        self._btn(act, '  Save Settings  ', self._on_settings_save).pack(
            side='right', padx=16, pady=10)
        self._btn(act, 'Reload from .env', self._on_settings_reload,
                  style='ghost').pack(side='right', padx=(0, 8), pady=10)
        # Clear forever — use a red-tinted ghost
        clr = self._btn(act, 'Clear All Forever', self._on_settings_clear, style='ghost')
        clr.configure(fg=RED)
        clr.pack(side='left', padx=16, pady=10)

        # ── Scrollable form ───────────────────────────────────────────────────
        canvas = tk.Canvas(tab, bg=NAVY, borderwidth=0, highlightthickness=0)
        vsb    = ttk.Scrollbar(tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner = tk.Frame(canvas, bg=NAVY)
        win   = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _resize(_):
            canvas.configure(scrollregion=canvas.bbox('all'))
            canvas.itemconfig(win, width=canvas.winfo_width())

        inner.bind('<Configure>', _resize)
        canvas.bind('<Configure>', _resize)
        canvas.bind('<MouseWheel>',
                    lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))

        # ── Field factory ─────────────────────────────────────────────────────
        def _field(parent, label, env_key, secret=False, is_path=False, options=None):
            row = tk.Frame(parent, bg=NAVY)
            row.pack(fill='x', padx=24, pady=(0, 8))

            tk.Label(row, text=label, font=(FONT, 9), bg=NAVY, fg=WHITE60,
                     width=22, anchor='w').pack(side='left')

            val = os.getenv(env_key, '')

            if options:
                var = tk.StringVar(value=val or options[0])
                ttk.Combobox(row, textvariable=var, values=options,
                             state='readonly', font=(FONT, 10),
                             width=44).pack(side='left')
            else:
                var = tk.StringVar(value=val)
                ent = tk.Entry(
                    row, textvariable=var, show='*' if secret else '',
                    bg=NAVY_MID, fg=WHITE, font=(FONT, 10),
                    insertbackground=WHITE, borderwidth=0,
                    highlightthickness=1, highlightcolor=CYAN,
                    highlightbackground=BORDER,
                )
                ent.pack(side='left', fill='x', expand=True, padx=(0, 6))

                if secret:
                    def _toggle(e=ent):
                        e.configure(show='' if e.cget('show') == '*' else '*')
                    show_lbl = tk.Label(row, text='Show', font=(FONT, 8),
                                        bg=NAVY_LIGHT, fg=WHITE40,
                                        cursor='hand2', padx=8, pady=4)
                    show_lbl.pack(side='left', padx=(0, 4))
                    show_lbl.bind('<Button-1>', lambda _: _toggle())

                if is_path:
                    def _browse(v=var):
                        d = filedialog.askdirectory(
                            title='Select folder',
                            initialdir=v.get() or 'C:\\')
                        if d:
                            v.set(os.path.normpath(d))
                    brw_lbl = tk.Label(row, text='Browse', font=(FONT, 8),
                                       bg=NAVY_LIGHT, fg=WHITE40,
                                       cursor='hand2', padx=8, pady=4)
                    brw_lbl.pack(side='left')
                    brw_lbl.bind('<Button-1>', lambda _: _browse())

            self._settings_vars[env_key] = var

        # ── GROQ AI ───────────────────────────────────────────────────────────
        self._lbl(inner, 'GROQ AI  —  console.groq.com', accent=CYAN_DIM)
        _field(inner, 'API Key',  'GROQ_API_KEY',  secret=True)
        _field(inner, 'Model',    'GROQ_MODEL',
               options=['llama-3.3-70b-versatile', 'llama-3.1-8b-instant'])

        # ── LINKEDIN ──────────────────────────────────────────────────────────
        self._lbl(inner, 'LINKEDIN  —  linkedin.com/developers', accent=LINKEDIN)
        _field(inner, 'Access Token',      'LINKEDIN_ACCESS_TOKEN', secret=True)
        _field(inner, 'Person URN',        'LINKEDIN_PERSON_URN')
        _field(inner, 'Org URN (company)', 'LINKEDIN_ORG_URN')
        _field(inner, 'Client ID',         'LINKEDIN_CLIENT_ID',     secret=True)
        _field(inner, 'Client Secret',     'LINKEDIN_CLIENT_SECRET', secret=True)
        tk.Label(inner,
                 text='  Person URN: urn:li:person:<id>   |   Org URN: urn:li:organization:<id>',
                 font=(FONT, 7), bg=NAVY, fg=WHITE40,
                 ).pack(anchor='w', padx=24, pady=(0, 6))

        # ── UNSPLASH ──────────────────────────────────────────────────────────
        self._lbl(inner, 'UNSPLASH  —  unsplash.com/developers', accent=ORANGE)
        _field(inner, 'Access Key', 'UNSPLASH_ACCESS_KEY', secret=True)

        # ── WEBSITE REPO ──────────────────────────────────────────────────────
        self._lbl(inner, 'WEBSITE REPO', accent=GREEN_DIM)
        _field(inner, 'Repo Path', 'WEBSITE_REPO_PATH', is_path=True)

        tk.Frame(inner, bg=NAVY, height=20).pack()   # bottom padding

    def _on_settings_save(self):
        env_path = os.path.join(_APP_DIR, '.env')
        updates  = {k: v.get().strip() for k, v in self._settings_vars.items()}

        # Read existing .env preserving comments and order
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            lines = []

        found    = set()
        new_lines = []
        for line in lines:
            stripped = line.rstrip('\n')
            if stripped.lstrip().startswith('#') or not stripped.strip():
                new_lines.append(line)
                continue
            if '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in updates:
                    new_lines.append('{}={}\n'.format(key, updates[key]))
                    found.add(key)
                    continue
            new_lines.append(line)

        # Append keys not previously in file
        for key, val in updates.items():
            if key not in found:
                new_lines.append('{}={}\n'.format(key, val))

        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

        load_dotenv(env_path, override=True)
        self._log('Settings saved to ' + env_path)
        messagebox.showinfo('Saved', 'Settings saved to .env successfully.')

    def _on_settings_reload(self):
        env_path = os.path.join(_APP_DIR, '.env')
        load_dotenv(env_path, override=True)
        for key, var in self._settings_vars.items():
            var.set(os.getenv(key, ''))
        self._log('Settings reloaded from .env')

    def _on_settings_clear(self):
        if not messagebox.askyesno(
            'Clear All Forever',
            'This will clear ALL settings from the UI and permanently\n'
            'remove their values from the .env file.\n\n'
            'Continue?',
            icon='warning',
        ):
            return
        for var in self._settings_vars.values():
            var.set('')
        self._on_settings_save()
        self._log('All settings cleared from .env permanently.')

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
        _clear_lbl = tk.Label(
            hdr, text='Clear', font=(FONT, 8), bg=NAVY_MID, fg=WHITE40,
            cursor='hand2',
        )
        _clear_lbl.pack(side='right')
        _clear_lbl.bind('<Button-1>', lambda _: self._log_clear())

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

    def _lbl(self, parent, text, accent=None):
        """Section header with a coloured left accent bar."""
        row = tk.Frame(parent, bg=NAVY)
        row.pack(fill='x', pady=(12, 4))
        tk.Frame(row, bg=accent or CYAN_DIM, width=3).pack(
            side='left', fill='y', padx=(0, 8))
        tk.Label(row, text=text, font=(FONT, 8, 'bold'),
                 bg=NAVY, fg=WHITE40, anchor='w').pack(side='left', fill='x')

    def _card(self, parent, padx=0, pady=0):
        """A bordered card frame using NAVY_MID background."""
        f = tk.Frame(parent, bg=NAVY_MID,
                     highlightbackground=BORDER, highlightthickness=1)
        f.pack(fill='x', padx=padx, pady=pady)
        return f

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
