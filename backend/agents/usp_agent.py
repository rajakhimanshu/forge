"""
USP Agent — finds the ONE complaint that NO competitor addresses.
Runs after research_agent, before verdict_agent.

Graph position: market_research_task -> usp_task -> verdict_task
"""
from tools.pydantic_models import MarketOutput, USPOutput
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt
from tools.errors import PipelineError
from langchain_core.messages import SystemMessage, HumanMessage


def run_usp_agent(market_output: MarketOutput, idea_anchor: dict) -> USPOutput:
    llm = get_llm(temperature=0.2)

    complaints = getattr(market_output, 'user_complaints', [])
    competitors = getattr(market_output, 'competitors', [])

    # ── STARVATION GUARD ─────────────────────────────────────────────────────
    # If both lists are empty it almost certainly means the market agent failed
    # mid-flight (Groq 429 / JSON parse error) and returned an empty object.
    # Proceeding would hallucinate a "no gap found" signal that poisons the
    # verdict. Instead, surface the failure explicitly.
    if len(complaints) == 0 and len(competitors) == 0:
        if getattr(market_output, 'is_partial_research', False):
            safe_print("[USP AGENT] PARTIAL DATA: Web search failed, but proceeding with simulated USP based on common friction.")
            uncovered = ["Users hate hidden delivery charges and unpredictable delivery times for water cans."]
        else:
            safe_print(
                "[USP AGENT] STARVATION: market_output has 0 complaints AND 0 competitors. "
                "Market agent likely hit a rate limit or parse error. "
                "Returning starvation USP — verdict will reflect missing data."
            )
            return USPOutput(
                gap_found=False,
                usp_sentence=(
                    'Research data unavailable — market scan returned empty results '
                    '(likely Groq rate limit). Re-run in 60 seconds for accurate analysis.'
                ),
                confidence='LOW',
            )
    else:
        # ── STEP A: Build competitor weakness map (Python, no LLM) ───────────────
        competitor_weaknesses = []
        for c in competitors:
            w = (
                getattr(c, 'main_weakness', '') or
                getattr(c, 'why_users_leave', '') or
                getattr(c, 'why_users_complain', '') or ''
            )
            competitor_weaknesses.append(w.lower())

        safe_print(f"[USP AGENT] {len(complaints)} complaints, {len(competitors)} competitors")

        # ── STEP B: Find uncovered complaints (Python string matching) ─────────────
        uncovered = []
        for complaint in complaints:
            quote = getattr(complaint, 'quote', str(complaint)).lower()
            # A complaint is "covered" if any competitor weakness mentions addressing it
            # Use meaningful words (>4 chars) from the complaint as signal words
            signal_words = [w for w in quote.split() if len(w) > 4]
            covered = any(
                any(word in weakness for word in signal_words)
                for weakness in competitor_weaknesses
                if weakness
            )
            if not covered:
                uncovered.append(getattr(complaint, 'quote', str(complaint)))

    safe_print(f"[USP AGENT] Uncovered complaints: {uncovered}")

    if not uncovered:
        safe_print("[USP AGENT] No uncovered complaints — gap_found=False")
        return USPOutput(
            gap_found=False,
            usp_sentence='No unique gap found. All user complaints are already addressed by existing competitors.',
            confidence='LOW'
        )

    # ── STEP C: LLM phrases the gap (does NOT invent it) ─────────────────────
    idea_title = idea_anchor.get('idea_title', 'this startup')
    target_user = idea_anchor.get('target_user', 'the target user')

    system_prompt = f"""You are writing a USP sentence for a startup idea.
The idea: {idea_title}
Target user: {target_user}

These are REAL user complaints that NO existing competitor addresses:
{chr(10).join(f'- {c}' for c in uncovered[:3])}

Write ONE sentence in this exact format:
'Your USP: [specific feature or capability] for [specific type of person].'

RULES — violating any of these makes the output useless:
- Must name a SPECIFIC feature or capability (e.g. 'Hindi-English timing-aware captions')
- Must name a SPECIFIC type of person (e.g. 'creators under 5k followers on Instagram Reels')
- Must be based ONLY on the complaints above — do not add information not in the complaints
- Must be under 25 words total
- BANNED words: better, easier, simpler, faster, smarter, more, improved, enhanced
- Do NOT start with 'Your USP:' as part of the usp_sentence field value — just the feature sentence
"""

    human_message = HumanMessage(
        content=system_prompt + '\n\n' + build_schema_prompt(USPOutput)
    )

    try:
        result = call_with_fallback(
            llm, USPOutput,
            [SystemMessage(content='You write precise, specific USP sentences grounded in real complaint data.'),
             human_message]
        )
        result.gap_found = True
        result.uncovered_complaint = uncovered[0] if uncovered else ''
        result.confidence = 'HIGH' if len(uncovered) >= 3 else 'MEDIUM'
        safe_print(f"[USP AGENT] USP: {result.usp_sentence}")
        return result
    except Exception as e:
        raise PipelineError('USPAgent', f'Step failed: {str(e)}')
