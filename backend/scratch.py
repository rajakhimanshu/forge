from tools.llm_router import safe_print
import sys
import re

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add dashboard imports
import_statement = "from tools.dashboard_store import load_dashboard, save_project, update_status, get_summary, format_dashboard_text\n"
code = code.replace("from agents.devguide_agent import run_devguide_agent, save_devguide", 
                    "from agents.devguide_agent import run_devguide_agent, save_devguide\n" + import_statement)

# 2. Add dashboard functions right before _last_forge_state
dash_funcs = """
def refresh_dashboard() -> str:
    return format_dashboard_text()

def update_project_status(project_name, new_status, notes) -> str:
    dashboard = load_dashboard()
    for p in dashboard:
        if p.get('project_name') == project_name:
            if update_status(p.get('id'), new_status, notes):
                return "Status updated."
            return "Update failed."
    if update_status(project_name, new_status, notes):
        return "Status updated."
    return "Project not found or invalid status."
"""
code = code.replace("_last_forge_state = {}", dash_funcs + "\n_last_forge_state = {}")

# 3. Add to forge_pipeline's final save
save_code = """
        _last_forge_state = state
        total = _elapsed()
        
        # Save to founder dashboard
        try:
            verdict_str = state.get("verdict", {}).get("verdict", "UNKNOWN")
            save_project(state.get("project_slug", "unknown"), state.get("user_idea", "")[:100], verdict_str)
        except Exception as e:
            log(f"Failed to save to dashboard: {e}")
            
        log(f"=== PIPELINE COMPLETE in {total} ===")
"""
code = code.replace("""        _last_forge_state = state
        total = _elapsed()
        log(f"=== PIPELINE COMPLETE in {total} ===")""", save_code)

# 4. Modify outputs of forge_pipeline to include the 6th, 7th, 8th tabs
# Find the returns! Both the intermediate yield, crash yield, empty yield and final yield.
# Empty yield
empty_yield = """            get_folder_tree_html(""), gr.update(visible=False),
        )"""
empty_yield_new = """            get_folder_tree_html(""), "", "", "", gr.update(visible=False),
        )"""
code = code.replace(empty_yield, empty_yield_new)

# Intermediate yield
inter_yield = """                    get_folder_tree_html(state.get("blueprint", "")),
                    gr.update(visible=False),
                )"""
inter_yield_new = """                    get_folder_tree_html(state.get("blueprint", "")),
                    state.get("gtm_plan", "No GTM plan generated"),
                    state.get("business_model", "No business model generated"),
                    state.get("launch_roadmap", "No launch roadmap generated"),
                    gr.update(visible=False),
                )"""
code = code.replace(inter_yield, inter_yield_new)

# Final yield
final_yield = """            get_folder_tree_html(state.get("blueprint", "")),
            gr.update(visible=True),
        )"""
final_yield_new = """            get_folder_tree_html(state.get("blueprint", "")),
            state.get("gtm_plan", "No GTM plan generated"),
            state.get("business_model", "No business model generated"),
            state.get("launch_roadmap", "No launch roadmap generated"),
            gr.update(visible=True),
        )"""
code = code.replace(final_yield, final_yield_new)

# 5. Add tabs in the UI
# Find `with gr.TabItem("Dev Blueprint"):` -> insert GTM, Business Model, Roadmap
tabs_code = """                with gr.TabItem("Dev Blueprint"):
                    out_blueprint = gr.HTML(get_folder_tree_html(""))
                with gr.TabItem("Go-To-Market"):
                    out_gtm = gr.Markdown()
                with gr.TabItem("Business Model"):
                    out_business = gr.Markdown()
                with gr.TabItem("Launch Roadmap"):
                    out_roadmap = gr.Markdown()"""
code = code.replace("""                with gr.TabItem("Dev Blueprint"):
                    out_blueprint = gr.HTML(get_folder_tree_html(""))""", tabs_code)

# 6. Add outputs to the click handler
outputs_old = """            out_tech, out_blueprint, build_section,
        ],"""
outputs_new = """            out_tech, out_blueprint, out_gtm, out_business, out_roadmap, build_section,
        ],"""
code = code.replace(outputs_old, outputs_new)

# 7. Add Founder Dashboard tab wrap
# Find `with gr.Row(elem_id="forge-layout"):`
# Replace with `with gr.Tabs() as top_tabs: \n with gr.Tab("Founder Dashboard"):... \n with gr.Tab("New Project"): \n with gr.Row(elem_id="forge-layout"):
dash_ui = """
    with gr.Tabs() as top_tabs:
        with gr.Tab("Founder Dashboard"):
            dash_md = gr.Markdown(refresh_dashboard)
            with gr.Row():
                dash_proj = gr.Dropdown(label="Project Name (from ideas)", choices=[], allow_custom_value=True)
                dash_status = gr.Dropdown(choices=["Not Started", "In Progress", "Achieved", "Abandoned"], label="Status")
            dash_notes = gr.Textbox(lines=2, placeholder="What happened?")
            dash_btn = gr.Button("Update Status", variant="secondary")
            dash_conf = gr.Markdown("")
            
            dash_btn.click(fn=update_project_status, inputs=[dash_proj, dash_status, dash_notes], outputs=[dash_conf])
        
        with gr.Tab("New Project"):
            with gr.Row(elem_id="forge-layout"):
"""
code = code.replace('    with gr.Row(elem_id="forge-layout"):', dash_ui)
# Also need to indent everything that was inside `with gr.Row(elem_id="forge-layout"):`
# But python gradio with gr.Row handles things gracefully since the context manager determines nesting. Indentation is mostly for readability but in Python it MUST be correct.
# Wait, replacing `with gr.Row():` with `with gr.Tab(): \n with gr.Row():` means I need to indent all lines from `with gr.Row...` to the end of that block by 8 spaces!
# Let's write a better patch for indentation!
lines = code.split("\\n")
in_block = False
for i, line in enumerate(lines):
    if 'with gr.Row(elem_id="forge-layout"):' in line:
        in_block = True
    elif in_block and line.startswith('    # Hidden question-text stores'):
        in_block = False
    
    if in_block and i > 0 and 'with gr.Row(elem_id="forge-layout"):' not in lines[i-1]:
        # we can't just blindly, let's just indent everything starting with 8 spaces to 12 or 16 if it's inside `with gr.Row`.
        pass

"""
Instead of parsing indentation which is brittle, I'll use multi_replace_file_content!
"""
safe_print("Do not use this script, doing it directly")