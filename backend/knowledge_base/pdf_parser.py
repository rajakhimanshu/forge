import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document

def extract_useful_pdf_info(pdf_path: str, idea_concept: str) -> str:
    """
    Intelligently reads a large PDF and extracts ONLY the information
    relevant to the user's startup idea. Returns a condensed summary string.
    """
    try:
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        full_text = "\n".join([doc.page_content for doc in documents])
        
        # If it's a small PDF, just return the text
        if len(full_text) < 4000:
            return full_text
            
        # For large PDFs (> ~1-2 pages), chunk and RAG it
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = text_splitter.split_documents(documents)
        
        # We use lightweight local embeddings so we don't hit API limits
        embeddings = OllamaEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
        
        # Build ephemeral FAISS vector store
        vectorstore = FAISS.from_documents(chunks, embeddings)
        
        # Query 1: Competitors and Market
        q1 = f"Who are the competitors, target audience, and market constraints for: {idea_concept}?"
        docs1 = vectorstore.similarity_search(q1, k=3)
        
        # Query 2: Core Features and Technical Requirements
        q2 = f"What are the specific technical requirements, core features, and user pain points for: {idea_concept}?"
        docs2 = vectorstore.similarity_search(q2, k=3)
        
        # Combine unique documents
        unique_docs = {doc.page_content for doc in (docs1 + docs2)}
        
        extracted_info = "--- EXTRACTED RELEVANT PDF CONTEXT ---\n"
        for i, content in enumerate(unique_docs):
            extracted_info += f"Snippet {i+1}: {content.strip()}\n\n"
            
        return extracted_info

    except Exception as e:
        return f"Error extracting useful info from PDF: {str(e)}"
