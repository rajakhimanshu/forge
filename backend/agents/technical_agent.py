import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from tools.pydantic_models import TechOutput, FeatureSpec, IdeaOutput, VerdictOutput
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt
from tools.rag_retriever import retrieve

load_dotenv()


def run_technical_agent(idea_output: IdeaOutput, verdict_output: VerdictOutput, pdf_context: str = '') -> TechOutput:
    prompt_path = Path('prompts/technical_prompt.txt')
    system_prompt = prompt_path.read_text(encoding='utf-8') if prompt_path.exists() else (
        'You are a world-class Senior Technical Architect specializing in rapid MVP development. '
        'Provide a precise, hyper-optimized tech stack tailored to the user\'s specific idea and context. '
        'Recommend highly scalable, modern, and free-tier optimized services. No bloatware.'
    )

    llm = get_llm(temperature=0.3)

    # Search knowledge base for relevant tech stack advice
    rag_context = ""
    try:
        query_text = idea_output.job_to_be_done if idea_output else "generic MVP"
        rag_context = retrieve(f"Best tech stack payments auth hosting for {query_text}")
    except Exception as e:
        safe_print(f"[RAG] Search failed: {e}")

    # Fix 2c: Add PDF override block
    pdf_block = ""
    if pdf_context.strip():
        pdf_block = f"""
 
PDF CONTEXT — PROVIDED BY THE FOUNDER:
{pdf_context}
 
CRITICAL RULES FOR PDF CONTEXT:
- If the PDF names a specific technology (e.g. Whisper AI, Supabase, a specific VPS provider), you MUST use that technology.
- If the PDF specifies a pricing model, use those exact prices.
- If the PDF names a hosting approach (e.g. cheap VPS), respect it.
- Do NOT replace PDF-specified tech with your own preference.
- If you must deviate, state the reason explicitly in your output.
"""

    # Build structured context dict
    context_dict = {
        "project_name": idea_output.project_name if idea_output else "Unknown",
        "job_to_be_done": idea_output.job_to_be_done if idea_output else "",
        "target_persona": idea_output.target_persona_name if idea_output else "",
        "verdict": verdict_output.verdict if verdict_output else "BUILD",
        "reasoning": verdict_output.reasoning if verdict_output else "",
        "rag_context": rag_context,
        "pdf_override": pdf_block,
    }

    combined_context = f"UPSTREAM PIPELINE CONTEXT:\n{json.dumps(context_dict, indent=2)}\n\n"

    system_message = SystemMessage(content=system_prompt)
    human_message = HumanMessage(content=(
        combined_context
        + 'RULES:\n'
        '- tech_stack dict MUST have exactly these keys: frontend, backend, database, auth, storage, payments\n'
        '- Recommend the best payment provider for the user\'s region (e.g. Stripe, Razorpay, Paddle)\n'
        '- Recommend the best SMS/OTP provider for the user\'s region (e.g. Twilio, MessageBird, Fast2SMS)\n'
        '- Hosting for MVP: Vercel, Render, or Railway free tiers\n'
        '- Provide hyper-realistic pricing estimates based on the user\'s likely scale'
        + build_schema_prompt(TechOutput)
    ))

    try:
        result = call_with_fallback(llm, TechOutput, [system_message, human_message])
    except Exception as e:
        safe_print(f"[TECHNICAL AGENT] call_with_fallback failed: {str(e)}")
        return TechOutput(
            failed=True,
            error=True,
            error_message=str(e),
            features=[],
            tech_stack={},
        )

    # Skip post-processing if the agent failed
    if result.failed or result.error:
        return result

    # Ensure India stack and no "None" values
    ts = result.tech_stack
    if 'payments' not in ts or not ts.get('payments') or 'stripe' in str(ts.get('payments', '')).lower() or str(ts.get('payments')).lower() == 'none':
        ts['payments'] = 'Razorpay (2% per transaction)'
    
    defaults = {
        'frontend': 'React.js (Next.js)',
        'backend': 'Node.js (Express) or Python (FastAPI)',
        'database': 'Supabase (PostgreSQL) or MongoDB Atlas',
        'auth': 'Supabase Auth or Firebase Auth',
        'storage': 'Cloudinary or Supabase Storage'
    }

    for key, default in defaults.items():
        val = ts.get(key)
        if not val or str(val).lower() == 'none' or str(val).lower() == 'to be determined':
            ts[key] = default

    return result


def format_tech_for_display(t: TechOutput) -> str:
    if getattr(t, 'error', False) or getattr(t, 'failed', False):
        return (
            '## 🏗️ Technical Architecture\n\n'
            f'> **Error:** {t.error_message}\n\n'
        )

    md = [
        f'## 🏗️ Technical Architecture: {t.architecture_type.replace("_", " ").title()}',
        '',
        '### 💰 Cost Estimates',
        f'- MVP: **{t.mvp_cost_inr_monthly}**',
        f'- Production: **{t.production_cost_inr_monthly}**',
        '',
        '### 🛠️ Tech Stack',
    ]
    for k, v in t.tech_stack.items():
        md.append(f'- **{k.capitalize()}**: {v}')
    md.extend(['', '### ⚙️ Features'])
    for f in t.features:
        free_tag = '✅ Free' if f.is_free else '💳 Paid'
        md.append(f'**{f.name}** [{free_tag}] — {f.pricing_detail}')
        md.append(f'  Recommended: {f.recommended_approach}')
        if f.alternative_approach:
            md.append(f'  Alternative: {f.alternative_approach}')
        md.append(f'  ⚠️ Limitation: {f.limitation}')
        md.append('')
    return '\n'.join(md)


def save_output(t: TechOutput, slug: str) -> str:
    out_dir = Path(f'outputs/{slug}')
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / 'technical_rd.md'
    md_path.write_text(format_tech_for_display(t), encoding='utf-8')
    json_path = out_dir / 'technical_rd.json'
    json_path.write_text(t.model_dump_json(indent=2), encoding='utf-8')
    return str(md_path)


if __name__ == '__main__':
    test_analysis = IdeaOutput(project_name='Test', job_to_be_done='Campus marketplace for TIT Bhopal students to buy/sell books, find teammates')
    result = run_technical_agent(test_analysis, VerdictOutput(verdict='BUILD'))
    safe_print(format_tech_for_display(result))
    save_output(result, 'test-tech')
