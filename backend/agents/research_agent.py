import os
import json
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from tools.errors import PipelineError
from tools.pydantic_models import MarketOutput, CompetitorInfo, CommunityInfo, IdeaOutput, CompetitorNamesOutput
from tools.web_search import search
from tools.competitor_scraper import scrape_competitor, format_scrape_result
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt

load_dotenv()


def extract_competitor_names(idea_title: str, target_user: str, llm) -> tuple[list[str], str]:
    """Find competitor product names from the web based on the idea."""
    search_text = ""
    for query in [
        f"{idea_title} app for {target_user}",
        f"{idea_title} tool for {target_user} ProductHunt",
        f"AI {idea_title} {target_user} 2025",
        f"{idea_title} startup site:producthunt.com OR site:techcrunch.com"
    ]:
        try:
            res = search(query)
            if res: search_text += f"Query: {query}\nResults: {res[:800]}\n\n"
        except Exception as e:
            safe_print(f"[RESEARCH AGENT] Competitor search failed for query '{query}': {e}")

    try:
        messages = [
            SystemMessage(content=f"You are an expert at extracting competitor names from search results.\n"
                                  f"ONLY include competitors that serve {target_user.upper()}.\n"
                                  f"Exclude accessibility tools, enterprise software, or tools for different use cases.\n"
                                  f"If you cannot confirm a tool serves {target_user} from the search results, exclude it."),
            HumanMessage(content=f"List the names of software products or companies in this text "
                                 f"that could be competitors. Return ONLY names, max 6. Text: {search_text[:4000]}\n\n"
                                 f"{build_schema_prompt(CompetitorNamesOutput)}")
        ]
        response = call_with_fallback(llm, CompetitorNamesOutput, messages)
        return response.names[:6], search_text
    except Exception as e:
        safe_print(f"[RESEARCH AGENT] extract_competitor_names LLM failed: {e}")
        return [], search_text


def run_research_agent(idea_output: IdeaOutput, original_idea: str, idea_anchor: dict = None) -> MarketOutput:
    # Try the upgraded research_prompt.txt first, fall back to market_prompt.txt
    prompt_path = Path('prompts/research_prompt.txt')
    if not prompt_path.exists():
        prompt_path = Path('prompts/market_prompt.txt')
    system_prompt = prompt_path.read_text(encoding='utf-8') if prompt_path.exists() else (
        'You are an elite startup market researcher. '
        'Your goal is to ruthlessly analyze user pain, current solutions, and market gaps globally or tailored to the specific user context provided.'
    )
    llm = get_llm(temperature=0.3)
    topic = idea_output.job_to_be_done if idea_output else original_idea[:50]
    idea_text = idea_output.job_to_be_done + " " + original_idea if idea_output else original_idea

    idea_title = idea_output.project_name if idea_output else original_idea[:50]
    target_user = idea_output.target_persona_description if idea_output and idea_output.target_persona_description else (idea_output.target_persona_name if idea_output else "Unknown")

    ANCHOR = f'''
    YOU ARE RESEARCHING THIS SPECIFIC IDEA: {idea_title}
    TARGET USER: {target_user}
    DO NOT reference any other idea or project in your analysis.
    Every competitor, complaint, and community must relate to: {idea_title}
    '''

    research_text = ""
    
    # Fix 1: Targeted Competitor Search
    competitor_names, initial_search_text = extract_competitor_names(idea_title, target_user, llm)
    research_text += initial_search_text

    if competitor_names:
        research_text += "\n--- TARGETED COMPETITOR SEARCH ---\n"
        for name in competitor_names:
            try:
                r1 = search(f'{name} reddit complaints {datetime.now().year}')
                r2 = search(f'{name} negative reviews why users leave')
                r3 = search(f'{name} alternatives site:reddit.com OR site:twitter.com')
                research_text += f"\nCOMPETITOR: {name}\n"
                research_text += f"Complaints: {r1[:300]}\n"
                research_text += f"Reviews: {r2[:300]}\n"
                research_text += f"Alternatives: {r3[:300]}\n"
                
                # 2. Deep scrape (NEW)
                scrape_result = scrape_competitor(name)
                research_text += format_scrape_result(scrape_result)
            except Exception as e:
                safe_print(f"[RESEARCH AGENT] Search failed for {name}: {e}")
                continue



    class _DummyState:
        pass
    state = _DummyState()

    # PASS 3 - Graveyard search
    graveyard_results = []
    for query in [
        f'{idea_title} startup shut down failed site:techcrunch.com',
        f'{idea_title} app discontinued reddit'
    ]:
        try:
            result = search(query)
            if result: graveyard_results.append(result)
        except Exception as e:
            safe_print(f"[RESEARCH AGENT] Graveyard search failed: {e}")
            continue
    state.graveyard_raw = graveyard_results
    if not graveyard_results:
        state.graveyard_note = 'No public graveyard data found.'

    # PASS 4 - Community search (persona-targeted — find WHERE the user lives, not where founders discuss the idea)
    community_results = []
    for query in [
        f'subreddit {target_user} community global',
        f'{target_user} discord telegram group members',
        f'"{target_user}" "i hate" site:reddit.com',
    ]:
        try:
            result = search(query)
            if result: community_results.append(result)
        except Exception as e:
            safe_print(f"[RESEARCH AGENT] Community search failed: {e}")
            continue
    state.communities_raw = community_results

    # Truncate raw dumps so the combined prompt stays under ~8k tokens
    MAX_CHUNK = 600
    graveyard_trimmed = [g[:MAX_CHUNK] for g in getattr(state, 'graveyard_raw', [])]
    community_trimmed = [c[:MAX_CHUNK] for c in getattr(state, 'communities_raw', [])]
    research_text_trimmed = research_text[:4000]

    context_dict = {
        "user_original_idea": original_idea,
        "project_name": idea_output.project_name if idea_output else "Unknown",
        "job_to_be_done": idea_output.job_to_be_done if idea_output else "",
        "target_persona": idea_output.target_persona_name if idea_output else "",
        "primary_friction": idea_output.primary_friction if idea_output else "",
        "research_signals": research_text_trimmed,
        "graveyard_raw": graveyard_trimmed,
        "graveyard_note": getattr(state, 'graveyard_note', ''),
        "communities_raw": community_trimmed,
    }

    combined_context = f"UPSTREAM PIPELINE CONTEXT:\n{json.dumps(context_dict, indent=2)}\n\n"
    
    # Check for quota exhaustion in ANY search text gathered so far
    all_raw = research_text + "".join(getattr(state, 'graveyard_raw', [])) + "".join(getattr(state, 'communities_raw', []))
    is_partial = False
    note = ""
    if "Quota exhausted" in all_raw:
        is_partial = True
        note = "Web search (Tavily) quota exhausted. Research data is incomplete."
        safe_print(f"[RESEARCH AGENT] {note}")

    human_message_content = (
        combined_context
        + 'RULES:\n'
        '- ONLY mention competitors that appear in the research signals above.\n'
        '- If you mention a competitor from the search, cite their pricing or complaints accurately.\n'
        '- user_complaints MUST have direct quotes and link to source.\n'
        '- first_50_users_communities must include specific relevant communities.\n'
        '- pricing_signals: what they currently pay based on search.\n'
        '- regional_pricing_ceiling: state maximum realistic monthly price tailored to the user\'s likely demographic/region.\n'
        '- competitor_pricing_detail: break down exactly what the main alternatives cost.\n'
        '- competitor_graveyard_lessons: strictly list lessons from alternatives that shut down.\n'
        '- If you cannot provide a real URL from the search results above, do NOT include\n'
        '  the complaint. An empty list is better than a hallucinated quote.\n'
        '- is_funded: set to true for a competitor ONLY if the search results contain explicit evidence\n'
        '  of VC funding, a YC batch (e.g. YC S22), or a Series A/B/C announcement. If no such\n'
        '  evidence appears in the search results, set is_funded to false — do NOT guess.\n'
        '- competitor_graveyard_lessons: CRITICAL RULE — you may ONLY list a company here if the search results\n'
        '  above contain a news article, TechCrunch report, or Reddit post explicitly confirming it SHUT DOWN\n'
        '  or CEASED OPERATIONS. If you cannot find such a source in the data above, return graveyard = [].\n'
        '  Companies that are STILL OPERATING and must NEVER appear in graveyard: Trint, Rev.com, GoTranscript,\n'
        '  Otter.ai, Descript, Kapwing, CapCut, Captions.ai, Zeemo, Submagic, 3Play Media.\n'
        '  An empty graveyard is the correct honest answer when no confirmed shutdown is found.\n'
        '- market_gap: the SPECIFIC missing feature from ALL existing products, in one sentence.\n'
        '- Use the competitor_pricing_detail field to cite exact pricing tiers with limits. If CapCut has a free tier with 10 min/month limit, say that exactly.\n'
    )
    if is_partial:
        human_message_content += "\nCRITICAL: Web search quota exhausted. For ANY field where you lack search data (like competitors, pricing, complaints), output the literal string 'NO DATA — search quota exhausted' instead of guessing.\n"

    anchor_text = f'''
=== IDEA LOCK ===
You are analyzing ONLY this idea: {idea_anchor['idea_title']}
Target user: {idea_anchor['target_user']}
If your context contains references to other ideas or projects, ignore them.
Every output you produce must be specifically about: {idea_anchor['idea_title']}
=== END LOCK ===
''' if idea_anchor else ""
    system_message = SystemMessage(content=anchor_text + "\n" + ANCHOR + "\n" + system_prompt)
    human_message = HumanMessage(
        content=human_message_content + build_schema_prompt(MarketOutput)
    )

    try:
        result = call_with_fallback(llm, MarketOutput, [system_message, human_message])
        result.is_partial_research = is_partial
        result.research_note = note

        # ── Nuclear graveyard filter ─────────────────────────────────────────
        # Strip any graveyard entry whose company name does NOT appear verbatim
        # in the raw search text Tavily returned. LLMs cannot invent shutdowns
        # for companies that don't appear in the search data.
        if result.competitor_graveyard_lessons:
            raw_text_lower = " ".join(graveyard_results).lower()
            confirmed = []
            for lesson in result.competitor_graveyard_lessons:
                # Extract candidate company name: first 1-3 capitalised words
                words = lesson.split()
                candidate_names = [
                    " ".join(words[:i]).lower().strip(".,:-")
                    for i in range(1, min(4, len(words) + 1))
                ]
                # Check if ANY variant of the name appears in raw Tavily text
                if any(name in raw_text_lower for name in candidate_names if len(name) > 3):
                    confirmed.append(lesson)
                else:
                    safe_print(f"[GRAVEYARD FILTER] Removed hallucinated entry: '{lesson[:60]}'")
            result.competitor_graveyard_lessons = confirmed
            if not confirmed:
                result.research_note = (
                    (result.research_note + " " if result.research_note else "")
                    + "Graveyard cleared: no confirmed shutdowns found in search data."
                )
        # ────────────────────────────────────────────────────────────────────

        return result
    except Exception as e:
        safe_print(f"[RESEARCH AGENT] call_with_fallback failed: {str(e)}")
        return MarketOutput(
            failed=True,
            error=True,
            error_message=str(e),
            competitors=[],
            open_source_alternatives=[],
            main_user_complaints=[],
            market_gap_summary="",
            first_50_users_communities=[],
            competitor_pricing_detail=[]
        )



def format_market_for_display(m: MarketOutput) -> str:
    if getattr(m, 'error', False) or getattr(m, 'failed', False):
        return (
            '## ⚠️ Market Research\n\n'
            f'> **Error:** {m.error_message}\n\n'
        )
        
    md = [
        '## 📊 Market Research',
        '',
        '---',
        '### 🏆 Competitors',
        '',
        '| Competitor | Pricing | Main Weakness | Why Users Leave |',
        '|------------|---------|---------------|-----------------|',
    ]
    for c in m.competitors:
        leave = getattr(c, 'why_users_leave', '') or c.why_users_complain
        md.append(f'| **{c.name}** | {c.pricing} | {c.main_weakness} | {leave} |')

    if m.open_source_alternatives:
        md.extend(['', '### 🔓 Open Source Alternatives'])
        for alt in m.open_source_alternatives:
            md.append(f'- {alt}')

    # Quoted complaints (new Layer 1 field)
    if getattr(m, 'user_complaints', None):
        md.extend(['', '---', '### 💬 Real User Complaints (Quoted)'])
        for q in m.user_complaints:
            md.append(f'> "{q.quote}"\\n> *Source: {q.source_url}*')
    else:
        md.extend(['', '---', '### 😤 Main User Complaints'])
        for i, complaint in enumerate(m.main_user_complaints, 1):
            md.append(f'{i}. {complaint}')

    md.extend([
        '',
        '---',
        '### 🎯 Market Gap',
        f'> **{m.market_gap or m.market_gap_summary}**',
    ])

    # Regional pricing ceiling (new)
    if m.regional_pricing_ceiling:
        md.extend([
            '',
            '---',
            '### 💰 Regional Pricing Ceiling',
            f'> {m.regional_pricing_ceiling}',
        ])

    # Pricing signals (new)
    if m.pricing_signals:
        md.extend(['', f'**Current pricing signals:** {m.pricing_signals}'])
        
    if getattr(m, 'competitor_pricing_detail', None):
        md.extend(['', '---', '### 💵 Detailed Competitor Pricing (Scraped)'])
        for p in m.competitor_pricing_detail:
            md.append(f'- **{p.competitor_name}**')
            md.append(f'  - Free Tier Limits: {p.free_tier_limits}')
            if p.paid_tiers:
                md.append('  - Paid Tiers:')
                for pt in p.paid_tiers:
                    md.append(f'    - {pt}')

    md.extend([
        '',
        '---',
        '### 👥 Where Your First 50 Users Are',
        '',
        '| Platform | Community | Best Time |',
        '|----------|-----------|-----------|',
    ])
    for c in m.first_50_users_communities:
        flag = f' ⚠️ {c.red_flag}' if c.red_flag else ''
        best = getattr(c, 'best_post_time', '') or ''
        md.append(f'| **{c.platform}** | {c.name_or_url}{flag} | {best} |')

    # Graveyard lessons (new)
    if m.competitor_graveyard_lessons:
        md.extend(['', '---', '### ⚰️ Competitor Graveyard Lessons'])
        for lesson in m.competitor_graveyard_lessons:
            md.append(f'- {lesson}')

    if getattr(m, 'regional_specific_insight', None):
        md.extend([
            '',
            '---',
            '### 📍 Regional Insight',
            f'> {m.regional_specific_insight}',
        ])
    return '\n'.join(md)


def save_output(m: MarketOutput, slug: str) -> str:
    out_dir = Path(f'outputs/{slug}')
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / 'market_research.md'
    md_path.write_text(format_market_for_display(m), encoding='utf-8')
    json_path = out_dir / 'market_research.json'
    json_path.write_text(m.model_dump_json(indent=2), encoding='utf-8')
    return str(md_path)


if __name__ == '__main__':
    test_analysis = IdeaOutput(job_to_be_done='Campus marketplace India for college students to buy books and find teammates')
    result = run_research_agent(test_analysis, 'TIT Bhopal campus marketplace app')
    safe_print(format_market_for_display(result))
    save_output(result, 'test-research')
