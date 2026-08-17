from tools.llm_router import safe_print
import os
from dotenv import load_dotenv
from tavily import TavilyClient
from langchain_community.tools.tavily_search import TavilySearchResults

# Load environment variables
load_dotenv()

import requests
import concurrent.futures

def get_search_tool():
    """Returns a LangChain TavilySearchResults tool."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or "YOUR_KEY_HERE" in api_key:
        raise ValueError("TAVILY_API_KEY not found in environment variables.")
    
    return TavilySearchResults(max_results=5)

def search_tavily(query: str) -> str:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or "YOUR_KEY_HERE" in api_key:
        return "Error: TAVILY_API_KEY is not set correctly in the .env file."

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query, 
            max_results=3, 
            search_depth="advanced", 
            include_raw_content=True
        )
        results = response.get('results', [])

        if not results:
            return "Tavily: No results found."

        formatted_output = f"--- GOOGLE/WEB SEARCH (Tavily) ---\n"
        for i, res in enumerate(results, 1):
            title = res.get('title', 'No Title')
            url = res.get('url', 'No URL')
            content = res.get('content', 'No snippet available.')
            raw_content = res.get('raw_content', '')
            
            if raw_content and len(raw_content) > len(content):
                content_to_use = raw_content[:1000].replace('\n', ' ').strip() + "... (truncated)"
            else:
                content_to_use = content

            formatted_output += f"{i}. {title}\n   URL: {url}\n   Extract: {content_to_use}\n\n"
        return formatted_output

    except Exception as e:
        err_msg = str(e)
        if "exceeds your plan's set usage limit" in err_msg:
            return "Tavily Error: Quota exhausted (Monthly limit reached). Research signals will be limited to HN/Reddit."
        return f"Tavily Error: {e}"

def search_reddit(query: str) -> str:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "ForgeResearch/1.0")
    
    if not client_id or not client_secret:
        return "Reddit Database: skipped (Credentials missing or invalid)."
        
    try:
        auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
        data = {'grant_type': 'client_credentials'}
        headers = {'User-Agent': user_agent}
        res = requests.post('https://www.reddit.com/api/v1/access_token', auth=auth, data=data, headers=headers)
        token = res.json().get('access_token')
        
        if not token:
            return "Reddit Database: Failed to authenticate."
            
        headers = {'Authorization': f"bearer {token}", 'User-Agent': user_agent}
        res = requests.get('https://oauth.reddit.com/search', headers=headers, params={'q': query, 'limit': 3, 'sort': 'relevance'})
        data = res.json().get('data', {}).get('children', [])
        
        if not data:
            return "Reddit Database: No results found."
            
        output = "--- REDDIT DISCUSSIONS ---\n"
        for item in data:
            post = item['data']
            output += f"Title: {post.get('title')}\n"
            output += f"URL: https://reddit.com{post.get('permalink')}\n"
            output += f"Score: {post.get('score')} | Comments: {post.get('num_comments')}\n"
            content = post.get('selftext', '')[:800]
            if content:
                output += f"Content: {content.replace(chr(10), ' ')}...\n"
            output += "\n"
        return output
    except Exception as e:
        return f"Reddit Search Error: {e}"

def search_hn(query: str) -> str:
    try:
        res = requests.get(f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=3")
        hits = res.json().get('hits', [])
        if not hits:
            return "Hacker News: No results found."
            
        output = "--- HACKER NEWS THREADS ---\n"
        for hit in hits:
            output += f"Title: {hit.get('title', '')}\n"
            url = hit.get('url') or hit.get('story_url')
            if url:
                output += f"URL: {url}\n"
            output += f"HN Link: https://news.ycombinator.com/item?id={hit.get('objectID')}\n"
            output += f"Score: {hit.get('points', 0)} | Comments: {hit.get('num_comments', 0)}\n\n"
        return output
    except Exception as e:
        return f"HN Search Error: {e}"

def search(query: str) -> str:
    """
    Performs parallel search across Tavily (Web), Reddit, and Hacker News.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        f_hn = executor.submit(search_hn, query)
        f_red = executor.submit(search_reddit, query)
        f_tav = executor.submit(search_tavily, query)
        
        results = []
        try:
            results.append(f_hn.result(timeout=10))
        except Exception as e:
            results.append(f"HN timeout: {e}")
            
        try:
            results.append(f_red.result(timeout=10))
        except Exception as e:
            results.append(f"Reddit timeout: {e}")
            
        try:
            results.append(f_tav.result(timeout=10))
        except Exception as e:
            results.append(f"Tavily timeout: {e}")
            
        return "\n\n".join(results)

if __name__ == "__main__":
    # Test query
    test_query = "top project management apps 2026 competitors"
    safe_print(f"Testing search tool with query: '{test_query}'...\n")
    
    try:
        results_text = search(test_query)
        safe_print(results_text)
    except Exception as e:
        safe_print(f"Test failed with error: {e}")