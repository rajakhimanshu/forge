import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from tools.web_search import get_search_tool
from tools.output_formatter import save_report, get_project_slug, format_report

# Load environment variables
load_dotenv()

def run_research_agent(idea_analysis: str) -> str:
    """
    Performs market research using the Research System Prompt, Tavily search tool, and LLM.
    Returns the structured research report and saves it to a markdown file.
    """
    # 1. Load Configuration
    model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # 2. Load System Prompt
    prompt_path = Path("prompts/research_prompt.txt")
    if not prompt_path.exists():
        raise FileNotFoundError("System prompt 'prompts/research_prompt.txt' not found.")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    # 3. Initialize LLM
    llm = ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.1
    )
    
    from tools.web_search import search

    # 4. Generate Search Queries
    print("Generating search queries for market research...")
    query_gen_prompt = (
        f"Based on this idea analysis:\n\n{idea_analysis}\n\n"
        "Generate 3-4 specific search queries to find competitors, pricing, and user pain points. "
        "Output ONLY the queries, one per line."
    )
    
    query_response = llm.invoke([HumanMessage(content=query_gen_prompt)])
    queries = [q.strip() for q in query_response.content.split("\n") if q.strip() and len(q) > 5][:4]
    
    if not queries:
        queries = [get_project_slug(idea_analysis[:50]) + " competitors pricing"]

    # 5. Execute Searches
    aggregated_results = ""
    for query in queries:
        print(f"Searching: {query}...")
        results = search(query)
        aggregated_results += f"\n--- Results for: {query} ---\n{results}\n"

    # 6. Synthesize Final Report
    print("Synthesizing market research report...")
    synthesis_input = (
        f"Original Idea Analysis:\n{idea_analysis}\n\n"
        f"Search Data Found:\n{aggregated_results}\n\n"
        "Using the above data, write a comprehensive Market Research Report as defined in your instructions."
    )
    
    final_response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=synthesis_input)
    ])
    
    research_report = final_response.content

    # 7. Format and Save Output
    # Extract original idea for slug if possible, or use snippet
    project_slug = get_project_slug(idea_analysis[:100])
    formatted_report = format_report("Market Research Report", research_report)
    save_report(formatted_report, project_slug, "market_research.md")

    print(f"Phase 2 complete: Market research saved.")
    return research_report

if __name__ == "__main__":
    # Test with a sample idea analysis
    sample_analysis = """# Idea Analysis: An app that helps freelancers automatically track time spent on client projects using AI
    - Problem: Freelancers lose billable hours due to manual time tracking errors.
    - Solution: AI-driven automatic time tracking based on active windows and tasks.
    - Target Users: Freelancers, creative professionals, and remote workers.
    - Market Size: Growing gig economy with millions of potential users.
    - Pain Score: 8/10
    """
    try:
        os.environ["PYTHONPATH"] = "."
        run_research_agent(sample_analysis)
    except Exception as e:
        print(f"Error running Research Agent: {e}")
