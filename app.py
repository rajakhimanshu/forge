import gradio as gr
import os
import re
from pathlib import Path
from agents.orchestrator import app
from agents.intake_agent import generate_intake_questions
from knowledge_base.ingest import extract_pdf_text

def get_questions(user_idea, uploaded_file):
    """Step 1: Generates 3 targeted questions based on the raw idea + PDF content."""
    combined_idea = user_idea
    if uploaded_file is not None:
        print(f"Extracting context from: {uploaded_file}...")
        pdf_text = extract_pdf_text(uploaded_file)
        combined_idea = f"{user_idea}\n\n--- DOCUMENT CONTEXT ---\n{pdf_text}"

    if not combined_idea.strip():
        return "", "", "", gr.update(visible=False)
    
    print(f"Generating intake questions for sharpened context...")
    qs = generate_intake_questions(combined_idea)
    
    # Return questions and make the intake panel visible
    return qs['q1'], qs['q2'], qs['q3'], gr.update(visible=True)

def run_forge_workflow(user_idea, uploaded_file, q1, a1, q2, a2, q3, a3, build_method, ai_tool, team_size):
    """Step 2: Runs the full 5-phase Forge pipeline with sharpened context."""
    combined_idea = user_idea
    if uploaded_file is not None:
        print(f"Using PDF context for analysis...")
        pdf_text = extract_pdf_text(uploaded_file)
        combined_idea = f"{user_idea}\n\n--- DOCUMENT CONTEXT ---\n{pdf_text}"

    if not combined_idea.strip():
        yield "Error: No idea provided.", "", "", "", "", ""
        return

    # Map UI values to coding_method codes
    coding_method = "manual"
    if build_method == "AI Coding Tool":
        if ai_tool == "Gemini CLI":
            coding_method = "gemini_cli"
        elif ai_tool == "Cursor":
            coding_method = "cursor"
        else:
            coding_method = "other_ai"
    elif build_method == "Mixed approach":
        coding_method = "mixed"

    # Package answers for the orchestrator
    intake_data = {
        "q1": q1, "a1": a1,
        "q2": q2, "a2": a2,
        "q3": q3, "a3": a3
    }

    # Initial state for the LangGraph
    state = {
        "user_idea": combined_idea,
        "intake_answers": intake_data,
        "coding_method": coding_method,
        "ai_tool_name": ai_tool if build_method == "AI Coding Tool" else build_method,
        "team_size": int(team_size),
        "sharpened_idea": None,
        "idea_analysis": "",
        "market_research": "",
        "verdict": {},
        "technical_rd": "",
        "blueprint": "",
        "project_slug": "",
        "current_phase": "start"
    }

    yield "=== Initializing Forge R&D ===", "", "", "", "", ""

    try:
        # Stream the graph execution
        for output in app.stream(state):
            for node_name, updates in output.items():
                state.update(updates)
                
                status_messages = {
                    "intake_task": "Phase 0: Sharpening your idea...",
                    "idea_analysis_task": "Phase 1: Analyzing core friction...",
                    "market_research_task": "Phase 2: Scanning market data...",
                    "verdict_task": "Phase 3: Calculating verdict & moat...",
                    "technical_rd_task": "Phase 4: Drafting technical requirements...",
                    "blueprint_task": "Phase 5: Finalizing dev blueprint..."
                }
                
                status = status_messages.get(node_name, f"Processing {node_name}...")
                
                yield (
                    status,
                    state.get("idea_analysis", ""),
                    state.get("market_research", ""),
                    state.get("verdict", {}).get("formatted_report") or state.get("verdict", {}).get("report", ""),
                    state.get("technical_rd", ""),
                    state.get("blueprint", "")
                )

        yield "=== Analysis Complete ===", state["idea_analysis"], state["market_research"], state.get("verdict", {}).get("formatted_report") or state.get("verdict", {}).get("report", ""), state["technical_rd"], state["blueprint"]

    except Exception as e:
        yield f"System Error: {str(e)}", "", "", "", "", ""

def save_all_reports(idea, analysis, research, verdict, tech, blueprint):
    """Saves outputs to the project's folder."""
    if not analysis:
        return "No analysis found. Run the Forge pipeline first."
    
    # Generate clean slug from first part of idea (ignore PDF blob if present)
    base_idea = idea.split("--- DOCUMENT CONTEXT ---")[0].strip()
    clean_text = re.sub(r'[^a-zA-Z0-9\s]', '', base_idea).lower()
    words = [w for w in clean_text.split() if w not in {"i", "want", "to", "build"}]
    project_slug = "-".join(words[:3]) if words else "project-report"
    
    output_dir = Path(f"outputs/{project_slug}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    files = {
        "1_idea_analysis.md": analysis,
        "2_market_research.md": research,
        "3_verdict.md": verdict,
        "4_technical_rd.md": tech,
        "5_dev_blueprint.md": blueprint
    }
    
    for filename, content in files.items():
        with open(output_dir / filename, "w", encoding="utf-8") as f:
            f.write(content)
            
    return f"Success! Reports saved to outputs/{project_slug}/"

# UI DESIGN
with gr.Blocks(theme=gr.themes.Soft(), title="FORGE | AI R&D Co-Pilot") as demo:
    with gr.Column(elem_id="main-container"):
        gr.Markdown("# ⚒️ FORGE: AI R&D Co-Pilot")
        gr.Markdown("Transform raw ideas into validated technical blueprints using a multi-agent R&D pipeline.")
        
        with gr.Row():
            with gr.Column(scale=2):
                idea_input = gr.Textbox(
                    label="Initial Startup Idea",
                    placeholder="Describe your vision (e.g., 'A local marketplace for campus students...')",
                    lines=4
                )
                file_upload = gr.File(label="Optional: Upload PDF Context", file_types=[".pdf"])
                get_qs_btn = gr.Button("Analyze Initial Idea & Get Questions", variant="secondary")
            
            with gr.Column(scale=1):
                status_output = gr.Textbox(label="Engine Status", interactive=False)
                save_btn = gr.Button("📦 Save All Reports")
                save_status = gr.Markdown("")

        # PHASE 0: INTAKE PANEL (Initially Hidden)
        with gr.Group(visible=False) as intake_panel:
            gr.Markdown("---")
            gr.Markdown("### 🔍 Step 2: Sharpen the Vision & Choose Your Tools")
            gr.Markdown("Answer these 3 clarifying questions and select your development approach.")
            
            with gr.Row():
                with gr.Column():
                    q1_label = gr.Textbox(label="Question 1", interactive=False)
                    a1_input = gr.Textbox(label="Your Answer", placeholder="Identify the specific persona...", lines=2)
                
                with gr.Column():
                    q2_label = gr.Textbox(label="Question 2", interactive=False)
                    a2_input = gr.Textbox(label="Your Answer", placeholder="How do they solve this today?", lines=2)
                
                with gr.Column():
                    q3_label = gr.Textbox(label="Question 3", interactive=False)
                    a3_input = gr.Textbox(label="Your Answer", placeholder="The non-negotiable core feature...", lines=2)
            
            with gr.Row():
                build_method = gr.Dropdown(
                    label='How will you build this?',
                    choices=['AI Coding Tool', 'Self (writing code manually)', 'Mixed approach'],
                    value='AI Coding Tool',
                    interactive=True
                )
                ai_tool = gr.Dropdown(
                    label='Which AI coding tool?',
                    choices=['Gemini CLI', 'Cursor', 'Windsurf / Codeium', 'GitHub Copilot', 'Other AI tool'],
                    value='Gemini CLI',
                    visible=True,
                    interactive=True
                )
                team_size = gr.Number(
                    label='Team size (including yourself)',
                    value=1, minimum=1, maximum=10, step=1
                )

            run_full_btn = gr.Button("🚀 Run Deep Analysis Pipeline", variant="primary")

        # RESULTS TABS
        with gr.Tabs():
            with gr.TabItem("1. Idea Analysis"):
                out_idea = gr.Markdown()
            with gr.TabItem("2. Market Research"):
                out_research = gr.Markdown()
            with gr.TabItem("3. Final Verdict"):
                out_verdict = gr.Markdown()
            with gr.TabItem("4. Technical R&D"):
                out_tech = gr.Markdown()
            with gr.TabItem("5. Dev Blueprint"):
                out_blueprint = gr.Markdown()

    # EVENT HANDLING
    get_qs_btn.click(
        fn=get_questions,
        inputs=[idea_input, file_upload],
        outputs=[q1_label, q2_label, q3_label, intake_panel]
    )
    
    run_full_btn.click(
        fn=run_forge_workflow,
        inputs=[
            idea_input, file_upload,
            q1_label, a1_input, 
            q2_label, a2_input, 
            q3_label, a3_input,
            build_method, ai_tool, team_size
        ],
        outputs=[status_output, out_idea, out_research, out_verdict, out_tech, out_blueprint]
    )
    
    save_btn.click(
        fn=save_all_reports,
        inputs=[idea_input, out_idea, out_research, out_verdict, out_tech, out_blueprint],
        outputs=[save_status]
    )

if __name__ == "__main__":
    os.environ["PYTHONPATH"] = "."
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
