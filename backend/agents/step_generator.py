"""
Layer 3 — Environment-Aware Step Generator
============================================
Converts blueprint tasks into typed SETUP + CODING steps using the user's
actual OS, AI CLI, and installed tools. Every terminal command is pre-decided.

Graph position: called by blueprint_node after service_resolver resolves services.
"""
import json
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage
from tools.errors import PipelineError

from tools.llm_router import get_llm, call_with_fallback, build_schema_prompt
from models.env_profile import EnvProfile
from models.build_step import BuildStep, StepType
from models.service_resolution import ServiceBundle

load_dotenv()

# ── OS-specific terminal commands ─────────────────────────────────────────────
TERMINAL_CMDS = {
    "windows": {
        "activate_venv":  ".\\venv\\Scripts\\activate",
        "create_venv":    "python -m venv venv",
        "npm_install":    "npm install",
        "run_server":     "node app.js",
        "open_file":      "notepad",
        "mkdir":          "mkdir",
        "copy_env":       "copy .env.example .env",
        "run_dev":        "npm run dev",
        "python":         "python",
        "pip":            "pip install",
    },
    "mac": {
        "activate_venv":  "source venv/bin/activate",
        "create_venv":    "python3 -m venv venv",
        "npm_install":    "npm install",
        "run_server":     "node app.js",
        "open_file":      "open -a TextEdit",
        "mkdir":          "mkdir -p",
        "copy_env":       "cp .env.example .env",
        "run_dev":        "npm run dev",
        "python":         "python3",
        "pip":            "pip3 install",
    },
    "linux": {
        "activate_venv":  "source venv/bin/activate",
        "create_venv":    "python3 -m venv venv",
        "npm_install":    "npm install",
        "run_server":     "node app.js",
        "open_file":      "nano",
        "mkdir":          "mkdir -p",
        "copy_env":       "cp .env.example .env",
        "run_dev":        "npm run dev",
        "python":         "python3",
        "pip":            "pip3 install",
    },
}

AI_CLI_NAMES = {
    "gemini":      "Gemini CLI — open your terminal and type: gemini",
    "claude_code": "Claude Code — open your terminal and type: claude",
    "cursor":      "Cursor AI Chat — press Ctrl+L to open the AI chat panel",
    "copilot":     "GitHub Copilot Chat — open the Copilot Chat panel in VS Code",
}

# ── Success condition templates per task type ─────────────────────────────────
SUCCESS_CONDITIONS = {
    "auth":      'Server logs "JWT secret loaded. Auth routes ready on /api/auth"',
    "jwt":       'Server logs "JWT secret loaded. Auth routes ready on /api/auth"',
    "otp":       'Postman POST /api/auth/send-otp returns { "status": "sent", "message_id": "..." }',
    "sms":       'Postman POST /api/auth/send-otp returns { "status": "sent", "message_id": "..." }',
    "upload":    'Upload test.jpg — console logs Cloudinary URL starting with https://res.cloudinary.com',
    "storage":   'Upload test.jpg — console logs Cloudinary URL starting with https://res.cloudinary.com',
    "database":  'Server logs "MongoDB connected: cluster0.xxxxx.mongodb.net"',
    "mongodb":   'Server logs "MongoDB connected: cluster0.xxxxx.mongodb.net"',
    "supabase":  'Server logs "Supabase connected" and test SELECT query returns rows',
    "frontend":  'npm run dev — browser at localhost:3000 shows the UI with correct form',
    "payment":   'Razorpay test mode — POST /api/pay returns { "order_id": "order_..." }',
    "razorpay":  'Razorpay test mode — POST /api/pay returns { "order_id": "order_..." }',
    "email":     'POST /api/notify returns { "messageId": "..." } and email arrives in inbox',
    "deploy":    'Railway dashboard shows "Deployed" and the URL returns HTTP 200',
}


def get_success_condition(task_description: str) -> str:
    """Pick a relevant success condition based on keywords in the task description."""
    desc_lower = task_description.lower()
    for keyword, condition in SUCCESS_CONDITIONS.items():
        if keyword in desc_lower:
            return condition
    return "Server starts without errors and returns HTTP 200 on the health check endpoint."


def _build_env_var_list(service_bundle: ServiceBundle) -> list[str]:
    """Extract env var names from the service bundle."""
    if not service_bundle or not service_bundle.services:
        return []
    return [s.env_var_name for s in service_bundle.services if s.env_var_name]


def generate_setup_step(
    step_number: int,
    label: str,
    commands: list[str],
    env: EnvProfile,
    files_created: list[str] = None,
    env_vars_needed: list[str] = None,
) -> BuildStep:
    """Build a SETUP step with OS-specific commands."""
    return BuildStep(
        step_number=step_number,
        step_type=StepType.SETUP,
        label=label,
        commands=commands,
        success_condition=f"Commands complete without error. {label} is ready.",
        time_estimate_minutes=5,
        files_created=files_created or [],
        env_vars_needed=env_vars_needed or [],
    )


def generate_coding_step(
    step_number: int,
    label: str,
    ai_prompt: str,
    task_description: str,
    files_created: list[str] = None,
    env_vars_needed: list[str] = None,
    time_estimate_minutes: int = 20,
) -> BuildStep:
    """Build a CODING step with success condition."""
    return BuildStep(
        step_number=step_number,
        step_type=StepType.CODING,
        label=label,
        ai_prompt=ai_prompt,
        success_condition=get_success_condition(task_description),
        time_estimate_minutes=time_estimate_minutes,
        files_created=files_created or [],
        env_vars_needed=env_vars_needed or [],
    )


def generate_steps_for_blueprint(
    blueprint_output,
    env: EnvProfile,
    service_bundle: ServiceBundle,
) -> list[BuildStep]:
    """
    Convert blueprint tasks into ordered SETUP + CODING steps.
    Each task produces one CODING step; project setup produces SETUP steps.
    """
    if not blueprint_output:
        return []

    cmds = TERMINAL_CMDS[env.os]
    ai_cli_instruction = AI_CLI_NAMES.get(env.ai_cli, "your AI coding assistant")
    env_vars = _build_env_var_list(service_bundle)

    steps: list[BuildStep] = []
    step_num = 1

    # ── SETUP Step 0: Project Initialization ─────────────────────────────────
    init_commands = []
    if not env.node_installed:
        init_commands.append("# Download Node.js from https://nodejs.org/en/download (LTS version)")
    if not env.python_installed:
        init_commands.append("# Download Python from https://python.org/downloads")

    # Project folder + venv
    project_slug = "my-project"
    init_commands += [
        f"{cmds['mkdir']} {project_slug} && cd {project_slug}",
        f"{cmds['create_venv']}",
        f"{cmds['activate_venv']}",
    ]
    steps.append(generate_setup_step(
        step_num, "Project Initialization", init_commands, env
    ))
    step_num += 1

    # ── SETUP Step 1: Install dependencies ───────────────────────────────────
    install_cmds = []
    for svc in (service_bundle.services if service_bundle else []):
        if svc.sdk_install_cmd and "npm install" in svc.sdk_install_cmd:
            install_cmds.append(svc.sdk_install_cmd)
        elif svc.sdk_install_cmd and "pip" in svc.sdk_install_cmd:
            install_cmds.append(svc.sdk_install_cmd)

    if not install_cmds:
        install_cmds = [f"{cmds['npm_install']}"]

    steps.append(generate_setup_step(
        step_num,
        "Install All Dependencies",
        install_cmds,
        env,
        env_vars_needed=env_vars,
    ))
    step_num += 1

    # ── SETUP Step 2: .env file setup ─────────────────────────────────────────
    env_file_lines = []
    for svc in (service_bundle.services if service_bundle else []):
        env_file_lines.append(f"{svc.env_var_name}=your_{svc.env_var_name.lower()}_here")

    if env_file_lines:
        env_file_cmd = (
            f"# Open .env in {cmds['open_file']} and paste:\n"
            + "\n".join(env_file_lines)
        )
        steps.append(generate_setup_step(
            step_num,
            "Configure .env File",
            [f"{cmds['open_file']} .env", env_file_cmd],
            env,
            files_created=[".env"],
            env_vars_needed=env_vars,
        ))
        step_num += 1

    # ── CODING Steps: from blueprint tasks ────────────────────────────────────
    if hasattr(blueprint_output, 'mvp_tasks') and blueprint_output.mvp_tasks:
        for task in blueprint_output.mvp_tasks:
            if task.tier != 'MVP':
                continue

            # Build enriched AI prompt
            enriched_prompt = _enrich_task_prompt(
                task=task,
                env=env,
                service_bundle=service_bundle,
                ai_cli_instruction=ai_cli_instruction,
                env_vars=env_vars,
            )

            steps.append(generate_coding_step(
                step_number=step_num,
                label=task.title,
                ai_prompt=enriched_prompt,
                task_description=task.what_it_does,
                files_created=[task.file_path] if task.file_path else [],
                env_vars_needed=env_vars,
                time_estimate_minutes=_parse_time(task.time_estimate),
            ))
            step_num += 1

            # Add test SETUP step after coding step
            if task.test_command:
                test_cmds = [task.test_command]
                steps.append(generate_setup_step(
                    step_num,
                    f"Test: {task.title}",
                    test_cmds,
                    env,
                ))
                step_num += 1

    return steps


def _parse_time(time_str: str) -> int:
    """Parse '2 hours' or '30 min' into minutes."""
    if not time_str:
        return 20
    ts = time_str.lower()
    if 'hour' in ts:
        try:
            return int(float(ts.split()[0]) * 60)
        except Exception as e:
            raise PipelineError('StepGenerator', f'Step failed: {str(e)}')
    try:
        return int(''.join(c for c in ts if c.isdigit()) or '20')
    except Exception as e:
        raise PipelineError('StepGenerator', f'Step failed: {str(e)}')


def _enrich_task_prompt(
    task,
    env: EnvProfile,
    service_bundle: ServiceBundle,
    ai_cli_instruction: str,
    env_vars: list[str],
) -> str:
    """Enrich a blueprint task's gemini_cli_prompt with env context."""
    services_summary = ""
    if service_bundle and service_bundle.services:
        lines = []
        for svc in service_bundle.services:
            lines.append(
                f"  - {svc.infra_need}: {svc.recommended_service} "
                f"(env var: {svc.env_var_name}, install: {svc.sdk_install_cmd})"
            )
        services_summary = "Configured services:\n" + "\n".join(lines)

    env_var_block = "\n".join(f"  {v}=<from .env>" for v in env_vars) if env_vars else "  (no external services)"

    return f"""Open {ai_cli_instruction} and paste this prompt:

---
You are writing code for a real project. Use ONLY these env variable names:
{env_var_block}

{services_summary}

Task: {task.what_it_does}
File to create: {task.file_path}

{task.gemini_cli_prompt}

Requirements:
- Use the exact env var names listed above (load from process.env or dotenv)
- Add a startup log confirming the feature is ready
- Include error handling for all external API calls
- Do NOT create files other than {task.file_path}
- Write the complete file content only, no explanation
---

Success check: {task.success_check}
Test command:  {task.test_command}
"""
