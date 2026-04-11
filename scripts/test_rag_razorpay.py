from tools.rag_retriever import retrieve
import os

if __name__ == "__main__":
    query = "Razorpay vs Cashfree for India student project"
    print(f"Query: {query}\n")
    context = retrieve(query)
    print(context)
