import os
import re
from pathlib import Path
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

# Load environment variables
load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

def clean_llm_output(text: str) -> str:
    """Strips markdown code fences and leading/trailing whitespace."""
    # Strip markdown code blocks (e.g., ```json, ```python, ```)
    text = re.sub(r'```[a-zA-Z]*\n?', '', text)
    text = text.replace('```', '')
    return text.strip()

def parse_verdict(text: str) -> dict:
    """Uses regex to extract verdict, scores, reasoning, and differentiator."""
    parsed = {
        "verdict": "UNKNOWN",
        "uniqueness": 0,
        "market_gap": 0,
        "feasibility": 0,
        "timing": 0,
        "reasoning": "See full report below",
        "differentiator": "See full report below"
    }

    # 1. Match VERDICT (handles **VERDICT:** or VERDICT:)
    verdict_match = re.search(r'VERDICT[:\s]+([A-Z]+)', text, re.IGNORECASE)
    if verdict_match:
        parsed["verdict"] = verdict_match.group(1).upper()

    # 2. Match Scores
    # Pattern catches 'Metric: 8/10', 'METRIC: 8', 'Metric (extra info): 8'
    score_patterns = {
        "uniqueness": r'uniqueness[^\d]*(\d+)',
        "market_gap": r'market.gap[^\d]*(\d+)',
        "feasibility": r'feasibility[^\d]*(\d+)',
        "timing": r'timing[^\d]*(\d+)'
    }
    
    for key, pattern in score_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            parsed[key] = int(match.group(1))

    # 3. Match Reasoning (handles **REASONING:** or REASONING:)
    # We look for the keyword, then optional stars/colons/whitespace, then capture until next header
    reasoning_match = re.search(r'REASONING[^\w]*\s*(.*?)(?=\n\n|\n[A-Z\s\*]+:|$)', text, re.IGNORECASE | re.DOTALL)
    if reasoning_match:
        parsed["reasoning"] = reasoning_match.group(1).strip().lstrip('*: \n\r')

    # 4. Match Differentiator (handles **DIFFERENTIATOR:** or Key pivot:)
    diff_match = re.search(r'(?:DIFFERENTIATOR|Key pivot)[^\w]*\s*(.*)', text, re.IGNORECASE | re.DOTALL)
    if diff_match:
        parsed["differentiator"] = diff_match.group(1).strip().lstrip('*: \n\r')

    return parsed

def format_verdict_card(parsed: dict, raw_report: str) -> str:
    """Returns a formatted markdown string summary card."""
    # Get first sentence of reasoning
    first_sentence = parsed["reasoning"].split('.')[0] + "."
    
    card = [
        f"## VERDICT: {parsed['verdict']}",
        "| Metric | Score |",
        "|--------|-------|",
        f"| Uniqueness | {parsed['uniqueness']}/10 |",
        f"| Market Gap | {parsed['market_gap']}/10 |",
        f"| Feasibility | {parsed['feasibility']}/10 |",
        f"| Timing | {parsed['timing']}/10 |",
        "",
        f"**Bottom line:** {first_sentence}"
    ]
    
    if parsed["verdict"] == "PIVOT":
        card.append(f"**Key pivot:** {parsed['differentiator']}")
    
    card.extend([
        "",
        "---",
        "",
        "## Full Analysis",
        raw_report
    ])
    
    return "\n".join(card)

def run_verdict_agent(idea_analysis: str, market_research: str) -> dict:
    """Runs the verdict agent using ChatOllama and returns the results."""
    # Load prompt
    prompt_path = Path("prompts/verdict_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    # Initialize LLM
    llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.2)

    # Build prompt
    combined_input = (
        f"PHASE 1: IDEA ANALYSIS\n{idea_analysis}\n\n"
        f"PHASE 2: MARKET RESEARCH\n{market_research}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=combined_input)
    ]

    # Get response and clean it
    response = llm.invoke(messages)
    cleaned_text = clean_llm_output(response.content)

    # Parse and format
    parsed = parse_verdict(cleaned_text)
    card_string = format_verdict_card(parsed, cleaned_text)

    # Update result dictionary
    result = parsed.copy()
    result.update({
        "report": cleaned_text,
        "formatted_report": card_string
    })

    return result

def save_output(content: str, project_slug: str) -> str:
    """Saves the verdict report to the specified directory."""
    out_dir = Path(f"outputs/{project_slug}")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = out_dir / "verdict.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return str(file_path)

if __name__ == '__main__':
    # Test with dummy inputs
    test_idea = "Idea: AI-powered task manager for remote teams."
    test_research = "Research: High competition but specific niche for remote dev teams is open."
    
    # Mock result for demonstration if LLM is not running, 
    # but the requirement is to test the actual function.
    try:
        res = run_verdict_agent(test_idea, test_research)
        print(res["formatted_report"])
        print(f"\n=== VERDICT: {res['verdict']} ===")
    except Exception as e:
        print(f"Error during testing: {e}")
        # Manual test of parser if LLM fails
        test_output = """
        ```markdown
        VERDICT: BUILD
        Uniqueness (Moat-focus): 8/10
        Market Gap: 7/10
        Feasibility: 9/10
        Timing: 8/10
        REASONING: This is a solid idea. The timing is perfect given the remote work trend.
        DIFFERENTIATOR: AI-driven task prioritization.
        ```
        """
        cleaned = clean_llm_output(test_output)
        parsed = parse_verdict(cleaned)
        print("\n--- Manual Parser Test ---")
        print(format_verdict_card(parsed, cleaned))
        print(f"=== VERDICT: {parsed['verdict']} ===")
