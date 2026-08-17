from tools.llm_router import safe_print
import os
from dotenv import load_dotenv

# Disable ChromaDB telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from langchain_ollama import OllamaEmbeddings

try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma

# Load environment variables
load_dotenv()

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
# MUST match the model used in knowledge_base/ingest.py — both must write/read
# with the same embedding model or similarity search returns dimensionality garbage.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

def get_vectorstore():
    """Initializes and returns the Chroma vector store."""
    try:
        embeddings = OllamaEmbeddings(
            model=EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL,
        )
    except Exception as e:
        safe_print(f"[RAG] Warning: Could not load OllamaEmbeddings ({e}).")
        return None
    
    if not os.path.exists(CHROMA_PATH):
        safe_print(f"[RAG]  Warning: ChromaDB path '{CHROMA_PATH}' not found.")
        return None

    try:
        return Chroma(
            persist_directory=CHROMA_PATH,
            embedding_function=embeddings,
            collection_name="forge_kb"
        )
    except Exception as e:
        safe_print(f"[RAG]  Warning: Could not load ChromaDB ({e}). Knowledge base will be skipped.")
        return None

def retrieve(query: str, k: int = 3) -> str:
    """
    Queries the vector store and returns a formatted string of the k most relevant documents.
    """
    db = get_vectorstore()
    if db is None:
        return "Error: Knowledge base not found. Please run ingestion first."

    try:
        results = db.similarity_search(query, k=k)
        if not results:
            return "No relevant documents found in the knowledge base."

        formatted_context = ""
        for doc in results:
            source = os.path.basename(doc.metadata.get("source", "Unknown"))
            content = doc.page_content
            formatted_context += f"--- Source: {source} ---\n{content}\n\n"

        return formatted_context

    except Exception as e:
        return f"Error during retrieval: {str(e)}"

def get_retriever(k: int = 3):
    """Returns a LangChain retriever object for use in chains."""
    db = get_vectorstore()
    if db is None:
        raise FileNotFoundError("ChromaDB path does not exist. Run ingest.py first.")
    return db.as_retriever(search_kwargs={"k": k})

if __name__ == "__main__":
    # Test query
    test_query = "What is the correct Git branching strategy for a solo developer?"
    safe_print(f"Querying knowledge base: '{test_query}'...\n")
    
    try:
        context = retrieve(test_query)
        safe_print(context)
    except Exception as e:
        safe_print(f"Test failed: {e}")