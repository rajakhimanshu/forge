import os
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.output_parsers import PydanticOutputParser
from tools.errors import PipelineError
from langchain_core.messages import SystemMessage, HumanMessage
from tools.pydantic_models import GTMOutput, CommunityPost, IdeaOutput, MarketOutput
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt
from tools.web_search import search

load_dotenv()


# Fix 5: Step 1
def extract_persona_description(idea_output: IdeaOutput) -> str:
    if not idea_output:
        return "target audience"
    return f"{idea_output.target_persona_name}: {idea_output.target_persona_description}"


def run_gtm_agent(idea_output: IdeaOutput, market_output: MarketOutput, project_name: str, idea_anchor: dict = None) -> GTMOutput:
    prompt_path = Path('prompts/gtm_prompt.txt')
    if not prompt_path.exists():
        raise FileNotFoundError('prompts/gtm_prompt.txt missing — run Step 16 first')
    system_prompt = prompt_path.read_text(encoding='utf-8')

    # Fix 5: Step 3 - Add GTM_COMMUNITY_RULES
    GTM_COMMUNITY_RULES = """
 
Find communities WHERE THE PERSONA LIVES, not where founders discuss startups.
 
BANNED communities for all end-user products:
  r/startups             — these are FOUNDERS, not users
  LinkedIn startup founders — FOUNDERS, not users
  r/entrepreneur         — FOUNDERS, not users
 
CORRECT mapping rules:
  YouTube/video creators → r/youtubers, r/NewTubers, r/ContentCreators, r/videography
  Forex/stock traders    → r/Forex, r/Daytrading, Telegram trading groups
  College students       → college WhatsApp groups, university subreddits, Discord study groups
  Developers             → r/webdev, r/learnprogramming, dev.to, HackerNews
  Small business owners  → r/smallbusiness, local Facebook business groups
 
Always match the community to the PERSONA, not to startup groups generally.
"""
    system_prompt += f"\n\nCRITICAL COMMUNITY RULES:\n{GTM_COMMUNITY_RULES}"

    llm = get_llm(temperature=0.3)

    # Fix 5: Step 2 - Persona-based search
    persona = extract_persona_description(idea_output)
    community_text = ""
    try:
        r1 = search(f"where do {persona} gather online reddit discord telegram subreddit")
        community_text += f'Persona Communities Search:\n{r1[:1200]}\n\n'
    except Exception as e:
        safe_print(f"[GTM AGENT] Persona community search failed (continuing): {e}")

    try:
        r2 = search(f'{project_name} alternative competitors users reddit')
        community_text += f'Competitor Users Search:\n{r2[:800]}\n\n'
    except Exception as e:
        safe_print(f"[GTM AGENT] Competitor search failed (continuing): {e}")

    context_dict = {
        "project_name": project_name,
        "job_to_be_done": idea_output.job_to_be_done if idea_output else "",
        "target_persona": idea_output.target_persona_name if idea_output else "",
        "persona_description": idea_output.target_persona_description if idea_output else "",
        "market_gap": market_output.market_gap_summary if market_output else "",
        "top_competitors": [c.name for c in market_output.competitors] if market_output and hasattr(market_output, 'competitors') else [],
        "first_50_users_communities": [c.name_or_url for c in market_output.first_50_users_communities] if market_output and hasattr(market_output, 'first_50_users_communities') else [],
        "community_search_signals": community_text,
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
    # Build a persona-first header that appears BEFORE anything else the LLM reads
    if idea_anchor:
        target_user_str = idea_anchor.get('target_user', idea_output.target_persona_name if idea_output else 'target user')
        platform_str = idea_anchor.get('platform_focus', '')
    else:
        target_user_str = idea_output.target_persona_name if idea_output else 'target user'
        platform_str = ''

    platform_line = f"\nTARGET PLATFORM: {platform_str}" if platform_str else ""
    persona_header = f"""=== WHO YOU ARE REACHING ===
TARGET USER: {target_user_str}{platform_line}

Find communities where THIS SPECIFIC PERSON spends time.
NOT startup communities. NOT SaaS communities. NOT r/microsaas. NOT r/entrepreneur.
The PERSON described above — where do THEY go online?

Community mapping by persona type:
  Reel / video creators     → r/NewTubers, r/ContentCreators, r/videography, Instagram creator hashtags, YouTube creator Discord
  Productivity / students   → r/productivity, r/getdisciplined, university Discord groups
  Forex / stock traders     → r/Forex, r/Daytrading, Telegram trading groups
  Developers                → r/webdev, r/learnprogramming, dev.to, HackerNews
  Small business owners     → r/smallbusiness, local Facebook business groups
  Fitness / health          → r/fitness, MyFitnessPal community, Strava groups

Match the community to the PERSON, not to the product category.
=== END WHO ===
"""

    system_message = SystemMessage(content=persona_header + "\n" + anchor_text + "\n" + system_prompt)

    # Compute a real 30-day deadline so the LLM never has to guess the date
    deadline_str = (datetime.now() + timedelta(days=30)).strftime("%B %d, %Y")

    human_message = HumanMessage(content=(
        combined_context
        + f'TODAY\'S DATE: {datetime.now().strftime("%B %d, %Y")}\n'
        + f'WEEK 4 MONEY ASK DEADLINE: {deadline_str} (use this exact date — do NOT invent a date)\n\n'
        + 'Generate a Go-To-Market plan for this project.\n'
        '- cold_outreach_script must be UNDER 50 words and start with "I noticed you"\n'
        '- Every community must include a specific URL or search instruction\n'
        '- Communities MUST match the TARGET USER above, not startup founders\n'
        '- NEVER say "social media" or "content marketing"'
        + build_schema_prompt(GTMOutput)
    ))

    try:
        result = call_with_fallback(llm, GTMOutput, [system_message, human_message])
    except Exception as e:
        safe_print(f"[GTM AGENT] call_with_fallback failed: {str(e)}")
        return GTMOutput(
            failed=True,
            error=True,
            error_message=str(e),
            first_50_users_plan=[],
            week1_actions=[],
            week2_actions=[],
            week3_actions=[],
            week4_money_ask=[],
        )

    # Skip post-processing if the agent failed — no real data to clean
    if result.failed or result.error:
        return result

    # ── Post-process: fill any empty post_content fields ─────────────────
    idea_title_str = idea_anchor.get('idea_title', 'this tool') if idea_anchor else 'this tool'
    usp_str = idea_anchor.get('usp_sentence', '') if idea_anchor else ''
    usp_short = usp_str.split('.')[0] if usp_str else f'helps {target_user_str} save time'

    for post in result.first_50_users_plan:
        if not post.post_content or len((post.post_content or '').strip()) < 20:
            community_label = f"{post.platform} — {post.community_name}"
            post.post_content = (
                f"I just built a free tool: {idea_title_str} — {usp_short}. "
                f"No signup. Genuinely want brutal feedback — "
                f"what would make you actually use this? Link in comments."
            )
            safe_print(f"[GTM POST FILL] Filled empty post_content for {community_label}")
    # ─────────────────────────────────────────────────────────────────────

    # Hard truncate cold script to 50 words
    words = result.cold_outreach_script.split()
    if len(words) > 50:
        result.cold_outreach_script = ' '.join(words[:45])

    # Ensure starts with "I noticed you"
    if not result.cold_outreach_script.lower().startswith('i noticed you'):
        result.cold_outreach_script = 'I noticed you ' + result.cold_outreach_script

    return result


def format_gtm_for_display(gtm: GTMOutput) -> str:
    if getattr(gtm, 'error', False) or getattr(gtm, 'failed', False):
        return (
            '## 🚀 Go-To-Market Plan\n\n'
            f'> **Error:** {gtm.error_message}\n\n'
        )

    word_count = len(gtm.cold_outreach_script.split())
    wc_status = '✅' if word_count <= 50 else '⚠️ OVER LIMIT'
    md = [
        '## 🚀 Go-To-Market Plan',
        '',
        '### 👥 Where Your First 50 Users Are',
        '',
        '| Platform | Community | Best Time |',
        '|----------|-----------|-----------|',
    ]
    for post in gtm.first_50_users_plan:
        md.append(f'| **{post.platform}** | {post.community_name} | {post.best_day_time} |')
    md.append('')
    for post in gtm.first_50_users_plan:
        md.extend([
            f'**{post.platform} — {post.community_name}**',
            f'> {post.post_content or "*(post content not generated)*"}',
            '',
        ])
    md.extend([
        '---',
        '### 📨 Cold Outreach Script',
        f'> **{gtm.cold_outreach_script}**',
        '',
        f'_{word_count} words {wc_status} (limit: 50)_',
        '',
        '---',
        '### 📅 Week-by-Week Launch Sequence',
        '',
        '**⚡ Week 1 — Find Users:**',
    ])
    for i, a in enumerate(gtm.week1_actions, 1):
        md.append(f'{i}. {a}')
    md.extend(['', '**🔁 Week 2 — Get Feedback:**'])
    for i, a in enumerate(gtm.week2_actions, 1):
        md.append(f'{i}. {a}')
    md.extend(['', '**📣 Week 3 — Build Credibility:**'])
    for i, a in enumerate(gtm.week3_actions, 1):
        md.append(f'{i}. {a}')
    md.extend(['', '**💰 Week 4 — The Money Ask:**'])
    for i, a in enumerate(gtm.week4_money_ask, 1):
        md.append(f'{i}. {a}')
    md.extend([
        '',
        '---',
        f'### 📡 Primary Channel',
        f'**{gtm.primary_channel}**',
        '',
        f'### 🦠 Viral Mechanic',
        gtm.viral_mechanic,
    ])
    return '\n'.join(md)


def save_output(gtm: GTMOutput, slug: str) -> str:
    out_dir = Path(f'outputs/{slug}')
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / 'go_to_market.md'
    md_path.write_text(format_gtm_for_display(gtm), encoding='utf-8')
    json_path = out_dir / 'go_to_market.json'
    json_path.write_text(gtm.model_dump_json(indent=2), encoding='utf-8')
    return str(md_path)


if __name__ == '__main__':
    result = run_gtm_agent(
        idea_output=IdeaOutput(target_persona_name='Forex Traders', target_persona_description='Active day traders in India using MT4/MT5'),
        market_output=MarketOutput(market_gap_summary='No easy way to sync economic calendar to Google Calendar'),
        project_name='ForexSync'
    )
    safe_print(format_gtm_for_display(result))
    save_output(result, 'forexsync')
