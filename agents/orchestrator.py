import os
import re
from typing import TypedDict, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

# Import agent functions
from agents.idea_agent import run_idea_agent
from agents.research_agent import run_research_agent
from agents.verdict_agent import run_verdict_agent
from agents.technical_agent import run_technical_agent
from agents.blueprint_agent import run_blueprint_agent
from agents.intake_agent import sharpen_idea

# Load environment variables
load_dotenv()

# 1. Define ForgeState
class ForgeState(TypedDict):
    user_idea: str
    sharpened_idea: Optional[str]
    intake_answers: Optional[dict]
    coding_method: str
    ai_tool_name: str
    team_size: int
    idea_analysis: str
    market_research: str
    verdict: Dict[str, Any]
    technical_rd: str
    blueprint: str
    project_slug: str
    current_phase: str
    error_log: Optional[list]

# 2. Node Functions
def intake_node(state: ForgeState):
    print("\n=== Running Phase 0: Intake & Sharpening ===")
    answers = state.get("intake_answers")
    
    if answers and all(k in answers for k in ["q1", "a1", "q2", "a2", "q3", "a3"]):
        print("Answers found. Sharpening original idea...")
        brief = sharpen_idea(
            state["user_idea"],
            answers["q1"], answers["a1"],
            answers["q2"], answers["a2"],
            answers["q3"], answers["a3"]
        )
        return {"sharpened_idea": brief, "current_phase": "intake"}
    
    print("No intake answers provided. Using raw idea.")
    return {"sharpened_idea": state["user_idea"], "current_phase": "intake"}

def idea_analysis_node(state: ForgeState):
    print("\n=== Running Phase 1: Idea Analysis ===")
    idea = state.get("sharpened_idea") or state.get("user_idea", "")
    analysis = run_idea_agent(idea)
    return {"idea_analysis": analysis, "current_phase": "idea_analysis"}

def market_research_node(state: ForgeState):
    print("\n=== Running Phase 2: Market Research ===")
    research = run_research_agent(state["idea_analysis"])
    return {"market_research": research, "current_phase": "market_research"}

def verdict_node(state: ForgeState):
    print("\n=== Running Phase 3: Verdict ===")
    verdict_data = run_verdict_agent(state["idea_analysis"], state["market_research"])
    return {"verdict": verdict_data, "current_phase": "verdict"}

def technical_rd_node(state: ForgeState):
    print("\n=== Running Phase 4: Technical R&D ===")
    tech_rd = run_technical_agent(state["idea_analysis"], state["verdict"])
    return {"technical_rd": tech_rd, "current_phase": "technical_rd"}

def compress_report(text: str, label: str, max_words: int = 200) -> str:
    '''Compress a report to max_words words while preserving key facts.'''
    if not text or len(text.split()) <= max_words:
        return text
    words = text.split()
    # Take first 60% and last 40% to preserve intro + conclusion
    first_part = words[:int(max_words * 0.6)]
    last_part = words[int(len(words) * 0.6):int(len(words) * 0.6) + int(max_words * 0.4)]
    compressed = ' '.join(first_part) + ' [...] ' + ' '.join(last_part)
    return f'[{label} — compressed to {max_words} words]\n{compressed}'

def run_blueprint_node(state: ForgeState) -> dict:
    print('=== Running Phase 5: Development Blueprint ===')
    try:
        # Compress all previous outputs — this is CRITICAL for llama3.2:3b
        compressed_idea = compress_report(state.get('idea_analysis',''), 'Idea Analysis', 200)
        compressed_market = compress_report(state.get('market_research',''), 'Market Research', 200)
        verdict_text = state.get('verdict', {}).get('report', '') if state.get('verdict') else ''
        compressed_verdict = compress_report(verdict_text, 'Verdict', 150)
        compressed_tech = compress_report(state.get('technical_rd',''), 'Technical R&D', 250)
        blueprint = run_blueprint_agent(
            idea_analysis=compressed_idea,
            market_research=compressed_market,
            verdict={'report': compressed_verdict, **({k:v for k,v in state['verdict'].items() if k != 'report'} if state.get('verdict') else {})},
            technical_rd=compressed_tech,
            coding_method=state.get('coding_method', 'gemini_cli'),
            ai_tool_name=state.get('ai_tool_name', 'Gemini CLI'),
            team_size=state.get('team_size', 1)
        )
        return {'blueprint': blueprint, 'current_phase': 'complete'}
    except Exception as e:
        error_msg = f'Blueprint agent error: {str(e)}'
        return {'blueprint': error_msg, 'error_log': state.get('error_log',[]) + [error_msg]}

# 3. Conditional Edge Logic
def should_continue(state: ForgeState):
    return "continue"

# 4. Construct the Graph
workflow = StateGraph(ForgeState)

# Add Nodes
workflow.add_node("intake_task", intake_node)
workflow.add_node("idea_analysis_task", idea_analysis_node)
workflow.add_node("market_research_task", market_research_node)
workflow.add_node("verdict_task", verdict_node)
workflow.add_node("technical_rd_task", technical_rd_node)
workflow.add_node("blueprint_task", run_blueprint_node)

# Connect Nodes
workflow.set_entry_point("intake_task")
workflow.add_edge("intake_task", "idea_analysis_task")
workflow.add_edge("idea_analysis_task", "market_research_task")
workflow.add_edge("market_research_task", "verdict_task")

# Conditional Routing after Verdict
workflow.add_conditional_edges(
    "verdict_task",
    should_continue,
    {
        "continue": "technical_rd_task",
        "end": END
    }
)

workflow.add_edge("technical_rd_task", "blueprint_task")
workflow.add_edge("blueprint_task", END)

# Compile the Graph
app = workflow.compile()

def run_forge(
    user_idea: str, 
    intake_answers: Optional[dict] = None,
    coding_method: str = "manual",
    ai_tool_name: str = "Manual",
    team_size: int = 1
) -> ForgeState:
    """
    Initializes and runs the Forge workflow for a given user idea.
    """
    initial_state = {
        "user_idea": user_idea,
        "sharpened_idea": None,
        "intake_answers": intake_answers,
        "coding_method": coding_method,
        "ai_tool_name": ai_tool_name,
        "team_size": team_size,
        "idea_analysis": "",
        "market_research": "",
        "verdict": {},
        "technical_rd": "",
        "blueprint": "",
        "project_slug": "",
        "current_phase": "start",
        "error_log": []
    }
    
    final_state = app.invoke(initial_state)
    return final_state

if __name__ == "__main__":
    test_idea = "An AI flashcard app that automatically creates study cards from any YouTube video or podcast the user listens to"
    
    try:
        os.environ["PYTHONPATH"] = "."
        result = run_forge(test_idea)
        print("\nForge Workflow Complete.")
    except Exception as e:
        print(f"Error in Forge Orchestrator: {e}")
