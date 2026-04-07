import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

def main():
    # 1. Load environment variables
    load_dotenv()
    
    model_name = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    print(f"Connecting to Ollama model: {model_name}...")

    try:
        # 2. Create ChatOllama instance
        llm = ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.7
        )

        # 3. Send a test message
        test_message = "You are Forge, an AI development co-pilot. Introduce yourself in 2 sentences."
        response = llm.invoke([HumanMessage(content=test_message)])

        # 4. Print the response
        print("\nForge Response:")
        print(response.content)
        
        # 5. Print success message
        print("\nForge is ready.")

    except Exception as e:
        print(f"\nERROR: Could not connect to Ollama.")
        print(f"Details: {str(e)}")
        print("\nMake sure Ollama is running and you have pulled the model:")
        print(f"ollama run {model_name}")

if __name__ == "__main__":
    main()
