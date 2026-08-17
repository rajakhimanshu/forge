import os
import re
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, HumanMessage
from tools.pydantic_models import RoadmapOutput, DayAction, IdeaOutput, GTMOutput, BusinessOutput
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt

load_dotenv()


def validate_dates(output: RoadmapOutput) -> RoadmapOutput:
    today = datetime.now()
    current_year = str(today.year)
    target_date = today + timedelta(days=14)
    deadline_str = target_date.strftime("%B %d")
    
    current_year_int = datetime.now().year
    past_years = [str(y) for y in range(current_year_int - 4, current_year_int + 1)]
    for yr in past_years:
        if yr in output.money_ask_message:
            output.money_ask_message = output.money_ask_message.replace(
                yr, current_year
            )
    
    if deadline_str.lower() not in output.money_ask_message.lower():
        # Only add if it doesn't look like it has a date
        if not any(month in output.money_ask_message for month in ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]):
             output.money_ask_message += f" — Deadline: {deadline_str}."
    
    return output


def run_roadmap_agent(idea_output: IdeaOutput, gtm_output: GTMOutput, business_output: BusinessOutput, project_name: str, idea_anchor: dict = None) -> RoadmapOutput:
    prompt_path = Path('prompts/roadmap_prompt.txt')
    if not prompt_path.exists():
        raise FileNotFoundError('prompts/roadmap_prompt.txt missing — run Step 16 first')
    system_prompt = prompt_path.read_text(encoding='utf-8')

    llm = get_llm(temperature=0.3)

    # Extract from GTM output
    primary_channel = 'LinkedIn + Reddit'
    cold_script = ''
    if gtm_output and hasattr(gtm_output, 'primary_channel'):
        primary_channel = gtm_output.primary_channel
        cold_script = gtm_output.cold_outreach_script
    elif isinstance(gtm_output, dict):
        primary_channel = gtm_output.get('primary_channel', 'LinkedIn + Reddit')

    # Extract from business output
    pro_price_inr = 'INR 199/month'
    upgrade_trigger = 'User hits free tier limit'
    if business_output and hasattr(business_output, 'pricing_tiers'):
        paid_tiers = [t for t in business_output.pricing_tiers if t.name.lower() != 'free']
        if paid_tiers:
            pro_price_inr = paid_tiers[0].price_inr
        upgrade_trigger = business_output.upgrade_trigger

    # Fix 4: Date Injection
    today = datetime.now()
    target_date = today + timedelta(days=14)
    today_str = today.strftime("%B %d, %Y")
    deadline_str = target_date.strftime("%B %d")
    current_year = str(today.year)

    date_constraint = f"""
TODAY IS: {today_str}
THE MONEY ASK DEADLINE MUST BE: {deadline_str} (exactly 14 days away)
NEVER use any year before {current_year}.
NEVER write a date that has already passed.
"""

    context_dict = {
        "project_name": project_name,
        "job_to_be_done": idea_output.job_to_be_done if idea_output else "",
        "target_persona": idea_output.target_persona_name if idea_output else "",
        "gtm_primary_channel": primary_channel,
        "gtm_cold_script": cold_script,
        "pro_price_inr": pro_price_inr,
        "upgrade_trigger": upgrade_trigger,
        "target_date_for_money_ask": deadline_str,
        "date_constraint": date_constraint
    }

    combined_context = f"UPSTREAM PIPELINE CONTEXT:\n{json.dumps(context_dict, indent=2)}\n\n"

    anchor_text = f'''
=== IDEA LOCK ===
You are analyzing ONLY this idea: {idea_anchor['idea_title']}
Target user: {idea_anchor['target_user']}
If your context contains references to other ideas or projects, ignore them.
Every output you produce must be specifically about: {idea_anchor['idea_title']}
=== END LOCK ===
''' if idea_anchor else ""
    system_message = SystemMessage(content=anchor_text + "\n" + system_prompt)
    human_message = HumanMessage(content=(
        combined_context
        + 'Generate a 30-day launch roadmap.\n'
        '- Every DayAction must use the ACTUAL project name — never [product name]\n'
        '- Days 1-7 must each use a DIFFERENT platform or action\n'
        '- money_ask_message must be under 100 words\n'
        f'- money_ask_message must contain: "{project_name}", the INR price, and "{deadline_str}"\n'
        '- day30_decision_tree must have exactly 3 branches: 0 paying/1-5 paying/6+ paying'
        + build_schema_prompt(RoadmapOutput)
    ))

    try:
        # Small delay before roadmap (last heavy agent) — avoids hitting rate limits
        time.sleep(1)
        result = call_with_fallback(llm, RoadmapOutput, [system_message, human_message])
    except Exception as e:
        safe_print(f"[ROADMAP AGENT] FAILED: {str(e)}")
        # Fix 7: Return empty/error instead of fake data
        return RoadmapOutput(
            failed=True,
            error=True,
            error_message=f"Agent failed: {str(e)[:200]}",
            days_1_7=[],
            user_call_script="",
            build_rule="",
            money_ask_message="",
            day30_success_definition="",
            day30_decision_tree="",
        )

    # Skip post-processing if the agent failed
    if result.failed or result.error:
        return result

    # Fix 4: Post-parse date validation
    result = validate_dates(result)

    # CRITICAL post-process: replace all placeholders with real project name
    msg = result.money_ask_message
    for placeholder in ['[product name]', '[product]', '[app name]', 'the app', '[your product]', '[Project Name]']:
        msg = msg.replace(placeholder, project_name)
        msg = msg.replace(placeholder.title(), project_name)
    result.money_ask_message = msg

    # Ensure project_name is in money_ask_message
    if project_name.lower() not in result.money_ask_message.lower():
        result.money_ask_message = f'{project_name}: ' + result.money_ask_message

    # Hard limit to 100 words
    words = result.money_ask_message.split()
    if len(words) > 95:
        result.money_ask_message = ' '.join(words[:95]) + '...'

    # Fix day actions for project name
    for action in result.days_1_7:
        if action.exact_message_template:
            for placeholder in ['[product name]', '[product]', '[app name]', '[your product]']:
                action.exact_message_template = action.exact_message_template.replace(placeholder, project_name)

    return result


def format_roadmap_for_display(r: RoadmapOutput) -> str:
    if getattr(r, 'error', False) or getattr(r, 'failed', False):
        return (
            '## ⚠️ 30-Day Launch Roadmap\n\n'
            f'> **Error:** {r.error_message}\n\n'
        )
    return '## 🗓️ 30-Day Launch Roadmap\n\n' + _format_roadmap_content(r)


def _format_roadmap_content(r: RoadmapOutput) -> str:
    md = []
    if r.days_1_7:
        md.append('### 📆 Days 1–7 (Execution)')
        for day in r.days_1_7:
            md.append(f'**Day {day.day}:** {day.action} — _{day.platform_or_method}_')
            if day.exact_message_template:
                md.append(f'  > {day.exact_message_template[:150]}')
    if r.user_call_script:
        md.extend(['', '### 📞 User Call Script', f'> {r.user_call_script}'])
    if r.build_rule:
        md.extend(['', '### 🔨 The One Build Rule', f'**{r.build_rule}**'])
    if r.money_ask_message:
        md.extend([
            '', '### 💬 The Money Ask Message',
            '---', r.money_ask_message, '---',
            f'*({len(r.money_ask_message.split())} words)*',
        ])
    if r.day30_success_definition:
        md.extend(['', '### 🎯 Day 30 Success Definition', r.day30_success_definition])
    if r.day30_decision_tree:
        md.extend(['', '### 🌳 Day 30 Decision Tree', r.day30_decision_tree])
    return '\n'.join(md)


def save_output(r: RoadmapOutput, slug: str) -> str:
    out_dir = Path(f'outputs/{slug}')
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / 'launch_roadmap.md'
    md_path.write_text(format_roadmap_for_display(r), encoding='utf-8')
    json_path = out_dir / 'launch_roadmap.json'
    json_path.write_text(r.model_dump_json(indent=2), encoding='utf-8')
    return str(md_path)


if __name__ == '__main__':
    result = run_roadmap_agent(
        idea_summary='TITConnect: Campus marketplace for TIT Bhopal students',
        gtm_output=None,
        business_output=None,
        project_name='TITConnect'
    )
    safe_print(format_roadmap_for_display(result))
    save_output(result, 'titconnect')
