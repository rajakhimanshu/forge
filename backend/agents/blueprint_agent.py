import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from tools.pydantic_models import BlueprintOutput, TaskItem, IdeaOutput, MarketOutput, VerdictOutput, TechOutput
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt

load_dotenv()


def run_blueprint_agent(idea_output: IdeaOutput, market_output: MarketOutput,
                        verdict_output: VerdictOutput, tech_output: TechOutput,
                        idea_anchor: dict = None) -> BlueprintOutput:
    prompt_path = Path('prompts/blueprint_prompt.txt')
    system_prompt = prompt_path.read_text(encoding='utf-8') if prompt_path.exists() else (
        'You are a senior software architect and startup CTO. '
        'Create precise, actionable development blueprints.'
    )

    system_prompt += (
        '\n\nCRITICAL RULES:\n'
        '- mvp_definition MUST complete the sentence: "The MVP is working when..."\n'
        '- Every TaskItem.gemini_cli_prompt must be a complete standalone prompt '
        'that someone can paste into Gemini CLI with no additional context.\n'
        '- tier field: MVP=build now, Phase2=after 10 paying users, Never=skip forever\n'
        '- folder_structure must be a literal tree diagram with all file paths'
    )

    llm = get_llm(temperature=0.3)

    # Correct approach — pass specific fields, not chopped strings
    context_dict = {
        "project_name": idea_output.project_name if idea_output else "Unknown",
        "job_to_be_done": idea_output.job_to_be_done if idea_output else "",
        "pain_score": idea_output.pain_score if idea_output else 0,
        "top_competitors": [c.name for c in market_output.competitors] if market_output and hasattr(market_output, 'competitors') else [],
        "market_gap": market_output.market_gap_summary if market_output else "",
        "verdict": verdict_output.verdict if verdict_output else "BUILD",
        "tech_stack": tech_output.tech_stack if tech_output else {},
    }
    
    combined_context = f"UPSTREAM PIPELINE CONTEXT:\n{json.dumps(context_dict, indent=2)}\n\n"

    anchor_text = f'''
=== IDEA LOCK ===
You are creating a blueprint for ONLY this idea: {idea_anchor['idea_title']}
Target user: {idea_anchor['target_user']}
If your context contains references to other ideas or projects, ignore them.
Every task and feature must be specifically tailored to: {idea_anchor['idea_title']}
=== END LOCK ===
''' if idea_anchor else ""

    system_message = SystemMessage(content=anchor_text + "\n" + system_prompt)
    human_message = HumanMessage(content=(
        combined_context
        + 'Generate a detailed development blueprint for this project.\n'
        'mvp_definition must start with "The MVP is working when". '
        'mvp_tasks must have at least 5 items. '
        'gemini_cli_prompt for each task must be at least 150 characters.'
        + build_schema_prompt(BlueprintOutput)
    ))

    try:
        result = call_with_fallback(llm, BlueprintOutput, [system_message, human_message])
    except Exception as e:
        safe_print(f"[BLUEPRINT AGENT] call_with_fallback failed: {str(e)}")
        return BlueprintOutput(
            failed=True,
            error=True,
            error_message=str(e),
            mvp_definition="",
            folder_structure="",
            mvp_tasks=[],
            phase2_features=[],
            never_features=[],
        )

    # Skip post-processing if the agent failed — no real data to clean
    if result.failed or result.error:
        return result

    # Ensure mvp_definition starts correctly
    if not result.mvp_definition.lower().startswith('the mvp'):
        result.mvp_definition = 'The MVP is working when ' + result.mvp_definition

    return result


def format_blueprint_for_display(b: BlueprintOutput) -> str:
    md = [
        '## 🗺️ Development Blueprint',
        '',
        '### ✅ MVP DEFINITION',
        f'> **{b.mvp_definition}**',
        '',
        '### 📁 Folder Structure',
        '```',
        b.folder_structure,
        '```',
        '',
        '### 🔨 MVP Tasks',
    ]
    for task in b.mvp_tasks:
        md.extend([
            f'#### Task {task.task_number}: {task.title} [{task.time_estimate}]',
            f'**File:** `{task.file_path}`',
            f'**What it does:** {task.what_it_does}',
            f'**Gemini CLI Prompt:**',
            f'```',
            task.gemini_cli_prompt,
            '```',
            f'**Test:** `{task.test_command}`',
            f'**Success:** {task.success_check}',
            f'**Commit:** `{task.commit_message}`',
            '',
        ])
    md.extend(['### 🚀 Phase 2 Features (after 10 paying users)'])
    for f in b.phase2_features:
        md.append(f'- {f}')
    md.extend(['', '### 🚫 Never Build'])
    for f in b.never_features:
        md.append(f'- {f}')
    return '\n'.join(md)


def save_output(b: BlueprintOutput, slug: str) -> str:
    out_dir = Path(f'outputs/{slug}')
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / 'dev_blueprint.md'
    md_path.write_text(format_blueprint_for_display(b), encoding='utf-8')
    json_path = out_dir / 'dev_blueprint.json'
    json_path.write_text(b.model_dump_json(indent=2), encoding='utf-8')
    return str(md_path)


if __name__ == '__main__':
    test_idea = 'Campus marketplace for TIT Bhopal students to buy/sell books, find project teams'
    test_market = 'Competitors: OLX, Facebook Marketplace. Communities: r/indianstartups'
    test_tech = 'Tech stack: Next.js, Supabase, Razorpay, Cloudinary, Vercel'
    result = run_blueprint_agent(test_idea, test_market, {'verdict': 'BUILD'}, test_tech)
    safe_print(format_blueprint_for_display(result))
    safe_print(f'\nmvp_definition starts with "The MVP": {result.mvp_definition.startswith("The MVP")}')
    safe_print(f'mvp_tasks count: {len(result.mvp_tasks)}')
    save_output(result, 'test-blueprint')
