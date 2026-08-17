from tools.llm_router import safe_print
import os
import time
import requests
import concurrent.futures
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

TAVILY_API_KEY = os.getenv('TAVILY_API_KEY', '')
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID', '')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET', '')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'ForgeResearch/1.0 by User')
PRODUCT_HUNT_API_KEY = os.getenv('PRODUCT_HUNT_API_KEY', '')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')


def search_tavily(query: str, max_results: int = 5) -> list[dict]:
    if not TAVILY_API_KEY:
        return []
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(query=query, max_results=max_results)
        results = []
        for r in response.get('results', []):
            results.append({
                'title': r.get('title', ''),
                'url': r.get('url', ''),
                'content': r.get('content', '')[:500]
            })
        return results
    except Exception:
        return []


def search_reddit(query: str, limit: int = 8) -> list[dict]:
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        return []
    try:
        import praw
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT
        )
        results = []
        # Search in all subreddits
        try:
            for submission in reddit.subreddit('all').search(query, limit=limit):
                results.append({
                    'title': submission.title,
                    'url': f'https://reddit.com{submission.permalink}',
                    'text': submission.selftext[:300] if submission.selftext else '',
                    'score': submission.score,
                    'subreddit': str(submission.subreddit)
                })
        except Exception:
            pass
        # Also search in India-specific subreddits
        try:
            for sub_name in ['india', 'indianstartups', 'startups']:
                for submission in reddit.subreddit(sub_name).search(query, limit=3):
                    results.append({
                        'title': submission.title,
                        'url': f'https://reddit.com{submission.permalink}',
                        'text': submission.selftext[:300] if submission.selftext else '',
                        'score': submission.score,
                        'subreddit': sub_name
                    })
        except Exception:
            pass
        return results[:limit]
    except Exception:
        return []


def search_hackernews(query: str, limit: int = 8) -> list[dict]:
    try:
        results = []
        queries = [query, f'Show HN: {query}']
        for q in queries:
            response = requests.get(
                f'https://hn.algolia.com/api/v1/search?query={requests.utils.quote(q)}&tags=story&hitsPerPage={limit}',
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                for hit in data.get('hits', []):
                    results.append({
                        'title': hit.get('title', ''),
                        'url': hit.get('url', f'https://news.ycombinator.com/item?id={hit.get("objectID")}'),
                        'points': hit.get('points', 0),
                        'num_comments': hit.get('num_comments', 0)
                    })
        return results[:limit]
    except Exception:
        return []


def search_github(query: str, limit: int = 5) -> list[dict]:
    try:
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if GITHUB_TOKEN:
            headers['Authorization'] = f'token {GITHUB_TOKEN}'
        response = requests.get(
            f'https://api.github.com/search/repositories?q={requests.utils.quote(query)}&sort=stars&per_page={limit}',
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data.get('items', []):
                if item.get('stargazers_count', 0) >= 10:
                    results.append({
                        'name': item.get('full_name', ''),
                        'description': item.get('description', ''),
                        'url': item.get('html_url', ''),
                        'stars': item.get('stargazers_count', 0),
                        'last_updated': item.get('updated_at', '')
                    })
            return results
        return []
    except Exception:
        return []


def search_producthunt(query: str, limit: int = 5) -> list[dict]:
    if not PRODUCT_HUNT_API_KEY:
        return []
    try:
        gql_query = '''
        query SearchPosts($query: String!, $first: Int!) {
          posts(first: $first, topic: $query, order: VOTES) {
            edges {
              node {
                name
                tagline
                url
                votesCount
              }
            }
          }
        }
        '''
        response = requests.post(
            'https://api.producthunt.com/v2/api/graphql',
            headers={
                'Authorization': f'Bearer {PRODUCT_HUNT_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={'query': gql_query, 'variables': {'query': query, 'first': limit}},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            edges = data.get('data', {}).get('posts', {}).get('edges', [])
            results = []
            for edge in edges:
                node = edge.get('node', {})
                results.append({
                    'name': node.get('name', ''),
                    'tagline': node.get('tagline', ''),
                    'url': node.get('url', ''),
                    'votes': node.get('votesCount', 0)
                })
            return results
        return []
    except Exception:
        return []


def run_deep_research(topic: str) -> dict:
    """Run all 5 searches in parallel using ThreadPoolExecutor."""
    searches = {
        'tavily': (search_tavily, topic),
        'reddit': (search_reddit, topic),
        'hackernews': (search_hackernews, topic),
        'github': (search_github, topic),
        'producthunt': (search_producthunt, topic),
    }

    results = {k: [] for k in searches}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_source = {
            executor.submit(fn, query): source_name
            for source_name, (fn, query) in searches.items()
        }
        for future in concurrent.futures.as_completed(future_to_source, timeout=30):
            source_name = future_to_source[future]
            try:
                results[source_name] = future.result()
            except Exception:
                results[source_name] = []

    # Count sources with results
    total_sources = sum(1 for v in results.values() if len(v) > 0)

    # Find graveyard signals (failed/discontinued products)
    graveyard_keywords = ['failed', 'shut down', 'discontinued', 'closed', 'acquired', 'dead', 'abandoned']
    graveyard_signals = []
    for item in results.get('reddit', []) + results.get('hackernews', []):
        title = item.get('title', '').lower()
        if any(kw in title for kw in graveyard_keywords):
            graveyard_signals.append(item)

    results['total_sources'] = total_sources
    results['graveyard_signals'] = graveyard_signals[:10]
    return results


def format_research_for_llm(research: dict) -> str:
    """Format all research results into clean text under 1500 words."""
    sections = []

    if research.get('tavily'):
        sections.append('=== WEB RESULTS ===')
        for r in research['tavily'][:5]:
            sections.append(f'• {r["title"]} | {r["url"]}')
            if r.get('content'):
                sections.append(f'  {r["content"][:200]}')

    if research.get('reddit'):
        sections.append('\n=== REDDIT DISCUSSIONS ===')
        for r in research['reddit'][:5]:
            sections.append(f'• [{r.get("subreddit","reddit")}] {r["title"]} | {r["url"]}')
            if r.get('text'):
                sections.append(f'  {r["text"][:150]}')

    if research.get('hackernews'):
        sections.append('\n=== HACKER NEWS POSTS ===')
        for r in research['hackernews'][:5]:
            sections.append(f'• {r["title"]} ({r.get("points",0)} points) | {r["url"]}')

    if research.get('github'):
        sections.append('\n=== OPEN SOURCE ALTERNATIVES ===')
        for r in research['github'][:5]:
            sections.append(f'• {r["name"]} ⭐{r.get("stars",0)} | {r["url"]}')
            if r.get('description'):
                sections.append(f'  {r["description"][:150]}')

    if research.get('producthunt'):
        sections.append('\n=== PRODUCT HUNT ===')
        for r in research['producthunt'][:5]:
            sections.append(f'• {r["name"]}: {r.get("tagline","")} ({r.get("votes",0)} votes) | {r["url"]}')

    graveyard = research.get('graveyard_signals', [])
    if graveyard:
        sections.append('\n=== GRAVEYARD SIGNALS (failed products) ===')
        for r in graveyard[:5]:
            sections.append(f'• {r.get("title", "Unknown")} | {r.get("url", "")}')

    text = '\n'.join(sections)
    # Limit to ~1500 words
    words = text.split()
    if len(words) > 1500:
        text = ' '.join(words[:1500])

    return text


if __name__ == '__main__':
    safe_print('Testing research sources with "forex trading calendar"...')
    result = run_deep_research('forex trading calendar')
    safe_print(f'\nTavily results: {len(result["tavily"])}')
    safe_print(f'Reddit results: {len(result["reddit"])}')
    safe_print(f'HN results: {len(result["hackernews"])}')
    safe_print(f'GitHub results: {len(result["github"])}')
    safe_print(f'ProductHunt results: {len(result["producthunt"])}')
    safe_print(f'Total sources: {result["total_sources"]}')
    safe_print(f'Graveyard signals: {len(result["graveyard_signals"])}')
    safe_print('\n=== Formatted for LLM ===')
    safe_print(format_research_for_llm(result)[:500])