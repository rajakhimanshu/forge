import requests
import re
from bs4 import BeautifulSoup
from tools.web_search import search_tavily
from tools.llm_router import safe_print

def find_pricing_url(company_name: str) -> str:
    """Uses Tavily to find the official pricing page for a competitor."""
    query = f"{company_name} pricing page official"
    tavily_text = search_tavily(query)
    
    # search_tavily returns strings like "URL: https://example.com/pricing"
    # Let's extract the first valid URL
    match = re.search(r'URL:\s*(https?://[^\s]+)', tavily_text)
    if match:
        return match.group(1)
    return ""

def scrape_pricing_page(url: str) -> dict:
    """Scrapes the visible text from a pricing page using BeautifulSoup."""
    if not url:
        return {"url": "", "raw_pricing_text": "", "error": "No URL provided"}
        
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script, style, header, footer, nav to focus on main content
        for element in soup(["script", "style", "header", "footer", "nav", "noscript"]):
            element.extract()
            
        text = soup.get_text(separator='\n', strip=True)
        # Condense multiple newlines
        text = re.sub(r'\n+', '\n', text)
        
        return {
            "url": url,
            "raw_pricing_text": text[:2000] # Limit length to avoid blowing up context
        }
    except Exception as e:
        safe_print(f"[SCRAPER] Error scraping {url}: {e}")
        return {"url": url, "raw_pricing_text": "", "error": str(e)}

def scrape_competitor(company_name: str) -> dict:
    url = find_pricing_url(company_name)
    if not url:
        return {"company_name": company_name, "error": "Could not find pricing URL"}
    
    data = scrape_pricing_page(url)
    data["company_name"] = company_name
    return data

def format_scrape_result(result: dict) -> str:
    if "error" in result and not result.get("raw_pricing_text"):
        return f"\nCOMPETITOR SCRAPE: {result.get('company_name', 'Unknown')}\nError: {result['error']}\n"
    
    return f"\nCOMPETITOR SCRAPE: {result.get('company_name', 'Unknown')}\nURL: {result.get('url', '')}\nPRICING DATA:\n{result.get('raw_pricing_text', '')}\n"

if __name__ == "__main__":
    res = scrape_competitor("CapCut")
    print(format_scrape_result(res))
