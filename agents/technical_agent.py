import os
import re
from pathlib import Path
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from tools.web_search import search
from tools.rag_retriever import retrieve
from tools.output_formatter import save_report, get_project_slug, format_report

# Load environment variables
load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Universal free-tier stack options, categorized by use-case.
# The agent will select the right entries based on the project's target market.
UNIVERSAL_TECH_STACK = {
    'payments_global': 'Stripe (free setup, pay-per-transaction, supports 135+ currencies)',
    'payments_india': 'Razorpay (free setup, 2% per transaction, native UPI/NEFT support)',
    'payments_india_alt': 'Cashfree (free setup, 1.75% per transaction, UPI/NEFT)',
    'sms_otp_global': 'Twilio (free trial $15 credit, then ~$0.0075/SMS)',
    'sms_otp_india': 'Fast2SMS (0.15 INR per SMS, 50 free on signup)',
    'sms_otp_india_alt': 'msg91 (bulk SMS, OTP, 0.20 INR/SMS)',
    'file_storage': 'Cloudinary (free: 25GB, 25K transforms/mo) or Supabase Storage (1GB free)',
    'backend_hosting': 'Railway (free: $5/month credit) or Render (free tier, sleeps after 15m)',
    'frontend_hosting': 'Vercel (free: unlimited static, 100GB bandwidth)',
    'database_sql': 'Supabase (free: 500MB PostgreSQL, 50MB file storage)',
    'database_nosql': 'MongoDB Atlas (512MB free tier)',
    'auth': 'Supabase Auth (free, supports OAuth + magic link) or Firebase Auth (free tier)',
    'email': 'Resend (free: 3000 emails/mo) or SendGrid (free: 100 emails/day)',
}

def verify_service_pricing(service_name: str) -> str:
    """Verifies service pricing using web search or pre-defined universal stack."""
    # Check if it's in our universal stack first
    for category, info in UNIVERSAL_TECH_STACK.items():
        if service_name.lower() in info.lower() or service_name.lower() in category.lower():
            return f"{service_name}: {info}"

    # Otherwise, perform a web search
    print(f"Verifying pricing for unknown service: {service_name}...")
    patterns = [r'free', r'\$\d+', r'INR\s*\d+', r'per month', r'per request', r'per SMS']
    
    for attempt in range(2):
        results = search(f'{service_name} pricing free tier 2025')
        if "Error:" in results:
            continue
            
        # Extract snippets and look for patterns
        snippets = re.findall(r'Snippet: (.*?)\n', results, re.IGNORECASE | re.DOTALL)
        for snippet in snippets:
            # Split into sentences
            sentences = re.split(r'(?<=[.!?])\s+', snippet)
            for sentence in sentences:
                if any(re.search(p, sentence, re.IGNORECASE) for p in patterns):
                    return f"{service_name}: {sentence.strip()}"
    
    return f"{service_name}: pricing varies — check official site"

def run_technical_agent(idea_analysis: str, verdict: dict) -> str:
    """Generates technical R&D report adapted to the project's target market and stack."""
    # 1. Setup LLM
    llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.3)
    
    # 2. Get Knowledge Base Context
    kb_context = retrieve(idea_analysis[:200])

    # 3. Load System Prompt
    prompt_path = Path("prompts/technical_prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        system_prompt_template = f.read()

    # 4. Build dynamic stack string from the universal options
    approved_stack_str = "\n".join([f"- {k.upper()}: {v}" for k, v in UNIVERSAL_TECH_STACK.items()])
    verdict_summary = f"VERDICT: {verdict.get('verdict', 'UNKNOWN')} | Scores: {verdict.get('uniqueness', 0)}/10, {verdict.get('market_gap', 0)}/10"

    synthesis_input = (
        f"AVAILABLE TECH OPTIONS (choose the most appropriate for this project):\n{approved_stack_str}\n\n"
        f"--- PHASE 1: IDEA ANALYSIS ---\n{idea_analysis}\n\n"
        f"--- PHASE 3: VERDICT SUMMARY ---\n{verdict_summary}\n\n"
        f"--- KNOWLEDGE BASE CONTEXT ---\n{kb_context}\n\n"
        "INSTRUCTION: Select the most appropriate tools from the AVAILABLE TECH OPTIONS above "
        "based on the project's target market, geography, and budget constraints described in the idea analysis. "
        "If the project targets India, prefer Indian payment and SMS gateways. "
        "If it targets a global audience, use globally available services. "
        "Justify each tool choice briefly."
    )

    # 5. Get Technical Plan
    print("Synthesizing Technical Requirements Document...")
    messages = [
        SystemMessage(content=system_prompt_template),
        HumanMessage(content=synthesis_input)
    ]
    response = llm.invoke(messages)
    technical_plan = response.content

    # 6. Verify Pricing for mentioned services
    print("Verifying service pricing...")
    # Extract potential service names from the plan
    all_tech_mentions = re.findall(
        r'(Razorpay|Cashfree|Stripe|PayPal|msg91|Fast2SMS|Twilio|Cloudinary|Supabase|Railway|Render|Cyclic|Vercel|MongoDB|PostgreSQL|Firebase|Resend|SendGrid)',
        technical_plan, re.IGNORECASE
    )
    services_to_verify = list(set(all_tech_mentions))
    
    pricing_section = "\n\n---\n## 💰 Service Pricing & Free Tiers\n"
    for service in services_to_verify:
        pricing_info = verify_service_pricing(service)
        pricing_section += f"- {pricing_info}\n"

    final_plan = technical_plan + pricing_section

    # 7. Save Output
    project_slug = get_project_slug(idea_analysis[:100])
    save_output(final_plan, project_slug)

    print(f"Phase 4 complete: Technical R&D saved.")
    return final_plan

def save_output(content: str, project_slug: str) -> str:
    """Saves the technical R&D report."""
    out_dir = Path(f"outputs/{project_slug}")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = out_dir / "technical_rd.md"
    # Format the report using the project's formatter
    formatted = format_report("Technical R&D Report", content)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(formatted)
    
    return str(file_path)

if __name__ == "__main__":
    # Test with dummy inputs
    test_idea = "Idea: AI-powered task manager for remote teams in India."
    test_verdict = {
        "verdict": "BUILD",
        "uniqueness": 7,
        "market_gap": 8,
        "report": "This is a solid idea for the Indian market."
    }
    
    try:
        os.environ["PYTHONPATH"] = "."
        plan = run_technical_agent(test_idea, test_verdict)
        print("\n--- FINAL TECHNICAL PLAN ---")
        print(plan)
    except Exception as e:
        print(f"Error during technical agent test: {e}")
