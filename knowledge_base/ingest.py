import os
from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Load environment variables
load_dotenv()

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

def extract_pdf_text(file_path: str) -> str:
    """Extracts text from a PDF file."""
    try:
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        return "\n".join([doc.page_content for doc in documents])
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def ingest_documents():
    # 1. Initialize Embeddings
    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL
    )

    # 2. Setup path and folders to scan
    kb_root = "knowledge_base"
    subfolders = ["best_practices", "tech_docs", "your_projects"]
    
    all_documents = []
    
    # 3. Scan subdirectories
    for folder in subfolders:
        folder_path = os.path.join(kb_root, folder)
        if not os.path.exists(folder_path):
            continue
            
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            
            try:
                if filename.endswith(".md") or filename.endswith(".txt"):
                    print(f"Ingesting: {filename}")
                    loader = TextLoader(file_path, encoding='utf-8')
                    all_documents.extend(loader.load())
                elif filename.endswith(".pdf"):
                    print(f"Ingesting: {filename}")
                    loader = PyPDFLoader(file_path)
                    all_documents.extend(loader.load())
            except Exception as e:
                print(f"Error loading {filename}: {e}")

    if not all_documents:
        print("No documents found to ingest.")
        return

    # 4. Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    chunks = text_splitter.split_documents(all_documents)

    # 5. Store in ChromaDB
    print(f"Creating vector store at {CHROMA_PATH}...")
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PATH,
        collection_name="forge_kb"
    )
    
    print(f"Done. {len(all_documents)} documents ({len(chunks)} chunks) indexed.")

if __name__ == "__main__":
    ingest_documents()
