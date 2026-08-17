import sys
sys.path.insert(0, '.')
from tools.llm_router import safe_print

safe_print('--- Testing Pydantic Models ---')
from tools.pydantic_models import (
    IdeaOutput, MarketOutput, VerdictOutput, TechOutput,
    BlueprintOutput, GTMOutput, BusinessOutput, RoadmapOutput
)
safe_print('All 8 Pydantic models OK')

safe_print('--- Testing LLM Router ---')
from tools.llm_router import safe_print, get_llm_info
info = get_llm_info()
safe_print('LLM Mode:', info['mode'], '| Model:', info['model_name'])

safe_print('--- Testing Dashboard Store (SQLite) ---')
from tools.dashboard_store import init_db, save_project, get_all_projects, format_dashboard_markdown
init_db()
save_project('TestProject', 'Test idea', 'BUILD', 8)
projects = get_all_projects()
safe_print('Projects in DB:', len(projects))
md = format_dashboard_markdown()
safe_print('Dashboard MD length:', len(md), 'chars')

safe_print('--- Testing Agent Imports ---')
from agents.idea_agent import run_idea_agent, format_idea_for_display
from agents.research_agent import run_research_agent, format_market_for_display
from agents.verdict_agent import run_verdict_agent, format_verdict_for_display
from agents.technical_agent import run_technical_agent, format_tech_for_display
from agents.blueprint_agent import run_blueprint_agent, format_blueprint_for_display
from agents.gtm_agent import run_gtm_agent, format_gtm_for_display
from agents.business_agent import run_business_agent, format_business_for_display
from agents.roadmap_agent import run_roadmap_agent, format_roadmap_for_display
safe_print('All 8 agent format functions OK')

safe_print('--- Testing Orchestrator Import ---')
from agents.orchestrator import app as forge_app, ForgeState
safe_print('Orchestrator + ForgeState OK')

safe_print('--- Testing Research Sources ---')
from tools.research_sources import search_hackernews, format_research_for_llm
safe_print('research_sources.py OK')

safe_print('')
safe_print('=== ALL SUCCESS CHECKS PASSED ===')
