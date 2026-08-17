from dotenv import load_dotenv
from tools.llm_router import safe_print, get_llm, call_with_fallback, build_schema_prompt
from langchain_core.messages import SystemMessage, HumanMessage
from tools.pydantic_models import IntakeQuestionsOutput, SharpenIdeaOutput

# 1. Load environment variables
load_dotenv()

def generate_intake_questions(raw_idea: str) -> dict:
    """
    Generates 3 targeted clarifying questions to sharpen a startup idea.
    """
    # 2 & 3. Get config and initialize LLM
    llm = get_llm(temperature=0.4)
    
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
        HumanMessage(content=f"Analyze the following combined input and generate 3 intake questions:\n\n{raw_idea}\n\n{build_schema_prompt(IntakeQuestionsOutput)}")
    ]
    
    try:
        response = call_with_fallback(llm, IntakeQuestionsOutput, messages)
        return {
            "q1": response.q1,
            "q2": response.q2,
            "q3": response.q3
        }
    except Exception as e:
        safe_print(f"Error generating intake questions: {e}")
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
    llm = get_llm(temperature=0.3)
    
    prompt = (
        "Rewrite this startup idea as a precise 150-word brief that incorporates the answers below. "
        "Be specific about who the user is, what pain they have, and what the solution does. "
        "No fluff. No generic statements.\n\n"
        f"Original Idea: {raw_idea}\n\n"
        f"Q: {q1}\nA: {a1}\n\n"
        f"Q: {q2}\nA: {a2}\n\n"
        f"Q: {q3}\nA: {a3}"
    )
    
    messages = [
        SystemMessage(content="You are an expert startup analyst."),
        HumanMessage(content=prompt + "\n\n" + build_schema_prompt(SharpenIdeaOutput))
    ]
    
    # 6.c & 6.d Run and return
    try:
        response = call_with_fallback(llm, SharpenIdeaOutput, messages)
        return response.sharpened_idea.strip()
    except Exception as e:
        return f"Error sharpening idea brief: {e}"

# 7. Test block
if __name__ == "__main__":
    test_idea = "An AI-powered personal finance tracker that automatically categorizes expenses from bank SMS/email and generates weekly insights for young professionals."
    
    safe_print("\n=== STEP 1: GENERATING QUESTIONS ===")
    questions = generate_intake_questions(test_idea)
    safe_print(f"Q1: {questions['q1']}")
    safe_print(f"Q2: {questions['q2']}")
    safe_print(f"Q3: {questions['q3']}")
    
    safe_print("\n=== STEP 2: SHARPENING IDEA ===")
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
    safe_print(sharpened)
