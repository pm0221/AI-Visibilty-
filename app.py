"""
app.py  —  AI Visibility Audit Web Server
Run with:  python app.py
Opens browser automatically at http://localhost:8000
"""
import asyncio
import json
import os
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="AI Visibility Audit Tool")

from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    tb = traceback.format_exc()
    print(tb)
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "traceback": tb}
    )

# ── Phase definitions ──────────────────────────────────────────────────────────
PHASES = [
    "Competitor Discovery",
    "Website Scraping",
    "Keyword Extraction",
    "Keyword Ranking (Gemini)",
    "Context Mining",
    "Category Analysis",
    "Query Generation",
    "Gemini Audit",
    "Scoring & Analytics",
    "Dashboard Generation",
]

# ── Global audit state ─────────────────────────────────────────────────────────
audit_state = {
    "status":        "idle",   # idle | running | done | error
    "current_phase": 0,
    "total_phases":  len(PHASES),
    "phases":        PHASES,
    "phase_name":    "",
    "log":           [],
    "report_ready":  False,
    "error":         None,
}
_lock = threading.Lock()

def _update(**kwargs):
    with _lock:
        audit_state.update(kwargs)

def _log(msg: str):
    with _lock:
        audit_state["log"].append(msg)
    print(msg)

# ── Request models ─────────────────────────────────────────────────────────────
class DiscoverRequest(BaseModel):
    brand_name: str
    brand_url:  str
    category:   str

class Competitor(BaseModel):
    name: str
    url:  str = ""

class AuditRequest(BaseModel):
    brand_name:  str
    brand_url:   str
    category:    str
    competitors: list

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    # Try multiple locations for the template
    possible_paths = [
        Path(__file__).parent / "templates" / "index.html",
        Path("templates") / "index.html",
        Path("index.html"),
    ]
    for p in possible_paths:
        if p.exists():
            return p.read_text(encoding="utf-8")
    # Show helpful error if template not found
    return HTMLResponse(f"""
<!DOCTYPE html><html><body style="background:#09090F;color:#E2E8F0;
font-family:system-ui;display:flex;align-items:center;justify-content:center;
min-height:100vh;flex-direction:column;gap:16px">
<h2 style="color:#EF4444">⚠ Template file not found</h2>
<p>Please make sure <b>templates/index.html</b> exists inside your Audit folder.</p>
<p style="color:#475569;font-size:13px">Looked in: {' | '.join(str(p) for p in possible_paths)}</p>
</body></html>
""", status_code=200)

@app.post("/discover")
async def discover(req: DiscoverRequest):
    """Auto-discover competitors using Google + Groq (no browser needed)."""
    try:
        from competitor_finder import _google_search, _extract_competitors, _groq_direct_search
        raw         = _google_search(
            f"{req.brand_name} {req.category} competitors India top brands")
        competitors = _extract_competitors(req.brand_name, req.category, raw) if raw.strip() else []
        if not competitors:
            competitors = _groq_direct_search(req.brand_name, req.category)

        # The discovery helpers return names.  Normalize them for the web UI so
        # the frontend never tries to read c.name from a plain string. URLs are
        # optional; the audit can still track a competitor by name.
        normalized = []
        seen = set()
        for item in competitors or []:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                url = str(item.get("url", "")).strip()
            else:
                name = str(item).strip()
                url = ""
            if name and name.lower() != req.brand_name.strip().lower() and name.lower() not in seen:
                seen.add(name.lower())
                normalized.append({"name": name, "url": url})

        return {"success": True, "competitors": normalized}
    except Exception as e:
        return {"success": False, "competitors": [], "error": str(e)}

@app.post("/start")
async def start_audit(req: AuditRequest, background_tasks: BackgroundTasks):
    """Start the full audit pipeline in background."""
    with _lock:
        if audit_state["status"] == "running":
            return {"success": False, "error": "Audit already running"}
        audit_state.update({
            "status": "running", "current_phase": 0,
            "phase_name": "", "log": [],
            "report_ready": False, "error": None
        })

    background_tasks.add_task(
        _run_background,
        req.brand_name, req.brand_url, req.category,
        [c if isinstance(c, dict) else c.dict() for c in req.competitors]
    )
    return {"success": True}

@app.get("/progress")
async def progress_stream():
    """Server-Sent Events — browser listens for live phase updates."""
    async def generator():
        while True:
            with _lock:
                data   = json.dumps(audit_state)
                status = audit_state["status"]
            yield f"data: {data}\n\n"
            if status in ("done", "error"):
                break
            await asyncio.sleep(0.8)
    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@app.get("/report", response_class=HTMLResponse)
async def get_report():
    """Serve the generated report HTML inline."""
    rp = "./outputs/report.html"
    if os.path.exists(rp):
        return Path(rp).read_text(encoding="utf-8")
    return HTMLResponse("<h1>Report not ready</h1>", status_code=404)

@app.get("/download")
async def download_report():
    """Download the report as a standalone HTML file."""
    rp = "./outputs/report.html"
    if os.path.exists(rp):
        return FileResponse(
            rp, filename="ai_visibility_report.html", media_type="text/html")
    return {"error": "Report not found"}

@app.post("/reset")
async def reset():
    """Reset state so a new audit can be started."""
    _update(status="idle", current_phase=0, phase_name="",
            log=[], report_ready=False, error=None)
    return {"success": True}

# ── Background pipeline runner ─────────────────────────────────────────────────
def _run_background(brand_name, brand_url, category, competitors):
    try:
        from web_runner import run_pipeline
        run_pipeline(brand_name, brand_url, category,
                     competitors, _update, _log)
        _update(status="done", report_ready=True,
                current_phase=len(PHASES))
        _log("✓ Audit complete! Report is ready.")
    except Exception as e:
        import traceback
        _update(status="error", error=str(e))
        _log(f"✗ Error: {e}")
        print(traceback.format_exc())

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    def _open():
        time.sleep(1.5)
        webbrowser.open("http://localhost:8000")
    threading.Thread(target=_open, daemon=True).start()
    print("=" * 55)
    print("  AI Visibility Audit Tool — Web Interface")
    print("  Opening browser at http://localhost:8000")
    print("=" * 55)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")