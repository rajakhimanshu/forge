import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from tools.errors import PipelineError
from tools.pydantic_models import VerdictOutput, GraveyardExample
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt
from tools.web_search import search

load_dotenv()


from tools.pydantic_models import VerdictOutput, IdeaOutput, MarketOutput

def run_graveyard_search(topic: str) -> str:
    try:
        results = search(f'{topic} startup failed shut down site:reddit.com')
        return results[:600] if results else 'Graveyard search unavailable'
    except Exception as e:
        raise PipelineError('VerdictAgent', f'Step failed: {str(e)}')


def score_idea(research_data: dict) -> dict:
    scores = {}
 
    # DIMENSION 1: Market proof (0-25)
    # Count user_complaints (with quotes), fall back to main_user_complaints count
    complaints = research_data.get('user_complaints', [])
    real_complaints = [c for c in complaints if isinstance(c, dict) and c.get('quote', '')]
    # Fallback: if structured complaints are empty, use plain complaint strings
    if not real_complaints:
        fallback = research_data.get('main_user_complaints', [])
        real_complaints = [c for c in fallback if isinstance(c, str) and len(c.strip()) > 5]
    if len(real_complaints) >= 5:   scores['market_proof'] = 25
    elif len(real_complaints) >= 3: scores['market_proof'] = 16
    elif len(real_complaints) >= 1: scores['market_proof'] = 8
    else:                           scores['market_proof'] = 0
 
    # DIMENSION 2: Competition density (0-25)
    competitors = research_data.get('competitors', [])
    # Count competitors that have a valid URL (real/found)
    real_competitors = [c for c in competitors if isinstance(c, dict) and c.get('url', '').startswith('http')]
    # Count funded ones specifically — stronger PIVOT signal
    funded_competitors = [c for c in real_competitors if c.get('is_funded', False)]
    if len(funded_competitors) >= 3 or len(real_competitors) >= 4:
        scores['competition'] = 5   # saturated — funded players dominate
    elif len(real_competitors) >= 2:
        scores['competition'] = 15  # competitive
    else:
        scores['competition'] = 25  # open
 
    scores['total'] = scores['market_proof'] + scores['competition']
    return scores

def run_verdict_agent(idea_output: IdeaOutput, market_output: MarketOutput, idea_anchor: dict = None) -> VerdictOutput:
    prompt_path = Path('prompts/verdict_prompt.txt')
    system_prompt = prompt_path.read_text(encoding='utf-8') if prompt_path.exists() else (
        'You are a startup investment analyst. Evaluate ideas with extreme precision. '
        'Give BUILD if there is a clear market gap, PIVOT if the angle needs changing, '
        'SKIP if the market is saturated with no differentiator.'
    )

    llm = get_llm(temperature=0.2)

    query_topic = idea_output.job_to_be_done if idea_output else "startup idea"
    graveyard_data = run_graveyard_search(query_topic[:100])

    # Prepare data for scoring
    research_data = market_output.model_dump() if market_output else {}
    is_partial = getattr(market_output, 'is_partial_research', False)
    scores = score_idea(research_data)
    
    # Print scores dict before returning verdict (TEST 3)
    safe_print(f"VERDICT SCORES: {scores}")

    # Hard SKIP: no evidence of pain (ONLY if research was full)
    if scores['market_proof'] == 0 and not is_partial:
        return VerdictOutput(
            verdict='SKIP',
            reasoning='Zero public complaints found with sources. No evidence of real user pain. Do not build until you find 5 real people complaining about this publicly.',
            scores=scores
        )
    
    if scores['market_proof'] == 0 and is_partial:
        safe_print("[VERDICT AGENT] Warning: Zero market proof but research was partial. Giving benefit of doubt.")
        scores['market_proof'] = 10 # Give some score to avoid hard SKIP
        scores['total'] = scores['market_proof'] + scores['competition']

    # Hard PIVOT: saturated market, not enough pain signal to justify entry
    if scores['competition'] == 5 and scores['market_proof'] < 16:
        return VerdictOutput(
            verdict='PIVOT',
            reasoning='Market has 4+ funded competitors and insufficient unique pain signal. You need a specific angle — the general version of this idea is already taken.',
            scores=scores
        )

    context_dict = {
        "project_name": idea_output.project_name if idea_output else "Unknown",
        "job_to_be_done": idea_output.job_to_be_done if idea_output else "",
        "target_persona": idea_output.target_persona_name if idea_output else "",
        "primary_friction": idea_output.primary_friction if idea_output else "",
        "pain_score": idea_output.pain_score if idea_output else 0,
        "market_size_estimate": idea_output.market_size_estimate if idea_output else "",
        "top_competitors": [c.name for c in market_output.competitors] if market_output and hasattr(market_output, 'competitors') else [],
        "market_gap": market_output.market_gap_summary if market_output else "",
        "graveyard_signals": graveyard_data,
        "scores": scores,
    }

    combined_message = (
        f"UPSTREAM PIPELINE CONTEXT:\n{json.dumps(context_dict, indent=2)}\n\n"
        'RULES:\n'
        '- All score fields (uniqueness_score, market_gap_score, feasibility_score, timing_score) must be integers 1-10.\n'
        '- graveyard: ONLY include companies if the graveyard_signals search text above contains the words\n'
        '  "shut down", "closed", "discontinued", or "ceased operations" about that company.\n'
        '- If no confirmed shutdown appears in the search data, return graveyard = [].\n'
        '- NEVER invent company names. Captiona, AutoCaptionPro, CaptionPro, AutoCap do not exist.\n'
        '- bottom_line must cite at least one real competitor name or complaint count.\n'
        '- differentiator must match the target persona from context above, not a generic statement.\n'
    )


    anchor_text = f'''
=== IDEA LOCK ===
You are analyzing ONLY this idea: {idea_anchor['idea_title']}
Target user: {idea_anchor['target_user']}
If your context contains references to other ideas or projects, ignore them.
Every output you produce must be specifically about: {idea_anchor['idea_title']}
=== END LOCK ===
''' if idea_anchor else ""
    system_message = SystemMessage(content=anchor_text + "\n" + system_prompt)
    human_message = HumanMessage(
        content=combined_message + build_schema_prompt(VerdictOutput)
    )

    try:
        result = call_with_fallback(llm, VerdictOutput, [system_message, human_message])
        result.scores = scores
        return result
    except Exception as e:
        safe_print(f"[VERDICT AGENT] call_with_fallback failed: {str(e)}")
        return VerdictOutput(
            failed=True,
            error=True,
            error_message=str(e),
            scores=scores,
        )



def format_verdict_for_display(v: VerdictOutput) -> str:
    verdict_emoji = {'BUILD': '▲ BUILD', 'PIVOT': '◈ PIVOT', 'SKIP': '▼ SKIP'}.get(v.verdict, v.verdict)
    md = [
        f'## VERDICT: {verdict_emoji}',
        '',
        '| Metric | Score |',
        '|--------|-------|',
        f'| Uniqueness | {v.uniqueness_score}/10 |',
        f'| Market Gap | {v.market_gap_score}/10 |',
        f'| Feasibility | {v.feasibility_score}/10 |',
        f'| Timing | {v.timing_score}/10 |',
        '',
        f'> **{v.bottom_line}**',
        '',
        '### Key Differentiator',
        v.differentiator,
        '',
        '### Graveyard Check (real examples from search)',
    ]
    for g in v.graveyard:
        md.append(f'- **{g.product_name}**: {g.what_they_built} → *Died: {g.why_they_died}*')
    md.extend(['', '### Reasoning', v.reasoning])
    if v.pivot_suggestion:
        md.extend(['', '### 💡 Pivot Suggestion', v.pivot_suggestion])
    return '\n'.join(md)


def save_output(v: VerdictOutput, slug: str) -> str:
    out_dir = Path(f'outputs/{slug}')
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / 'verdict.md'
    md_path.write_text(format_verdict_for_display(v), encoding='utf-8')
    json_path = out_dir / 'verdict.json'
    json_path.write_text(v.model_dump_json(indent=2), encoding='utf-8')
    return str(md_path)


if __name__ == '__main__':
    test_idea = 'An app for TIT Bhopal students to buy/sell books and form project teams'
    test_market = 'Competitors: Internshala, OLX. Market: 2M college students in India'
    result = run_verdict_agent(test_idea, test_market)
    safe_print(format_verdict_for_display(result))
    save_output(result, 'test-verdict')
    safe_print('\nverdicts.json created.')
