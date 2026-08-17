from tools.llm_router import safe_print
import sys, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(__file__))

from tools.pydantic_models import RoadmapOutput, BusinessOutput, GTMOutput, IdeaOutput, MarketOutput, VerdictOutput
from agents.business_agent import validate_paid_market_verdict

def test_pydantic_validators():
    safe_print("Testing Pydantic Validators (Fix 8)...")
    
    # Test RoadmapOutput date validator auto-fix
    current_year = str(datetime.now().year)
    past_year = str(datetime.now().year - 1)
    r = RoadmapOutput(money_ask_message=f"Pay me in {past_year} for this amazing service that I just launched today", error=False)
    if current_year in r.money_ask_message:
        safe_print("✅ RoadmapOutput: Successfully auto-fixed past date")
    else:
        safe_print(f"❌ RoadmapOutput: Failed to fix past date. Got: {r.money_ask_message}")

    # Test BusinessOutput paid contradiction validator auto-fix
    b = BusinessOutput(paid_market_exists=False, paid_market_evidence="Users pay $10/month for Rev.com")
    if b.paid_market_exists:
        safe_print("✅ BusinessOutput: Successfully auto-fixed paid market contradiction")
    else:
        safe_print("❌ BusinessOutput: Failed to fix paid market contradiction")

    # Test GTMOutput script length validator auto-fix
    g = GTMOutput(cold_outreach_script="Try it")
    if len(g.cold_outreach_script.split()) >= 5:
        safe_print(f"✅ GTMOutput: Successfully auto-fixed short script")
    else:
        safe_print(f"❌ GTMOutput: Short script failed to trigger auto-fix")

def test_error_handling():
    safe_print("\nTesting Agent Error Handling (Fix 7)...")
    from agents.gtm_agent import run_gtm_agent
    from agents.roadmap_agent import run_roadmap_agent
    
    g = GTMOutput(error=True, error_message="Test Error")
    if g.error and g.error_message == "Test Error":
        safe_print("✅ GTMOutput supports error fields")
    else:
        safe_print("❌ GTMOutput error fields failed")

    r = RoadmapOutput(error=True, error_message="Test Error")
    if r.error and r.error_message == "Test Error":
        safe_print("✅ RoadmapOutput supports error fields")
    else:
        safe_print("❌ RoadmapOutput error fields failed")

def test_paid_market_logic():
    safe_print("\nTesting Paid Market Logic (Fix 3)...")
    b = BusinessOutput(paid_market_exists=False, paid_market_evidence="Rev.com has a $10/month subscription")
    b = validate_paid_market_verdict(b)
    if b.paid_market_exists:
        safe_print("✅ validate_paid_market_verdict successfully fixed contradiction")
    else:
        safe_print("❌ validate_paid_market_verdict failed")

if __name__ == "__main__":
    test_pydantic_validators()
    test_error_handling()
    test_paid_market_logic()
    safe_print("\n=== VALIDATION COMPLETE ===")