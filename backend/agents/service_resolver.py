"""
Layer 2 — Service Resolver Agent
=================================
Detects infra needs from TechOutput, runs live Tavily search per need,
uses LLM to pick the best free/cheap service for each, and caches results
for 30 days to protect Tavily quota.

Graph position: technical_rd_task → service_resolver → blueprint_task
"""
import os
import hashlib
import json
from dotenv import load_dotenv
from tools.errors import PipelineError

from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt
from models.service_resolution import ServiceResolution, ServiceBundle
from db.service_cache import get_cached, set_cached, increment_quota, warn_if_quota_high

load_dotenv()

# ── Keyword → infra category mapping ─────────────────────────────────────────
# Keywords to detect + their canonical category name used in Tavily queries
INFRA_KEYWORD_MAP = {
    "otp":                "OTP SMS verification",
    "sms":                "OTP SMS verification",
    "twilio":             "OTP SMS verification",
    "fast2sms":           "OTP SMS verification",
    "authentication":     "user authentication JWT",
    "auth":               "user authentication JWT",
    "login":              "user authentication JWT",
    "jwt":                "user authentication JWT",
    "file storage":       "file storage cloud upload",
    "image upload":       "file storage cloud upload",
    "cloudinary":         "file storage cloud upload",
    "upload":             "file storage cloud upload",
    "email":              "transactional email service",
    "smtp":               "transactional email service",
    "payments":           "best payment gateway for startups",
    "razorpay":           "best payment gateway for startups",
    "stripe":             "best payment gateway for startups",
    "paddle":             "merchant of record payment gateway",
    "database":           "database hosting free tier",
    "mongodb":            "database hosting free tier",
    "postgresql":         "database hosting free tier",
    "mysql":              "database hosting free tier",
    "supabase":           "database hosting free tier",
    "hosting":            "app hosting deployment free",
    "deploy":             "app hosting deployment free",
    "railway":            "app hosting deployment free",
    "vercel":             "app hosting deployment free",
    "cdn":                "CDN static assets free tier",
    "push notifications": "push notifications free tier",
    "fcm":                "push notifications free tier",
    "firebase":           "push notifications free tier",
}

# Canonical names to avoid duplicates in the resolved list
CANONICAL_CATEGORIES: list[str] = []
for v in INFRA_KEYWORD_MAP.values():
    if v not in CANONICAL_CATEGORIES:
        CANONICAL_CATEGORIES.append(v)


def detect_infra_needs(tech_output, fallback_text: str = "") -> list[str]:
    """
    Extract unique infra categories from TechOutput (Pydantic model or dict).
    If tech_output is None or failed, falls back to scanning fallback_text (user_idea).
    Returns a deduplicated list of canonical category strings.
    """
    stack_text = ""

    if tech_output is not None and not getattr(tech_output, 'failed', False):
        # Serialise to plain text for keyword scanning
        if hasattr(tech_output, 'model_dump_json'):
            stack_text = tech_output.model_dump_json()
        elif isinstance(tech_output, dict):
            stack_text = json.dumps(tech_output)
        else:
            stack_text = str(tech_output)

    # Always also scan fallback text (user idea) for extra coverage
    if fallback_text:
        stack_text = stack_text + " " + fallback_text.lower()

    if not stack_text.strip():
        return []

    stack_lower = stack_text.lower()
    found: list[str] = []
    for keyword, category in INFRA_KEYWORD_MAP.items():
        if keyword in stack_lower and category not in found:
            found.append(category)

    return found


def _search_for_service(need: str) -> str:
    """Run a Tavily search for the infra need. Returns formatted results string."""
    try:
        from tools.web_search import search_tavily
        query = f"best free {need} service 2026 API bootstrap startup"
        result = search_tavily(query)
        increment_quota('tavily')
        return result
    except Exception as e:
        return f"Search unavailable: {e}"


def _resolve_single_need(need: str, llm) -> ServiceResolution:
    """
    Use Tavily + LLM to produce a ServiceResolution for one infra need.
    Falls back to a sensible default if LLM call fails.
    """
    from langchain_core.messages import SystemMessage, HumanMessage

    search_results = _search_for_service(need)

    system_msg = SystemMessage(content=(
        "You are a senior global startup CTO in April 2026. "
        "You MUST resolve this infrastructure need: {need}. "
        "You ALWAYS prefer services with robust global support, generous free tiers, and modern developer experience. "
        "Review the live web search results below and pick EXACTLY ONE free-tier service that is best for "
        "a bootstrapped startup."
    ))

    human_msg = HumanMessage(content=(
        f"Infra need: {need}\n\n"
        f"Live search results (April 2026):\n{search_results}\n\n"
        "Based on the search results above, pick the single best free/cheap service for "
        "Supabase/PlanetScale free (DB), Brevo/Resend free (email). "
        f"tavily_search_query MUST be the exact query you would run to verify free tier limits in 2026.\n"
        + build_schema_prompt(ServiceResolution)
    ))

    try:
        return call_with_fallback(llm, ServiceResolution, [system_msg, human_msg])
    except Exception as e:
        safe_print(f"[SERVICE RESOLVER] LLM failed for '{need}': {e}")
        # Return a sensible default so the pipeline never blocks
        return ServiceResolution(
            infra_need=need,
            recommended_service="Research required",
            current_free_tier="Unknown — check official docs",
            signup_url="https://google.com",
            sdk_install_cmd="# Determine after signup",
            api_key_location="Dashboard → API Keys",
            env_var_name=need.replace(" ", "_").upper() + "_API_KEY",
            free_tier_limit_warning="Verify current limits before production launch.",
            tavily_search_query=f"best free {need} service 2026",
        )


def resolve_services(state: dict) -> dict:
    """
    LangGraph node — resolves all infra services for the idea.

    Reads:  state['tech_output'], state['user_idea'], state['blueprint_output']
    Writes: state['service_bundle']
    """
    tech_output = state.get('tech_output')
    idea_title = ""
    idea_out = state.get('idea_output')
    if idea_out and hasattr(idea_out, 'project_name'):
        idea_title = idea_out.project_name
    if not idea_title:
        idea_title = state.get('user_idea', 'unknown')[:60]

    # Use raw user_idea as fallback text so we detect services even when tech_output failed
    fallback_text = state.get('user_idea', '')
    # Also include blueprint MVP definition if available
    blueprint = state.get('blueprint_output')
    if blueprint and not getattr(blueprint, 'failed', False) and hasattr(blueprint, 'mvp_definition'):
        fallback_text += ' ' + (blueprint.mvp_definition or '')

    infra_needs = detect_infra_needs(tech_output, fallback_text=fallback_text)

    if not infra_needs:
        safe_print("[SERVICE RESOLVER] No infra needs detected — skipping.")
        empty_bundle = ServiceBundle(services=[], cache_key="empty")
        state['service_bundle'] = empty_bundle
        return state

    # Build cache key from idea title + sorted needs list
    cache_key = hashlib.md5(
        (idea_title + str(sorted(infra_needs))).encode()
    ).hexdigest()

    cached = get_cached(cache_key)
    if cached:
        safe_print(f"[SERVICE RESOLVER] Cache HIT — skipping Tavily ({len(infra_needs)} needs).")
        try:
            bundle = ServiceBundle(**cached)
        except Exception as e:
            raise PipelineError('ServiceResolver', f'Step failed: {str(e)}')
        state['service_bundle'] = bundle
        return state

    safe_print(f"[SERVICE RESOLVER] Resolving {len(infra_needs)} infra needs via Tavily...")
    warn_if_quota_high()

    llm = get_llm(temperature=0.2)
    resolutions = []

    for need in infra_needs:
        safe_print(f"  → Resolving: {need}")
        resolution = _resolve_single_need(need, llm)
        resolutions.append(resolution)

    bundle = ServiceBundle(services=resolutions, cache_key=cache_key)
    set_cached(cache_key, bundle)

    safe_print(f"[SERVICE RESOLVER] [OK] Resolved {len(resolutions)} services. Cached for 30 days.")
    state['service_bundle'] = bundle
    return state
