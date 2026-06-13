"""FastAPI server: serves the Baxie-branded workspace and the /run endpoint.

The workspace POSTs to /run and animates the returned events into the team
activity feed. /run defaults to the deterministic scripted scenario so the live
demo can never stall; set live=true to drive the real agents (org credits).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from orchestrator import run_change_order

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"

app = FastAPI(title="Baxie Digital Back Office")


@app.get("/health")
def health():
    return {"ok": True, "service": "baxie-digital-back-office"}


@app.post("/run")
async def run(request: Request):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    from agents.base import agents_enabled
    message = (body or {}).get("message", "homeowner wants to add a window")
    live = bool((body or {}).get("live")) and agents_enabled()
    result = run_change_order(message, live=live)
    # attach the self-grading scoreboard if the gold set is built
    result["scoreboard"] = _scoreboard()
    return JSONResponse(result)


def _scoreboard() -> dict:
    try:
        from grader import score_goldset
        return score_goldset()
    except Exception:
        return {"available": False}


@app.get("/", response_class=HTMLResponse)
def index():
    idx = STATIC / "index.html"
    if idx.exists():
        return HTMLResponse(idx.read_text())
    return HTMLResponse("<h1>Baxie Digital Back Office</h1><p>workspace building…</p>")


# mount any other static assets (css/js/img) if present
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
