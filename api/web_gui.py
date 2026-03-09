"""Phoenix Web GUI — served at GET / by the FastAPI app.

Provides a browser-based control panel with the same capabilities as the
Tkinter GUI, accessible from any machine on the network.
"""

from __future__ import annotations

import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

router = APIRouter()

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
_INDEX_HTML = os.path.join(_STATIC_DIR, "index.html")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def web_gui() -> HTMLResponse:
    """Serve the single-page web control panel."""
    with open(_INDEX_HTML, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# Minimal 1x1 orange pixel favicon — eliminates 404 noise in browser console
_FAVICON_ICO = (
    b"\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x18\x00"
    b"\x30\x00\x00\x00\x16\x00\x00\x00\x28\x00\x00\x00\x01\x00"
    b"\x00\x00\x02\x00\x00\x00\x01\x00\x18\x00\x00\x00\x00\x00"
    b"\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x3d\x6a\xff\x00\x00\x00\x00\x00"
)


@router.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    """Return a minimal favicon to eliminate 404 console errors."""
    return Response(content=_FAVICON_ICO, media_type="image/x-icon")
