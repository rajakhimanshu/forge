"""
Layer 1 — Deep Feature Understanding Agent
==========================================
Runs after Idea Analysis and before Technical R&D.
Breaks each product feature into technical requirements and produces
a dependency-ordered build queue (FeatureBundle).

Graph position: idea_analysis_task → feature_agent → market_research_task
"""
import json
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage

from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt
from tools.pydantic_models import IdeaOutput
from models.feature_spec import FeatureSpec, FeatureBundle

load_dotenv()

FEATURE_SYSTEM_PROMPT = """You are a senior full-stack architect who specialises in breaking down
startup ideas into precise, orderable technical features.

Your job: given a startup idea and its analysis, decompose the product into individual features.
For each feature, identify every technical component needed to build it:
- Which infra services are needed (OTP, payments, file storage, etc.)
- Which frontend components to build (React/Next.js component names)
- Which backend API routes to create (HTTP method + path)
- Which database collections/tables to create
- Which other features must be built first (dependency order)
- Priority: 1=MVP must-have, 2=should have, 3=nice to have
- Realistic build time in hours for one developer

India-specific rules:
- Auth = OTP-based (Fast2SMS), NOT email link
- Payments = Razorpay, NOT Stripe
- Database = MongoDB Atlas free tier or Supabase free tier
- Hosting = Railway or Render free tier
- File uploads = Cloudinary free tier (10GB)
"""


def run_feature_agent(idea_output: IdeaOutput, user_idea: str = "", idea_anchor: dict = None) -> FeatureBundle:
    """
    Decompose the idea into a FeatureBundle with dependency-ordered build queue.
    """
    llm = get_llm(temperature=0.3)

    project_name = ""
    job = ""
    friction = ""
    pain_score = 0

    if idea_output and not getattr(idea_output, 'failed', False):
        project_name = idea_output.project_name or ""
        job = idea_output.job_to_be_done or ""
        friction = idea_output.primary_friction or ""
        pain_score = idea_output.pain_score or 0

    combined = user_idea or project_name or "Unknown project"

    context = {
        "project_name": project_name,
        "user_idea": user_idea[:500] if user_idea else "",
        "job_to_be_done": job,
        "primary_friction": friction,
        "pain_score": pain_score,
    }

    anchor_text = f'''
=== IDEA LOCK ===
You are analyzing ONLY this idea: {idea_anchor['idea_title']}
Target user: {idea_anchor['target_user']}
If your context contains references to other ideas or projects, ignore them.
Every output you produce must be specifically about: {idea_anchor['idea_title']}
=== END LOCK ===
''' if idea_anchor else ""
    system_msg = SystemMessage(content=anchor_text + "\n" + FEATURE_SYSTEM_PROMPT)
    human_msg = HumanMessage(content=(
        f"Project context:\n{json.dumps(context, indent=2)}\n\n"
        "Decompose this product into features. Rules:\n"
        "- Minimum 3 features, maximum 8 features\n"
        "- Features must be dependency-ordered in build_order (auth before profile, etc.)\n"
        "- mvp_features must contain ONLY priority-1 feature names\n"
        "- infra_needs must use these canonical names: "
        "OTP, file storage, payments, database, email, hosting, push notifications, CDN\n"
        "- backend_routes must use REST format: POST /api/auth/register\n"
        "- depends_on must contain exact feature_name values from the same list\n"
        + build_schema_prompt(FeatureBundle)
    ))

    try:
        result = call_with_fallback(llm, FeatureBundle, [system_msg, human_msg])
        safe_print(f"[FEATURE AGENT] [OK] Decomposed into {len(result.features)} features. MVP: {result.mvp_features}")
        safe_print(f"  Features: {result.build_order}")
        return result
    except Exception as e:
        safe_print(f"[FEATURE AGENT] call_with_fallback failed: {e}")
        # Fix 7: Return empty/error instead of fake data
        return FeatureBundle(
            failed=True,
            error=True,
            error_message=str(e),
            features=[],
            build_order=[],
            mvp_features=[],
        )
