import os
import json
from tools.pydantic_models import FinalVerdict
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt
from tools.errors import PipelineError
from langchain_core.messages import SystemMessage, HumanMessage

def run_final_verdict_composer(state: dict) -> FinalVerdict:
    llm = get_llm(temperature=0.3)
    
    idea_output = state.get('idea_output')
    market_output = state.get('market_output')
    verdict_output = state.get('verdict_output')
    kill_condition_output = state.get('kill_condition_output')
    usp_output = state.get('usp_output')
    idea_anchor = state.get('idea_anchor') or {}
    
    if not verdict_output:
        raise PipelineError("FinalVerdictComposer", "Missing verdict_output in state")
        
    decision = getattr(verdict_output, 'verdict', 'UNKNOWN')
    # Use USP agent sentence if available, else fall back to LLM differentiator
    usp_sentence = getattr(usp_output, 'usp_sentence', '') if usp_output else ''
    your_edge = usp_sentence or getattr(verdict_output, 'differentiator', '')
    
    kill_event = getattr(kill_condition_output, 'kill_event', 'N/A') if kill_condition_output else 'N/A'
    kill_timeline = getattr(kill_condition_output, 'kill_timeline', 'N/A') if kill_condition_output else 'N/A'
    
    complaints = getattr(market_output, 'user_complaints', []) if market_output else []
    competitors = getattr(market_output, 'competitors', []) if market_output else []
    communities = getattr(market_output, 'first_50_users_communities', []) if market_output else []
    
    communities_str = "\\n".join([f"- {c.platform}: {c.name_or_url}" for c in communities])
    
    # Calculate confidence based on rules
    num_complaints = len(complaints)
    num_competitors = len(competitors)
    if num_complaints >= 5 and num_competitors >= 2:
        confidence = "HIGH"
    elif num_complaints >= 2 and num_competitors >= 1:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
        
    # Heuristic for score (can be LLM-generated, but we give a baseline)
    score_baseline = 50 + (num_complaints * 5) + (num_competitors * 5)
    score_baseline = min(100, score_baseline)
    
    system_prompt = f"""
You are the Final Verdict Composer. You must synthesize the research into a single action plan.

DECISION: {decision}
EDGE: {your_edge}
CONFIDENCE: {confidence}
KILL EVENT: {kill_event}
KILL TIMELINE: {kill_timeline}

COMMUNITIES FOUND:
{communities_str}

RULES for build_first field:
- Must name ONE specific page, feature, or interaction — not a list
- Must specify what success looks like: 'If X people do Y, you have signal'
- Must end with: 'Build nothing else until this signal appears'

RULES for do_tomorrow field:
- Must name ONE specific community from communities above
- Must include the exact words to post — not a template, actual sentences
- Must say: 'Reply to every comment within 2 hours'

RULES for decision_reason:
- Max 2 sentences. Must cite real data.

Your score should reflect the overall viability (0-100). Baseline is around {score_baseline}.
"""

    system_message = SystemMessage(content="You are a startup analyst composing the final verdict.")
    human_message = HumanMessage(
        content=system_prompt + "\\n\\n" + build_schema_prompt(FinalVerdict)
    )

    try:
        result = call_with_fallback(llm, FinalVerdict, [system_message, human_message])
        # ── Hard overrides (Python always wins over LLM) ───────────────────
        result.decision = decision
        result.your_edge = your_edge
        result.kill_condition = kill_event
        result.kill_timeline = kill_timeline
        result.confidence = confidence

        # ── Step 2: do_tomorrow community enforcement ──────────────────────
        # Build community list with human-readable labels (prefer market_output objects)
        community_entries = []  # list of (display_label, name_lower)
        if market_output:
            for c in getattr(market_output, 'first_50_users_communities', []):
                name = getattr(c, 'name_or_url', '') or ''
                platform = getattr(c, 'platform', '') or ''
                if name:
                    label = f"{platform} — {name}" if platform else name
                    community_entries.append((label, name.lower()))

        # Fallback: raw communities_raw strings
        if not community_entries:
            for c in state.get('communities_raw', []):
                if isinstance(c, dict):
                    name = c.get('name_or_url') or c.get('name') or c.get('url', '')
                    if name:
                        community_entries.append((name, name.lower()))
                elif isinstance(c, str) and c:
                    community_entries.append((c, c.lower()))

        if community_entries:
            mentioned = any(entry[1] in result.do_tomorrow.lower() for entry in community_entries)
            if not mentioned and community_entries:
                display_label, _ = community_entries[0]
                idea_title = idea_anchor.get('idea_title', 'my tool')
                usp_short = your_edge.split('.')[0] if your_edge else idea_title
                result.do_tomorrow = (
                    f'Open {display_label} right now. '
                    f'Post this exact message: '
                    f'"I just built a free tool: {usp_short}. '
                    f'No signup needed. Roast it — what is broken, what is missing?" '
                    f'Reply to every single comment within 2 hours. '
                    f'DM anyone who says they want it with a direct link. '
                    f'Do not edit the post.'
                )

        return result
    except Exception as e:
        safe_print(f"[FINAL VERDICT COMPOSER] call_with_fallback failed: {str(e)}")
        raise PipelineError("FinalVerdictComposer", str(e))
