#!/usr/bin/env python3
"""
Phoenix Marketing Intelligence Engine — Control Panel GUI v1.0
Run:  python phoenix_gui.py
"""

from __future__ import annotations

import os
import sys
import json
import sqlite3
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
from datetime import datetime

# ── Exe-aware root ────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    _ROOT = os.path.dirname(sys.executable)
else:
    _ROOT = os.path.dirname(os.path.abspath(__file__))

if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"), override=True)

# ── Python executable (venv-aware) ────────────────────────────────────────────
_VENV_PY = os.path.join(_ROOT, ".venv", "Scripts", "python.exe")
PYTHON = _VENV_PY if os.path.exists(_VENV_PY) else sys.executable

API_URL = "http://127.0.0.1:8000"

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "#0b0b0c"
SURFACE  = "#111111"
SURFACE2 = "#161618"
BORDER   = "#1e293b"
ACCENT   = "#ff6a3d"
ACCENT2  = "#ff4d2d"
TEXT     = "#ffffff"
MUTED    = "#64748b"
SUCCESS  = "#4ade80"
WARNING  = "#facc15"
ERROR    = "#f87171"
BLUE     = "#60a5fa"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _api(path: str, method: str = "GET", body: dict | None = None) -> tuple[dict | None, str | None]:
    """Call the API. Returns (data, error_msg). error_msg is None on success."""
    try:
        import urllib.request, urllib.error
        url = API_URL + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode())
            msg = detail.get("detail") or detail.get("error") or str(detail)
        except Exception:
            msg = f"HTTP {e.code}: {e.reason}"
        return None, msg
    except urllib.error.URLError as e:
        return None, f"Connection failed: {e.reason}"
    except Exception as e:
        return None, str(e)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ─────────────────────────────────────────────────────────────────────────────
# Reusable widgets
# ─────────────────────────────────────────────────────────────────────────────

def _label(parent, text, size=11, color=TEXT, bold=False, **kw):
    font = ("Segoe UI", size, "bold" if bold else "normal")
    return tk.Label(parent, text=text, font=font, fg=color, bg=kw.pop("bg", SURFACE), **kw)


def _btn(parent, text, cmd, accent=True, small=False, **kw):
    bg = ACCENT if accent else SURFACE2
    fg = TEXT
    size = 9 if small else 10
    b = tk.Button(
        parent, text=text, command=cmd,
        font=("Segoe UI", size, "bold"),
        fg=fg, bg=bg, activeforeground=fg, activebackground=ACCENT2,
        relief="flat", cursor="hand2",
        padx=14 if not small else 8,
        pady=6 if not small else 4,
        **kw,
    )
    b.bind("<Enter>", lambda e: b.config(bg=ACCENT2 if accent else BORDER))
    b.bind("<Leave>", lambda e: b.config(bg=ACCENT if accent else SURFACE2))
    return b


def _card(parent, **kw):
    return tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER,
                    highlightthickness=1, **kw)


def _log_widget(parent, height=10):
    st = scrolledtext.ScrolledText(
        parent, height=height,
        bg="#0a0a0b", fg="#94a3b8",
        insertbackground=ACCENT,
        font=("Consolas", 9),
        relief="flat", bd=0,
        wrap="word",
        state="disabled",
    )
    st.tag_config("accent",  foreground=ACCENT)
    st.tag_config("success", foreground=SUCCESS)
    st.tag_config("warning", foreground=WARNING)
    st.tag_config("error",   foreground=ERROR)
    st.tag_config("blue",    foreground=BLUE)
    st.tag_config("muted",   foreground=MUTED)
    return st


def _log(widget, msg: str, tag: str = "") -> None:
    widget.config(state="normal")
    widget.insert("end", msg + "\n", tag)
    widget.see("end")
    widget.config(state="disabled")


def _spinbox(parent, from_, to, width=6, **kw):
    return ttk.Spinbox(parent, from_=from_, to=to, width=width,
                       font=("Segoe UI", 9), **kw)


# ─────────────────────────────────────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────────────────────────────────────

class PhoenixGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Phoenix Marketing Intelligence Engine v1.0")
        self.root.geometry("1200x760")
        self.root.minsize(1000, 640)
        self.root.configure(bg=BG)
        self._set_icon()

        self._server_proc: subprocess.Popen | None = None
        self._server_running = False
        self._logs: dict[str, scrolledtext.ScrolledText] = {}
        self._global_logs: list[tuple[str, str, str, str]] = []  # (ts, source, msg, tag)
        self._log_tail_pos: int = 0

        self._build_ui()
        self._refresh_status()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_icon(self):
        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Sidebar
        self._sidebar = tk.Frame(self.root, bg=SURFACE, width=210,
                                 highlightbackground=BORDER, highlightthickness=1)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        self._build_sidebar()

        # Right side: main + status bar
        right = tk.Frame(self.root, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        # Status bar (bottom)
        self._statusbar = tk.Frame(right, bg=SURFACE2, height=28,
                                   highlightbackground=BORDER, highlightthickness=1)
        self._statusbar.pack(side="bottom", fill="x")
        self._statusbar.pack_propagate(False)
        self._build_statusbar()

        # Main content
        self._content = tk.Frame(right, bg=BG)
        self._content.pack(side="top", fill="both", expand=True)

        # Pages
        page_names = ("Dashboard", "Signals", "Insights", "Content",
                      "Distribution", "Analytics", "Pipeline",
                      "Sources", "Database", "Growth", "Logs", "Settings")
        self._pages: dict[str, tk.Frame] = {}
        for name in page_names:
            page = tk.Frame(self._content, bg=BG)
            self._pages[name] = page

        self._build_dashboard()
        self._build_signals()
        self._build_insights()
        self._build_content()
        self._build_distribution()
        self._build_analytics()
        self._build_pipeline()
        self._build_sources()
        self._build_database()
        self._build_growth()
        self._build_logs()
        self._build_settings()

        self._show_page("Dashboard")

    def _build_statusbar(self):
        self._sb_server = tk.Label(self._statusbar, text="● Offline",
                                   font=("Segoe UI", 8, "bold"),
                                   fg=ERROR, bg=SURFACE2)
        self._sb_server.pack(side="left", padx=(10, 4))

        tk.Label(self._statusbar, text="|", fg=MUTED, bg=SURFACE2,
                 font=("Segoe UI", 8)).pack(side="left")

        # Worker status labels
        self._sb_workers: dict[str, tk.Label] = {}
        for name, short in (("signal", "Signal"), ("insight", "Insight"),
                             ("content", "Content"), ("distribution", "Dist"),
                             ("analytics", "Analytics")):
            lbl = tk.Label(self._statusbar, text=f"{short} ●",
                           font=("Segoe UI", 8), fg=MUTED, bg=SURFACE2)
            lbl.pack(side="left", padx=4)
            self._sb_workers[name] = lbl

        tk.Label(self._statusbar, text="|", fg=MUTED, bg=SURFACE2,
                 font=("Segoe UI", 8)).pack(side="left", padx=4)

        self._sb_pipeline = tk.Label(self._statusbar, text="Pipeline: never run",
                                     font=("Segoe UI", 8), fg=MUTED, bg=SURFACE2)
        self._sb_pipeline.pack(side="left", padx=4)

        tk.Label(self._statusbar,
                 text="API: http://127.0.0.1:8000  |  Web GUI: http://127.0.0.1:8000",
                 font=("Segoe UI", 8), fg=MUTED, bg=SURFACE2).pack(side="right", padx=10)

    def _update_statusbar(self, workers_data: dict | None, server_ok: bool):
        self._sb_server.config(
            text="● Online" if server_ok else "● Offline",
            fg=SUCCESS if server_ok else ERROR,
        )
        if workers_data:
            for name, lbl in self._sb_workers.items():
                info = workers_data.get(name, {})
                running = info.get("running", False)
                interval = info.get("interval_hours") or info.get("interval_minutes")
                unit = "h" if "interval_hours" in info else "m"
                lbl.config(
                    text=f"{name.capitalize()[:4]} {'●' if running else '○'} {interval}{unit}",
                    fg=SUCCESS if running else MUTED,
                )

    def _build_sidebar(self):
        # Logo
        logo_frame = tk.Frame(self._sidebar, bg=SURFACE, pady=16)
        logo_frame.pack(fill="x", padx=16)
        tk.Label(logo_frame, text="⚡", font=("Segoe UI", 20),
                 fg=ACCENT, bg=SURFACE).pack(side="left")
        tf = tk.Frame(logo_frame, bg=SURFACE)
        tf.pack(side="left", padx=8)
        tk.Label(tf, text="Phoenix", font=("Segoe UI", 12, "bold"),
                 fg=TEXT, bg=SURFACE).pack(anchor="w")
        tk.Label(tf, text="Intelligence Engine v1.0", font=("Segoe UI", 8),
                 fg=MUTED, bg=SURFACE).pack(anchor="w")

        tk.Frame(self._sidebar, bg=BORDER, height=1).pack(fill="x")

        # Server status badge
        self._srv_badge = tk.Label(
            self._sidebar, text="● Server Offline",
            font=("Segoe UI", 9, "bold"),
            fg=ERROR, bg=SURFACE, pady=8,
        )
        self._srv_badge.pack(fill="x", padx=16)
        tk.Frame(self._sidebar, bg=BORDER, height=1).pack(fill="x")

        # Nav buttons
        tk.Label(self._sidebar, text="NAVIGATION",
                 font=("Segoe UI", 8, "bold"),
                 fg=MUTED, bg=SURFACE, pady=8).pack(fill="x", padx=16)

        self._nav_btns: dict[str, tk.Button] = {}
        pages = [
            ("Dashboard",    "◈  Dashboard"),
            ("Signals",      "📡  Signals"),
            ("Insights",     "💡  Insights"),
            ("Content",      "✍  Content"),
            ("Distribution", "📬  Distribution"),
            ("Analytics",    "📊  Analytics"),
            ("Pipeline",     "⚙  Pipeline"),
            ("Sources",      "📋  Signal Sources"),
            ("Database",     "🗄  Database"),
            ("Growth",       "📈  LinkedIn Growth"),
            ("Logs",         "📋  Logs"),
            ("Settings",     "⚙  Settings"),
        ]
        for key, label in pages:
            b = tk.Button(
                self._sidebar, text=label,
                font=("Segoe UI", 9),
                fg=MUTED, bg=SURFACE,
                activeforeground=TEXT, activebackground=SURFACE2,
                relief="flat", anchor="w",
                padx=20, pady=6, cursor="hand2",
                command=lambda k=key: self._show_page(k),
            )
            b.pack(fill="x")
            self._nav_btns[key] = b

        # Server controls
        tk.Frame(self._sidebar, bg=BORDER, height=1).pack(fill="x", side="bottom")
        ctrl = tk.Frame(self._sidebar, bg=SURFACE, pady=10)
        ctrl.pack(side="bottom", fill="x")
        _btn(ctrl, "▶ Start Server", self._start_server).pack(fill="x", padx=12, pady=2)
        _btn(ctrl, "■ Stop Server",  self._stop_server, accent=False).pack(fill="x", padx=12, pady=2)

    def _show_page(self, name: str):
        for pg in self._pages.values():
            pg.pack_forget()
        self._pages[name].pack(fill="both", expand=True)
        for k, b in self._nav_btns.items():
            b.config(fg=ACCENT if k == name else MUTED,
                     bg=SURFACE2 if k == name else SURFACE)

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _build_dashboard(self):
        pg = self._pages["Dashboard"]
        _label(pg, "Dashboard", 18, bold=True, bg=BG).pack(anchor="w", padx=24, pady=(20, 4))
        _label(pg, "System overview — Signals → Insights → Content → Distribution → Analytics",
               10, MUTED, bg=BG).pack(anchor="w", padx=24, pady=(0, 16))

        cards_frame = tk.Frame(pg, bg=BG)
        cards_frame.pack(fill="x", padx=24, pady=(0, 16))

        self._stat_vars: dict[str, tk.StringVar] = {}
        stats = [
            ("signals",  "Signals",   "—"),
            ("insights", "Insights",  "—"),
            ("content",  "Content",   "—"),
            ("queue",    "Queued",    "—"),
        ]
        for key, label, default in stats:
            v = tk.StringVar(value=default)
            self._stat_vars[key] = v
            c = _card(cards_frame, padx=16, pady=12)
            c.pack(side="left", expand=True, fill="both", padx=(0, 8))
            _label(c, label, 8, MUTED).pack(anchor="w")
            tk.Label(c, textvariable=v, font=("Segoe UI", 28, "bold"),
                     fg=ACCENT, bg=SURFACE).pack(anchor="w", pady=(4, 0))

        log_card = _card(pg)
        log_card.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        hdr = tk.Frame(log_card, bg=SURFACE, pady=10)
        hdr.pack(fill="x", padx=16)
        _label(hdr, "Live Log", 10, bold=True).pack(side="left")
        _btn(hdr, "Refresh Stats", self._refresh_status, small=True).pack(side="right")

        self._dash_log = _log_widget(log_card, height=14)
        self._dash_log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._logs["dashboard"] = self._dash_log

        _log(self._dash_log, f"[{_ts()}] Phoenix Intelligence Engine GUI v1.0 started.", "accent")
        _log(self._dash_log, f"[{_ts()}] Click 'Start Server' in the sidebar to begin.", "muted")
        _log(self._dash_log, f"[{_ts()}] Web GUI: http://127.0.0.1:8000 once server is running.", "muted")

    # ── Engine page template ───────────────────────────────────────────────────

    def _build_engine_page(self, pg, title, icon, subtitle, actions, log_key, extra=None):
        _label(pg, f"{icon}  {title}", 18, bold=True, bg=BG).pack(anchor="w", padx=24, pady=(20, 4))
        _label(pg, subtitle, 10, MUTED, bg=BG).pack(anchor="w", padx=24, pady=(0, 12))

        if extra:
            extra(pg)

        btn_frame = _card(pg, pady=12)
        btn_frame.pack(fill="x", padx=24, pady=(0, 8))
        bf = tk.Frame(btn_frame, bg=SURFACE)
        bf.pack(fill="x", padx=16)
        for label, cmd in actions:
            _btn(bf, label, cmd, small=True).pack(side="left", padx=(0, 8))

        log_card = _card(pg)
        log_card.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        hdr = tk.Frame(log_card, bg=SURFACE, pady=8)
        hdr.pack(fill="x", padx=16)
        _label(hdr, "Output", 10, bold=True).pack(side="left")
        _btn(hdr, "Clear", lambda k=log_key: self._clear_log(k), small=True, accent=False).pack(side="right")

        log_w = _log_widget(log_card, height=16)
        log_w.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._logs[log_key] = log_w

    # ── Signals ───────────────────────────────────────────────────────────────

    def _build_signals(self):
        pg = self._pages["Signals"]
        self._build_engine_page(
            pg, "Signals", "📡",
            "Collect market intelligence from RSS feeds and Reddit",
            actions=[
                ("Collect Now",   lambda: self._api_post("/api/signals/collect", "signals")),
                ("Worker Status", lambda: self._api_get("/api/signals/worker",    "signals")),
                ("List Signals",  lambda: self._api_get("/api/signals?limit=20",  "signals")),
            ],
            log_key="signals",
        )

    # ── Insights ──────────────────────────────────────────────────────────────

    def _build_insights(self):
        pg = self._pages["Insights"]
        self._build_engine_page(
            pg, "Insights", "💡",
            "Generate decision intelligence from collected signals",
            actions=[
                ("Generate Now",  lambda: self._api_post("/api/insights/generate", "insights")),
                ("Worker Status", lambda: self._api_get("/api/insights/worker",    "insights")),
                ("List Insights", lambda: self._api_get("/api/insights?limit=20",  "insights")),
            ],
            log_key="insights",
        )

    # ── Content ───────────────────────────────────────────────────────────────

    def _build_content(self):
        pg = self._pages["Content"]
        self._build_engine_page(
            pg, "Content", "✍",
            "Generate blog posts and LinkedIn content from insights",
            actions=[
                ("Auto-Generate", lambda: self._api_post("/api/content/generate", "content")),
                ("Worker Status", lambda: self._api_get("/api/content/worker",    "content")),
                ("List Content",  lambda: self._api_get("/api/content?limit=20",  "content")),
            ],
            log_key="content",
            extra=self._build_content_extra,
        )

    def _build_content_extra(self, parent):
        """Topic + multi-select type standalone generation."""
        frame = _card(parent)
        frame.pack(fill="x", padx=24, pady=(0, 8))

        hdr = tk.Frame(frame, bg=SURFACE, pady=8)
        hdr.pack(fill="x", padx=16)
        _label(hdr, "Generate for Topic", 10, bold=True).pack(side="left")

        row1 = tk.Frame(frame, bg=SURFACE, pady=6)
        row1.pack(fill="x", padx=16)
        _label(row1, "Topic:", 10).pack(side="left")
        self._topic_entry = tk.Entry(row1, font=("Segoe UI", 10),
                                     bg=SURFACE2, fg=TEXT, insertbackground=ACCENT,
                                     relief="flat", bd=4, width=35)
        self._topic_entry.pack(side="left", padx=8)

        row2 = tk.Frame(frame, bg=SURFACE, pady=4)
        row2.pack(fill="x", padx=16)
        _label(row2, "Content types:", 9, MUTED).pack(side="left", padx=(0, 8))

        self._ct_blog = tk.BooleanVar(value=True)
        self._ct_linkedin = tk.BooleanVar(value=True)
        self._ct_linkedin_linked = tk.BooleanVar(value=False)

        for var, lbl in (
            (self._ct_blog,           "Blog Post"),
            (self._ct_linkedin,       "LinkedIn (standalone)"),
            (self._ct_linkedin_linked,"LinkedIn (blog-linked)"),
        ):
            tk.Checkbutton(row2, text=lbl, variable=var,
                           font=("Segoe UI", 9), fg=TEXT, bg=SURFACE,
                           selectcolor=SURFACE2, activebackground=SURFACE,
                           activeforeground=ACCENT).pack(side="left", padx=6)

        row3 = tk.Frame(frame, bg=SURFACE, pady=6)
        row3.pack(fill="x", padx=16)
        _label(row3, "Publish to:", 9, MUTED).pack(side="left", padx=(0, 8))

        self._pub_website  = tk.BooleanVar(value=False)
        self._pub_linkedin = tk.BooleanVar(value=False)

        tk.Checkbutton(row3, text="Website", variable=self._pub_website,
                       font=("Segoe UI", 9), fg=TEXT, bg=SURFACE,
                       selectcolor=SURFACE2, activebackground=SURFACE).pack(side="left", padx=6)
        tk.Checkbutton(row3, text="LinkedIn", variable=self._pub_linkedin,
                       font=("Segoe UI", 9), fg=TEXT, bg=SURFACE,
                       selectcolor=SURFACE2, activebackground=SURFACE).pack(side="left", padx=6)

        _btn(row3, "Generate Selected", self._generate_topic, small=True).pack(side="left", padx=12)

    def _generate_topic(self):
        topic = self._topic_entry.get().strip()
        if not topic:
            messagebox.showwarning("Missing Topic", "Enter a topic first.")
            return

        types = []
        if self._ct_blog.get():
            types.append("blog_post")
        if self._ct_linkedin.get():
            types.append("linkedin_post")
        if self._ct_linkedin_linked.get():
            types.append("linkedin_post_linked")

        if not types:
            messagebox.showwarning("Nothing selected", "Select at least one content type.")
            return

        channels = []
        if self._pub_website.get():
            channels.append("website")
        if self._pub_linkedin.get():
            channels.append("linkedin")

        for ct in types:
            body: dict = {"topic": topic, "content_type": ct}
            if channels:
                body["channels"] = channels
            self._api_post("/api/content/generate", "content", body=body)

    # ── Distribution ──────────────────────────────────────────────────────────

    def _build_distribution(self):
        pg = self._pages["Distribution"]
        self._build_engine_page(
            pg, "Distribution", "📬",
            "Publish content to LinkedIn and the website",
            actions=[
                ("Run Worker",    lambda: self._api_post("/api/distribution/run",           "distribution")),
                ("Worker Status", lambda: self._api_get("/api/distribution/worker",         "distribution")),
                ("View Queue",    lambda: self._api_get("/api/distribution/queue?limit=20", "distribution")),
            ],
            log_key="distribution",
        )

    # ── Analytics ─────────────────────────────────────────────────────────────

    def _build_analytics(self):
        pg = self._pages["Analytics"]
        self._build_engine_page(
            pg, "Analytics", "📊",
            "Collect metrics, score performance, update feedback signals",
            actions=[
                ("Collect Now",    lambda: self._api_post("/api/analytics/collect",    "analytics")),
                ("Dashboard Data", lambda: self._api_get("/api/analytics/dashboard",   "analytics")),
                ("Top Content",    lambda: self._api_get("/api/analytics/top-content", "analytics")),
                ("Worker Status",  lambda: self._api_get("/api/analytics/worker",      "analytics")),
            ],
            log_key="analytics",
        )

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def _build_pipeline(self):
        pg = self._pages["Pipeline"]
        _label(pg, "⚙  Automation Pipeline", 18, bold=True, bg=BG).pack(anchor="w", padx=24, pady=(20, 4))
        _label(pg, "Worker schedules, step selection, and full pipeline execution", 10, MUTED, bg=BG).pack(
            anchor="w", padx=24, pady=(0, 12))

        # ── Daily Content Pipeline ───────────────────────────────────────────
        daily_card = _card(pg, pady=10)
        daily_card.pack(fill="x", padx=24, pady=(0, 8))
        _label(daily_card, "Daily Content Pipeline", 11, bold=True).pack(anchor="w", padx=16, pady=(8, 4))
        _label(daily_card, "Research → Pick Topic → Generate Blog + LinkedIn → Publish", 9, MUTED).pack(
            anchor="w", padx=16, pady=(0, 6))

        # Topic row
        topic_row = tk.Frame(daily_card, bg=SURFACE)
        topic_row.pack(fill="x", padx=16, pady=2)
        _label(topic_row, "Topic:", 9).pack(side="left")
        self._daily_topic = tk.StringVar()
        tk.Entry(topic_row, textvariable=self._daily_topic, width=42,
                 font=("Segoe UI", 9), bg=SURFACE2, fg=TEXT,
                 insertbackground=TEXT, relief="flat", bd=4).pack(side="left", padx=(6, 0))
        _label(topic_row, "  (leave blank to auto-pick from research)", 8, MUTED).pack(side="left")

        # Mode + options row
        opt_row = tk.Frame(daily_card, bg=SURFACE)
        opt_row.pack(fill="x", padx=16, pady=4)
        _label(opt_row, "Mode:", 9).pack(side="left")
        self._daily_mode = tk.StringVar(value="blog_and_linkedin")
        modes = [
            ("Blog + LinkedIn", "blog_and_linkedin"),
            ("LinkedIn Only",   "li_only"),
            ("Blog Only",       "blog_only"),
        ]
        for txt, val in modes:
            tk.Radiobutton(opt_row, text=txt, variable=self._daily_mode, value=val,
                           font=("Segoe UI", 9), fg=TEXT, bg=SURFACE,
                           selectcolor=SURFACE2, activebackground=SURFACE,
                           activeforeground=ACCENT).pack(side="left", padx=6)

        pub_row = tk.Frame(daily_card, bg=SURFACE)
        pub_row.pack(fill="x", padx=16, pady=2)
        self._daily_publish_web = tk.BooleanVar(value=True)
        self._daily_publish_li = tk.BooleanVar(value=True)
        self._daily_dry_run = tk.BooleanVar(value=False)
        tk.Checkbutton(pub_row, text="Publish to Website", variable=self._daily_publish_web,
                       font=("Segoe UI", 9), fg=TEXT, bg=SURFACE,
                       selectcolor=SURFACE2, activebackground=SURFACE).pack(side="left", padx=(0, 8))
        tk.Checkbutton(pub_row, text="Publish to LinkedIn", variable=self._daily_publish_li,
                       font=("Segoe UI", 9), fg=TEXT, bg=SURFACE,
                       selectcolor=SURFACE2, activebackground=SURFACE).pack(side="left", padx=(0, 8))
        tk.Checkbutton(pub_row, text="Dry Run (generate only, no publish)",
                       variable=self._daily_dry_run,
                       font=("Segoe UI", 9), fg=WARNING, bg=SURFACE,
                       selectcolor=SURFACE2, activebackground=SURFACE).pack(side="left")

        btn_row = tk.Frame(daily_card, bg=SURFACE, pady=6)
        btn_row.pack(fill="x", padx=16)
        _btn(btn_row, "▶  Run Pipeline Now", self._run_daily_pipeline).pack(side="left", padx=(0, 8))
        _btn(btn_row, "🔍  Research Topics Now", self._run_research, small=True, accent=False).pack(side="left")

        # ── Daily Schedule ────────────────────────────────────────────────────
        sched_daily_card = _card(pg, pady=10)
        sched_daily_card.pack(fill="x", padx=24, pady=(0, 8))
        _label(sched_daily_card, "Daily Schedule", 11, bold=True).pack(anchor="w", padx=16, pady=(8, 4))

        time_row = tk.Frame(sched_daily_card, bg=SURFACE)
        time_row.pack(fill="x", padx=16, pady=4)
        _label(time_row, "Run at:", 9).pack(side="left")
        self._sched_hour = tk.IntVar(value=9)
        self._sched_minute = tk.IntVar(value=0)
        _spinbox(time_row, from_=0, to=23, width=3, textvariable=self._sched_hour).pack(side="left", padx=(6, 0))
        _label(time_row, " : ", 9).pack(side="left")
        _spinbox(time_row, from_=0, to=59, width=3, textvariable=self._sched_minute).pack(side="left")
        _label(time_row, "   (local time, 24h format)", 8, MUTED).pack(side="left")

        self._sched_enabled_var = tk.BooleanVar(value=False)
        tk.Checkbutton(time_row, text="Enable Scheduler",
                       variable=self._sched_enabled_var,
                       font=("Segoe UI", 9, "bold"), fg=ACCENT, bg=SURFACE,
                       selectcolor=SURFACE2, activebackground=SURFACE).pack(side="left", padx=12)

        # Day grid
        _label(sched_daily_card, "Content per day:", 9, MUTED).pack(anchor="w", padx=16, pady=(4, 0))
        days_frame = tk.Frame(sched_daily_card, bg=SURFACE)
        days_frame.pack(fill="x", padx=16, pady=4)

        day_options = ["blog_and_li", "li_only", "off"]
        day_labels  = {"blog_and_li": "Blog + LinkedIn", "li_only": "LinkedIn Only", "off": "Off"}
        self._day_mode_vars: dict[str, tk.StringVar] = {}
        self._day_active_vars: dict[str, tk.BooleanVar] = {}

        header_row = tk.Frame(days_frame, bg=SURFACE)
        header_row.pack(fill="x")
        for col, text in enumerate(["Day", "Active", "Content Type"]):
            _label(header_row, text, 8, MUTED).grid(row=0, column=col, padx=(0, 16), sticky="w") if False else None
            tk.Label(header_row, text=text, font=("Segoe UI", 8), fg=MUTED, bg=SURFACE).pack(side="left", padx=(0 if col == 0 else 4, 12))

        default_types = {
            "Mon": "blog_and_li", "Tue": "off", "Wed": "blog_and_li",
            "Thu": "li_only", "Fri": "blog_and_li", "Sat": "off", "Sun": "off",
        }
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            row = tk.Frame(days_frame, bg=SURFACE)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=day, width=5, font=("Segoe UI", 9), fg=TEXT, bg=SURFACE, anchor="w").pack(side="left")
            active_var = tk.BooleanVar(value=default_types[day] != "off")
            self._day_active_vars[day] = active_var
            tk.Checkbutton(row, variable=active_var, bg=SURFACE,
                           selectcolor=SURFACE2, activebackground=SURFACE).pack(side="left", padx=(4, 8))
            mode_var = tk.StringVar(value=default_types[day])
            self._day_mode_vars[day] = mode_var
            day_dd = tk.OptionMenu(row, mode_var, *day_options)
            day_dd.config(font=("Segoe UI", 9), bg=SURFACE2, fg=TEXT,
                          activebackground=SURFACE2, relief="flat", bd=0, width=14)
            day_dd.pack(side="left")

        sched_btn_row = tk.Frame(sched_daily_card, bg=SURFACE, pady=6)
        sched_btn_row.pack(fill="x", padx=16)
        _btn(sched_btn_row, "Save Schedule", self._save_schedule).pack(side="left", padx=(0, 8))
        _btn(sched_btn_row, "Load Current", self._load_schedule, small=True, accent=False).pack(side="left")

        # Scheduler control — Start / Stop / Pause / Resume
        ctrl_row = tk.Frame(sched_daily_card, bg=SURFACE, pady=4)
        ctrl_row.pack(fill="x", padx=16)
        _btn(ctrl_row, "▶ Start",   self._sched_start,  small=True).pack(side="left", padx=(0, 4))
        _btn(ctrl_row, "■ Stop",    self._sched_stop,   small=True, accent=False).pack(side="left", padx=(0, 4))
        _btn(ctrl_row, "⏸ Pause",  self._sched_pause,  small=True, accent=False).pack(side="left", padx=(0, 4))
        _btn(ctrl_row, "▶ Resume", self._sched_resume, small=True, accent=False).pack(side="left", padx=(0, 12))

        # Status indicator
        status_row = tk.Frame(sched_daily_card, bg=SURFACE, pady=2)
        status_row.pack(fill="x", padx=16, pady=(0, 6))
        self._sched_status_var = tk.StringVar(value="Status: unknown")
        self._sched_status_lbl = tk.Label(
            status_row, textvariable=self._sched_status_var,
            font=("Segoe UI", 8), fg=MUTED, bg=SURFACE, anchor="w",
        )
        self._sched_status_lbl.pack(side="left")
        _btn(status_row, "⟳", self._sched_status_refresh, small=True, accent=False).pack(side="left", padx=(6, 0))

        # ── Worker Schedule Control ──────────────────────────────────────────
        sched_card = _card(pg, pady=10)
        sched_card.pack(fill="x", padx=24, pady=(0, 8))
        _label(sched_card, "Worker Schedules", 10, bold=True).pack(anchor="w", padx=16, pady=(8, 4))

        self._worker_rows: dict[str, dict] = {}
        workers = [
            ("signal",       "Signal Engine",   6,  "hours"),
            ("insight",      "Insight Engine",  12, "hours"),
            ("content",      "Content Engine",  24, "hours"),
            ("distribution", "Distribution",    30, "minutes"),
            ("analytics",    "Analytics",       24, "hours"),
        ]
        for engine, label, default_val, unit in workers:
            row = tk.Frame(sched_card, bg=SURFACE, pady=4)
            row.pack(fill="x", padx=16)

            dot = tk.Label(row, text="●", font=("Segoe UI", 10), fg=MUTED, bg=SURFACE)
            dot.pack(side="left")
            _label(row, f"  {label}", 9).pack(side="left")

            ivar = tk.IntVar(value=default_val)
            sb = _spinbox(row, from_=1, to=720, width=5, textvariable=ivar)
            sb.pack(side="right", padx=4)
            tk.Label(row, text=unit, font=("Segoe UI", 9), fg=MUTED, bg=SURFACE).pack(side="right")

            def make_apply(eng=engine, var=ivar, u=unit):
                def apply():
                    key = "interval_hours" if u == "hours" else "interval_minutes"
                    self._api_post(f"/api/system/workers/{eng}/restart", "pipeline",
                                   body={key: var.get()})
                return apply

            def make_stop(eng=engine):
                return lambda: self._api_post(f"/api/system/workers/{eng}/stop", "pipeline")

            def make_start(eng=engine):
                return lambda: self._api_post(f"/api/system/workers/{eng}/start", "pipeline")

            _btn(row, "Apply", make_apply(), small=True).pack(side="right", padx=2)
            _btn(row, "Stop",  make_stop(),  small=True, accent=False).pack(side="right", padx=2)
            _btn(row, "Start", make_start(), small=True, accent=False).pack(side="right", padx=2)

            run_map = {
                "signal":       "/api/signals/collect",
                "insight":      "/api/insights/generate",
                "content":      "/api/content/generate",
                "distribution": "/api/distribution/run",
                "analytics":    "/api/analytics/collect",
            }
            def make_run(eng=engine):
                path = run_map[eng]
                method = "POST"
                return lambda: self._api_post(path, "pipeline") if method == "POST" else self._api_get(path, "pipeline")

            _btn(row, "Run Now", make_run(), small=True).pack(side="right", padx=2)
            self._worker_rows[engine] = {"dot": dot, "ivar": ivar}

        _btn(sched_card, "Refresh Worker Status", self._refresh_workers, small=True).pack(
            anchor="w", padx=16, pady=(4, 8))

        # ── Step Selector ────────────────────────────────────────────────────
        step_card = _card(pg, pady=10)
        step_card.pack(fill="x", padx=24, pady=(0, 8))
        _label(step_card, "Pipeline Steps", 10, bold=True).pack(anchor="w", padx=16, pady=(8, 4))

        self._step_vars: list[tk.BooleanVar] = []
        steps = [
            "1  Collect Signals",
            "2  Generate Insights",
            "3  Generate Content",
            "4  Schedule Distribution",
            "5  Publish Content",
            "6  Collect Analytics",
            "7  Update Feedback Signals",
        ]
        sf = tk.Frame(step_card, bg=SURFACE)
        sf.pack(fill="x", padx=16)
        for i, s in enumerate(steps):
            v = tk.BooleanVar(value=True)
            self._step_vars.append(v)
            tk.Checkbutton(sf, text=s, variable=v,
                           font=("Segoe UI", 9), fg=TEXT, bg=SURFACE,
                           selectcolor=SURFACE2, activebackground=SURFACE,
                           activeforeground=ACCENT).pack(anchor="w", pady=1)

        # Dry-run checkbox
        self._dry_run_var = tk.BooleanVar(value=False)
        tk.Checkbutton(step_card, text="Dry Run (log steps only)",
                       variable=self._dry_run_var,
                       font=("Segoe UI", 9), fg=WARNING, bg=SURFACE,
                       selectcolor=SURFACE2, activebackground=SURFACE).pack(anchor="w", padx=16, pady=(4, 0))

        ctrl = tk.Frame(step_card, bg=SURFACE, pady=8)
        ctrl.pack(fill="x", padx=16)
        _btn(ctrl, "▶  Run Selected Steps", self._run_pipeline).pack(side="left", padx=(0, 8))
        _btn(ctrl, "Select All",   lambda: [v.set(True)  for v in self._step_vars], small=True, accent=False).pack(side="left", padx=4)
        _btn(ctrl, "Select None",  lambda: [v.set(False) for v in self._step_vars], small=True, accent=False).pack(side="left")

        # Pipeline status
        self._pipeline_status = tk.StringVar(value="Idle")
        status_row = tk.Frame(pg, bg=BG)
        status_row.pack(fill="x", padx=24, pady=(0, 4))
        _label(status_row, "Status:", 9, MUTED, bg=BG).pack(side="left")
        tk.Label(status_row, textvariable=self._pipeline_status,
                 font=("Segoe UI", 10, "bold"), fg=SUCCESS, bg=BG).pack(side="left", padx=8)

        # Pipeline log
        log_card = _card(pg)
        log_card.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        hdr = tk.Frame(log_card, bg=SURFACE, pady=8)
        hdr.pack(fill="x", padx=16)
        _label(hdr, "Pipeline Log", 10, bold=True).pack(side="left")
        _btn(hdr, "Clear", lambda: self._clear_log("pipeline"), small=True, accent=False).pack(side="right")

        lw = _log_widget(log_card, height=10)
        lw.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._logs["pipeline"] = lw

    # ── Signal Sources Editor ─────────────────────────────────────────────────

    def _build_sources(self):
        pg = self._pages["Sources"]
        _label(pg, "📋  Signal Sources", 18, bold=True, bg=BG).pack(anchor="w", padx=24, pady=(20, 4))
        _label(pg, "Manage RSS feeds and Reddit subreddits for signal collection",
               10, MUTED, bg=BG).pack(anchor="w", padx=24, pady=(0, 12))

        # Toolbar
        toolbar = tk.Frame(pg, bg=BG)
        toolbar.pack(fill="x", padx=24, pady=(0, 8))
        _btn(toolbar, "Load from File", self._sources_load, small=True).pack(side="left", padx=(0, 6))
        _btn(toolbar, "+ Add Source",   self._sources_add,  small=True).pack(side="left", padx=(0, 6))
        _btn(toolbar, "Edit Selected",  self._sources_edit, small=True, accent=False).pack(side="left", padx=(0, 6))
        _btn(toolbar, "Remove",         self._sources_remove, small=True, accent=False).pack(side="left", padx=(0, 6))
        _btn(toolbar, "Save to File",   self._sources_save, small=True).pack(side="left")

        # Treeview
        tree_card = _card(pg)
        tree_card.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        cols = ("type", "category", "url_or_sub", "limit")
        self._sources_tree = ttk.Treeview(tree_card, columns=cols, show="headings", height=20)
        for c, w, head in zip(cols, (80, 140, 380, 60),
                              ("Type", "Category", "URL / Subreddit", "Limit")):
            self._sources_tree.heading(c, text=head)
            self._sources_tree.column(c, width=w)
        vsb = ttk.Scrollbar(tree_card, orient="vertical", command=self._sources_tree.yview)
        self._sources_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._sources_tree.pack(fill="both", expand=True, padx=8, pady=8)

        self._sources_load()

    def _sources_load(self):
        path = os.path.join(_ROOT, "signal_sources.json")
        try:
            with open(path) as f:
                self._sources_data = json.load(f)
        except FileNotFoundError:
            self._sources_data = []
        self._sources_refresh_tree()

    def _sources_refresh_tree(self):
        for item in self._sources_tree.get_children():
            self._sources_tree.delete(item)
        for s in self._sources_data:
            t = s.get("type", "rss")
            cat = s.get("category", "")
            url = s.get("url") or s.get("subreddit", "")
            lim = s.get("limit", "")
            self._sources_tree.insert("", "end", values=(t, cat, url, lim))

    def _sources_add(self):
        dlg = _SourceDialog(self.root)
        if dlg.result:
            self._sources_data.append(dlg.result)
            self._sources_refresh_tree()

    def _sources_edit(self):
        sel = self._sources_tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Select a source to edit.")
            return
        idx = self._sources_tree.index(sel[0])
        dlg = _SourceDialog(self.root, existing=self._sources_data[idx])
        if dlg.result:
            self._sources_data[idx] = dlg.result
            self._sources_refresh_tree()

    def _sources_remove(self):
        sel = self._sources_tree.selection()
        if not sel:
            return
        idx = self._sources_tree.index(sel[0])
        del self._sources_data[idx]
        self._sources_refresh_tree()

    def _sources_save(self):
        path = os.path.join(_ROOT, "signal_sources.json")
        try:
            with open(path, "w") as f:
                json.dump(self._sources_data, f, indent=2)
            messagebox.showinfo("Saved", f"signal_sources.json saved ({len(self._sources_data)} sources)")
        except Exception as exc:
            messagebox.showerror("Save Error", str(exc))

    # ── Database Browser ──────────────────────────────────────────────────────

    def _build_database(self):
        pg = self._pages["Database"]
        _label(pg, "🗄  Database Browser", 18, bold=True, bg=BG).pack(anchor="w", padx=24, pady=(20, 4))
        _label(pg, "View records in any table directly", 10, MUTED, bg=BG).pack(
            anchor="w", padx=24, pady=(0, 12))

        ctrl = tk.Frame(pg, bg=BG)
        ctrl.pack(fill="x", padx=24, pady=(0, 8))

        tables = ["signals", "insights", "content", "distribution_queue",
                  "metrics", "posts", "schema_version", "schedule_preferences"]
        self._db_table_var = tk.StringVar(value="signals")
        ttk.Combobox(ctrl, textvariable=self._db_table_var, values=tables,
                     font=("Segoe UI", 10), width=22, state="readonly").pack(side="left", padx=(0, 8))

        self._db_limit_var = tk.IntVar(value=50)
        _spinbox(ctrl, 10, 500, width=5, textvariable=self._db_limit_var).pack(side="left", padx=(0, 4))
        tk.Label(ctrl, text="rows", font=("Segoe UI", 9), fg=MUTED, bg=BG).pack(side="left", padx=(0, 8))

        _btn(ctrl, "Load", self._db_load, small=True).pack(side="left")
        self._db_count = tk.StringVar(value="")
        tk.Label(ctrl, textvariable=self._db_count, font=("Segoe UI", 9),
                 fg=MUTED, bg=BG).pack(side="left", padx=12)

        tree_card = _card(pg)
        tree_card.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._db_tree = ttk.Treeview(tree_card, show="headings", height=22)
        vsb = ttk.Scrollbar(tree_card, orient="vertical", command=self._db_tree.yview)
        hsb = ttk.Scrollbar(tree_card, orient="horizontal", command=self._db_tree.xview)
        self._db_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self._db_tree.pack(fill="both", expand=True, padx=4, pady=4)

    def _db_load(self):
        table = self._db_table_var.get()
        limit = self._db_limit_var.get()
        # Use direct SQLite (server may be offline)
        try:
            db_path = os.path.join(_ROOT, "blog_marketing.db")
            con = sqlite3.connect(db_path)
            con.row_factory = sqlite3.Row
            cur = con.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            con.close()
        except Exception as exc:
            messagebox.showerror("DB Error", str(exc))
            return

        # Rebuild treeview
        self._db_tree["columns"] = cols
        for c in cols:
            self._db_tree.heading(c, text=c)
            self._db_tree.column(c, width=max(80, len(c) * 10), minwidth=60)
        for item in self._db_tree.get_children():
            self._db_tree.delete(item)
        for row in rows:
            self._db_tree.insert("", "end", values=[str(row[c])[:120] for c in cols])
        self._db_count.set(f"{len(rows)} row(s) — {table}")

    # ── LinkedIn Growth ───────────────────────────────────────────────────────

    def _build_growth(self):
        pg = self._pages["Growth"]
        _label(pg, "📈  LinkedIn Growth", 18, bold=True, bg=BG).pack(anchor="w", padx=24, pady=(20, 4))
        _label(pg, "AI-powered engagement automation — scan feed, classify, comment, track viral posts",
               10, MUTED, bg=BG).pack(anchor="w", padx=24, pady=(0, 12))

        # Status + controls
        ctrl_card = _card(pg, pady=10)
        ctrl_card.pack(fill="x", padx=24, pady=(0, 8))
        cf = tk.Frame(ctrl_card, bg=SURFACE)
        cf.pack(fill="x", padx=16)
        _btn(cf, "Scan Feed Now",    lambda: self._api_post("/api/engagement/feed",   "growth"), small=True).pack(side="left", padx=(0, 6))
        _btn(cf, "Run Engagement",   lambda: self._api_post("/api/engagement/run",    "growth"), small=True).pack(side="left", padx=(0, 6))
        _btn(cf, "Worker Status",    lambda: self._api_get("/api/engagement/worker",  "growth"), small=True, accent=False).pack(side="left", padx=(0, 6))
        _btn(cf, "Engagement Log",   lambda: self._api_get("/api/engagement/log",     "growth"), small=True, accent=False).pack(side="left", padx=(0, 6))
        _btn(cf, "Stats",            lambda: self._api_get("/api/engagement/stats",   "growth"), small=True, accent=False).pack(side="left", padx=(0, 6))
        _btn(cf, "Viral Posts",      lambda: self._api_get("/api/engagement/viral",   "growth"), small=True, accent=False).pack(side="left")

        # Influencer targets
        inf_card = _card(pg, pady=10)
        inf_card.pack(fill="x", padx=24, pady=(0, 8))
        ihdr = tk.Frame(inf_card, bg=SURFACE)
        ihdr.pack(fill="x", padx=16)
        _label(ihdr, "Influencer Targets", 10, bold=True).pack(side="left")
        _btn(ihdr, "+ Add", self._growth_add_influencer, small=True).pack(side="right")
        _btn(ihdr, "Remove", self._growth_remove_influencer, small=True, accent=False).pack(side="right", padx=4)
        _btn(ihdr, "Refresh", lambda: self._api_get("/api/engagement/influencers", "growth"), small=True, accent=False).pack(side="right", padx=4)

        cols = ("name", "url", "category", "priority")
        self._inf_tree = ttk.Treeview(inf_card, columns=cols, show="headings", height=5)
        for c, w, h in zip(cols, (150, 300, 120, 70),
                           ("Name", "LinkedIn URL", "Category", "Priority")):
            self._inf_tree.heading(c, text=h)
            self._inf_tree.column(c, width=w)
        self._inf_tree.pack(fill="x", padx=8, pady=8)

        # Worker schedule row
        wrow = tk.Frame(pg, bg=BG)
        wrow.pack(fill="x", padx=24, pady=(0, 6))
        _label(wrow, "Engagement Worker interval:", 9, MUTED, bg=BG).pack(side="left")
        self._growth_interval_var = tk.IntVar(value=2)
        _spinbox(wrow, 1, 24, width=5, textvariable=self._growth_interval_var).pack(side="left", padx=4)
        tk.Label(wrow, text="hours", font=("Segoe UI", 9), fg=MUTED, bg=BG).pack(side="left", padx=(0, 8))
        _btn(wrow, "Apply", self._growth_apply_interval, small=True).pack(side="left")

        # Output log
        log_card = _card(pg)
        log_card.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        hdr = tk.Frame(log_card, bg=SURFACE, pady=8)
        hdr.pack(fill="x", padx=16)
        _label(hdr, "Growth Output", 10, bold=True).pack(side="left")
        _btn(hdr, "Clear", lambda: self._clear_log("growth"), small=True, accent=False).pack(side="right")
        lw = _log_widget(log_card, height=12)
        lw.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._logs["growth"] = lw

        _log(lw, f"[{_ts()}] LinkedIn Growth Engine — implement Phase G to activate.", "muted")
        _log(lw, f"[{_ts()}] Requires: playwright install chromium", "muted")

    def _growth_add_influencer(self):
        name = simpledialog.askstring("Add Influencer", "Name:", parent=self.root)
        if not name:
            return
        url = simpledialog.askstring("Add Influencer", "LinkedIn URL:", parent=self.root)
        if not url:
            return
        cat = simpledialog.askstring("Add Influencer", "Category (optional):", parent=self.root) or ""
        self._api_post("/api/engagement/influencers", "growth",
                       body={"name": name, "linkedin_url": url, "category": cat})

    def _growth_remove_influencer(self):
        sel = self._inf_tree.selection()
        if not sel:
            return
        values = self._inf_tree.item(sel[0])["values"]
        if messagebox.askyesno("Remove", f"Remove influencer '{values[0]}'?"):
            self._api_post("/api/engagement/influencers/remove", "growth",
                           body={"linkedin_url": values[1]})

    def _growth_apply_interval(self):
        self._api_post("/api/system/workers/engagement/restart", "growth",
                       body={"interval_hours": self._growth_interval_var.get()})

    # ── Settings ──────────────────────────────────────────────────────────────

    def _build_settings(self):
        pg = self._pages["Settings"]
        _label(pg, "⚙  Settings", 18, bold=True, bg=BG).pack(anchor="w", padx=24, pady=(20, 4))
        _label(pg, "API keys, environment variables, and runtime thresholds",
               10, MUTED, bg=BG).pack(anchor="w", padx=24, pady=(0, 12))

        canvas = tk.Canvas(pg, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(pg, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=(24, 0))

        self._env_entries: dict[str, tk.Entry] = {}

        groups = [
            ("Groq AI", [
                ("GROQ_API_KEY", "API Key"),
                ("GROQ_MODEL",   "Model (default: llama-3.3-70b-versatile)"),
            ]),
            ("LinkedIn", [
                ("LINKEDIN_ACCESS_TOKEN",  "Access Token"),
                ("LINKEDIN_ORG_URN",       "Org URN"),
                ("LINKEDIN_PERSON_URN",    "Person URN"),
                ("LINKEDIN_CLIENT_ID",     "Client ID (for OAuth)"),
                ("LINKEDIN_CLIENT_SECRET", "Client Secret (for OAuth)"),
            ]),
            ("Website", [
                ("WEBSITE_REPO_PATH", "Repo Path"),
                ("WEBSITE_BASE_URL",  "Base URL"),
            ]),
            ("Images", [
                ("UNSPLASH_ACCESS_KEY",  "Unsplash Key"),
                ("STABLE_DIFFUSION_URL", "Stable Diffusion URL"),
            ]),
            ("Analytics", [
                ("GA_PROPERTY_ID", "Google Analytics Property ID (optional)"),
            ]),
        ]

        for group_title, fields in groups:
            card = _card(scroll_frame, pady=10)
            card.pack(fill="x", pady=(0, 8), padx=(0, 24))
            _label(card, group_title, 11, bold=True).pack(anchor="w", padx=16, pady=(8, 4))
            for env_key, label in fields:
                row = tk.Frame(card, bg=SURFACE, pady=4)
                row.pack(fill="x", padx=16)
                _label(row, label, 9, MUTED).pack(anchor="w")
                show = "*" if any(k in env_key for k in ("KEY", "TOKEN", "SECRET")) else ""
                entry = tk.Entry(row, font=("Consolas", 9),
                                 bg=SURFACE2, fg=TEXT, insertbackground=ACCENT,
                                 relief="flat", bd=4, width=60, show=show)
                entry.insert(0, os.getenv(env_key, ""))
                entry.pack(fill="x", pady=(2, 0))
                self._env_entries[env_key] = entry

        # LinkedIn OAuth button
        oauth_card = _card(scroll_frame, pady=10)
        oauth_card.pack(fill="x", pady=(0, 8), padx=(0, 24))
        _label(oauth_card, "LinkedIn OAuth", 11, bold=True).pack(anchor="w", padx=16, pady=(8, 4))
        _label(oauth_card, "Opens browser to complete OAuth 2.0 authorization flow. Saves token to .env.", 9, MUTED).pack(anchor="w", padx=16)
        _btn(oauth_card, "Connect LinkedIn", self._oauth_linkedin).pack(anchor="w", padx=16, pady=8)

        # Runtime thresholds
        thresh_card = _card(scroll_frame, pady=10)
        thresh_card.pack(fill="x", pady=(0, 8), padx=(0, 24))
        _label(thresh_card, "Runtime Thresholds", 11, bold=True).pack(anchor="w", padx=16, pady=(8, 4))

        tr = tk.Frame(thresh_card, bg=SURFACE)
        tr.pack(fill="x", padx=16, pady=4)
        _label(tr, "Content Confidence Min:", 9, MUTED).pack(side="left")
        self._conf_var = tk.DoubleVar(value=0.5)
        _spinbox(tr, 0.1, 1.0, width=6, textvariable=self._conf_var).pack(side="left", padx=8)
        _label(tr, "Max Content per Cycle:", 9, MUTED).pack(side="left", padx=(16, 4))
        self._max_content_var = tk.IntVar(value=20)
        _spinbox(tr, 1, 100, width=6, textvariable=self._max_content_var).pack(side="left", padx=8)
        _btn(tr, "Apply Thresholds", self._apply_thresholds, small=True).pack(side="left", padx=8)

        # API connection
        api_card = _card(scroll_frame, pady=10)
        api_card.pack(fill="x", pady=(0, 8), padx=(0, 24))
        _label(api_card, "API Connection", 11, bold=True).pack(anchor="w", padx=16, pady=(8, 4))
        ar = tk.Frame(api_card, bg=SURFACE)
        ar.pack(fill="x", padx=16, pady=4)
        _label(ar, "Host:", 9, MUTED).pack(side="left")
        self._api_host_entry = tk.Entry(ar, font=("Consolas", 9), bg=SURFACE2, fg=TEXT,
                                        insertbackground=ACCENT, relief="flat", bd=4, width=20)
        self._api_host_entry.insert(0, "127.0.0.1")
        self._api_host_entry.pack(side="left", padx=(4, 12))
        _label(ar, "Port:", 9, MUTED).pack(side="left")
        self._api_port_entry = tk.Entry(ar, font=("Consolas", 9), bg=SURFACE2, fg=TEXT,
                                        insertbackground=ACCENT, relief="flat", bd=4, width=8)
        self._api_port_entry.insert(0, "8000")
        self._api_port_entry.pack(side="left", padx=4)
        _btn(ar, "Apply", self._apply_api_url, small=True).pack(side="left", padx=8)

        # Save buttons
        btns_row = tk.Frame(scroll_frame, bg=BG)
        btns_row.pack(anchor="w", pady=8, padx=(0, 24))
        _btn(btns_row, "Save to .env", self._save_env).pack(side="left", padx=(0, 8))
        _btn(btns_row, "Save & Restart Server", self._save_and_restart, accent=False).pack(side="left")

    def _oauth_linkedin(self):
        def _run():
            try:
                import importlib
                spec = importlib.util.spec_from_file_location(
                    "linkedin_auth", os.path.join(_ROOT, "linkedin_auth.py"))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "run_auth_flow"):
                    token = mod.run_auth_flow()
                else:
                    token = mod.main() if hasattr(mod, "main") else None
                if token:
                    self.root.after(0, lambda t=token: (
                        self._env_entries.get("LINKEDIN_ACCESS_TOKEN") and
                        (self._env_entries["LINKEDIN_ACCESS_TOKEN"].delete(0, "end") or
                         self._env_entries["LINKEDIN_ACCESS_TOKEN"].insert(0, t))
                    ))
                    self.root.after(0, lambda: messagebox.showinfo(
                        "OAuth Success", "LinkedIn access token obtained! Click 'Save to .env'."))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("OAuth Error", str(exc)))
        threading.Thread(target=_run, daemon=True).start()

    def _apply_thresholds(self):
        body = {
            "content_confidence_threshold": self._conf_var.get(),
            "content_max_per_cycle": self._max_content_var.get(),
        }
        self._api_post("/api/system/config", "dashboard", body=body)
        messagebox.showinfo("Applied", "Thresholds updated. Restart workers to take effect.")

    def _apply_api_url(self):
        global API_URL
        host = self._api_host_entry.get().strip() or "127.0.0.1"
        port = self._api_port_entry.get().strip() or "8000"
        API_URL = f"http://{host}:{port}"
        messagebox.showinfo("Updated", f"API URL set to {API_URL}")

    def _save_and_restart(self):
        self._save_env()
        self._stop_server()
        self.root.after(1500, self._start_server)

    # ── Server management ─────────────────────────────────────────────────────

    def _start_server(self):
        if self._server_running:
            msg = f"[{_ts()}] Server is already running."
            _log(self._dash_log, msg, "warning")
            self._glog(msg, "warning", "server")
            return
        msg = f"[{_ts()}] Starting API server on {API_URL}..."
        _log(self._dash_log, msg, "accent")
        self._glog(msg, "accent", "server")

        def _run():
            try:
                host = API_URL.split("//")[1].split(":")[0]
                port = API_URL.split(":")[-1]
                self._server_proc = subprocess.Popen(
                    [PYTHON, "-m", "uvicorn", "api.main:app",
                     "--host", host, "--port", port,
                     "--log-level", "warning"],
                    cwd=_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                self._server_running = True
                self.root.after(0, self._refresh_status)
                for line in self._server_proc.stdout:
                    line = line.rstrip()
                    if line:
                        entry = f"[server] {line}"
                        self.root.after(0, lambda l=entry: (
                            _log(self._dash_log, l, "muted"),
                            self._glog(l, "muted", "server"),
                        ))
            except Exception as exc:
                msg2 = f"[{_ts()}] Start failed: {exc}"
                self.root.after(0, lambda: (
                    _log(self._dash_log, msg2, "error"),
                    self._glog(msg2, "error", "server"),
                ))
            finally:
                self._server_running = False
                self.root.after(0, self._refresh_status)

        threading.Thread(target=_run, daemon=True).start()

    def _stop_server(self):
        stopped = False
        if self._server_proc:
            self._server_proc.terminate()
            self._server_proc = None
            self._server_running = False
            stopped = True
        # Also kill any externally-started uvicorn on port 8000
        killed = self._kill_port(8000)
        if killed:
            stopped = True
        msg = f"[{_ts()}] Server stopped." if stopped else f"[{_ts()}] No server process found."
        tag = "warning" if stopped else "muted"
        _log(self._dash_log, msg, tag)
        self._glog(msg, tag, "server")
        self._refresh_status()

    def _kill_port(self, port: int) -> bool:
        """Kill all processes listening on *port*. Returns True if any were killed."""
        killed = False
        try:
            result = subprocess.run(
                ["netstat", "-ano"], capture_output=True, text=True
            )
            pids: set[str] = set()
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if parts:
                        pids.add(parts[-1])
            for pid in pids:
                r = subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
                if r.returncode == 0:
                    _log(self._dash_log, f"[{_ts()}] Killed PID {pid} (port {port}).", "warning")
                    killed = True
        except Exception as exc:
            _log(self._dash_log, f"[{_ts()}] _kill_port error: {exc}", "error")
        return killed

    def _refresh_status(self):
        data, _ = _api("/health")
        alive = data is not None
        self._server_running = alive

        self._srv_badge.config(
            text="● Server Online" if alive else "● Server Offline",
            fg=SUCCESS if alive else ERROR,
        )

        if alive:
            signals,  _ = _api("/api/signals?limit=1")
            insights, _ = _api("/api/insights?limit=1")
            content,  _ = _api("/api/content?limit=1")
            queue,    _ = _api("/api/distribution/queue?limit=1")
            self._stat_vars["signals"].set(signals["total"]   if signals  else "—")
            self._stat_vars["insights"].set(insights["total"] if insights else "—")
            self._stat_vars["content"].set(content["total"]   if content  else "—")
            self._stat_vars["queue"].set(queue["total"]        if queue    else "—")
            _log(self._dash_log, f"[{_ts()}] API v{data.get('version','?')} — stats refreshed.", "success")

            workers, _ = _api("/api/system/workers")
            self._update_statusbar(workers, True)
            if workers:
                self._update_worker_dots(workers)
        else:
            for k in self._stat_vars:
                self._stat_vars[k].set("—")
            self._update_statusbar(None, False)

        self.root.after(30000, self._refresh_status)

    def _refresh_workers(self):
        def _run():
            data, err = _api("/api/system/workers")
            if data:
                self.root.after(0, lambda: self._update_worker_dots(data))
                self.root.after(0, lambda: self._update_statusbar(data, True))
                self.root.after(0, lambda: _log(
                    self._logs["pipeline"],
                    f"[{_ts()}] Workers: {json.dumps(data, indent=2)}", "blue"))
            else:
                self.root.after(0, lambda: _log(
                    self._logs["pipeline"], f"[{_ts()}] Error: {err}", "error"))
        threading.Thread(target=_run, daemon=True).start()

    def _update_worker_dots(self, workers: dict):
        for engine, row in self._worker_rows.items():
            info = workers.get(engine, {})
            running = info.get("running", False)
            row["dot"].config(fg=SUCCESS if running else ERROR)

    # ── API call helpers ──────────────────────────────────────────────────────

    def _api_get(self, path: str, log_key: str):
        def _run():
            msg = f"[{_ts()}] GET {path}"
            self.root.after(0, lambda: _log(self._logs[log_key], msg, "blue"))
            self.root.after(0, lambda: self._glog(msg, "blue", "api"))
            result, err = _api(path)
            if result is None:
                emsg = f"  Error: {err}"
                self.root.after(0, lambda: _log(self._logs[log_key], emsg, "error"))
                self.root.after(0, lambda: self._glog(emsg, "error", "api"))
            else:
                pretty = json.dumps(result, indent=2)
                self.root.after(0, lambda: _log(self._logs[log_key], pretty, ""))
                self.root.after(0, lambda: self._glog(f"GET {path} → OK", "success", "api"))
        threading.Thread(target=_run, daemon=True).start()

    def _api_post(self, path: str, log_key: str, body: dict | None = None):
        def _run():
            msg = f"[{_ts()}] POST {path}"
            self.root.after(0, lambda: _log(self._logs[log_key], msg, "accent"))
            self.root.after(0, lambda: self._glog(msg, "accent", "api"))
            result, err = _api(path, method="POST", body=body if body is not None else {})
            if result is None:
                emsg = f"  Error: {err}"
                self.root.after(0, lambda: _log(self._logs[log_key], emsg, "error"))
                self.root.after(0, lambda: self._glog(emsg, "error", "api"))
            else:
                pretty = json.dumps(result, indent=2)
                self.root.after(0, lambda: _log(self._logs[log_key], pretty, "success"))
                self.root.after(0, lambda: self._glog(f"POST {path} → OK", "success", "api"))
        threading.Thread(target=_run, daemon=True).start()

    def _clear_log(self, log_key: str):
        w = self._logs.get(log_key)
        if w:
            w.config(state="normal")
            w.delete("1.0", "end")
            w.config(state="disabled")

    # ── Daily pipeline handlers ────────────────────────────────────────────────

    def _run_daily_pipeline(self):
        topic = self._daily_topic.get().strip() or None
        mode = self._daily_mode.get()
        dry_run = self._daily_dry_run.get()
        publish = not dry_run and (self._daily_publish_web.get() or self._daily_publish_li.get())

        log_w = self._logs["pipeline"]
        _log(log_w, f"\n[{_ts()}] === Daily Pipeline Starting ===", "accent")
        _log(log_w, f"  Topic: {topic or '(auto-pick)'}  Mode: {mode}  DryRun: {dry_run}", "muted")
        self._glog(f"[{_ts()}] Pipeline started — topic={topic or 'auto'} mode={mode} dry={dry_run}", "accent", "pipeline")
        self._pipeline_status.set("Running daily pipeline…")

        body = {
            "topic": topic,
            "content_types": [mode],
            "publish": publish,
            "dry_run": dry_run,
        }

        def _run():
            result, err = _api("/api/pipeline/daily", method="POST", body=body)
            if err:
                self.root.after(0, lambda: _log(log_w, f"[{_ts()}] Error: {err}", "error"))
                self.root.after(0, lambda: self._pipeline_status.set("Error"))
            else:
                self.root.after(0, lambda: self._pipeline_status.set("Complete"))
                self.root.after(0, lambda: _log(
                    log_w, f"[{_ts()}] Done — topic: {result.get('topic','?')}", "success"))
                if result.get("error"):
                    self.root.after(0, lambda: _log(log_w, f"  Pipeline error: {result['error']}", "error"))
                else:
                    blog_url = result.get("blog_url") or "—"
                    li_path  = result.get("linkedin_path") or "—"
                    self.root.after(0, lambda: _log(log_w, f"  Blog URL: {blog_url}", ""))
                    self.root.after(0, lambda: _log(log_w, f"  LinkedIn: {li_path}", ""))

        threading.Thread(target=_run, daemon=True).start()

    def _run_research(self):
        log_w = self._logs["pipeline"]
        _log(log_w, f"\n[{_ts()}] Running topic research...", "accent")
        self._pipeline_status.set("Researching topics…")

        def _run():
            result, err = _api("/api/research/run", method="POST", body={})
            if err:
                self.root.after(0, lambda: _log(log_w, f"[{_ts()}] Research error: {err}", "error"))
                self.root.after(0, lambda: self._pipeline_status.set("Research failed"))
            else:
                count = result.get("count", 0)
                self.root.after(0, lambda: self._pipeline_status.set(f"Research done — {count} topics"))
                self.root.after(0, lambda: _log(
                    log_w, f"[{_ts()}] Research complete — {count} topics saved", "success"))
                for t in (result.get("topics") or [])[:5]:
                    title = t.get("generated_title", "?")
                    score = t.get("reddit_score", 0)
                    self.root.after(0, lambda tt=title, sc=score: _log(
                        log_w, f"  [{sc:>4}] {tt}", "muted"))

        threading.Thread(target=_run, daemon=True).start()

    def _save_schedule(self):
        log_w = self._logs["pipeline"]
        h = self._sched_hour.get()
        m = self._sched_minute.get()
        slot = f"{h:02d}:{m:02d}"

        day_content: dict = {}
        active_days: list = []
        for day, mode_var in self._day_mode_vars.items():
            active = self._day_active_vars[day].get()
            ct = mode_var.get() if active else "off"
            day_content[day] = ct
            if active and ct != "off":
                active_days.append(day)

        body = {
            "enabled": self._sched_enabled_var.get(),
            "slots": [slot],
            "days": active_days,
            "day_content_type": day_content,
            "dry_run": self._daily_dry_run.get(),
        }

        def _run():
            result, err = _api("/api/schedule/config", method="POST", body=body)
            if err:
                self.root.after(0, lambda: _log(log_w, f"[{_ts()}] Save error: {err}", "error"))
            else:
                self.root.after(0, lambda: _log(log_w, f"[{_ts()}] Schedule saved — {slot}", "success"))

        threading.Thread(target=_run, daemon=True).start()

    def _load_schedule(self):
        log_w = self._logs["pipeline"]

        def _run():
            cfg, err = _api("/api/schedule/config")
            if err:
                self.root.after(0, lambda: _log(log_w, f"[{_ts()}] Load error: {err}", "error"))
                return

            def _apply():
                slots = cfg.get("slots", ["09:00"])
                if slots:
                    try:
                        h, m = map(int, slots[0].split(":"))
                        self._sched_hour.set(h)
                        self._sched_minute.set(m)
                    except Exception:
                        pass
                self._sched_enabled_var.set(bool(cfg.get("enabled", False)))
                day_ct = cfg.get("day_content_type", {})
                for day, mode_var in self._day_mode_vars.items():
                    ct = day_ct.get(day, "off")
                    mode_var.set(ct)
                    self._day_active_vars[day].set(ct != "off")
                _log(log_w, f"[{_ts()}] Schedule loaded", "success")

            self.root.after(0, _apply)

        threading.Thread(target=_run, daemon=True).start()

    def _sched_status_refresh(self):
        """Fetch and display current scheduler status."""
        def _run():
            data, err = _api("/api/schedule/status")
            if err:
                self.root.after(0, lambda: (
                    self._sched_status_var.set(f"Status: error — {err}"),
                    self._sched_status_lbl.config(fg=ERROR),
                ))
                return
            running = data.get("running", False)
            paused  = data.get("paused", False)
            nf      = data.get("next_fire")
            dry     = "  [DRY RUN]" if data.get("dry_run") else ""
            if paused:
                state, color = "Paused", WARNING
            elif running:
                nf_str = f"  — next: {nf[:16].replace('T', ' ')}" if nf else ""
                state, color = f"Running{nf_str}", SUCCESS
            else:
                state, color = "Stopped", MUTED
            self.root.after(0, lambda s=state, c=color, d=dry: (
                self._sched_status_var.set(f"Status: {s}{d}"),
                self._sched_status_lbl.config(fg=c),
            ))
        threading.Thread(target=_run, daemon=True).start()

    def _sched_start(self):
        log_w = self._logs["pipeline"]
        def _run():
            _, err = _api("/api/schedule/start", method="POST", body={})
            if err:
                self.root.after(0, lambda: _log(log_w, f"[{_ts()}] Start error: {err}", "error"))
            else:
                self.root.after(0, lambda: (
                    _log(log_w, f"[{_ts()}] Scheduler started", "success"),
                    self._sched_status_refresh(),
                ))
        threading.Thread(target=_run, daemon=True).start()

    def _sched_stop(self):
        log_w = self._logs["pipeline"]
        def _run():
            _, err = _api("/api/schedule/stop", method="POST", body={})
            if err:
                self.root.after(0, lambda: _log(log_w, f"[{_ts()}] Stop error: {err}", "error"))
            else:
                self.root.after(0, lambda: (
                    _log(log_w, f"[{_ts()}] Scheduler stopped", "success"),
                    self._sched_status_refresh(),
                ))
        threading.Thread(target=_run, daemon=True).start()

    def _sched_pause(self):
        log_w = self._logs["pipeline"]
        def _run():
            _, err = _api("/api/schedule/pause", method="POST", body={})
            if err:
                self.root.after(0, lambda: _log(log_w, f"[{_ts()}] Pause error: {err}", "error"))
            else:
                self.root.after(0, lambda: (
                    _log(log_w, f"[{_ts()}] Scheduler paused", "success"),
                    self._sched_status_refresh(),
                ))
        threading.Thread(target=_run, daemon=True).start()

    def _sched_resume(self):
        log_w = self._logs["pipeline"]
        def _run():
            _, err = _api("/api/schedule/resume", method="POST", body={})
            if err:
                self.root.after(0, lambda: _log(log_w, f"[{_ts()}] Resume error: {err}", "error"))
            else:
                self.root.after(0, lambda: (
                    _log(log_w, f"[{_ts()}] Scheduler resumed", "success"),
                    self._sched_status_refresh(),
                ))
        threading.Thread(target=_run, daemon=True).start()

    # ── Pipeline run ──────────────────────────────────────────────────────────

    def _run_pipeline(self):
        selected_steps = [i + 1 for i, v in enumerate(self._step_vars) if v.get()]
        if not selected_steps:
            messagebox.showwarning("No Steps", "Select at least one pipeline step.")
            return

        dry_run = self._dry_run_var.get()
        self._pipeline_status.set("Running…")
        _log(self._logs["pipeline"], f"\n[{_ts()}] === Pipeline Starting ===", "accent")
        _log(self._logs["pipeline"], f"  Steps: {selected_steps}  Dry run: {dry_run}", "muted")

        def _run():
            import importlib
            try:
                spec = importlib.util.spec_from_file_location(
                    "pipeline", os.path.join(_ROOT, "automation", "pipeline.py"))
                pipeline = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(pipeline)

                import logging as _logging

                class GUIHandler(_logging.Handler):
                    def __init__(self, widget, gui):
                        super().__init__()
                        self._w = widget
                        self._gui = gui

                    def emit(self, record):
                        msg = self.format(record)
                        tag = "success" if "complete" in msg.lower() else "error" if "fail" in msg.lower() or "error" in msg.lower() else ""
                        self._gui.root.after(0, lambda m=msg, t=tag: _log(self._w, m, t))

                handler = GUIHandler(self._logs["pipeline"], self)
                handler.setFormatter(_logging.Formatter("%(message)s"))
                pipeline.logger.addHandler(handler)

                result = pipeline.run(dry_run=dry_run, steps=selected_steps)
                self.root.after(0, lambda: self._pipeline_status.set(
                    f"Done in {result.get('elapsed_seconds', 0):.1f}s"))
                self.root.after(0, lambda: _log(
                    self._logs["pipeline"], f"[{_ts()}] === Pipeline Complete ===", "success"))
                self.root.after(0, self._refresh_status)

            except Exception as exc:
                self.root.after(0, lambda: self._pipeline_status.set(f"Error: {exc}"))
                self.root.after(0, lambda: _log(self._logs["pipeline"], f"Error: {exc}", "error"))

        threading.Thread(target=_run, daemon=True).start()

    # ── Settings save ─────────────────────────────────────────────────────────

    def _save_env(self):
        env_path = os.path.join(_ROOT, ".env")
        try:
            with open(env_path) as f:
                existing = f.read().splitlines()
        except FileNotFoundError:
            existing = []

        existing_keys: dict[str, str] = {}
        for line in existing:
            if "=" in line and not line.startswith("#"):
                k = line.split("=", 1)[0].strip()
                existing_keys[k] = line

        for key, entry in self._env_entries.items():
            val = entry.get().strip()
            if val:
                existing_keys[key] = f"{key}={val}"

        with open(env_path, "w") as f:
            written: set[str] = set()
            for line in existing:
                if "=" in line and not line.startswith("#"):
                    k = line.split("=", 1)[0].strip()
                    f.write(existing_keys.get(k, line) + "\n")
                    written.add(k)
                else:
                    f.write(line + "\n")
            for k, v in existing_keys.items():
                if k not in written:
                    f.write(v + "\n")

        load_dotenv(env_path, override=True)
        messagebox.showinfo("Saved", f".env saved.\nRestart the server to apply key changes.")

    # ── Global log ────────────────────────────────────────────────────────────

    def _glog(self, msg: str, tag: str = "", source: str = "gui") -> None:
        """Append to the global log buffer and the Logs page widget."""
        ts = _ts()
        self._global_logs.append((ts, source, msg, tag))
        if "logs" in self._logs:
            _log(self._logs["logs"], msg, tag)

    # ── Logs page ─────────────────────────────────────────────────────────────

    def _build_logs(self) -> None:
        pg = self._pages["Logs"]
        _label(pg, "System Logs", 18, bold=True, bg=BG).pack(anchor="w", padx=24, pady=(20, 4))
        _label(pg, "Unified log tracker — GUI activity, server output, and file logs",
               10, MUTED, bg=BG).pack(anchor="w", padx=24, pady=(0, 12))

        # Filter / control bar
        ctrl = _card(pg, pady=8)
        ctrl.pack(fill="x", padx=24, pady=(0, 8))
        row = tk.Frame(ctrl, bg=SURFACE)
        row.pack(fill="x", padx=12)

        _label(row, "Filter:", 9, MUTED).pack(side="left", padx=(0, 6))
        self._log_filter = tk.StringVar(value="all")
        for val, lbl in (("all", "All"), ("server", "Server"), ("api", "API"),
                         ("pipeline", "Pipeline"), ("error", "Errors")):
            rb = tk.Radiobutton(
                row, text=lbl, variable=self._log_filter, value=val,
                font=("Segoe UI", 9), fg=MUTED, bg=SURFACE,
                selectcolor=SURFACE2, activebackground=SURFACE,
                activeforeground=ACCENT,
                command=self._apply_log_filter,
            )
            rb.pack(side="left", padx=4)

        _btn(row, "Reload File Log", self._reload_file_log, small=True).pack(side="right", padx=(8, 0))
        _btn(row, "Clear", self._clear_global_log, small=True, accent=False).pack(side="right")

        # Search bar
        srow = tk.Frame(ctrl, bg=SURFACE, pady=4)
        srow.pack(fill="x", padx=12)
        _label(srow, "Search:", 9, MUTED).pack(side="left", padx=(0, 6))
        self._log_search_var = tk.StringVar()
        self._log_search_var.trace_add("write", lambda *_: self._apply_log_filter())
        tk.Entry(srow, textvariable=self._log_search_var,
                 font=("Segoe UI", 9), bg=SURFACE2, fg=TEXT,
                 insertbackground=ACCENT, relief="flat", bd=4, width=40).pack(side="left")

        # Log file path indicator
        log_file = os.path.join(_ROOT, "logs", "server.log")
        _label(srow, f"  Tailing: {log_file}", 8, MUTED).pack(side="left", padx=8)

        # Main log widget
        log_card = _card(pg)
        log_card.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        hdr = tk.Frame(log_card, bg=SURFACE, pady=8)
        hdr.pack(fill="x", padx=16)
        _label(hdr, "Log Output", 10, bold=True).pack(side="left")
        self._log_count_lbl = tk.Label(hdr, text="0 entries",
                                       font=("Segoe UI", 8), fg=MUTED, bg=SURFACE)
        self._log_count_lbl.pack(side="right")

        log_w = _log_widget(log_card, height=28)
        log_w.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._logs["logs"] = log_w

        # Start file log tailing thread
        threading.Thread(target=self._tail_server_log, daemon=True).start()

    def _apply_log_filter(self) -> None:
        """Re-render the Logs widget from the global buffer applying filter + search."""
        if "logs" not in self._logs:
            return
        filt = self._log_filter.get()
        search = self._log_search_var.get().lower()
        w = self._logs["logs"]
        w.config(state="normal")
        w.delete("1.0", "end")
        shown = 0
        for ts, source, msg, tag in self._global_logs:
            if filt != "all" and source != filt:
                continue
            if filt == "error" and tag != "error":
                continue
            if search and search not in msg.lower():
                continue
            w.insert("end", msg + "\n", tag)
            shown += 1
        w.see("end")
        w.config(state="disabled")
        self._log_count_lbl.config(text=f"{shown} entries")

    def _clear_global_log(self) -> None:
        self._global_logs.clear()
        if "logs" in self._logs:
            self._logs["logs"].config(state="normal")
            self._logs["logs"].delete("1.0", "end")
            self._logs["logs"].config(state="disabled")
        self._log_count_lbl.config(text="0 entries")

    def _reload_file_log(self) -> None:
        """Force-reload the entire server.log file into the Logs page."""
        self._log_tail_pos = 0
        self._tail_server_log_once()

    def _tail_server_log(self) -> None:
        """Background thread: continuously tail logs/server.log every 3 s."""
        import time
        while True:
            try:
                self._tail_server_log_once()
            except Exception:
                pass
            time.sleep(3)

    def _tail_server_log_once(self) -> None:
        log_file = os.path.join(_ROOT, "logs", "server.log")
        if not os.path.exists(log_file):
            return
        with open(log_file, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(self._log_tail_pos)
            new_lines = fh.read()
            self._log_tail_pos = fh.tell()
        if new_lines:
            for line in new_lines.splitlines():
                line = line.strip()
                if not line:
                    continue
                tag = "error" if "ERROR" in line or "error" in line.lower() else \
                      "warning" if "WARNING" in line or "WARN" in line else "muted"
                entry = f"[file] {line}"
                self._global_logs.append((_ts(), "server", entry, tag))
                self.root.after(0, lambda e=entry, t=tag: _log(self._logs.get("logs"), e, t)
                                if "logs" in self._logs else None)
            self.root.after(0, lambda: self._log_count_lbl.config(
                text=f"{len(self._global_logs)} entries") if hasattr(self, "_log_count_lbl") else None)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def _on_close(self):
        if self._server_proc:
            self._server_proc.terminate()
        self.root.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Source Editor Dialog
# ─────────────────────────────────────────────────────────────────────────────

class _SourceDialog(tk.Toplevel):
    def __init__(self, parent, existing: dict | None = None):
        super().__init__(parent)
        self.title("Signal Source")
        self.configure(bg=SURFACE)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None

        self._build(existing or {})
        self.wait_window()

    def _build(self, src: dict):
        pad = {"padx": 16, "pady": 6}

        # Type
        r1 = tk.Frame(self, bg=SURFACE)
        r1.pack(fill="x", **pad)
        tk.Label(r1, text="Type:", font=("Segoe UI", 10), fg=TEXT, bg=SURFACE, width=12, anchor="w").pack(side="left")
        self._type_var = tk.StringVar(value=src.get("type", "rss"))
        ttk.Combobox(r1, textvariable=self._type_var, values=["rss", "reddit"],
                     state="readonly", width=14).pack(side="left")

        # Category
        r2 = tk.Frame(self, bg=SURFACE)
        r2.pack(fill="x", **pad)
        tk.Label(r2, text="Category:", font=("Segoe UI", 10), fg=TEXT, bg=SURFACE, width=12, anchor="w").pack(side="left")
        self._cat_entry = tk.Entry(r2, font=("Segoe UI", 10), bg=SURFACE2, fg=TEXT,
                                   insertbackground=ACCENT, relief="flat", bd=4, width=30)
        self._cat_entry.insert(0, src.get("category", ""))
        self._cat_entry.pack(side="left")

        # URL / Subreddit
        r3 = tk.Frame(self, bg=SURFACE)
        r3.pack(fill="x", **pad)
        tk.Label(r3, text="URL/Sub:", font=("Segoe UI", 10), fg=TEXT, bg=SURFACE, width=12, anchor="w").pack(side="left")
        self._url_entry = tk.Entry(r3, font=("Segoe UI", 10), bg=SURFACE2, fg=TEXT,
                                   insertbackground=ACCENT, relief="flat", bd=4, width=40)
        self._url_entry.insert(0, src.get("url") or src.get("subreddit", ""))
        self._url_entry.pack(side="left")

        # Limit
        r4 = tk.Frame(self, bg=SURFACE)
        r4.pack(fill="x", **pad)
        tk.Label(r4, text="Limit:", font=("Segoe UI", 10), fg=TEXT, bg=SURFACE, width=12, anchor="w").pack(side="left")
        self._limit_var = tk.IntVar(value=src.get("limit", 10))
        ttk.Spinbox(r4, from_=1, to=100, width=8, textvariable=self._limit_var,
                    font=("Segoe UI", 10)).pack(side="left")

        # Buttons
        bf = tk.Frame(self, bg=SURFACE)
        bf.pack(fill="x", padx=16, pady=10)
        tk.Button(bf, text="Save", font=("Segoe UI", 10, "bold"),
                  fg=TEXT, bg=ACCENT, activebackground=ACCENT2,
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self._save).pack(side="left", padx=(0, 8))
        tk.Button(bf, text="Cancel", font=("Segoe UI", 10),
                  fg=TEXT, bg=SURFACE2, relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self.destroy).pack(side="left")

    def _save(self):
        t = self._type_var.get()
        url_val = self._url_entry.get().strip()
        entry: dict = {
            "type": t,
            "category": self._cat_entry.get().strip(),
        }
        if t == "rss":
            entry["url"] = url_val
        else:
            entry["subreddit"] = url_val
            entry["limit"] = self._limit_var.get()
        self.result = entry
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Vertical.TScrollbar",
                    background=BORDER, troughcolor=BG,
                    arrowcolor=MUTED, bordercolor=BG)
    style.configure("Horizontal.TScrollbar",
                    background=BORDER, troughcolor=BG,
                    arrowcolor=MUTED, bordercolor=BG)
    style.configure("TCombobox",
                    fieldbackground=SURFACE2, background=SURFACE2,
                    foreground=TEXT, selectbackground=ACCENT,
                    arrowcolor=TEXT)
    style.configure("TSpinbox",
                    fieldbackground=SURFACE2, background=SURFACE,
                    foreground=TEXT, arrowcolor=TEXT)
    style.configure("Treeview",
                    background=SURFACE, fieldbackground=SURFACE,
                    foreground=TEXT, rowheight=22)
    style.configure("Treeview.Heading",
                    background=SURFACE2, foreground=MUTED,
                    font=("Segoe UI", 9, "bold"))
    style.map("Treeview", background=[("selected", ACCENT)])

    app = PhoenixGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
