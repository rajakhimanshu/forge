import os
import re
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

# 1. Load environment variables
load_dotenv()

def generate_intake_questions(raw_idea: str) -> dict:
    """
    Generates 3 targeted clarifying questions to sharpen a startup idea.
    """
    # 2 & 3. Get config and initialize LLM
    model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.4)
    
    # 5.b & 5.c Create messages
    system_content = (
        "You are an expert startup analyst. You will be provided with a user's initial startup idea "
        "and potentially some document context from a PDF. "
        "Your goal is to generate exactly 3 clarifying questions that will make the analysis more precise. "
        "You MUST consider both the user's typed idea AND the provided document context if it exists. "
        "Questions must identify: (1) the exact user persona, (2) current behaviour without "
        "the solution, (3) the single non-negotiable core feature. Format as:\n"
        "QUESTION_1: ...\n"
        "QUESTION_2: ...\n"
        "QUESTION_3: ..."
    )
    
    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=f"Analyze the following combined input and generate 3 intake questions:\n\n{raw_idea}")
    ]
    
    # 5.d Parse response
    try:
        response = llm.invoke(messages)
        content = response.content
        
        q1_match = re.search(r"QUESTION_1:\s*(.*)", content, re.IGNORECASE)
        q2_match = re.search(r"QUESTION_2:\s*(.*)", content, re.IGNORECASE)
        q3_match = re.search(r"QUESTION_3:\s*(.*)", content, re.IGNORECASE)
        
        # 5.e Fallback logic
        return {
            "q1": q1_match.group(1).strip() if q1_match else "Who is the primary user? (Be specific)",
            "q2": q2_match.group(1).strip() if q2_match else "What does the user currently do instead of your solution?",
            "q3": q3_match.group(1).strip() if q3_match else "What is the one feature without which the whole product is useless?"
        }
    except Exception as e:
        print(f"Error generating intake questions: {e}")
        return {
            "q1": "Who is the primary user? (Be specific)",
            "q2": "What does the user currently do instead of your solution?",
            "q3": "What is the one feature without which the whole product is useless?"
        }

def sharpen_idea(raw_idea: str, q1: str, a1: str, q2: str, a2: str, q3: str, a3: str) -> str:
    """
    Combines the raw idea and the Q&A into a sharpened brief.
    """
    # 6.a & 6.b Setup
    model_name = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    llm = ChatOllama(model=model_name, base_url=base_url, temperature=0.3)
    
    prompt = (
        "Rewrite this startup idea as a precise 150-word brief that incorporates the answers below. "
        "Be specific about who the user is, what pain they have, and what the solution does. "
        "No fluff. No generic statements.\n\n"
        f"Original Idea: {raw_idea}\n\n"
        f"Q: {q1}\nA: {a1}\n\n"
        f"Q: {q2}\nA: {a2}\n\n"
        f"Q: {q3}\nA: {a3}"
    )
    
    # 6.c & 6.d Run and return
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception as e:
        return f"Error sharpening idea brief: {e}"

# 7. Test block
if __name__ == "__main__":
    test_idea = "An AI-powered personal finance tracker that automatically categorizes expenses from bank SMS/email and generates weekly insights for young professionals."
    
    print("\n=== STEP 1: GENERATING QUESTIONS ===")
    questions = generate_intake_questions(test_idea)
    print(f"Q1: {questions['q1']}")
    print(f"Q2: {questions['q2']}")
    print(f"Q3: {questions['q3']}")
    
    print("\n=== STEP 2: SHARPENING IDEA ===")
    # Simulating user answers
    answers = {
        "a1": "Young professionals (22-30) who struggle to track where their salary goes each month.",
        "a2": "They rely on manual spreadsheets or generic banking apps that don't categorize spending intelligently.",
        "a3": "Auto-categorization of expenses from SMS/email — zero manual entry required."
    }
    
    sharpened = sharpen_idea(
        test_idea,
        questions['q1'], answers['a1'],
        questions['q2'], answers['a2'],
        questions['q3'], answers['a3']
    )
    print(sharpened)
