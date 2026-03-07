"""
paths.py — Centralised path resolution for dev + PyInstaller frozen builds.

Usage:
    from paths import app_dir, resource_dir

    app_dir()       -> directory of exe (or script). User data lives here.
                       (.env, tracker.csv, Blogs/ output, LinkedIn Posts/, Log.txt)

    resource_dir()  -> directory of bundled read-only assets.
                       (Prompts/, Blogs/_new-post.html, MarketingSchedule/Calender.json)
                       In dev mode this is the same as app_dir().
                       In frozen mode this is sys._MEIPASS (temp extraction dir).
"""

import os
import sys


def app_dir() -> str:
    """
    Directory of the exe when frozen, or directory of this script in dev mode.
    All user-generated and user-editable files live here.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir() -> str:
    """
    Directory containing bundled read-only resource files.
    In PyInstaller frozen mode this is sys._MEIPASS.
    In dev mode this is the same as app_dir().
    """
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))
