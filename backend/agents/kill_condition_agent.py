import os
import json
from datetime import datetime
from tools.pydantic_models import KillConditionOutput
from tools.web_search import search
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt
from tools.errors import PipelineError
from langchain_core.messages import SystemMessage, HumanMessage

def run_kill_condition_agent(competitor_names: list, idea_title: str, founder_edge: str, idea_anchor: dict = None) -> KillConditionOutput:
    llm = get_llm(temperature=0.3)
    
    # RESEARCH
    research_results = ""
    safe_print(f"\n--- KILL CONDITION RESEARCH FOR {idea_title} ---")
    for name in competitor_names[:3]:
        try:
            r1 = search(f'{name} new features {datetime.now().year}')
            r2 = search(f'{name} funding announcement {datetime.now().year}')
            r3 = search(f'{name} product roadmap')
            research_results += f"\nCOMPETITOR: {name}\n"
            research_results += f"New Features: {r1[:400]}\n"
            research_results += f"Funding: {r2[:400]}\n"
            research_results += f"Roadmap: {r3[:400]}\n"
        except Exception as e:
            raise PipelineError('KillConditionAgent', f'Step failed: {str(e)}')

    # Prepare search text
    is_partial = "Quota exhausted" in research_results
    if is_partial:
        safe_print("[KILL CONDITION AGENT] Warning: Web search quota exhausted. Results will be limited.")

    system_prompt = f'''
You are analyzing the kill condition for this startup idea: {idea_title}
The founder's edge is: {founder_edge}
'''
    if is_partial:
        system_prompt += "\nNOTE: Web search quota is exhausted, so recent news is limited. If you cannot find a specific threat, set KILL_PROBABILITY to LOW.\n"

    system_prompt += f'''
Here is recent news about the top competitors: {research_results}

Based ONLY on the search results above, answer in this exact format:
KILL_EVENT: [The specific thing that makes this idea irrelevant, e.g. 'CapCut ships accurate Hindi auto-captions']
KILL_TIMELINE: [Estimated months, e.g. '6-18 months']
KILL_PROBABILITY: [LOW / MEDIUM / HIGH]
SURVIVAL_MOVE: [One specific action founder must take before kill event happens]
SOURCE: [URL from search results that informed this, or 'no direct evidence found']

If the search results contain no relevant news, say:
KILL_EVENT: No kill condition found in current search data
KILL_PROBABILITY: LOW
Do NOT invent scenarios not supported by search results.
'''

    anchor_text = f'''
=== IDEA LOCK ===
You are analyzing ONLY this idea: {idea_anchor['idea_title']}
Target user: {idea_anchor['target_user']}
If your context contains references to other ideas or projects, ignore them.
Every output you produce must be specifically about: {idea_anchor['idea_title']}
=== END LOCK ===
''' if idea_anchor else ""

    full_system = f"""{anchor_text}
You are a startup analyst specializing in competitive threats.
You are analyzing the kill condition for this startup idea: {idea_title}
The founder's edge is: {founder_edge}

{"NOTE: Web search quota is exhausted, so recent news is limited. If you cannot find a specific threat, set kill_probability to LOW." if is_partial else ""}

Recent news about top competitors:
{research_results if research_results else "No competitor search results available."}

RULES:
- kill_event must be ONE specific product launch or feature ship that makes this idea irrelevant.
  Example format: "[Competitor] ships [specific feature] for free to [target user]"
  NEVER write vague events like "competitor improves product" or "market changes".
- kill_timeline: estimate as a range, e.g. "6-18 months" or "12-24 months".
- kill_probability must be LOW / MEDIUM / HIGH — based ONLY on search data above.
  If no relevant news found, set LOW.
- survival_move: ONE concrete technical or distribution move the founder can complete in 2 weeks
  that creates a moat against the kill event. Must name the specific feature or channel.
- Do NOT invent scenarios not supported by search results.
- If search results contain no relevant news: set kill_event to
  "No confirmed kill threat found in current search data" and kill_probability to LOW.
"""

    system_message = SystemMessage(content=full_system)
    human_message = HumanMessage(
        content="Based on the competitive research in the system prompt, generate the kill condition analysis.\n\n"
                + build_schema_prompt(KillConditionOutput)
    )

    try:
        result = call_with_fallback(llm, KillConditionOutput, [system_message, human_message])

        # Post-process: enforce specificity on kill_event
        if result.kill_event and len(result.kill_event.split()) < 5:
            result.kill_event = f"No confirmed kill threat found in current search data for {idea_title}"
            result.kill_probability = "LOW"

        # Post-process: enforce specificity on survival_move
        vague_moves = ["improve", "be better", "focus on quality", "build faster", "iterate"]
        if result.survival_move and any(v in result.survival_move.lower() for v in vague_moves):
            result.survival_move = (
                f"Lock in {idea_anchor.get('target_user', 'target users') if idea_anchor else 'target users'} "
                f"with a waitlist + 3 free uses before any competitor can replicate — "
                f"goal: 100 signups before shipping v1."
            )

        return result
    except Exception as e:
        safe_print(f"[KILL CONDITION AGENT] call_with_fallback failed: {str(e)}")
        return KillConditionOutput(
            failed=True,
            error=True,
            error_message=str(e),
            kill_event="Error computing kill condition",
            kill_timeline="Unknown",
            kill_probability="LOW",
            survival_move="N/A",
            source_url=None
        )
