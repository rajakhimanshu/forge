import gradio as gr
import os
import re
import time
from pathlib import Path
from agents.orchestrator import app as forge_app
from agents.intake_agent import generate_intake_questions
from knowledge_base.ingest import extract_pdf_text
from agents.devguide_agent import run_devguide_agent, save_devguide

# ==========================================
# CSS LOADER
# ==========================================
def load_css():
    css_path = Path("forge_theme.css")
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

CSS = load_css()

# ==========================================
# TERMINAL LOGGER  (prints always visible)
# ==========================================
def log(msg, level="INFO"):
    prefix = {"INFO": "[ FORGE ]", "WARN": "[WARNING]", "ERR ": "[ ERROR ]"}.get(level, "[  LOG  ]")
    print(f"{prefix}  {msg}", flush=True)

# ==========================================
# HTML COMPONENT BUILDERS
# ==========================================
def get_header_html(step=1):
    steps = ["Input", "Intake", "Analysis", "Build"]
    pills = []
    for i, s in enumerate(steps):
        num = i + 1
        cls = "phase-pill done" if num < step else "phase-pill active" if num == step else "phase-pill"
        sep = '<span class="phase-sep">·</span>' if i < len(steps) - 1 else ""
        pills.append(f'<span class="{cls}">{num} {s.upper()}</span>{sep}')
    return (
        f'<div id="forge-header">'
        f'<div class="forge-wordmark"><span class="wm-accent">⚒</span> FORGE</div>'
        f'<div class="phase-pills">{"".join(pills)}</div>'
        f'<div class="hdr-actions"><span class="version-tag">v2.0</span></div>'
        f'</div>'
    )

def get_status_bar_html(message, running=False, elapsed=None):
    dot   = '<span class="status-dot-live"></span>' if running else '<span class="status-dot-idle"></span>'
    color = "var(--cyan)" if running else "var(--text-2)"
    timer = elapsed if elapsed is not None else "00:00"
    return (
        f'<div id="forge-status-bar">'
        f'<div class="status-message" style="color:{color};">{dot}<span>{message}</span></div>'
        f'<div class="status-timer" id="forge-timer">{timer}</div>'
        f'</div>'
    )

def get_intake_status_html(message="", running=False):
    """Inline status strip shown below the Analyze button."""
    if not message:
        return ""
    dot   = '<span class="status-dot-live"></span>' if running else '<span class="status-dot-idle"></span>'
    color = "var(--cyan)" if running else "var(--text-2)"
    border = "var(--cyan)" if running else "#555"
    return (
        f'<div style="margin:8px 0;padding:10px 14px;'
        f'background:rgba(255,255,255,0.04);border-radius:8px;'
        f'border-left:3px solid {border};'
        f'font-family:\'Space Mono\',monospace;font-size:0.75rem;'
        f'display:flex;align-items:center;gap:8px;color:{color};">'
        f'{dot}<span>{message}</span></div>'
    )

def get_phase_strip_html(current_task=None):
    phases = [
        ("PHASE 01", "Idea Analysis",   "idea_analysis_task"),
        ("PHASE 02", "Market Research", "market_research_task"),
        ("PHASE 03", "Final Verdict",   "verdict_task"),
        ("PHASE 04", "Technical R&D",   "technical_rd_task"),
        ("PHASE 05", "Dev Blueprint",   "blueprint_task"),
    ]
    cards, found = [], False
    for p_num, p_name, task_id in phases:
        if current_task == "complete":
            cls, icon, status = "done", "✓", "COMPLETE"
        elif current_task and task_id == current_task:
            cls, icon, status = "active", "◉", "RUNNING"
            found = True
        elif current_task and not found:
            cls, icon, status = "done", "✓", "COMPLETE"
        else:
            cls, icon, status = "", "○", "PENDING"
        cards.append(
            f'<div class="phase-card {cls}">'
            f'<div class="p-num">{p_num}</div>'
            f'<div class="p-name">{p_name}<span>{icon}</span></div>'
            f'<div class="p-status">{status}</div></div>'
        )
    return f'<div id="forge-phase-strip"><div class="phase-strip">{"".join(cards)}</div></div>'

def get_verdict_html(verdict):
    if not verdict or not isinstance(verdict, dict) or not verdict.get("verdict"):
        return '<div class="empty-state">Waiting for analysis pipeline...</div>'
    v_type = verdict.get("verdict", "UNKNOWN").upper()
    if v_type == "BUILD":
        color, bg, border, icon = "var(--green)", "var(--green-dim)", "rgba(30,217,138,0.3)", "▲"
    elif v_type == "PIVOT":
        color, bg, border, icon = "var(--amber)", "var(--amber-dim)", "rgba(245,166,35,0.3)", "◈"
    else:
        color, bg, border, icon = "var(--red)", "var(--red-dim)", "rgba(255,77,106,0.3)", "▼"

    def gauge(label, score, fill_color):
        pct = min(max(float(score) * 10, 0), 100)
        return (
            f'<div><div class="score-label">{label}</div>'
            f'<div class="score-track"><div class="score-fill" style="width:{pct}%;background:{fill_color};"></div></div>'
            f'<div class="score-val">{score} <span style="color:var(--text-3);">/ 10</span></div></div>'
        )

    scores = (
        gauge("MARKET OPPORTUNITY",    verdict.get("market_gap", 0),  "var(--green)") +
        gauge("TECHNICAL FEASIBILITY", verdict.get("feasibility", 0), "var(--accent)") +
        gauge("COMPETITIVE MOAT",      verdict.get("uniqueness", 0),  "var(--amber)")
    )
    report = verdict.get("report", "").replace(chr(10), "<br>")
    return (
        f'<div class="verdict-wrap">'
        f'<div class="verdict-badge" style="background:{bg};border:1px solid {border};color:{color};">'
        f'{icon}&nbsp;&nbsp;{v_type}</div>'
        f'<div class="verdict-scores">{scores}</div>'
        f'<div class="gr-markdown" style="padding:0!important;margin-top:20px;">{report}</div>'
        f'</div>'
    )

def get_folder_tree_html(blueprint_text):
    if not blueprint_text:
        return '<div class="empty-state">Waiting for blueprint generation...</div>'
    return f'<div class="tree-wrap"><pre style="margin:0;padding:20px;background:transparent;border:none;"><code>{blueprint_text}</code></pre></div>'

def get_dev_guide_html(guide_text):
    if not guide_text:
        return '<div class="empty-state">Ready to generate — use the build bar below.</div>'
    return f'<div class="gr-markdown" style="padding:28px;">{guide_text}</div>'

# ==========================================
# HELPERS
# ==========================================
_last_forge_state = {}

def get_coding_method(build_method, ai_tool):
    if "Manual" in build_method: return "manual", "Manual coding"
    if "Mixed"  in build_method: return "mixed",  ai_tool
    tool_map = {
        "Gemini CLI": "gemini_cli", "Cursor": "cursor",
        "Windsurf / Codeium": "windsurf", "GitHub Copilot": "copilot", "Other AI tool": "ai_generic",
    }
    return tool_map.get(ai_tool, "gemini_cli"), ai_tool

def resolve_file_path(uploaded_file):
    if not uploaded_file: return None
    if isinstance(uploaded_file, str): return uploaded_file
    if isinstance(uploaded_file, dict) and "name" in uploaded_file: return uploaded_file["name"]
    if hasattr(uploaded_file, "name"): return uploaded_file.name
    return str(uploaded_file)

def _fmt_elapsed(seconds):
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"

# ==========================================
# INTAKE  (streaming generator — 9 outputs)
# ==========================================
# IMPORTANT: get_qs_btn must NOT be in outputs — Gradio forbids using the
# triggering component as an output in some versions, causing "Too many
# arguments" on the client side.  We use a separate gr.HTML for button state.

def update_intake_ui(user_idea, uploaded_file):
    """
    Streams real-time status to the sidebar while Ollama generates questions.

    Outputs (9 components):
        0  intake_panel   – Column visibility
        1  q1_label       – HTML
        2  q2_label       – HTML
        3  q3_label       – HTML
        4  header_html    – HTML
        5  q1_hidden      – Textbox
        6  q2_hidden      – Textbox
        7  q3_hidden      – Textbox
        8  intake_status  – HTML
    """
    HIDDEN = gr.update(visible=False)
    BLANK  = ""

    def _err(msg):
        log(f"Intake error: {msg}", "ERR ")
        return [HIDDEN, BLANK, BLANK, BLANK, get_header_html(1), BLANK, BLANK, BLANK,
                get_intake_status_html(msg, running=False)]

    def _busy(msg):
        return [HIDDEN, BLANK, BLANK, BLANK, get_header_html(1), BLANK, BLANK, BLANK,
                get_intake_status_html(msg, running=True)]

    # ── Validate ──────────────────────────────────────────────
    if not (user_idea or "").strip() and not uploaded_file:
        yield _err("⚠ Please enter an idea or upload a PDF first.")
        return

    log("=== ANALYZE IDEA clicked ===")
    yield _busy("⏳ Reading your input...")

    # ── Build combined text ────────────────────────────────────
    combined = (user_idea or "").strip()
    pdf_path = resolve_file_path(uploaded_file)

    if pdf_path:
        log(f"PDF uploaded: {pdf_path}")
        yield _busy("📄 Extracting PDF context...")
        try:
            pdf_text = extract_pdf_text(pdf_path)
            if not pdf_text.startswith("Error"):
                combined = f"USER TEXT IDEA: {user_idea}\n\n--- DOCUMENT CONTEXT ---\n{pdf_text}"
                log(f"PDF extracted successfully ({len(pdf_text)} chars)")
            else:
                log(f"PDF extraction warning: {pdf_text}", "WARN")
        except Exception as exc:
            log(f"PDF extraction failed: {exc}", "ERR ")

    if not combined.strip():
        yield _err("⚠ Could not extract content — re-upload or type your idea.")
        return

    # ── LLM call ──────────────────────────────────────────────
    log("Calling Ollama to generate intake questions...")
    yield _busy("🤖 Ollama generating questions... (15–60 s)")

    t0 = time.time()
    try:
        qs = generate_intake_questions(combined)
        elapsed = _fmt_elapsed(time.time() - t0)
        log(f"Questions generated in {elapsed}")
        log(f"  Q1: {qs.get('q1','')[:80]}")
        log(f"  Q2: {qs.get('q2','')[:80]}")
        log(f"  Q3: {qs.get('q3','')[:80]}")
    except Exception as exc:
        log(f"LLM error: {exc}", "ERR ")
        yield _err(f"❌ LLM error: {exc}")
        return

    elapsed_str = _fmt_elapsed(time.time() - t0)

    h1 = f'<div class="q-label-html">{qs.get("q1","Question 1")}</div>'
    h2 = f'<div class="q-label-html">{qs.get("q2","Question 2")}</div>'
    h3 = f'<div class="q-label-html">{qs.get("q3","Question 3")}</div>'

    yield [
        gr.update(visible=True),
        h1, h2, h3,
        get_header_html(2),
        qs.get("q1", ""), qs.get("q2", ""), qs.get("q3", ""),
        get_intake_status_html(f"✅ Questions ready  ({elapsed_str})", running=False),
    ]

# ==========================================
# MAIN PIPELINE  (streaming generator)
# ==========================================
def forge_pipeline(user_idea, uploaded_file, q1, a1, q2, a2, q3, a3,
                   build_method, ai_tool, team_size):
    global _last_forge_state
    log("=== RUN PIPELINE clicked ===")

    combined_idea = (user_idea or "").strip()
    pdf_path = resolve_file_path(uploaded_file)

    if pdf_path:
        log(f"Re-extracting PDF for pipeline: {pdf_path}")
        try:
            pdf_text = extract_pdf_text(pdf_path)
            if not pdf_text.startswith("Error"):
                combined_idea = f"USER TEXT IDEA: {user_idea}\n\n--- DOCUMENT CONTEXT ---\n{pdf_text}"
                log(f"PDF merged into idea ({len(pdf_text)} chars)")
        except Exception as exc:
            log(f"PDF extraction failed in pipeline: {exc}", "ERR ")

    if not combined_idea:
        log("No idea content — aborting pipeline.", "WARN")
        yield (
            get_header_html(2),
            get_status_bar_html("Error: No idea provided.", False),
            get_phase_strip_html(), "", "", get_verdict_html({}), "",
            get_folder_tree_html(""), gr.update(visible=False),
        )
        return

    coding_method, ai_tool_name = get_coding_method(build_method, ai_tool)
    log(f"Coding method: {coding_method}  |  Tool: {ai_tool_name}  |  Team: {team_size}")

    state = {
        "user_idea":       combined_idea,
        "intake_answers":  {"q1": q1, "a1": a1, "q2": q2, "a2": a2, "q3": q3, "a3": a3},
        "coding_method":   coding_method,
        "ai_tool_name":    ai_tool_name,
        "team_size":       int(team_size),
        "sharpened_idea":  None,
        "idea_analysis":   "",
        "market_research": "",
        "verdict":         {},
        "technical_rd":    "",
        "blueprint":       "",
        "project_slug":    "",
        "current_phase":   "start",
    }

    t_start = time.time()
    def _elapsed(): return _fmt_elapsed(time.time() - t_start)

    STATUS = {
        "intake_task":          "Sharpening idea vision...",
        "idea_analysis_task":   "Analyzing core friction maps...",
        "market_research_task": "Scanning market gaps & competitors...",
        "verdict_task":         "Calculating investment verdict...",
        "technical_rd_task":    "Drafting technical specifications...",
        "blueprint_task":       "Generating project blueprint...",
    }

    log("Initializing Forge engine...")
    yield (
        get_header_html(3),
        get_status_bar_html("Initializing Forge Engine...", True, _elapsed()),
        get_phase_strip_html(), "", "", get_verdict_html({}), "",
        get_folder_tree_html(""), gr.update(visible=False),
    )

    try:
        for output in forge_app.stream(state):
            for node_name, updates in output.items():
                state.update(updates)
                status_msg = STATUS.get(node_name, f"Processing: {node_name}")
                log(f"  [{_elapsed()}] Node: {node_name}  →  {status_msg}")

                # Per-node content preview in terminal
                if node_name == "idea_analysis_task" and state.get("idea_analysis"):
                    log(f"    Idea analysis: {str(state['idea_analysis'])[:120]}...")
                elif node_name == "market_research_task" and state.get("market_research"):
                    log(f"    Market research: {str(state['market_research'])[:120]}...")
                elif node_name == "verdict_task" and state.get("verdict"):
                    v = state.get("verdict", {})
                    log(f"    Verdict: {v.get('verdict','?')} | gap={v.get('market_gap','?')} feasibility={v.get('feasibility','?')} unique={v.get('uniqueness','?')}")
                elif node_name == "technical_rd_task" and state.get("technical_rd"):
                    log(f"    Technical R&D: {str(state['technical_rd'])[:120]}...")
                elif node_name == "blueprint_task" and state.get("blueprint"):
                    log(f"    Blueprint: {str(state['blueprint'])[:120]}...")

                yield (
                    get_header_html(3),
                    get_status_bar_html(status_msg, True, _elapsed()),
                    get_phase_strip_html(node_name),
                    state.get("idea_analysis", ""),
                    state.get("market_research", ""),
                    get_verdict_html(state.get("verdict", {})),
                    state.get("technical_rd", ""),
                    get_folder_tree_html(state.get("blueprint", "")),
                    gr.update(visible=False),
                )

        _last_forge_state = state
        total = _elapsed()
        log(f"=== PIPELINE COMPLETE in {total} ===")
        yield (
            get_header_html(4),
            get_status_bar_html(f"Pipeline Complete — All phases finished.  [{total}]", False, total),
            get_phase_strip_html("complete"),
            state.get("idea_analysis", ""),
            state.get("market_research", ""),
            get_verdict_html(state.get("verdict", {})),
            state.get("technical_rd", ""),
            get_folder_tree_html(state.get("blueprint", "")),
            gr.update(visible=True),
        )

    except Exception as exc:
        import traceback
        traceback.print_exc()
        log(f"Pipeline crashed: {exc}", "ERR ")
        yield (
            get_header_html(3),
            get_status_bar_html(f"Error: {str(exc)}", False, _elapsed()),
            get_phase_strip_html(), "", "", get_verdict_html({}), "",
            get_folder_tree_html(""), gr.update(visible=False),
        )

# ==========================================
# DEV GUIDE
# ==========================================
def generate_dev_guide(build_choice, tool_choice):
    global _last_forge_state
    if not _last_forge_state or not _last_forge_state.get("idea_analysis"):
        yield "Run the analysis pipeline first.", get_dev_guide_html("")
        return
    log("=== GENERATE DEV GUIDE clicked ===")
    yield "Initializing Guide Architect...", get_dev_guide_html("")
    tool_map = {
        "Gemini CLI":               "gemini_cli",
        "Antigravity (Claude Code)":"antigravity",
        "Cursor":                   "cursor",
        "Windsurf / Codeium":       "cursor",
        "GitHub Copilot":           "cursor",
    }
    try:
        log(f"Building dev guide for tool: {tool_choice}")
        yield "Building roadmap (2–3 min)...", get_dev_guide_html("")
        ctx    = _last_forge_state.copy()
        guide  = run_devguide_agent(ctx, tool_map.get(tool_choice, "gemini_cli"))
        path   = save_devguide(guide, ctx.get("project_slug", "output"),
                               tool_map.get(tool_choice, "gemini_cli"))
        log(f"Dev guide saved → {path}")
        yield f"Saved → {path}", get_dev_guide_html(guide)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        log(f"Dev guide failed: {exc}", "ERR ")
        yield f"Error: {str(exc)}", get_dev_guide_html("")

# ==========================================
# UI LAYOUT
# ==========================================
with gr.Blocks(css=CSS, title="FORGE | AI R&D Co-Pilot", theme=gr.themes.Monochrome()) as demo:
    gr.HTML("""
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Space+Mono:ital,wght@0,400;0,700;1,400&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500&display=swap" rel="stylesheet">
    """)

    header_html = gr.HTML(get_header_html(1))

    with gr.Row(elem_id="forge-layout"):
        # ── LEFT SIDEBAR ───────────────────────────────────────
        with gr.Column(scale=1, elem_id="forge-sidebar"):
            gr.HTML('<span class="forge-label">Step 1 — Initial Idea</span>')
            idea_input = gr.Textbox(
                show_label=False,
                placeholder=(
                    "Describe your startup idea...\n\n"
                    "e.g. 'An AI tool that auto-generates weekly dev reports from Git + Jira'\n"
                    "or  'A habit tracker that uses voice notes instead of manual logging'\n"
                    "or  'A B2B SaaS for freelance invoice reconciliation with Stripe'"
                ),
                lines=7,
            )
            file_upload = gr.File(
                label="Context PDF (optional)", file_types=[".pdf"], type="filepath"
            )
            get_qs_btn = gr.Button("ANALYZE IDEA →", elem_classes=["primary-btn"])

            # Live status below the Analyze button (NOT in outputs of get_qs_btn)
            intake_status = gr.HTML("")

            gr.HTML('<div class="intake-divider"></div>')

            with gr.Column(visible=False) as intake_panel:
                gr.HTML('<span class="forge-label accent-label">Step 2 — Sharpen Vision</span>')

                q1_label = gr.HTML('<div class="q-label-html">Question 1</div>')
                a1_input = gr.Textbox(show_label=False, placeholder="Your answer...", lines=2)

                q2_label = gr.HTML('<div class="q-label-html" style="margin-top:8px;">Question 2</div>')
                a2_input = gr.Textbox(show_label=False, placeholder="Your answer...", lines=2)

                q3_label = gr.HTML('<div class="q-label-html" style="margin-top:8px;">Question 3</div>')
                a3_input = gr.Textbox(show_label=False, placeholder="Your answer...", lines=2)

                gr.HTML('<div class="intake-divider"></div>')
                gr.HTML('<span class="forge-label">Build Method</span>')

                build_method = gr.Dropdown(
                    show_label=False,
                    choices=["AI Coding Tool", "Manual Coding", "Mixed Approach"],
                    value="AI Coding Tool",
                )
                ai_tool = gr.Dropdown(
                    show_label=False,
                    choices=["Gemini CLI", "Cursor", "Windsurf / Codeium", "GitHub Copilot", "Other AI tool"],
                    value="Gemini CLI",
                )
                team_size = gr.Slider(label="Team size", minimum=1, maximum=6, step=1, value=1)
                run_full_btn = gr.Button("RUN PIPELINE ▶", elem_classes=["primary-btn"])

        # ── MAIN CONTENT AREA ──────────────────────────────────
        with gr.Column(scale=4, elem_id="forge-main"):
            status_bar    = gr.HTML(get_status_bar_html("Engine Idle — awaiting input."))
            phase_tracker = gr.HTML(get_phase_strip_html())

            with gr.Tabs():
                with gr.TabItem("Idea Analysis"):
                    out_idea = gr.Markdown()
                with gr.TabItem("Market Research"):
                    out_research = gr.Markdown()
                with gr.TabItem("Final Verdict"):
                    out_verdict = gr.HTML(get_verdict_html(None))
                with gr.TabItem("Technical R&D"):
                    out_tech = gr.Markdown()
                with gr.TabItem("Dev Blueprint"):
                    out_blueprint = gr.HTML(get_folder_tree_html(""))
                with gr.TabItem("Dev Guide"):
                    out_devguide = gr.HTML(get_dev_guide_html(""))

            # Build bar — revealed after pipeline completes
            with gr.Column(visible=False, elem_id="forge-build-bar") as build_section:
                with gr.Row(elem_classes=["build-bar-row"]):
                    gr.HTML('<span class="build-label-tag">READY TO BUILD</span>')
                    build_choice = gr.Dropdown(
                        label="Approach",
                        choices=["Yes — AI coding tool", "No — writing code myself", "Mixed"],
                        value="Yes — AI coding tool",
                    )
                    tool_choice = gr.Dropdown(
                        label="Tool",
                        choices=["Gemini CLI", "Antigravity (Claude Code)", "Cursor",
                                 "Windsurf / Codeium", "GitHub Copilot"],
                        value="Gemini CLI",
                    )
                    gen_guide_btn = gr.Button(
                        "GENERATE DEV GUIDE ▶", elem_classes=["primary-btn", "build-cta"]
                    )
                guide_status = gr.Textbox(
                    show_label=False, placeholder="Guide status...",
                    interactive=False, elem_id="guide-status",
                )

    # Hidden question-text stores
    q1_hidden = gr.Textbox(visible=False)
    q2_hidden = gr.Textbox(visible=False)
    q3_hidden = gr.Textbox(visible=False)

    # ── Event handlers ────────────────────────────────────────
    # NOTE: get_qs_btn is NOT listed in outputs — avoids the Gradio
    # "Too many arguments" client-side error when a triggering button
    # is also referenced as an output component.
    get_qs_btn.click(
        fn=update_intake_ui,
        inputs=[idea_input, file_upload],
        outputs=[
            intake_panel,
            q1_label, q2_label, q3_label,
            header_html,
            q1_hidden, q2_hidden, q3_hidden,
            intake_status,               # 9 outputs total
        ],
    )

    run_full_btn.click(
        fn=forge_pipeline,
        inputs=[
            idea_input, file_upload,
            q1_hidden, a1_input,
            q2_hidden, a2_input,
            q3_hidden, a3_input,
            build_method, ai_tool, team_size,
        ],
        outputs=[
            header_html, status_bar, phase_tracker,
            out_idea, out_research, out_verdict,
            out_tech, out_blueprint, build_section,
        ],
    )

    gen_guide_btn.click(
        fn=generate_dev_guide,
        inputs=[build_choice, tool_choice],
        outputs=[guide_status, out_devguide],
    )

if __name__ == "__main__":
    os.environ["PYTHONPATH"] = "."
    log("Starting FORGE on http://127.0.0.1:7860")
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
