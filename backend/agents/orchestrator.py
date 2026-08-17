"""
FORGE Orchestrator — LangGraph Pipeline (v2.0)
===============================================
Full pipeline with all 5 upgrade layers wired:

  idea_analysis_task
    → feature_agent          (Layer 1 — deep feature decomposition)
    → market_research_task   (Layer 1 — upgraded market research)
    → verdict_task
    → technical_rd_task
    → service_resolver       (Layer 2 — live Tavily service resolution + SQLite cache)
    → blueprint_task
    → step_generator         (Layer 3 — OS-aware SETUP/CODING steps)
    → prompt_engineer        (Layer 4 — hyper-specific prompt rewriting)
    → gtm
    → business
    → roadmap
    → docx_export            (Layer 5 — formatted Word document)
    → END
"""
from tools.llm_router import safe_print
import os
import time
from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
from tools.errors import PipelineError

from agents.idea_agent import run_idea_agent, get_project_slug
from agents.research_agent import run_research_agent
from agents.verdict_agent import run_verdict_agent
from agents.kill_condition_agent import run_kill_condition_agent
from agents.final_verdict_composer import run_final_verdict_composer
from agents.technical_agent import run_technical_agent
from agents.blueprint_agent import run_blueprint_agent
from agents.gtm_agent import run_gtm_agent
from agents.business_agent import run_business_agent
from agents.roadmap_agent import run_roadmap_agent
from agents.feature_agent import run_feature_agent
from agents.usp_agent import run_usp_agent
from agents.service_resolver import resolve_services
from agents.step_generator import generate_steps_for_blueprint
from agents.prompt_engineer import enrich_build_steps
from agents.docx_exporter import export_build_guide

from tools.pydantic_models import (
    IdeaOutput, MarketOutput, VerdictOutput, TechOutput,
    BlueprintOutput, GTMOutput, BusinessOutput, RoadmapOutput,
    KillConditionOutput, FinalVerdict, USPOutput
)
from models.service_resolution import ServiceBundle
from models.env_profile import EnvProfile
from models.feature_spec import FeatureBundle
from models.build_step import BuildStep

load_dotenv()


# ── Pipeline result cache (Suggestion 3) ─────────────────────────────────────
from db.pipeline_cache import get_cached_pipeline, set_cached_pipeline


# ── Phase-level retry decorator (Suggestion 2) ───────────────────────────────
def _with_phase_retry(node_fn, retry_delay: int = 30):
    """
    Wraps a LangGraph node function. If the node's Pydantic output has
    failed=True (all providers exhausted), waits retry_delay seconds and
    tries the node exactly one more time before giving up.
    """
    def wrapper(state):
        result = node_fn(state)
        has_failure = any(
            hasattr(v, 'failed') and v.failed
            for v in result.values()
            if v is not None
        )
        if has_failure:
            safe_print(
                f'[PHASE RETRY] {node_fn.__name__} output failed. '
                f'Retrying in {retry_delay}s...'
            )
            time.sleep(retry_delay)
            result = node_fn(state)
        return result
    wrapper.__name__ = node_fn.__name__
    return wrapper


# ── State definition ──────────────────────────────────────────────────────────

class ForgeState(TypedDict):
    # Core inputs
    user_idea: str
    pdf_context: str
    project_slug: str

    # Environment profile (Layer 3)
    env_profile: Optional[EnvProfile]

    # Pydantic output models
    idea_output: Optional[IdeaOutput]
    market_output: Optional[MarketOutput]
    verdict_output: Optional[VerdictOutput]
    kill_condition_output: Optional[KillConditionOutput]
    tech_output: Optional[TechOutput]
    blueprint_output: Optional[BlueprintOutput]
    gtm_output: Optional[GTMOutput]
    business_output: Optional[BusinessOutput]
    roadmap_output: Optional[RoadmapOutput]
    final_verdict: Optional[FinalVerdict]

    # New layer outputs
    idea_anchor: Optional[dict]
    intake_answers: Optional[dict]   # {q1, a1, q2, a2, q3, a3} from intake questionnaire
    usp_output: Optional[USPOutput]      # USPOutput from usp_agent

    # Layer 2 — resolved services
    service_bundle: Optional[ServiceBundle]
    stack_locked: bool        # NEW — prevents post-resolver stack changes (Fix 2 step 2a)

    # Layer 3 + 4 — enriched build steps
    build_steps: Optional[List[BuildStep]]

    # Layer 5 — output docx path
    docx_path: str

    # Summarised text passed between agents
    idea_summary: str
    market_summary: str
    verdict_summary: str
    tech_summary: str
    gtm_summary: str
    business_summary: str

    error_log: list

    # Legacy display fields (kept for UI compatibility)
    idea_analysis: str
    market_research: str
    verdict: dict
    technical_rd: str
    blueprint: str
    gtm_plan: str
    business_model: str
    launch_roadmap: str
    current_phase: str


# ── Summary helpers ───────────────────────────────────────────────────────────

def summarize_idea(result: IdeaOutput, display_text: str) -> str:
    try:
        graveyard_str = ""
        if result.graveyard:
            graveyard_str = f"\nGraveyard: {', '.join(g.product_name for g in result.graveyard[:3])}"
        return (
            f'Project: {result.project_name}\n'
            f'Job-to-be-Done: {result.job_to_be_done}\n'
            f'Target Persona: {result.target_persona_name} — {result.target_persona_description[:200]}\n'
            f'Primary Friction: {result.primary_friction}\n'
            f'Pain Score: {result.pain_score}/10 — {result.pain_reasoning[:200]}\n'
            f'Market Size: {result.market_size_estimate}\n'
            f'AI Native: {result.ai_native_potential[:200]}\n'
            f'Regional Insight: {result.regional_specific_insight[:200]}\n'
            f'Universal Problem: {result.is_universal_problem}'
            f'{graveyard_str}'
        )
    except Exception as e:
        raise PipelineError('Orchestrator', f'Step failed: {str(e)}')


def summarize_market(result: MarketOutput, display_text: str) -> str:
    try:
        competitor_names = ', '.join(c.name for c in result.competitors[:4])
        complaints = '; '.join(result.main_user_complaints[:3])
        communities = ', '.join(c.name_or_url for c in result.first_50_users_communities[:3])
        return (
            f'Competitors: {competitor_names}\n'
            f'Market Gap: {result.market_gap_summary}\n'
            f'User Complaints: {complaints}\n'
            f'First 50 Users: {communities}\n'
            f'Regional Pricing Ceiling: {result.regional_pricing_ceiling}\n'
            f'Regional Insight: {result.regional_specific_insight}'
        )
    except Exception as e:
        raise PipelineError('Orchestrator', f'Step failed: {str(e)}')


def summarize_verdict(result: VerdictOutput, display_text: str) -> str:
    try:
        return (
            f'Verdict: {result.verdict}\n'
            f'Uniqueness: {result.uniqueness_score}/10 | Market Gap: {result.market_gap_score}/10 | '
            f'Feasibility: {result.feasibility_score}/10 | Timing: {result.timing_score}/10\n'
            f'Bottom Line: {result.bottom_line}\n'
            f'Differentiator: {result.differentiator}\n'
            f'Reasoning: {result.reasoning[:400]}'
        )
    except Exception as e:
        raise PipelineError('Orchestrator', f'Step failed: {str(e)}')


def summarize_tech(result: TechOutput, display_text: str) -> str:
    try:
        features = ', '.join(f.name for f in result.features[:5])
        stack_str = ' | '.join(f'{k}: {v}' for k, v in result.tech_stack.items())
        return (
            f'Architecture: {result.architecture_type}\n'
            f'Tech Stack: {stack_str}\n'
            f'Features: {features}\n'
            f'MVP Cost: {result.mvp_cost_inr_monthly}\n'
            f'Production Cost: {result.production_cost_inr_monthly}'
        )
    except Exception as e:
        raise PipelineError('Orchestrator', f'Step failed: {str(e)}')


def summarize_gtm(result: GTMOutput, display_text: str) -> str:
    try:
        communities = ' | '.join(
            f'{p.platform}: {p.community_name}' for p in result.first_50_users_plan[:3]
        )
        return (
            f'Primary Channel: {result.primary_channel}\n'
            f'Cold Script: {result.cold_outreach_script}\n'
            f'Communities: {communities}\n'
            f'Week 1: {" | ".join(result.week1_actions[:3])}\n'
            f'Viral Mechanic: {result.viral_mechanic}'
        )
    except Exception as e:
        raise PipelineError('Orchestrator', f'Step failed: {str(e)}')


# ── Node functions ────────────────────────────────────────────────────────────

def run_idea_node(state: ForgeState) -> dict:
    safe_print('\n=== Running Phase 1: Idea Analysis ===')
    try:
        pdf_ctx = state.get('pdf_context', '')
        result = run_idea_agent(state['user_idea'], pdf_ctx)
        slug = get_project_slug(result)
        display_text = (
            f'**Project: {result.project_name}**\n\n'
            f'Pain Score: {result.pain_score}/10\n\n'
            f'Persona: {result.target_persona_name}\n\n'
            f'{result.job_to_be_done}'
        )
        summary = summarize_idea(result, display_text)
        idea_anchor = {
            'idea_title': result.project_name,
            'idea_one_line': result.job_to_be_done,
            # Use persona DESCRIPTION (the user TYPE), not persona NAME (character name like "Aakash")
            # This ensures community search finds r/NewTubers not r/Aakashians
            'target_user': result.target_persona_description or result.target_persona_name,
            'persona_name': result.target_persona_name,   # kept separately for display only
            'platform_focus': 'Digital Product',
            'usp_sentence': '',   # populated by USP agent later
        }
        # Override with founder answers if intake was completed
        intake = state.get('intake_answers')
        if intake:
            if intake.get('a1'):
                idea_anchor['target_user'] = intake['a1']
            if intake.get('a2'):
                idea_anchor['platform_focus'] = intake['a2']
            if intake.get('a3'):
                idea_anchor['founder_edge'] = intake['a3']
            idea_anchor['founder_answers'] = intake
        return {
            'idea_output': result,
            'project_slug': slug,
            'idea_anchor': idea_anchor,
            'idea_summary': summary,
            'idea_analysis': display_text,
            'current_phase': 'idea_analysis_task',
        }
    except Exception as e:
        err = f'Phase 1 error: {str(e)}'
        safe_print(f'IDEA NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'idea_output': IdeaOutput(failed=True, error=True, error_message=err),
            'idea_summary': state.get('user_idea', ''),
            'idea_analysis': err,
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'idea_analysis_task',
        }


def run_feature_node(state: ForgeState) -> dict:
    safe_print('\n=== Running Phase 1b: Feature Decomposition ===')
    try:
        result = run_feature_agent(
            idea_output=state.get('idea_output'),
            user_idea=state.get('user_idea', ''),
            idea_anchor=state.get('idea_anchor')
        )
        safe_print(f'  Features: {result.build_order}')
        return {
            'feature_bundle': result,
            'current_phase': 'feature_agent',
        }
    except Exception as e:
        err = f'Feature agent error: {str(e)}'
        safe_print(f'FEATURE NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'feature_bundle': FeatureBundle(failed=True, error=True, error_message=err, features=[], build_order=[], mvp_features=[]),
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'feature_agent',
        }


def run_market_node(state: ForgeState) -> dict:
    safe_print('\n=== Running Phase 2: Market Research ===')
    try:
        result = run_research_agent(
            state.get('idea_output'),
            state.get('user_idea', ''),
            idea_anchor=state.get('idea_anchor')
        )
        display_text = (
            f'**Competitors Found:** {len(result.competitors)}\n\n'
            f'**Communities:** {len(result.first_50_users_communities)}\n\n'
            f'{result.market_gap_summary}'
        )
        summary = summarize_market(result, display_text)
        return {
            'market_output': result,
            'market_summary': summary,
            'market_research': display_text,
            'current_phase': 'market_research_task',
        }
    except Exception as e:
        err = f'Phase 2 error: {str(e)}'
        safe_print(f'MARKET NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'market_output': MarketOutput(failed=True, error=True, error_message=err),
            'market_summary': '',
            'market_research': err,
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'market_research_task',
        }


def run_usp_node(state: ForgeState) -> dict:
    safe_print('\n=== Running USP Agent: Finding uncovered gap ===')
    try:
        result = run_usp_agent(
            market_output=state.get('market_output'),
            idea_anchor=state.get('idea_anchor') or {}
        )
        safe_print(f'  USP gap_found: {result.gap_found} | {result.usp_sentence[:80]}')
        # Wire USP sentence back into idea_anchor so GTM + final verdict can use it
        current_anchor = state.get('idea_anchor') or {}
        updated_anchor = {**current_anchor, 'usp_sentence': result.usp_sentence or ''}
        return {
            'usp_output': result,
            'idea_anchor': updated_anchor,
            'current_phase': 'usp_task',
        }
    except Exception as e:
        err = f'USP agent error: {str(e)}'
        safe_print(f'USP NODE ERROR: {err}')
        return {
            'usp_output': USPOutput(failed=True, error=True, error_message=err),
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'usp_task',
        }


def run_verdict_node(state: ForgeState) -> dict:
    safe_print('\n=== Running Phase 3: Verdict ===')
    try:
        result = run_verdict_agent(
            state.get('idea_output'),
            state.get('market_output'),
            idea_anchor=state.get('idea_anchor')
        )
        display_text = f'## {result.verdict}\n\n{result.bottom_line}'
        summary = summarize_verdict(result, display_text)
        verdict_dict = {
            'verdict': result.verdict,
            'uniqueness': result.uniqueness_score,
            'market_gap': result.market_gap_score,
            'feasibility': result.feasibility_score,
            'timing': result.timing_score,
            'report': result.reasoning,
            'formatted_report': f'## {result.verdict}\n{result.reasoning}',
        }
        return {
            'verdict_output': result,
            'verdict_summary': summary,
            'verdict': verdict_dict,
            'current_phase': 'verdict_task',
        }
    except Exception as e:
        err = f'Phase 3 error: {str(e)}'
        safe_print(f'VERDICT NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'verdict_output': VerdictOutput(failed=True, error=True, error_message=err),
            'verdict_summary': '',
            'verdict': {'verdict': 'ERROR', 'report': err, 'market_gap': 5, 'feasibility': 5, 'uniqueness': 5},
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'verdict_task',
        }

def route_after_verdict(state: ForgeState) -> str:
    verdict_out = state.get('verdict_output')
    if verdict_out and verdict_out.verdict == 'BUILD':
        return 'kill_condition_task'
    return 'technical_rd_task'

def run_kill_condition_node(state: ForgeState) -> dict:
    time.sleep(8)  # 8s cooldown — gives Groq TPM bucket time to partially refill
    safe_print('\\n=== Running Phase 3.5: Kill Condition ===')
    try:
        market_output = state.get('market_output')
        idea_output = state.get('idea_output')
        verdict_output = state.get('verdict_output')
        
        competitor_names = [c.name for c in market_output.competitors] if market_output and hasattr(market_output, 'competitors') else []
        idea_title = idea_output.project_name if idea_output else state.get('user_idea', '')
        founder_edge = verdict_output.differentiator if verdict_output else ""
        
        result = run_kill_condition_agent(competitor_names, idea_title, founder_edge, idea_anchor=state.get('idea_anchor'))
        return {
            'kill_condition_output': result,
            'current_phase': 'kill_condition_task',
        }
    except Exception as e:
        err = f'Phase 3.5 error: {str(e)}'
        safe_print(f'KILL CONDITION NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'kill_condition_output': KillConditionOutput(failed=True, error=True, error_message=err),
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'kill_condition_task',
        }



def run_tech_node(state: ForgeState) -> dict:
    time.sleep(8)  # 8s cooldown — gives Groq TPM bucket time to partially refill
    safe_print('\n=== Running Phase 4: Technical R&D ===')
    try:
        result = run_technical_agent(
            state.get('idea_output'),
            state.get('verdict_output'),
            state.get('pdf_context', '')
        )
        display_text = (
            f'**Architecture:** {result.architecture_type}\n\n'
            f'**Stack:** {result.tech_stack}\n\n'
            f'**MVP Cost:** {result.mvp_cost_inr_monthly}'
        )
        summary = summarize_tech(result, display_text)
        return {
            'tech_output': result,
            'tech_summary': summary,
            'technical_rd': display_text,
            'current_phase': 'technical_rd_task',
        }
    except Exception as e:
        err = f'Phase 4 error: {str(e)}'
        safe_print(f'TECH NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'tech_output': TechOutput(failed=True, error=True, error_message=err, tech_stack={}, features=[]),
            'tech_summary': '',
            'technical_rd': err,
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'technical_rd_task',
        }


def run_service_resolver_node(state: ForgeState) -> dict:
    time.sleep(8)  # 8s cooldown — gives Groq TPM bucket time to partially refill
    safe_print('\n=== Running Phase 4b: Service Resolver ===')
    try:
        updated = resolve_services(dict(state))
        bundle = updated.get('service_bundle')
        if bundle:
            service_count = len(bundle.services)
            safe_print(f'  Services resolved: {service_count}')
        return {
            'service_bundle': updated.get('service_bundle'),
            'current_phase': 'service_resolver',
        }
    except Exception as e:
        err = f'Service resolver error: {str(e)}'
        safe_print(f'SERVICE RESOLVER NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'service_bundle': ServiceBundle(failed=True, error=True, error_message=err, services=[], cache_key="error"),
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'service_resolver',
        }


# Fix 6: Tech Stack Consistency Check
def enforce_stack_consistency(
    tech_output: TechOutput,
    service_bundle: ServiceBundle
) -> TechOutput:
    """
    Services resolver is the source of truth.
    Update tech_output to match what services actually resolved.
    """
    if not service_bundle or getattr(service_bundle, 'failed', False):
        return tech_output
        
    resolved_services = {s.infra_need.lower(): s.recommended_service for s in service_bundle.services}
    
    # Check Database
    db_service = resolved_services.get("database", "").lower()
    if "supabase" in db_service:
        tech_output.tech_stack["database"] = "Supabase (PostgreSQL)"
        tech_output.tech_stack.pop("mongodb", None)
    elif "mongodb" in db_service:
         tech_output.tech_stack["database"] = "MongoDB Atlas"
         tech_output.tech_stack.pop("supabase", None)

    # Check Auth
    auth_service = resolved_services.get("auth", "").lower()
    if "supabase" in auth_service:
        tech_output.tech_stack["auth"] = "Supabase Auth"
    elif "firebase" in auth_service:
        tech_output.tech_stack["auth"] = "Firebase Auth"

    # Check Storage
    storage_service = resolved_services.get("storage", "").lower()
    if "cloudinary" in storage_service:
        tech_output.tech_stack["storage"] = "Cloudinary"
    elif "supabase" in storage_service:
        tech_output.tech_stack["storage"] = "Supabase Storage"
    elif "aws s3" in storage_service or "s3" in storage_service:
        tech_output.tech_stack["storage"] = "AWS S3"

    return tech_output


def run_blueprint_node(state: ForgeState) -> dict:
    safe_print('\n=== Running Phase 5: Dev Blueprint ===')
    try:
        # Fix 6: Enforce consistency BEFORE blueprint runs
        tech_output = state.get('tech_output')
        service_bundle = state.get('service_bundle')
        if tech_output and service_bundle:
            tech_output = enforce_stack_consistency(tech_output, service_bundle)
            
        result = run_blueprint_agent(
            state.get('idea_output'),
            state.get('market_output'),
            state.get('verdict_output'),
            tech_output,
            idea_anchor=state.get('idea_anchor')
        )
        display_text = (
            f'**MVP Definition:** {result.mvp_definition}\n\n'
            f'**Tasks:** {len(result.mvp_tasks)} defined'
        )
        return {
            'tech_output': tech_output,
            'blueprint_output': result,
            'blueprint': display_text,
            'stack_locked': True, # Fix 2 step 2a
            'current_phase': 'blueprint_task',
        }
    except Exception as e:
        err = f'Phase 5 error: {str(e)}'
        safe_print(f'BLUEPRINT NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'blueprint_output': BlueprintOutput(failed=True, error=True, error_message=err),
            'blueprint': err,
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'blueprint_task',
        }


def run_step_generator_node(state: ForgeState) -> dict:
    safe_print('\n=== Running Phase 5b: Step Generator ===')
    try:
        env = state.get('env_profile') or EnvProfile()
        service_bundle = state.get('service_bundle')
        blueprint_output = state.get('blueprint_output')

        steps = generate_steps_for_blueprint(blueprint_output, env, service_bundle)
        safe_print(f'  Generated {len(steps)} build steps')
        return {
            'build_steps': steps,
            'current_phase': 'step_generator',
        }
    except Exception as e:
        err = f'Step generator error: {str(e)}'
        safe_print(f'STEP GENERATOR NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'build_steps': [],
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'step_generator',
        }


def run_prompt_engineer_node(state: ForgeState) -> dict:
    safe_print('\n=== Running Phase 5c: Prompt Engineer ===')
    try:
        updated = enrich_build_steps(dict(state))
        enriched_steps = updated.get('build_steps', [])
        safe_print(f'  Enriched {len(enriched_steps)} build steps')
        return {
            'build_steps': enriched_steps,
            'current_phase': 'prompt_engineer',
        }
    except Exception as e:
        err = f'Prompt engineer error: {str(e)}'
        safe_print(f'PROMPT ENGINEER NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'prompt_engineer',
        }


def run_gtm_node(state: ForgeState) -> dict:
    time.sleep(8)  # 8s cooldown — gives Groq TPM bucket time to partially refill
    safe_print('\n=== Running Phase 6: Go-To-Market ===')
    try:
        project_name = state.get('project_slug') or state.get('user_idea', 'unknown')[:30]
        result = run_gtm_agent(
            idea_output=state.get('idea_output'),
            market_output=state.get('market_output'),
            project_name=project_name,
            idea_anchor=state.get('idea_anchor')
        )
        display_text = (
            f'**Primary Channel:** {result.primary_channel}\n\n'
            f'**Cold Script:** {result.cold_outreach_script}'
        )
        summary = summarize_gtm(result, display_text)
        return {
            'gtm_output': result,
            'gtm_summary': summary,
            'gtm_plan': display_text,
            'current_phase': 'gtm',
        }
    except Exception as e:
        err = f'Phase 6 error: {str(e)}'
        safe_print(f'GTM NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'gtm_output': GTMOutput(failed=True, error=True, error_message=err),
            'gtm_summary': '',
            'gtm_plan': err,
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'gtm',
        }


def run_business_node(state: ForgeState) -> dict:
    safe_print('\n=== Running Phase 7: Business Model ===')
    try:
        project_name = state.get('project_slug') or state.get('user_idea', 'unknown')[:30]
        result = run_business_agent(
            idea_output=state.get('idea_output'),
            gtm_output=state.get('gtm_output'),
            project_name=project_name,
            idea_anchor=state.get('idea_anchor')
        )
        display_text = (
            f'**Paid Market:** {"YES" if result.paid_market_exists else "NO"}\n\n'
            f'**Upgrade Trigger:** {result.upgrade_trigger}'
        )
        return {
            'business_output': result,
            'business_summary': display_text,
            'business_model': display_text,
            'current_phase': 'business',
        }
    except Exception as e:
        err = f'Phase 7 error: {str(e)}'
        safe_print(f'BUSINESS NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'business_output': BusinessOutput(failed=True, error=True, error_message=err),
            'business_summary': '',
            'business_model': err,
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'business',
        }


def run_roadmap_node(state: ForgeState) -> dict:
    time.sleep(8)  # 8s cooldown — gives Groq TPM bucket time to partially refill
    safe_print('\n=== Running Phase 8: Launch Roadmap ===')
    try:
        project_name = state.get('project_slug') or state.get('user_idea', 'unknown')[:30]
        result = run_roadmap_agent(
            idea_output=state.get('idea_output'),
            gtm_output=state.get('gtm_output'),
            business_output=state.get('business_output'),
            project_name=project_name,
            idea_anchor=state.get('idea_anchor')
        )
        display_text = (
            f'**Money Ask:** {result.money_ask_message}\n\n'
            f'**Day 30:** {result.day30_success_definition}'
        )
        return {
            'roadmap_output': result,
            'launch_roadmap': display_text,
            'current_phase': 'roadmap',
        }
    except Exception as e:
        err = f'Phase 8 error: {str(e)}'
        safe_print(f'ROADMAP NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'roadmap_output': RoadmapOutput(failed=True, error=True, error_message=err),
            'launch_roadmap': err,
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'roadmap',
        }


def run_final_verdict_composer_node(state: ForgeState) -> dict:
    time.sleep(8)  # 8s cooldown — gives Groq TPM bucket time to partially refill
    safe_print('\\n=== Running Phase 8.5: Final Verdict Composer ===')
    try:
        result = run_final_verdict_composer(dict(state))
        return {
            'final_verdict': result,
            'current_phase': 'final_verdict_composer',
        }
    except Exception as e:
        err = f'Phase 8.5 error: {str(e)}'
        safe_print(f'FINAL VERDICT COMPOSER NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'final_verdict_composer',
        }


def run_docx_export_node(state: ForgeState) -> dict:
    safe_print('\n=== Running Phase 9: Docx Export ===')
    try:
        updated = export_build_guide(dict(state))
        docx_path = updated.get('docx_path', '')
        safe_print(f'  Docx saved: {docx_path}')
        return {
            'docx_path': docx_path,
            'current_phase': 'complete',
        }
    except Exception as e:
        err = f'Docx export error: {str(e)}'
        safe_print(f'DOCX EXPORT NODE ERROR: {err}')
        import traceback; traceback.print_exc()
        return {
            'docx_path': '',
            'error_log': state.get('error_log', []) + [err],
            'current_phase': 'complete',
        }


# ── Build the LangGraph ───────────────────────────────────────────────────────

workflow = StateGraph(ForgeState)

# Register all nodes
workflow.add_node('idea_analysis_task',  run_idea_node)
workflow.add_node('feature_agent',       run_feature_node)
workflow.add_node('market_research_task', run_market_node)
workflow.add_node('usp_task',            run_usp_node)
workflow.add_node('verdict_task',        run_verdict_node)
workflow.add_node('kill_condition_task', run_kill_condition_node)
workflow.add_node('technical_rd_task',   run_tech_node)
workflow.add_node('service_resolver',    run_service_resolver_node)
workflow.add_node('blueprint_task',      run_blueprint_node)
workflow.add_node('step_generator',      run_step_generator_node)
workflow.add_node('prompt_engineer',     run_prompt_engineer_node)
# Heavy LLM nodes wrapped with phase-retry (Suggestion 2)
workflow.add_node('gtm',                 _with_phase_retry(run_gtm_node))
workflow.add_node('business',            _with_phase_retry(run_business_node))
workflow.add_node('roadmap',             _with_phase_retry(run_roadmap_node))
workflow.add_node('final_verdict_composer', _with_phase_retry(run_final_verdict_composer_node))
workflow.add_node('docx_export',         run_docx_export_node)

# Wire the graph
workflow.set_entry_point('idea_analysis_task')
workflow.add_edge('idea_analysis_task',   'feature_agent')
workflow.add_edge('feature_agent',        'market_research_task')
workflow.add_edge('market_research_task', 'usp_task')
workflow.add_edge('usp_task',             'verdict_task')
workflow.add_conditional_edges(
    'verdict_task',
    route_after_verdict,
    {
        'kill_condition_task': 'kill_condition_task',
        'technical_rd_task': 'technical_rd_task'
    }
)
workflow.add_edge('kill_condition_task', 'technical_rd_task')
workflow.add_edge('technical_rd_task',    'service_resolver')
workflow.add_edge('service_resolver',     'blueprint_task')
workflow.add_edge('blueprint_task',       'step_generator')
workflow.add_edge('step_generator',       'prompt_engineer')
workflow.add_edge('prompt_engineer',      'gtm')
workflow.add_edge('gtm',                  'business')
workflow.add_edge('business',             'roadmap')
workflow.add_edge('roadmap',              'final_verdict_composer')
workflow.add_edge('final_verdict_composer', 'docx_export')
workflow.add_edge('docx_export',          END)

app = workflow.compile()


# ── Public entry point ────────────────────────────────────────────────────────

def run_forge(
    user_idea: str,
    pdf_content: str = '',
    env_profile: EnvProfile = None,
    intake_answers: dict = None,
    coding_method: str = 'gemini',
    ai_tool_name: str = 'Gemini CLI',
    team_size: int = 1,
) -> ForgeState:
    # ── Suggestion 3: Check pipeline result cache before running ──
    cached = get_cached_pipeline(user_idea)
    if cached:
        safe_print(f'[PIPELINE CACHE] HIT — returning cached result for: {user_idea[:60]}')
        return cached

    initial = {
        'user_idea': user_idea,
        'pdf_context': pdf_content[:3000] if pdf_content else '',
        'project_slug': '',
        'env_profile': env_profile or EnvProfile(),
        # Pydantic output models
        'idea_output': None,
        'market_output': None,
        'verdict_output': None,
        'kill_condition_output': None,
        'tech_output': None,
        'blueprint_output': None,
        'gtm_output': None,
        'business_output': None,
        'roadmap_output': None,
        'final_verdict': None,
        # New layer outputs
        'idea_anchor': None,
        'feature_bundle': None,
        'service_bundle': None,
        'stack_locked': False,
        'build_steps': [],
        'docx_path': '',
        # Summary fields
        'idea_summary': '',
        'market_summary': '',
        'verdict_summary': '',
        'tech_summary': '',
        'gtm_summary': '',
        'business_summary': '',
        # Legacy display fields
        'idea_analysis': '',
        'market_research': '',
        'verdict': {},
        'technical_rd': '',
        'blueprint': '',
        'gtm_plan': '',
        'business_model': '',
        'launch_roadmap': '',
        'error_log': [],
        'current_phase': 'start',
    }

    try:
        result = app.invoke(initial)
    except PipelineError as e:
        safe_print(f'[PIPELINE ERROR] Agent: {e.agent_name} | Reason: {e.reason}')
        return initial

    # ── Suggestion 3: Store successful result in cache ──
    try:
        set_cached_pipeline(user_idea, result)
    except Exception as cache_err:
        safe_print(f'[PIPELINE CACHE] store error (non-fatal): {cache_err}')

    # Auto-save to dashboard
    try:
        from tools.dashboard_store import save_project
        verdict_str = 'UNKNOWN'
        if result.get('verdict_output'):
            verdict_str = result['verdict_output'].verdict
        elif result.get('verdict'):
            verdict_str = result['verdict'].get('verdict', 'UNKNOWN')
        idea_out = result.get('idea_output')
        project_name = (
            idea_out.project_name
            if idea_out and hasattr(idea_out, 'project_name')
            else result.get('project_slug', 'unknown')
        )
        save_project(
            project_name=project_name,
            idea_summary=user_idea[:100],
            verdict=verdict_str,
            phases_completed=9 if result.get('docx_path') else 8 if result.get('roadmap_output') else 5
        )
    except Exception as e:
        raise PipelineError('Orchestrator', f'Step failed: {str(e)}')

    return result


if __name__ == '__main__':
    os.environ['PYTHONPATH'] = '.'
    test_idea = 'An Inter-College Networking platform for Bhopal students to find teammates, sell books, and share opportunities'
    result = run_forge(test_idea)
    safe_print('\n=== FORGE COMPLETE ===')
    for key in ['project_slug', 'feature_bundle', 'service_bundle', 'build_steps', 'docx_path']:
        val = result.get(key)
        if key == 'build_steps':
            safe_print(f'{key}: {len(val) if val else 0} steps')
        elif key == 'service_bundle':
            safe_print(f'{key}: {len(val.services) if val else 0} services')
        elif key == 'feature_bundle':
            safe_print(f'{key}: {val.build_order if val else "None"}')
        else:
            safe_print(f'{key}: {val}')
    safe_print(f'Errors: {result.get("error_log", [])}')