"""
Layer 4 — Hyper-Specific Prompt Engineer
==========================================
Rewrites every CODING STEP prompt to include:
  - Exact file path to create/edit
  - All env var names from the resolved service bundle
  - Project folder structure already created
  - Concrete success condition tied to an actual log line or test output
  - Inline error handling requirement for all external API calls

Called after step_generator produces BuildStep list.
"""
from tools.llm_router import safe_print
from models.build_step import BuildStep, StepType
from models.service_resolution import ServiceBundle

# ── Prompt template ───────────────────────────────────────────────────────────
PROMPT_TEMPLATE = """You are writing code for this exact project:

Project root: {project_root}

Files already created:
{existing_files}

Environment variables available in .env:
{env_vars}

Services already configured:
{services_summary}

Task: {task_description}
File to create or edit: {target_file}

Requirements:
- Import ONLY from packages already in requirements.txt or package.json
- Use the EXACT env var names listed above (load with dotenv/process.env)
- Add a startup log: console.log("{success_log_line}") or safe_print("{success_log_line}")
- Include inline error handling for ALL external API calls (try/catch or try/except)
- Do NOT create any files other than {target_file}
- Write ONLY the complete file content. No explanation. No markdown fences.
- Start with the import statements. End with the last closing bracket or statement.

Success condition: {success_condition}
"""

# ── Success condition map (task type → condition) ─────────────────────────────
SUCCESS_CONDITION_MAP = {
    "auth":     'Server logs "JWT secret loaded. Auth routes ready on /api/auth"',
    "jwt":      'Server logs "JWT secret loaded. Auth routes ready on /api/auth"',
    "register": 'POST /api/auth/register returns { "token": "eyJ..." } with HTTP 201',
    "otp":      'Postman POST /api/auth/send-otp returns { "status": "sent", "message_id": "..." }',
    "sms":      'Postman POST /api/auth/send-otp returns { "status": "sent", "message_id": "..." }',
    "cloudinary": 'Upload test.jpg — console logs Cloudinary URL starting with https://res.cloudinary.com',
    "upload":   'Upload test.jpg — console logs Cloudinary URL starting with https://res.cloudinary.com',
    "storage":  'Upload test.jpg — console logs Cloudinary URL starting with https://res.cloudinary.com',
    "database": 'Server logs "MongoDB connected: cluster0.xxxxx.mongodb.net"',
    "mongodb":  'Server logs "MongoDB connected: cluster0.xxxxx.mongodb.net"',
    "supabase": 'Supabase client init logs "Connected" and test query returns rows',
    "login":    'npm run dev — browser at localhost:3000 shows Login form with email + OTP fields',
    "frontend": 'npm run dev — browser at localhost:3000 shows the correct UI',
    "payment":  'Razorpay test mode — POST /api/pay returns { "order_id": "order_..." }',
    "razorpay": 'Razorpay test mode — POST /api/pay returns { "order_id": "order_..." }',
    "email":    'POST /api/notify sends email and returns { "messageId": "..." }',
    "deploy":   'Railway dashboard shows "Deployed" — public URL returns HTTP 200',
    "test":     'pytest tests/ -v shows all tests PASSED',
    "profile":  'GET /api/profile returns user object with { "id": "...", "name": "..." }',
    "listing":  'GET /api/listings returns array with at least one listing object',
    "search":   'GET /api/search?q=test returns filtered results within 200ms',
}


def get_success_condition(task_label: str, task_description: str) -> str:
    """Return the best success condition based on task keywords."""
    combined = (task_label + " " + task_description).lower()
    for keyword, condition in SUCCESS_CONDITION_MAP.items():
        if keyword in combined:
            return condition
    return "Server starts without error and returns HTTP 200 on the health check endpoint."


def get_success_log_line(task_label: str, task_description: str) -> str:
    """Return a console.log line that signals this feature is working."""
    combined = (task_label + " " + task_description).lower()
    if "auth" in combined or "jwt" in combined:
        return "JWT auth loaded — /api/auth routes ready"
    if "otp" in combined or "sms" in combined:
        return "OTP service ready — Fast2SMS connected"
    if "upload" in combined or "cloudinary" in combined or "storage" in combined:
        return "File upload ready — Cloudinary connected"
    if "database" in combined or "mongodb" in combined:
        return "Database connected — MongoDB ready"
    if "payment" in combined or "razorpay" in combined:
        return "Payment gateway ready — Razorpay test mode"
    if "email" in combined:
        return "Email service ready — transactional emails enabled"
    if "deploy" in combined:
        return "Server deployed — health check passing"
    return f"{task_label} — feature ready"


def summarise_services(bundle: ServiceBundle) -> str:
    """Produce a compact services summary for prompt injection."""
    if not bundle or not bundle.services:
        return "No external services resolved yet."
    lines = []
    for svc in bundle.services:
        lines.append(
            f"  • {svc.infra_need}: {svc.recommended_service}\n"
            f"    Env var: {svc.env_var_name}\n"
            f"    Install: {svc.sdk_install_cmd}\n"
            f"    Free tier: {svc.current_free_tier}"
        )
    return "\n".join(lines)


def rewrite_prompt(task: dict, state: dict) -> str:
    """
    Rewrite a generic task prompt into a hyper-specific CODING STEP prompt.

    task dict keys: description, file, success_log (all strings)
    state dict keys: project_root, created_files (list), service_bundle (ServiceBundle)
    """
    service_bundle: ServiceBundle = state.get("service_bundle")
    env_vars = []
    if service_bundle and service_bundle.services:
        env_vars = [s.env_var_name for s in service_bundle.services if s.env_var_name]

    task_description = task.get("description", "")
    target_file = task.get("file", "")
    success_log = task.get("success_log", get_success_log_line(target_file, task_description))

    return PROMPT_TEMPLATE.format(
        project_root=state.get("project_root", "./my-project"),
        existing_files="\n".join(
            f"  - {f}" for f in state.get("created_files", [])
        ) or "  (start of project — no files yet)",
        env_vars="\n".join(f"  {v}" for v in env_vars) or "  (no external services configured)",
        services_summary=summarise_services(service_bundle),
        task_description=task_description,
        target_file=target_file,
        success_log_line=success_log,
        success_condition=get_success_condition(target_file, task_description),
    )


def enrich_build_steps(state: dict) -> dict:
    """
    LangGraph node — rewrites all CODING step prompts in state['build_steps']
    to be hyper-specific using service bundle + project context.

    Reads:  state['build_steps'], state['service_bundle'], state['project_slug']
    Writes: state['build_steps'] (updated ai_prompt for CODING steps)
    """
    build_steps: list[BuildStep] = state.get('build_steps', [])
    if not build_steps:
        safe_print("[PROMPT ENGINEER] No build_steps in state — skipping.")
        return state

    service_bundle: ServiceBundle = state.get('service_bundle')
    project_slug = state.get('project_slug', 'my-project')

    # Track files created as we walk through steps
    created_files: list[str] = []
    enriched: list[BuildStep] = []

    for step in build_steps:
        if step.step_type == StepType.CODING and step.files_created:
            # Rewrite the AI prompt with full context
            task = {
                "description": step.label,
                "file": step.files_created[0] if step.files_created else "",
                "success_log": get_success_log_line(step.label, step.ai_prompt[:100]),
            }
            rich_state = {
                "project_root": f"./{project_slug}",
                "created_files": list(created_files),
                "service_bundle": service_bundle,
            }
            step.ai_prompt = rewrite_prompt(task, rich_state)
            step.success_condition = get_success_condition(step.label, task["description"])

        # Update created files tracker
        created_files.extend(step.files_created)
        enriched.append(step)

    safe_print(f"[PROMPT ENGINEER] [OK] Enriched {len(enriched)} build steps with exact context.")
    state['build_steps'] = enriched
    return state