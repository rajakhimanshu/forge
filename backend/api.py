from tools.llm_router import safe_print
# Disable ChromaDB telemetry to prevent "capture() takes 1 argument" crash
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

# Monkeypatch ChromaDB telemetry before it can be imported anywhere else
try:
    import chromadb.telemetry
    def mocked_capture(*args, **kwargs): pass
    if hasattr(chromadb.telemetry, 'Telemetry'):
        chromadb.telemetry.Telemetry.capture = mocked_capture
    if hasattr(chromadb.telemetry, 'capture'):
        chromadb.telemetry.capture = mocked_capture
    safe_print("[SYSTEM] ChromaDB telemetry monkeypatched.")
except Exception:
    pass

import json
import asyncio
import time
import tempfile
import shutil
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, Form, Request, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from agents.orchestrator import app as forge_app
from pydantic import BaseModel
from tools.dashboard_store import get_all_projects, update_status_by_id
from models.env_profile import EnvProfile

class ProjectStatusUpdate(BaseModel):
    status: str
    commitment: str = ""
    notes: str = ""

from knowledge_base.pdf_parser import extract_useful_pdf_info
from agents.idea_agent import format_idea_for_display
from agents.research_agent import format_market_for_display
from agents.verdict_agent import format_verdict_for_display
from agents.technical_agent import format_tech_for_display
from agents.blueprint_agent import format_blueprint_for_display
from agents.gtm_agent import format_gtm_for_display
from agents.business_agent import format_business_for_display
from agents.roadmap_agent import format_roadmap_for_display
from agents.intake_agent import generate_intake_questions, sharpen_idea as sharpen_idea_fn
from contextlib import asynccontextmanager


# ── Suggestion 5: Ollama health check at startup ──────────────────────────────
async def check_ollama_health():
    """
    If OLLAMA_MODEL is configured, ping localhost:11434 at startup.
    Logs a clear warning if Ollama is unreachable so the user knows
    before the pipeline exhausts all Groq quota mid-run.
    """
    import httpx
    ollama_model = os.getenv("OLLAMA_MODEL", "")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    if not ollama_model:
        return  # Ollama not configured — skip check
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            if resp.status_code == 200:
                safe_print(f"[OLLAMA] ✓ Reachable at {ollama_url} | Model: {ollama_model}")
            else:
                safe_print(
                    f"[OLLAMA] WARNING: {ollama_url} returned HTTP {resp.status_code}. "
                    f"Ollama fallback may fail during pipeline runs."
                )
    except Exception as e:
        safe_print(
            f"[OLLAMA] WARNING: Cannot reach {ollama_url} — {e}. "
            f"Set OLLAMA_MODEL= in .env to disable this check, or start Ollama."
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_ollama_health()
    yield

app = FastAPI(title="FORGE Pipeline API v2.0", lifespan=lifespan)


@app.get("/api/health")
async def health_check():
    """Health check endpoint — returns API status and LLM mode."""
    from tools.llm_router import safe_print, get_llm_info
    llm_info = get_llm_info()
    return {
        "status": "ok",
        "version": "2.0",
        "llm_mode": llm_info["mode"],
        "llm_model": llm_info["model_name"],
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store
active_sessions = {}


@app.post("/api/forge/intake")
async def get_intake_questions(
    idea_concept: str = Form(...),
    idea_context: str = Form('')
):
    """Step 1 of 2: generate 3 clarifying questions for the idea."""
    combined = idea_concept + '\n' + idea_context
    questions = generate_intake_questions(combined)
    return questions  # {q1: '...', q2: '...', q3: '...'}


@app.post("/api/forge/sharpen")
async def sharpen_idea_endpoint(
    idea_concept: str = Form(...),
    q1: str = Form(...), a1: str = Form(...),
    q2: str = Form(...), a2: str = Form(...),
    q3: str = Form(...), a3: str = Form(...)
):
    """Step 2 of 2: turn raw idea + founder answers into a precise brief."""
    sharpened = sharpen_idea_fn(idea_concept, q1, a1, q2, a2, q3, a3)
    return {
        'sharpened_idea': sharpened,
        'qa_pairs': {'q1': q1, 'a1': a1, 'q2': q2, 'a2': a2, 'q3': q3, 'a3': a3}
    }


@app.post("/api/forge/start")
async def start_pipeline(
    idea_concept: str = Form(...),
    idea_context: str = Form(""),
    pdf_file: UploadFile = File(None),
    # Intake questionnaire answers (optional — sent after /api/forge/sharpen)
    q1: str = Form(''), a1: str = Form(''),
    q2: str = Form(''), a2: str = Form(''),
    q3: str = Form(''), a3: str = Form(''),
    # Layer 3 — Environment Profile fields
    env_os: str = Form("windows"),
    env_gpu: str = Form("none"),
    env_ai_cli: str = Form("gemini"),
    env_experience: str = Form("intermediate"),
    env_node_installed: str = Form("false"),
    env_python_installed: str = Form("true"),
):
    session_id = f"session_{int(time.time()*1000)}"

    pdf_text = ""
    if pdf_file and pdf_file.filename:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copyfileobj(pdf_file.file, tmp)
            tmp_path = tmp.name
        try:
            pdf_text = extract_useful_pdf_info(tmp_path, idea_concept)
            if pdf_text.startswith("Error"):
                pdf_text = ""
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # Build EnvProfile from form fields
    env_profile = EnvProfile(
        os=env_os if env_os in ("windows", "mac", "linux") else "windows",
        gpu=env_gpu or "none",
        ai_cli=env_ai_cli if env_ai_cli in ("gemini", "claude_code", "cursor", "copilot") else "gemini",
        experience=env_experience if env_experience in ("beginner", "intermediate", "advanced") else "intermediate",
        node_installed=env_node_installed.lower() == "true",
        python_installed=env_python_installed.lower() == "true",
    )

    state = {
        # Core inputs
        "user_idea": idea_concept,
        "pdf_context": (idea_context + "\n\n" + pdf_text).strip(),
        "project_slug": "",
        "env_profile": env_profile,
        # Pydantic output models
        "idea_output": None,
        "market_output": None,
        "verdict_output": None,
        "tech_output": None,
        "blueprint_output": None,
        "gtm_output": None,
        "business_output": None,
        "roadmap_output": None,
        # New layer outputs
        "feature_bundle": None,
        "service_bundle": None,
        "build_steps": [],
        "docx_path": "",
        # Summary fields
        "idea_summary": "",
        "market_summary": "",
        "verdict_summary": "",
        "tech_summary": "",
        "gtm_summary": "",
        "business_summary": "",
        # Legacy fields
        "idea_analysis": "",
        "market_research": "",
        "verdict": {},
        "technical_rd": "",
        "blueprint": "",
        "gtm_plan": "",
        "business_model": "",
        "launch_roadmap": "",
        "error_log": [],
        "current_phase": "start",
        # Intake answers — populated when founder completes questionnaire
        "intake_answers": (
            {'q1': q1, 'a1': a1, 'q2': q2, 'a2': a2, 'q3': q3, 'a3': a3}
            if any([a1, a2, a3]) else None
        ),
        "usp_output": None,
        "idea_anchor": None,
        "kill_condition_output": None,
        "final_verdict": None,
        "stack_locked": False,
    }

    active_sessions[session_id] = {
        "state": state,
        "queue": asyncio.Queue(),
        "is_complete": False,
    }

    asyncio.create_task(run_pipeline_task(session_id))
    return {"session_id": session_id}


async def run_pipeline_task(session_id: str):
    session = active_sessions[session_id]
    state = session["state"]
    q = session["queue"]

    STATUS = {
        "idea_analysis_task":  "Analyzing core friction maps...",
        "feature_agent":       "Decomposing features into technical specs...",
        "market_research_task": "Scanning market gaps & competitors...",
        "verdict_task":        "Calculating investment verdict...",
        "technical_rd_task":   "Drafting technical specifications...",
        "service_resolver":    "Researching best free services (Tavily)...",
        "blueprint_task":      "Generating project blueprint...",
        "step_generator":      "Building OS-aware SETUP & CODING steps...",
        "prompt_engineer":     "Enriching AI prompts with exact context...",
        "gtm":                 "Building Go-To-Market plan...",
        "business":            "Designing business model & pricing...",
        "roadmap":             "Mapping 30-day launch roadmap...",
        "docx_export":         "Packaging final build guide (.docx)...",
    }

    try:
        main_loop = asyncio.get_running_loop()

        def run_sync():
            for output in forge_app.stream(state):
                for node_name, updates in output.items():
                    msg_text = STATUS.get(node_name, f"Processing: {node_name}")
                    state.update(updates)

                    formatted_markdowns = {}
                    phase_failed = False
                    phase_error_message = ""

                    OUTPUT_MAP = [
                        ("idea_output",       "idea_analysis",  format_idea_for_display),
                        ("market_output",     "market_research", format_market_for_display),
                        ("verdict_output",    "verdict",         format_verdict_for_display),
                        ("tech_output",       "technical_rd",    format_tech_for_display),
                        ("blueprint_output",  "blueprint",       format_blueprint_for_display),
                        ("gtm_output",        "gtm",             format_gtm_for_display),
                        ("business_output",   "business",        format_business_for_display),
                        ("roadmap_output",    "roadmap",         format_roadmap_for_display),
                    ]

                    LEGACY_KEYS = {
                        "idea_analysis", "market_research", "verdict",
                        "technical_rd", "blueprint", "gtm", "business", "roadmap",
                    }

                    for k, v in updates.items():
                        matched = [(tab, fmt) for (out_key, tab, fmt) in OUTPUT_MAP if out_key == k]
                        if matched and v:
                            tab_key, formatter = matched[0]
                            if getattr(v, "failed", False):
                                phase_failed = True
                                phase_error_message = getattr(v, "error_message", "Unknown error")
                                formatted_markdowns[tab_key] = {
                                    "_failed": True,
                                    "_error_message": phase_error_message,
                                }
                            else:
                                formatted_markdowns[tab_key] = formatter(v)
                        elif k == "service_bundle" and v:
                            # Send service bundle summary to frontend
                            if hasattr(v, 'services') and v.services:
                                svc_lines = [
                                    f"- **{svc.infra_need}** -> {svc.recommended_service} "
                                    f"(`{svc.env_var_name}`)"
                                    for svc in v.services
                                ]
                                formatted_markdowns["services"] = (
                                    "## Resolved Services\n\n"
                                    + "\n".join(svc_lines)
                                )
                        elif k == "build_steps" and v:
                            # Count SETUP vs CODING steps
                            setup_count = sum(
                                1 for s in v
                                if hasattr(s, 'step_type') and str(s.step_type).lower() in ('setup', 'steptype.setup')
                            )
                            coding_count = len(v) - setup_count
                            formatted_markdowns["build_steps_summary"] = (
                                f"## Build Steps Generated\n\n"
                                f"- **{setup_count}** SETUP steps (terminal commands)\n"
                                f"- **{coding_count}** CODING steps (AI prompts)\n"
                                f"- **Total:** {len(v)} steps"
                            )
                        elif k == "docx_path" and v:
                            formatted_markdowns["docx_ready"] = {
                                "path": v,
                                "download_url": f"/api/forge/download/{state.get('project_slug', 'project')}",
                            }
                        elif k == "final_verdict" and v:
                            # Send special SSE event BEFORE document rendering
                            asyncio.run_coroutine_threadsafe(q.put({"type": "verdict_card", "data": v.model_dump()}), main_loop)
                        elif k in LEGACY_KEYS:
                            pass
                        else:
                            # Only pass through plain serialisable scalars - ignore Pydantic/LangGraph internals
                            if isinstance(v, (str, int, float, bool, list, dict)) and v:
                                formatted_markdowns[k] = v

                    data = {
                        "node": node_name,
                        "status_message": msg_text,
                        "updates": formatted_markdowns,
                        "phase_failed": phase_failed,
                        "phase_error_message": phase_error_message,
                    }
                    asyncio.run_coroutine_threadsafe(q.put(data), main_loop)

            # Auto-save to dashboard after pipeline finishes
            try:
                from tools.dashboard_store import save_project
                verdict_str = 'UNKNOWN'
                if state.get('verdict_output') and hasattr(state.get('verdict_output'), 'verdict'):
                    verdict_str = state['verdict_output'].verdict
                idea_out = state.get('idea_output')
                if idea_out and hasattr(idea_out, 'project_name'):
                    project_name = idea_out.project_name
                else:
                    project_name = state.get('project_slug') or "Unknown Project"

                if isinstance(project_name, str) and project_name.strip():
                    save_project(
                        project_name=project_name,
                        idea_summary=state.get('user_idea', '')[:100],
                        verdict=verdict_str,
                        phases_completed=9 if state.get('docx_path') else 8 if state.get('roadmap_output') else 5
                    )
            except Exception as e:
                safe_print(f"Error saving to dashboard: {e}")

        await asyncio.to_thread(run_sync)
        await q.put({
            "node": "complete",
            "status_message": "Pipeline completed! Build guide ready.",
            "updates": {
                "docx_url": f"/api/forge/download/{state.get('project_slug', 'project')}"
                if state.get('docx_path') else None
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        await q.put({"node": "error", "status_message": f"Pipeline Error: {str(e)}"})
    finally:
        session["is_complete"] = True


@app.get("/api/forge/stream/{session_id}")
async def stream_pipeline(session_id: str, request: Request):
    if session_id not in active_sessions:
        return {"error": "Session not found"}

    session = active_sessions[session_id]
    q = session["queue"]

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(q.get(), timeout=1.0)
                yield {
                    "event": "message",
                    "id": session_id,
                    "data": json.dumps(data),
                }
                if data.get("node") in ["complete", "error"]:
                    break
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "keep-alive"}
                if session["is_complete"] and q.empty():
                    break

    return EventSourceResponse(event_generator())


@app.get("/api/forge/download/{project_slug}")
async def download_build_guide(project_slug: str):
    """Serve the generated .docx build guide for download."""
    # Sanitise slug
    safe_slug = "".join(c for c in project_slug if c.isalnum() or c in "-_")
    docx_path = Path("outputs") / safe_slug / f"{safe_slug}_build_guide.docx"

    if not docx_path.exists():
        # Try to find any docx in the outputs dir
        outputs_dir = Path("outputs") / safe_slug
        if outputs_dir.exists():
            docx_files = list(outputs_dir.glob("*.docx"))
            if docx_files:
                docx_path = docx_files[0]

    if not docx_path.exists():
        return {"error": f"Build guide not found for project: {safe_slug}"}

    return FileResponse(
        path=str(docx_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{safe_slug}_build_guide.docx",
    )


@app.get("/api/forge/quota")
async def get_tavily_quota():
    """Return current Tavily quota usage for this month."""
    try:
        from db.service_cache import get_quota_used
        used = get_quota_used('tavily')
        limit = int(os.getenv("TAVILY_MONTHLY_LIMIT", "1000"))
        return {"used": used, "limit": limit, "remaining": limit - used}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/dashboard")
async def get_dashboard():
    return get_all_projects()


@app.patch("/api/dashboard/{project_id}")
async def update_project_status(project_id: str, update: ProjectStatusUpdate):
    success = update_status_by_id(project_id, update.status, update.commitment, update.notes)
    if success:
        return {"success": True}
    return {"success": False, "error": "Project not found"}


# ── Pipeline cache management endpoints ───────────────────────────────────────
@app.get("/api/cache/stats")
async def get_cache_stats():
    """Return how many pipeline results are cached (< 24h old)."""
    try:
        from db.pipeline_cache import _conn
        conn = _conn()
        active = conn.execute(
            "SELECT COUNT(*) as cnt FROM pipeline_cache "
            "WHERE created_at > datetime('now', '-24 hours')"
        ).fetchone()
        total = conn.execute("SELECT COUNT(*) as cnt FROM pipeline_cache").fetchone()
        return {"active_entries": active["cnt"], "total_entries": total["cnt"], "ttl_hours": 24}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/api/cache/clear")
async def clear_pipeline_cache():
    """Delete all expired (> 24h) pipeline cache entries."""
    try:
        from db.pipeline_cache import clear_expired_cache
        deleted = clear_expired_cache()
        return {"deleted_entries": deleted, "status": "ok"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)