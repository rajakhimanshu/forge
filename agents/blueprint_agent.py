import os
import re
from pathlib import Path
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from tools.output_formatter import get_project_slug, format_report

# Load environment variables
load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

KNOWN_STACKS = {
    'React': {'frontend': 'React.js'},
    'Next.js': {'frontend': 'Next.js (React)'},
    'Vue': {'frontend': 'Vue.js'},
    'Svelte': {'frontend': 'SvelteKit'},
    'Node': {'backend': 'Node.js + Express'},
    'FastAPI': {'backend': 'Python + FastAPI'},
    'Django': {'backend': 'Python + Django'},
    'MongoDB': {'database': 'MongoDB Atlas (512MB free)'},
    'Supabase': {'database': 'Supabase PostgreSQL (500MB free)'},
    'PostgreSQL': {'database': 'PostgreSQL'},
    'Firebase': {'database': 'Firebase Firestore'},
    'Razorpay': {'payments': 'Razorpay (2% per transaction)'},
    'Stripe': {'payments': 'Stripe (pay-per-transaction)'},
    'Cashfree': {'payments': 'Cashfree (1.75% per transaction)'},
    'Cloudinary': {'storage': 'Cloudinary (25GB free)'},
    'JWT': {'auth': 'JWT tokens (jsonwebtoken)'},
    'Supabase Auth': {'auth': 'Supabase Auth (free, OAuth + magic link)'},
    'Firebase Auth': {'auth': 'Firebase Auth (free tier)'},
    'Vercel': {'hosting': 'Vercel (free frontend)'},
    'Railway': {'hosting': 'Railway (free backend)'},
    'Render': {'hosting': 'Render (free backend)'},
    'Twilio': {'notifications': 'Twilio SMS'},
    'Fast2SMS': {'notifications': 'Fast2SMS (0.15 INR/SMS)'},
    'Resend': {'email': 'Resend (3000 emails/mo free)'},
    'SendGrid': {'email': 'SendGrid (100 emails/day free)'},
}

def extract_tech_stack(technical_rd: str) -> dict:
    """Scans the technical_rd string for known tech names and returns a categorized dict."""
    tech_stack = {
        'frontend': 'to be determined',
        'backend': 'to be determined',
        'database': 'to be determined',
        'auth': 'to be determined',
        'storage': 'to be determined',
        'payments': 'to be determined',
        'hosting': 'to be determined'
    }
    
    for tech, categories in KNOWN_STACKS.items():
        if re.search(re.escape(tech), technical_rd, re.IGNORECASE):
            for cat, name in categories.items():
                # Prefer more specific or previously found stack items if needed, 
                # but here we'll just update with the last found matching tech.
                tech_stack[cat] = name
                
    return tech_stack

def build_context_header(idea_analysis: str, market_research: str, verdict: dict, 
                         technical_rd: str, coding_method: str, ai_tool_name: str, 
                         team_size: int) -> str:
    """Returns a compact context header summarizing project info and tech stack."""
    # Project Idea: first 150 words
    idea_snippet = " ".join(idea_analysis.split()[:150])
    
    # Verdict summary
    verdict_word = verdict.get('verdict', 'UNKNOWN')
    uniqueness = verdict.get('uniqueness', 0)
    market_gap = verdict.get('market_gap', 0)
    verdict_summary = f"{verdict_word} | Uniqueness: {uniqueness}/10, Market Gap: {market_gap}/10"
    
    # Tech Stack
    stack = extract_tech_stack(technical_rd)
    stack_list = "\n".join([f"- {k.capitalize()}: {v}" for k, v in stack.items()])
    
    # Key Features: first 5 bullet points from technical_rd
    features = []
    lines = technical_rd.split('\n')
    for line in lines:
        if line.strip().startswith(('-', '*', 'FEATURE:')):
            features.append(line.strip())
        if len(features) >= 5:
            break
    features_list = "\n".join(features) if features else "No features extracted."

    header = f"""
PROJECT IDEA: {idea_snippet}...

VERDICT: {verdict_summary}

APPROVED STACK:
{stack_list}

CODING METHOD: {coding_method}
AI TOOL: {ai_tool_name}
TEAM SIZE: {team_size}

KEY FEATURES:
{features_list}
"""
    return header.strip()

def run_blueprint_agent(idea_analysis, market_research, verdict, technical_rd, 
                         coding_method='gemini_cli', ai_tool_name='Gemini CLI', 
                         team_size=1) -> str:
    """Generates the complete development blueprint for the project."""
    # Load prompt
    prompt_path = Path("prompts/blueprint_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    # Build context
    context_header = build_context_header(
        idea_analysis, market_research, verdict, technical_rd, 
        coding_method, ai_tool_name, team_size
    )

    # Initialize LLM
    llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.4)

    print(f"Generating complete development blueprint for {ai_tool_name}...")
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=context_header + "\n\nGenerate the complete development blueprint for this project.\n"
                                               "Use the exact format specified in your instructions.\n"
                                               f"Every task must have a {ai_tool_name} prompt box.")
    ]
    
    response = llm.invoke(messages)
    blueprint_content = response.content

    # Save Output
    project_slug = get_project_slug(idea_analysis[:100])
    save_output(blueprint_content, project_slug, coding_method)

    return blueprint_content

def save_output(content: str, project_slug: str, coding_method: str) -> str:
    """Saves the blueprint to standard and method-specific files."""
    out_dir = Path(f"outputs/{project_slug}")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Format report
    formatted = format_report("Development Blueprint", content)
    
    # Save standard file
    file_path = out_dir / "dev_blueprint.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(formatted)
        
    # Save method-specific file
    method_file_path = out_dir / f"dev_blueprint_{coding_method}.md"
    with open(method_file_path, "w", encoding="utf-8") as f:
        f.write(formatted)
    
    return str(file_path)

if __name__ == "__main__":
    # Test with realistic dummy inputs
    test_idea = "An AI-powered tool that automatically generates weekly progress reports for remote engineering teams by analyzing Git commits, pull requests, and Jira tickets."
    test_research = "Research shows remote teams spend 2-3 hours/week on manual status updates. Tools like Range, Geekbot partially solve this but lack deep code-level insights."
    test_verdict = {
        "verdict": "BUILD",
        "uniqueness": 8,
        "market_gap": 8,
        "report": "Strong demand among remote-first engineering teams. No tool combines Git + Jira intelligence in automated reports."
    }
    test_tech = """
    FEATURE: Git Integration
    APPROACH A: GitHub API (free, 5000 req/hr)
    RECOMMENDED: GitHub API for direct repo access.
    
    FEATURE: Report Generation
    APPROACH A: OpenAI GPT-4o API
    APPROACH B: Ollama (self-hosted llama3)
    
    TECH STACK SUMMARY:
    - Frontend: Next.js
    - Backend: FastAPI
    - Database: Supabase
    - Auth: Supabase Auth
    - Hosting: Vercel + Railway
    """
    
    try:
        os.environ["PYTHONPATH"] = "."
        result = run_blueprint_agent(
            test_idea, test_research, test_verdict, test_tech, 
            coding_method='gemini_cli', ai_tool_name='Gemini CLI'
        )
        print("\n--- BLUEPRINT PREVIEW ---")
        print(result[:500] + "...")
        print("\nPhase 5 complete.")
    except Exception as e:
        print(f"Error in blueprint agent test: {e}")
