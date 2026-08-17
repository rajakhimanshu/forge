from tools.llm_router import safe_print
from tools.rag_retriever import retrieve
import os

if __name__ == "__main__":
    query = "Razorpay vs Cashfree for India student project"
    safe_print(f"Query: {query}\n")
    context = retrieve(query)
    safe_print(context)