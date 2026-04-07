import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from tools.output_formatter import save_report, get_project_slug, format_report

# Load environment variables
load_dotenv()

def run_idea_agent(user_idea: str) -> str:
    """
    Performs deep idea analysis using the Idea System Prompt and LLM.
    Returns the structured analysis and saves it to a markdown file.
    """
    # 1. Load Configuration
    model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # 2. Load System Prompt
    prompt_path = Path("prompts/idea_prompt.txt")
    if not prompt_path.exists():
        raise FileNotFoundError("System prompt 'prompts/idea_prompt.txt' not found.")
    
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt = f.read()

    # 3. Initialize LLM
    llm = ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.7
    )

    # 4. Invoke LLM
    print(f"Analyzing idea: '{user_idea[:50]}...'")
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Analyze this idea: {user_idea}")
    ]
    
    response = llm.invoke(messages)
    analysis = response.content

    # 5. Format and Save Output
    project_slug = get_project_slug(user_idea)
    formatted_analysis = format_report(f"Idea Analysis: {user_idea}", analysis)
    save_report(formatted_analysis, project_slug, "idea_analysis.md")

    print(f"Phase 1 complete: Idea analysis saved.")
    return analysis

if __name__ == "__main__":
    # Test query
    test_idea = "An app that helps freelancers automatically track time spent on client projects using AI"
    try:
        run_idea_agent(test_idea)
    except Exception as e:
        print(f"Error running Idea Agent: {e}")
