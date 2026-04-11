import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from tools.output_formatter import save_report, get_project_slug, format_report
from tools.web_search import search

# Load environment variables
load_dotenv()

SEARCH_TEMPLATES = {
    'campus_platform': [
        '{niche} campus community app students 2025 alternatives',
        '{niche} student platform networking marketplace competitors',
        '{niche} inter-college app startup reviews pricing model',
        '{idea_keywords} student tools platform open source alternatives',
    ],
    'ai_media_tool': [
        '{core_feature} competitors alternatives pricing 2025',
        'AI {core_feature} service startup 2025 market',
        '{core_feature} tool competitors reviews Otter Rev Whisper alternatives',
        '{core_feature} SaaS pricing free tier market',
    ],
    'b2b_saas': [
        '{core_feature} software alternatives pricing 2025',
        '{core_feature} SaaS competitors market share',
        'best {core_feature} tools reviews 2025',
        '{core_feature} open source alternatives github',
    ],
    'consumer_marketplace': [
        '{niche} marketplace app 2025 alternatives',
        '{niche} platform competitors pricing model',
        'best {niche} apps user reviews complaints 2025',
        '{niche} startup funding traction growth',
    ],
    'productivity_tool': [
        '{idea_keywords} productivity app alternatives 2025',
        '{idea_keywords} tool competitors pricing free tier',
        'best {idea_keywords} apps reviews complaints users 2025',
        '{idea_keywords} open source self-hosted alternatives',
    ],
    'general_startup': [
        '{idea_keywords} competitors alternatives 2025',
        '{idea_keywords} existing solutions market size',
        '{idea_keywords} startup reviews complaints users',
        '{idea_keywords} open source free alternatives',
    ],
}

def detect_project_type(idea_analysis: str) -> str:
    """Detects the type of project from the idea analysis text."""
    text = idea_analysis.lower()

    # AI/media tools: captioning, transcription, audio/video processing
    ai_media_signals = ['caption', 'transcri', 'subtitle', 'whisper', 'audio', 'video processing', 'speech-to-text', 'stt']
    if sum(1 for k in ai_media_signals if k in text) >= 2:
        return 'ai_media_tool'

    # Campus platform: require 3+ dedicated campus-context signals to avoid false positives
    campus_signals = ['college', 'campus', 'university', 'inter-college', 'hostel', 'dormitory', 'student club', 'academic']
    campus_hits = sum(1 for k in campus_signals if k in text)
    if campus_hits >= 3:
        return 'campus_platform'

    # B2B / SaaS
    if any(k in text for k in ['b2b', 'saas', 'enterprise', 'business software', 'crm', 'erp']):
        return 'b2b_saas'

    # Consumer marketplace
    if any(k in text for k in ['marketplace', 'buy and sell', 'ecommerce', 'listing']):
        return 'consumer_marketplace'

    # Productivity tools
    if any(k in text for k in ['productivity', 'habit', 'task', 'time tracking', 'note', 'focus', 'discipline']):
        return 'productivity_tool'

    return 'general_startup'

def run_research_agent(idea_analysis: str, original_idea: str = "") -> str:
    """
    Performs market research using targeted search queries and LLM synthesis.
    Returns the structured research report and saves it to a markdown file.
    """
    # 1. Load Configuration
    model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # 2. Detect Project Type and Get Queries
    project_type = detect_project_type(idea_analysis)
    print(f"Detected project type: {project_type}")
    
    # Extract keywords for templates
    # This is a simple extraction, could be improved with another LLM call
    idea_keywords = get_project_slug(idea_analysis[:100]).replace('-', ' ')
    
    raw_queries = SEARCH_TEMPLATES[project_type]
    queries = []
    for q in raw_queries:
        queries.append(q.format(
            core_feature=idea_keywords,
            niche=idea_keywords,
            idea_keywords=idea_keywords
        ))
    
    print(f"Executing targeted queries: {queries}")

    # 3. Execute Searches
    aggregated_results = ""
    for query in queries:
        print(f"Searching: {query}...")
        try:
            results = search(query)
            aggregated_results += f"\n--- Results for: {query} ---\n{results}\n"
        except Exception as e:
            print(f"Search error for '{query}': {e}")
            aggregated_results += f"\n--- Results for: {query} ---\nError performing search.\n"

    # 4. Initialize LLM
    llm = ChatOllama(
        model=model_name,
        base_url=base_url,
        temperature=0.1
    )

    # 5. Synthesize Final Report
    print("Synthesizing market research report...")
    synthesis_prompt = (
        "You are a market research analyst. Synthesise the search results below "
        "into a structured competitor analysis. Be specific: name real competitors, "
        "their pricing, their weaknesses, and what users complain about. "
        "Focus on the market and geography relevant to the idea being analyzed. "
        "No generic industry statistics — cite specific tools, services, and user complaints."
    )
    
    synthesis_input = (
        f"Original Idea Analysis:\n{idea_analysis}\n\n"
        f"Search Data Found:\n{aggregated_results}\n\n"
        "Using the above data, write a comprehensive Market Research Report that is "
        "specific to the idea's target market, geography, and user segment."
    )
    
    final_response = llm.invoke([
        SystemMessage(content=synthesis_prompt),
        HumanMessage(content=synthesis_input)
    ])
    
    research_report = final_response.content

    # 6. Format and Save Output
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
