import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from tools.output_formatter import save_report, get_project_slug, format_report
from tools.scaffold_generator import generate_all_scaffold

# Load environment variables
load_dotenv()

def run_blueprint_agent(
    idea_analysis: str, 
    market_research: str, 
    verdict: dict, 
    technical_rd: str,
    coding_method: str = 'gemini_cli',
    ai_tool_name: str = 'Gemini CLI',
    team_size: int = 1
) -> str:
    """Generates a complete, tool-aware development blueprint."""
    model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    prompt_path = Path("prompts/blueprint_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.3)

    context_header = f"""
    --- CONTEXT VARIABLES ---
    CODING_METHOD: {coding_method}
    AI_TOOL_NAME: {ai_tool_name}
    TEAM_SIZE: {team_size}
    --------------------------
    """

    combined_input = (
        f"{context_header}\n\n"
        f"The developer will use {ai_tool_name} to write code. "
        f"Write every checklist step as a ready-to-use {ai_tool_name} prompt. "
        "Do not write generic steps. Every step must be immediately actionable "
        f"with {ai_tool_name}.\n\n"
        "Create a complete Development Blueprint based on the following data:\n\n"
        f"--- PHASE 1: IDEA ANALYSIS ---\n{idea_analysis}\n\n"
        f"--- PHASE 2: MARKET RESEARCH ---\n{market_research}\n\n"
        f"--- PHASE 3: VERDICT ---\n{verdict.get('report', '')}\n\n"
        f"--- PHASE 4: TECHNICAL R&D ---\n{technical_rd}\n"
    )

    print(f"Generating tool-aware development blueprint for {ai_tool_name}...")
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=combined_input)]
    response = llm.invoke(messages)
    blueprint = response.content

    # NEW: Scaffold Generation logic
    project_slug = get_project_slug(idea_analysis[:100])
    project_name = project_slug.replace("-", " ").title()
    
    # Simple tech stack extraction
    known_techs = [
        "React", "Next.js", "Node", "Python", "FastAPI", "Supabase", 
        "Firebase", "MongoDB", "PostgreSQL", "Tailwind", "Prisma", "JWT", "Tavily"
    ]
    tech_stack = [tech for tech in known_techs if tech.lower() in technical_rd.lower()]
    
    output_dir = f"outputs/{project_slug}"
    scaffold_files = generate_all_scaffold(
        project_name, 
        idea_analysis[:200], 
        tech_stack, 
        output_dir
    )
    
    # Append scaffold info to blueprint
    blueprint += "\n\n---\n## 📦 Generated Project Scaffolding\n"
    blueprint += "The following starter files have been generated in the `scaffold/` directory:\n\n"
    
    for filename, content in scaffold_files.items():
        preview = "\n".join(content.split("\n")[:10])
        blueprint += f"### `{filename}`\n"
        blueprint += f"*Location: outputs/{project_slug}/scaffold/{filename}*\n"
        blueprint += f"```text\n{preview}\n...\n```\n\n"

    # Format and Save Output
    formatted_report = format_report(f"Final Development Blueprint ({ai_tool_name})", blueprint)
    
    # Save primary file
    save_report(formatted_report, project_slug, "dev_blueprint.md")
    # Save method-specific version
    save_report(formatted_report, project_slug, f"dev_blueprint_{coding_method}.md")

    print(f"Phase 5 complete: Development blueprint ({coding_method}) saved.")
    return blueprint

if __name__ == "__main__":
    sample_idea = "Idea: AI Time Tracker for Freelancers."
    sample_research = "Research showing gap in automatic tracking."
    sample_verdict = {"verdict": "BUILD IT", "report": "Verdict is BUILD IT."}
    sample_tech = "Technical R&D: Suggested stack is Python."
    try:
        os.environ["PYTHONPATH"] = "."
        run_blueprint_agent(
            sample_idea, 
            sample_research, 
            sample_verdict, 
            sample_tech,
            coding_method='gemini_cli',
            ai_tool_name='Gemini CLI'
        )
    except Exception as e:
        print(f"Error running Blueprint Agent: {e}")
