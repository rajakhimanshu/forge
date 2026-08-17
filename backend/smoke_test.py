from tools.llm_router import safe_print
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from agents.orchestrator import app
from agents.idea_agent import format_idea_for_display
from agents.research_agent import format_market_for_display
from agents.feature_agent import run_feature_agent
from agents.service_resolver import detect_infra_needs, resolve_services
from agents.step_generator import generate_steps_for_blueprint, TERMINAL_CMDS, AI_CLI_NAMES
from agents.prompt_engineer import rewrite_prompt, enrich_build_steps, get_success_condition
from agents.docx_exporter import export_build_guide, DOCX_AVAILABLE
from tools.pydantic_models import IdeaOutput, MarketOutput, VerdictOutput, TechOutput, BlueprintOutput, GraveyardExample
from models.service_resolution import ServiceResolution, ServiceBundle
from models.env_profile import EnvProfile
from models.build_step import BuildStep, StepType
from models.feature_spec import FeatureSpec, FeatureBundle
from db.service_cache import get_cached, set_cached, get_quota_used, increment_quota

safe_print("=== FORGE v2.0 — Full Import Check ===")
node_names = [n for n in app.nodes if not n.startswith("__")]
safe_print(f"Orchestrator nodes ({len(node_names)}): {node_names}")
safe_print(f"python-docx available: {DOCX_AVAILABLE}")
safe_print(f"Tavily quota used this month: {get_quota_used('tavily')} calls")

# Model sanity checks
i = IdeaOutput(
    project_name="TestApp",
    pain_score=9,
    india_specific_insight="UPI preferred over cards",
    first_week_validation="Post on r/bhopal asking about the problem",
    technical_feasibility="Solo 2nd-year can build in 4 weeks. Hardest: OTP rate-limits, MongoDB indexing, real-time chat",
    graveyard=[
        GraveyardExample(
            product_name="OyeLabs",
            what_they_built="Campus marketplace app",
            why_they_died="No retention loop, users came once and left",
            lesson="Build a daily-use hook — notifications alone aren't enough"
        )
    ]
)
safe_print(f"IdeaOutput graveyard: {len(i.graveyard)} examples, india_insight: {bool(i.india_specific_insight)}")

m = MarketOutput(
    india_pricing_ceiling="Rs.99/month — students pay Spotify India at this tier",
    competitor_graveyard_lessons=["Avoid feature bloat", "Don't ignore WhatsApp group as primary discovery channel"]
)
safe_print(f"MarketOutput india_pricing_ceiling: {m.india_pricing_ceiling[:40]}")
safe_print(f"MarketOutput graveyard_lessons: {len(m.competitor_graveyard_lessons)}")

env = EnvProfile(os="windows", ai_cli="gemini", experience="intermediate", node_installed=True, python_installed=True)
safe_print(f"EnvProfile: {env.os}/{env.ai_cli}/{env.experience}/node={env.node_installed}/py={env.python_installed}")

cond = get_success_condition("OTP auth route", "Fast2SMS OTP integration")
safe_print(f"OTP success condition: {cond[:80]}")

needs = detect_infra_needs({"tech_stack": {"auth": "JWT OTP", "payments": "Razorpay", "storage": "Cloudinary"}})
safe_print(f"Detected infra needs: {needs}")

safe_print("=== ALL CHECKS PASSED ===")