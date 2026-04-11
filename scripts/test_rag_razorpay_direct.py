from tools.rag_retriever import retrieve
import os

if __name__ == "__main__":
    query = "Razorpay"
    print(f"Query: {query}\n")
    context = retrieve(query)
    print(context)
