import os
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import Chroma

# Load environment variables
load_dotenv()

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

def get_vectorstore():
    """Initializes and returns the Chroma vector store."""
    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL
    )
    
    if not os.path.exists(CHROMA_PATH):
        return None

    return Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embeddings,
        collection_name="forge_kb"
    )

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
    print(f"Querying knowledge base: '{test_query}'...\n")
    
    try:
        context = retrieve(test_query)
        print(context)
    except Exception as e:
        print(f"Test failed: {e}")
