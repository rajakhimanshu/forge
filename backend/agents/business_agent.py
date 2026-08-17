import os
import re
import json
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from tools.errors import PipelineError
from langchain_core.messages import SystemMessage, HumanMessage
from tools.pydantic_models import BusinessOutput, PricingTier, IdeaOutput, GTMOutput
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt
from tools.web_search import search

load_dotenv()


def check_paid_market(project_name: str) -> tuple[bool, str]:
    try:
        results = search(f'{project_name} alternative paid pricing')
        if not results:
            return False, 'No paid products found in search'
        
        evidence = []
        for line in results.split('\n'):
            if any(w in line.lower() for w in ['price', 'pricing', 'paid', '$/mo', 'inr', 'plan']):
                evidence.append(line[:100])
                
        evidence_str = ' | '.join(evidence[:3]) if evidence else 'No paid products found in search'
        return bool(evidence), evidence_str
    except Exception as e:
        raise PipelineError('BusinessAgent', f'Step failed: {str(e)}')


def validate_paid_market_verdict(biz: BusinessOutput) -> BusinessOutput:
    """Fix 3: Ensure paid_market_exists is True if evidence contains pricing signals."""
    if biz.failed or biz.error:
        return biz
    signals = ["$","₹","/month","subscription","pricing","plan","paid"]
    if not biz.paid_market_exists and any(
        s in biz.paid_market_evidence.lower() for s in signals
    ):
        biz.paid_market_exists = True
    return biz


def run_business_agent(idea_output: IdeaOutput, gtm_output: GTMOutput, project_name: str, idea_anchor: dict = None) -> BusinessOutput:
    prompt_path = Path('prompts/business_prompt.txt')
    if not prompt_path.exists():
        raise FileNotFoundError('prompts/business_prompt.txt missing — run Step 16 first')
    system_prompt = prompt_path.read_text(encoding='utf-8')


    llm = get_llm(temperature=0.3)

    paid_exists, evidence = check_paid_market(project_name)

    # Get primary channel from GTM output
    primary_channel = 'Not specified'
    if gtm_output and hasattr(gtm_output, 'primary_channel'):
        primary_channel = gtm_output.primary_channel
    elif isinstance(gtm_output, dict):
        primary_channel = gtm_output.get('primary_channel', 'Not specified')

    context_dict = {
        "project_name": project_name,
        "job_to_be_done": idea_output.job_to_be_done if idea_output else "",
        "target_persona": idea_output.target_persona_name if idea_output else "",
        "market_size_estimate": idea_output.market_size_estimate if idea_output else "",
        "paid_market_check": "YES" if paid_exists else "NO",
        "paid_market_evidence": evidence,
        "gtm_primary_channel": primary_channel,
    }

    combined_context = f"UPSTREAM PIPELINE CONTEXT:\n{json.dumps(context_dict, indent=2)}\n\n"

    anchor_text = f'''
=== IDEA LOCK ===
You are creating a business model for ONLY this idea: {idea_anchor['idea_title']}
Target user: {idea_anchor['target_user']}
Unique selling proposition: {idea_anchor.get('usp_sentence', '')}
If your context contains references to other ideas or projects, ignore them.
Every pricing tier and feature must be specifically tailored to: {idea_anchor['idea_title']}
=== END LOCK ===
''' if idea_anchor else ""

    system_message = SystemMessage(content=anchor_text + "\n" + system_prompt)
    human_message = HumanMessage(content=(
        combined_context
        + 'Generate a business and pricing model for this startup.\n'
        '- MANDATORY: Always generate exactly 3 pricing tiers, regardless of whether paid_market_check is YES or NO.\n'
        '  Even if there is zero market evidence, generate tiers based on the idea type and global SaaS benchmarks.\n'
        '  Default structure: Free (₹0, hard limit), Basic (₹99-199/month), Pro (₹299-499/month).\n'
        '  Tailor each tier name, limit, and target_user to the specific product, not generic descriptions.\n'
        '- Pro tier price must be UNDER INR 500/month for consumer products\n'
        '- upgrade_trigger must describe ONE SPECIFIC feature wall (e.g. "User tries to upload their 4th video")\n'
        '- NEVER write vague triggers like "when they see value"\n'
        '- pricing_tiers must have exactly 2 or 3 tiers\n'
        '- paid_market_evidence must cite actual companies from the search\n'
        '- revenue_milestone_week4 format: "₹X MRR from N users at Y price" — must be a revenue number, not an action.'
        + build_schema_prompt(BusinessOutput)
    ))

    try:
        result = call_with_fallback(llm, BusinessOutput, [system_message, human_message])
    except Exception as e:
        safe_print(f"[BUSINESS AGENT] call_with_fallback failed: {str(e)}")
        return BusinessOutput(
            failed=True,
            error=True,
            error_message=str(e),
        )

    # Skip post-processing if the agent failed
    if result.failed or result.error:
        return result

    # Fix 3: Validate paid market verdict
    result = validate_paid_market_verdict(result)

    # Post-process: check if pricing is too low
    try:
        if result.pricing_tiers:
            paid_tiers = [t for t in result.pricing_tiers if t.name.lower() != 'free']
            if paid_tiers:
                price_str = paid_tiers[0].price_inr
                price_match = re.search(r'\d+', price_str)
                if price_match:
                    pro_price = int(price_match.group())
                    if pro_price > 0 and (10000 / pro_price) > 100:
                        result.pricing_too_low_warning = (
                            f'At INR {pro_price}/mo, you need {int(10000/pro_price)}+ users for INR 10k MRR. '
                            'Consider raising price or adding annual plan.'
                        )
    except Exception as e:
        raise PipelineError('BusinessAgent', f'Step failed: {str(e)}')

    return result


def format_business_for_display(biz: BusinessOutput) -> str:
    paid_label = '✅ YES — People pay for this' if biz.paid_market_exists else '❌ NO — No evidence of paid market'
    md = [
        '## 💰 Business Model',
        '',
        f'### Will Anyone Pay? {paid_label}',
        f'> {biz.paid_market_evidence}',
        '',
        '### 💳 Pricing Tiers',
        '| Tier | Price | Hard Limit | Target User |',
        '|------|-------|------------|-------------|',
    ]
    for t in biz.pricing_tiers:
        md.append(f'| {t.name} | {t.price_inr} | {t.hard_limit} | {t.target_user} |')
    md.extend([
        '',
        '### 🔒 Upgrade Trigger (the exact moment)',
        f'> **{biz.upgrade_trigger}**',
        '',
        '### 📈 Revenue Milestones',
        f'- **Week 4:** {biz.revenue_milestone_week4}',
        f'- **Month 2:** {biz.revenue_milestone_month2}',
        f'- **Month 6:** {biz.revenue_milestone_month6}',
    ])
    if biz.pricing_too_low_warning:
        md.extend(['', f'> ⚠️ **Pricing Warning:** {biz.pricing_too_low_warning}'])
    return '\n'.join(md)


def save_output(biz: BusinessOutput, slug: str) -> str:
    out_dir = Path(f'outputs/{slug}')
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / 'business_model.md'
    md_path.write_text(format_business_for_display(biz), encoding='utf-8')
    json_path = out_dir / 'business_model.json'
    json_path.write_text(biz.model_dump_json(indent=2), encoding='utf-8')
    return str(md_path)


if __name__ == '__main__':
    result = run_business_agent(
        idea_summary='Capso: AI video captioning using Whisper AI on a VPS for Indian content creators.',
        gtm_output=None,
        project_name='Capso'
    )
    safe_print(format_business_for_display(result))
    safe_print(f'\nPro tier under INR 500: {result.pricing_tiers[1].price_inr if len(result.pricing_tiers) > 1 else "N/A"}')
    safe_print(f'Upgrade trigger: {result.upgrade_trigger}')
    save_output(result, 'capso')
