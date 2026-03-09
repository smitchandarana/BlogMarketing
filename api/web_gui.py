"""Phoenix Web GUI — served at GET / by the FastAPI app.

Provides a browser-based control panel with the same capabilities as the
Tkinter GUI, accessible from any machine on the network.
"""

from __future__ import annotations

import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

router = APIRouter()

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
_INDEX_HTML = os.path.join(_STATIC_DIR, "index.html")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def web_gui() -> HTMLResponse:
    """Serve the single-page web control panel."""
    with open(_INDEX_HTML, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
