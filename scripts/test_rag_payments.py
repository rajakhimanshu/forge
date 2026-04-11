from tools.rag_retriever import retrieve
import os

if __name__ == "__main__":
    query = "Which payment gateway should I use for an Indian student project?"
    print(f"Query: {query}\n")
    context = retrieve(query)
    print(context)
