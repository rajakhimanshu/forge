import os
from dotenv import load_dotenv
from tavily import TavilyClient
from langchain_community.tools.tavily_search import TavilySearchResults

# Load environment variables
load_dotenv()

def get_search_tool():
    """Returns a LangChain TavilySearchResults tool."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or "YOUR_KEY_HERE" in api_key:
        raise ValueError("TAVILY_API_KEY not found in environment variables.")
    
    return TavilySearchResults(max_results=5)

def search(query: str) -> str:
    """
    Performs a Tavily search and returns a clean, formatted string of results.
    Each result includes Title, URL, and Snippet.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or "YOUR_KEY_HERE" in api_key:
        return "Error: TAVILY_API_KEY is not set correctly in the .env file."

    try:
        client = TavilyClient(api_key=api_key)
        # Search using the client
        response = client.search(query=query, max_results=5)
        results = response.get('results', [])

        if not results:
            return "No results found for your query."

        formatted_output = f"Search Results for: '{query}'\n" + "="*40 + "\n"
        for i, res in enumerate(results, 1):
            title = res.get('title', 'No Title')
            url = res.get('url', 'No URL')
            content = res.get('content', 'No snippet available.')
            
            formatted_output += f"{i}. {title}\n"
            formatted_output += f"   URL: {url}\n"
            formatted_output += f"   Snippet: {content}\n\n"

        return formatted_output

    except Exception as e:
        error_msg = str(e)
        if "rate limit" in error_msg.lower():
            return "Error: Tavily API rate limit exceeded."
        return f"Error during search: {error_msg}"

if __name__ == "__main__":
    # Test query
    test_query = "top project management apps 2026 competitors"
    print(f"Testing search tool with query: '{test_query}'...\n")
    
    try:
        results_text = search(test_query)
        print(results_text)
    except Exception as e:
        print(f"Test failed with error: {e}")
