import os
import requests
from dotenv import load_dotenv
from tavily import TavilyClient
import chromadb

def test_connections():
    # 1. Load environment variables
    load_dotenv()
    
    # 2. Test Ollama connection
    print("Testing Ollama...")
    ollama_status = "FAILED"
    ollama_error = ""
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            ollama_status = "OK"
        else:
            ollama_error = f"Status Code: {response.status_code}"
    except Exception as e:
        ollama_error = str(e)
    print(f"Ollama: {ollama_status}" + (f" - {ollama_error}" if ollama_status == "FAILED" else ""))

    # 3. Test Tavily API
    print("Testing Tavily...")
    tavily_status = "FAILED"
    tavily_error = ""
    tavily_key = os.getenv("TAVILY_API_KEY")
    try:
        if not tavily_key or "YOUR_KEY_HERE" in tavily_key:
            tavily_error = "API Key not set in .env"
        else:
            client = TavilyClient(api_key=tavily_key)
            client.search("test")
            tavily_status = "OK"
    except Exception as e:
        tavily_error = str(e)

    # 4. Test ChromaDB
    chroma_status = "FAILED"
    chroma_error = ""
    chroma_path = os.getenv("CHROMA_PATH", "./chroma_db")
    try:
        client = chromadb.PersistentClient(path=chroma_path)
        # Simple operation to verify it's working
        client.heartbeat()
        chroma_status = "OK"
    except Exception as e:
        chroma_error = str(e)

    # 5. Print results
    print(f"Ollama: {ollama_status}" + (f" - {ollama_error}" if ollama_status == "FAILED" else ""))
    print(f"Tavily: {tavily_status}" + (f" - {tavily_error}" if tavily_status == "FAILED" else ""))
    print(f"ChromaDB: {chroma_status}" + (f" - {chroma_error}" if chroma_status == "FAILED" else ""))

if __name__ == "__main__":
    test_connections()
