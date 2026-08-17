import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from tools.pydantic_models import IdeaOutput
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt

load_dotenv()


def run_idea_agent(user_idea: str, pdf_context: str = '') -> IdeaOutput:
    prompt_path = Path('prompts/idea_prompt.txt')
    system_prompt = prompt_path.read_text(encoding='utf-8') if prompt_path.exists() else (
        'You are a world-class startup idea analyst. '
        'Analyze ideas with a ruthless focus on real user pain, market size, and execution feasibility.'
    )

    # We inject the schema directly into the human message so it knows what JSON to produce.
    system_prompt += (
        '\n\nCRITICAL: target_persona_name MUST be a realistic, culturally appropriate name based on the context.'
    )

    llm = get_llm(temperature=0.4)

    combined_input = f"IDEA: {user_idea}" if user_idea else "IDEA: [See document context below]"
    if pdf_context:
        combined_input += f'\n\n--- DOCUMENT CONTEXT ---\n{pdf_context[:5000]}\n----------------------\n'

    system_message = SystemMessage(content=system_prompt)
    human_message = HumanMessage(
        content=(
            f'Analyze this startup idea and strictly follow the structured schema:\n{combined_input}'
            + build_schema_prompt(IdeaOutput)
        )
    )

    try:
        result = call_with_fallback(llm, IdeaOutput, [system_message, human_message])

        # ── Nuclear graveyard filter ──────────────────────────────────────────
        # Strip any entry whose name does not appear in the input context.
        # Since the Idea Agent has no web search, it cannot legitimately find
        # new graveyard examples. If it's not in the context, it's hallucinated.
        if hasattr(result, 'graveyard') and result.graveyard:
            context_text = (user_idea + " " + pdf_context).lower()
            filtered = []
            for entry in result.graveyard:
                name_lower = (entry.product_name or '').lower()
                if len(name_lower) > 2 and name_lower not in context_text:
                    safe_print(f"[IDEA GRAVEYARD FILTER] Removed hallucinated entry: '{entry.product_name}'")
                else:
                    filtered.append(entry)
            result.graveyard = filtered
        # ─────────────────────────────────────────────────────────────────────

        return result
    except Exception as e:
        safe_print(f"[IDEA AGENT] call_with_fallback failed: {str(e)}")
        return IdeaOutput(
            failed=True,
            error=True,
            error_message=str(e),
        )


def get_project_slug(idea: IdeaOutput) -> str:
    return idea.project_name.lower().replace(' ', '-').replace('/', '-').replace('\\', '-')


def format_idea_for_display(idea: IdeaOutput) -> str:
    score = idea.pain_score
    filled = '█' * score
    empty = '░' * (10 - score)
    bar = f'{filled}{empty}  {score}/10'
    universal = '🌍 Yes — universal problem' if idea.is_universal_problem else '📍 No — niche/regional opportunity'
    md = [
        f'## 💡 {idea.project_name}',
        '',
        '---',
        '### 🎯 Job To Be Done',
        f'> {idea.job_to_be_done}',
        '',
        '### 😤 Primary Friction',
        f'> {idea.primary_friction}',
        '',
        '---',
        f'### 👤 Target Persona — **{idea.target_persona_name}**',
        idea.target_persona_description,
        '',
        '---',
        f'### 🔥 Pain Score',
        f'`{bar}`',
        '',
        idea.pain_reasoning,
        '',
        '---',
        '### 📊 Market Size Estimate',
        f'> {idea.market_size_estimate}',
        '',
        '### 🤖 AI Native Potential',
        idea.ai_native_potential,
        '',
        '---',
        f'### 🌐 Problem Scope: {universal}',
    ]

    # ── Layer 1 upgrade fields ────────────────────────────────────────────
    if idea.regional_specific_insight:
        md.extend(['', '---', '### 📍 Regional Insight', f'> {idea.regional_specific_insight}'])

    if idea.technical_feasibility:
        md.extend(['', '---', '### 🛠️ Technical Feasibility', idea.technical_feasibility])

    if idea.first_week_validation:
        md.extend(['', '---', '### ✅ First-Week Validation',
                   f'**Before writing any code, do this:**',
                   f'> {idea.first_week_validation}'])

    if idea.graveyard:
        md.extend(['', '---', '### ⚰️ Graveyard — Products That Failed Here'])
        for g in idea.graveyard:
            md.extend([
                f'',
                f'**{g.product_name}**',
                f'- Built: {g.what_they_built}',
                f'- Died: {g.why_they_died}',
                f'- Lesson: *{g.lesson}*',
            ])

    return '\n'.join(md)



def save_output(idea: IdeaOutput, slug: str) -> str:
    out_dir = Path(f'outputs/{slug}')
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / 'idea_analysis.md'
    md_path.write_text(format_idea_for_display(idea), encoding='utf-8')
    json_path = out_dir / 'idea_analysis.json'
    json_path.write_text(idea.model_dump_json(indent=2), encoding='utf-8')
    return str(md_path)


if __name__ == '__main__':
    test_idea = 'An app for TIT Bhopal college students to buy and sell textbooks and form project teams'
    result = run_idea_agent(test_idea)
    safe_print(format_idea_for_display(result))
    slug = get_project_slug(result)
    save_output(result, slug)
    safe_print(f'\nPersona name: {result.target_persona_name}')
    safe_print('idea_analysis.json created.')
