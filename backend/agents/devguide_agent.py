import os
import json
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from tools.llm_router import safe_print, get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from tools.output_formatter import get_project_slug

# 1. Load Configuration
load_dotenv()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# 2. TOOL_PROFILES constant
TOOL_PROFILES = {
    'gemini_cli': {
        'name': 'Gemini CLI',
        'open_instruction': 'Open PowerShell, type: gemini',
        'prompt_label': 'GEMINI CLI PROMPT — paste this exactly:',
        'box_open': '┌─────────────────────────────────────────┐',
        'box_close': '└─────────────────────────────────────────┘',
        'save_instruction': 'notepad {filepath}',
        'prompt_suffix': 'Show me the complete file. No explanation.',
    },
    'antigravity': {
        'name': 'Antigravity (Claude Code)',
        'open_instruction': 'Open your terminal, navigate to project folder',
        'prompt_label': 'ANTIGRAVITY PROMPT — type this in Claude Code:',
        'box_open': '┌─────────────────────────────────────────┐',
        'box_close': '└─────────────────────────────────────────┘',
        'save_instruction': 'Claude Code will create the file automatically',
        'prompt_suffix': 'Create this file now.',
    },
    'cursor': {
        'name': 'Cursor',
        'open_instruction': 'Open Cursor, navigate to your project folder',
        'prompt_label': 'CURSOR PROMPT — press Ctrl+K and type:',
        'box_open': '┌─────────────────────────────────────────┐',
        'box_close': '└─────────────────────────────────────────┘',
        'save_instruction': 'Cursor will generate the file in place',
        'prompt_suffix': 'Generate the complete file.',
    },
    'manual': {
        'name': 'Manual (no AI tool)',
        'open_instruction': 'Open your code editor',
        'prompt_label': 'WHAT TO WRITE — follow this specification:',
        'box_open': '┌─────────────────────────────────────────┐',
        'box_close': '└─────────────────────────────────────────┘',
        'save_instruction': 'Save the file to the path shown',
        'prompt_suffix': '',
    },
}

# 3. Helper function for LLM calls
def llm_call(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
    llm = get_llm(temperature=temperature)
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    
    content = response.content
    # Strip markdown code fences
    if content.startswith("```"):
        content = "\n".join(content.split("\n")[1:])
    if content.endswith("```"):
        content = "\n".join(content.split("\n")[:-1])
    
    return content.strip()

# 4. Function: generate_folder_structure
def generate_folder_structure(project_name: str, tech_stack: str, feature_list: list) -> str:
    system_prompt = (
        'You generate ONLY folder and file trees. Every file gets a '
        'one-line comment. Use the exact tech stack provided. Never use generic '
        'names. Format: project/ ├── folder/ │   ├── file.js  # what it does'
    )
    user_prompt = (
        f'Project: {project_name}. Stack: {tech_stack}. '
        f'Features: {", ".join(feature_list[:8])}. Generate the complete folder tree.'
    )
    return llm_call(system_prompt, user_prompt)

# 5. Function: generate_env_file
def generate_env_file(tech_stack: str) -> str:
    system_prompt = (
        'Generate a .env.example file. Every variable needs a comment '
        'explaining what it is and where to get it. Include generation commands '
        'for secrets.'
    )
    user_prompt = f'Tech stack: {tech_stack}. Generate the complete .env.example.'
    return llm_call(system_prompt, user_prompt)

# --- Project Type Detection & Feature Groups ---
def detect_project_type(idea_analysis: str) -> str:
    """Detects the type of project from the idea analysis text."""
    text = idea_analysis.lower()

    # AI/media tools: captioning, transcription, audio/video processing
    ai_media_signals = ['caption', 'transcri', 'subtitle', 'whisper', 'audio', 'video processing', 'speech-to-text', 'stt', 'ai']
    if sum(1 for k in ai_media_signals if k in text) >= 2:
        return 'ai_media_tool'

    # Campus platform: require 3+ dedicated campus-context signals to avoid false positives
    campus_signals = ['college', 'campus', 'university', 'inter-college', 'hostel', 'dormitory', 'student club', 'academic']
    campus_hits = sum(1 for k in campus_signals if k in text)
    if campus_hits >= 3:
        return 'campus_platform'

    if any(k in text for k in ['b2b', 'saas', 'enterprise', 'business software', 'crm', 'erp']):
        return 'b2b_saas'
    if any(k in text for k in ['marketplace', 'buy and sell', 'ecommerce', 'listing']):
        return 'consumer_marketplace'
    if any(k in text for k in ['productivity', 'habit', 'task', 'time tracking', 'note', 'focus', 'discipline']):
        return 'productivity_tool'
    return 'general_startup'

FEATURE_GROUPS_BY_TYPE = {
    'campus_platform': {
        'setup': ['Project setup', 'Node.js/Python server', 'Database connection', 'Environment variables', 'Git initialization'],
        'auth': ['Student registration', 'Login endpoint', 'JWT tokens', 'OTP verification', 'Student verification', 'Auth middleware'],
        'backend_models': ['User model', 'Listing model', 'Notes model', 'Service model', 'Announcement model', 'Team model'],
        'api_routes': ['Listings API', 'Notes API', 'Services API', 'Announcements API', 'Teams API', 'Search API'],
        'frontend': ['React/Flutter app setup', 'Auth pages', 'Marketplace page', 'Notes hub page', 'Announcements page', 'User profile page'],
        'payments_sms': ['Payment gateway integration', 'OTP/SMS service', 'File upload storage'],
        'testing_deploy': ['API testing', 'Frontend + Backend deploy', 'Environment variables setup', 'Final checks'],
    },
    'b2b_saas': {
        'setup': ['Project setup', 'Backend server', 'Database schema', 'Auth config', 'Environment variables'],
        'auth': ['User signup', 'Organization/Team setup', 'RBAC (Roles)', 'JWT/Session auth', 'Email verification'],
        'backend_models': ['User model', 'Organization model', 'Subscription model', 'Project/Task model', 'Audit log model'],
        'api_routes': ['Org management API', 'Billing API', 'Resource API', 'Reporting API', 'User management API'],
        'frontend': ['Dashboard layout', 'Org settings', 'Resource management', 'Billing/Plans page', 'User directory'],
        'payments_sms': ['Payment gateway integration', 'Email notifications', 'Webhooks'],
        'testing_deploy': ['Unit/Integration tests', 'CI/CD pipeline', 'Cloud deployment'],
    },
    'ai_media_tool': {
        'setup': ['Project setup', 'Processing engine setup', 'Storage config', 'Environment variables'],
        'auth': ['User registration', 'API key management', 'Usage quotas', 'Auth middleware'],
        'backend_models': ['User model', 'Media item model', 'Processing job model', 'Result model'],
        'api_routes': ['Upload API', 'Processing trigger API', 'Status polling API', 'Result download API'],
        'frontend': ['Upload interface', 'Media player/viewer', 'Job status dashboard', 'Export options'],
        'ai_integration': ['LLM/AI Model integration', 'Media processing pipeline', 'Processing engine setup'],
        'testing_deploy': ['GPU/Compute setup', 'Storage scaling', 'Deployment'],
    },
    'productivity_tool': {
        'setup': ['Project setup', 'Core server', 'Database setup', 'Config', 'Environment variables'],
        'auth': ['User auth', 'Session management', 'OAuth integrations', 'Auth routes'],
        'backend_models': ['User model', 'Core item model', 'Activity/Log model', 'Settings model'],
        'api_routes': ['Core feature API', 'Sync API', 'Analytics API', 'User API'],
        'frontend': ['Main dashboard', 'Core feature UI', 'Analytics view', 'Settings page'],
        'extras': ['Reminders/Notifications', 'Third-party integrations', 'Export features'],
        'testing_deploy': ['Final testing', 'Deployment prep', 'Cloud launch'],
    },
    'general_startup': {
        'setup': ['Project setup', 'Core server', 'Database setup', 'Config', 'Environment variables'],
        'auth': ['User auth', 'Session management', 'Security headers', 'Auth routes'],
        'backend_models': ['User model', 'Core data model 1', 'Core data model 2', 'Notification model'],
        'api_routes': ['Core feature API 1', 'Core feature API 2', 'User API', 'Search API'],
        'frontend': ['Main dashboard', 'Core feature UI 1', 'Core feature UI 2', 'Settings page'],
        'extras': ['Email/SMS notifications', 'File storage', 'External API integration'],
        'testing_deploy': ['Final testing', 'Deployment prep', 'Cloud launch'],
    }
}

DEFAULT_FEATURES_BY_TYPE = {
    'campus_platform': [
        'User Registration and Verification',
        'Student Marketplace (Buy/Sell/Rent Items)',
        'Notes and Resource Sharing',
        'Academic Services Marketplace',
        'Team Formation and Project Collaboration',
        'Campus Announcements and Events',
        'User Profiles and Ratings',
        'Search and Filters',
        'Notifications (OTP/Push)',
        'Payment Integration',
    ],
    'b2b_saas': [
        'Multi-tenant Organization Management',
        'Role-Based Access Control (RBAC)',
        'Subscription and Billing Management',
        'Real-time Dashboard Analytics',
        'Automated Reporting and Exports',
        'Team Collaboration and Comments',
        'API Access and Integrations',
        'Activity Logs and Auditing',
        'Custom Domain Support',
        'Notification Center',
    ],
    'ai_media_tool': [
        'High-speed Media Upload and Storage',
        'AI-driven Processing Pipeline',
        'Job Queue and Status Tracking',
        'Interactive Results Preview',
        'Batch Processing Capability',
        'API Key and Usage Management',
        'Downloadable AI Insights/Exports',
        'Custom Model Tuning Options',
        'Collaborative Project Spaces',
        'Versioning and History',
    ],
    'productivity_tool': [
        'User Onboarding and Profiles',
        'Core Habit/Task Management',
        'Progress Tracking and Streaks',
        'Analytics and Insights Dashboard',
        'Reminders and Notifications',
        'Third-party App Integrations',
        'Export and Sharing Features',
        'Offline Mode',
        'Mobile-responsive UI',
        'Settings and Customization',
    ],
    'general_startup': [
        'User Onboarding and Profiles',
        'Core Functionality Module 1',
        'Core Functionality Module 2',
        'Search and Discovery Engine',
        'Real-time Notifications',
        'Data Visualization and Reports',
        'Payment/Subscription Integration',
        'Settings and Customization',
        'Mobile-responsive UI',
        'Security and Performance Monitoring',
    ]
}

BATCH_TO_GROUP = {
    (1, 5):   'setup',
    (6, 10):  'auth',
    (11, 15): 'backend_models',
    (16, 20): 'api_routes',
    (21, 25): 'frontend',
    (26, 28): 'payments_sms',
    (29, 30): 'testing_deploy',
}

def generate_task_batch(task_start: int, task_end: int,
    project_name: str, tech_stack: str, features: list,
    tool_profile: dict, project_type: str = 'general_startup') -> str:

    # Determine which group this batch belongs to
    batch_key = (task_start, task_end)
    type_groups = FEATURE_GROUPS_BY_TYPE.get(project_type, FEATURE_GROUPS_BY_TYPE['general_startup'])
    
    # Map batch keys to group names, or fallback to chronological list
    group_names = list(type_groups.keys())
    batch_index = list(BATCH_TO_GROUP.keys()).index(batch_key) if batch_key in BATCH_TO_GROUP else 0
    group = group_names[batch_index] if batch_index < len(group_names) else group_names[-1]
    
    group_tasks = type_groups.get(group, [])

    # Pick relevant features from the project's actual feature list
    relevant = [f for f in features if any(
        keyword.lower() in f.lower()
        for keyword in ['auth', 'user', 'register', 'login', 'profile',
                        'marketplace', 'listing', 'note', 'service',
                        'announcement', 'team', 'payment', 'search', 'ai', 'process']
    )][:5]
    feature_context = ', '.join(relevant) if relevant else ', '.join(group_tasks[:3])

    tool_name = tool_profile['name']
    prompt_label = tool_profile['prompt_label']
    prompt_suffix = tool_profile['prompt_suffix']
    save_instruction = tool_profile['save_instruction']

    # Load base system prompt from file
    prompt_file = Path("prompts/devguide_prompt_base.txt")
    if prompt_file.exists():
        with open(prompt_file, "r", encoding="utf-8") as f:
            base_prompt = f.read()
    else:
        base_prompt = "You are an expert developer. Write tasks in the specified format."

    system_prompt = base_prompt.format(
        project_name=project_name,
        tool_name=tool_name,
        prompt_label=prompt_label,
        prompt_suffix=prompt_suffix,
        save_instruction=save_instruction
    )
    
    # Ensure project name is explicitly set if not handled by .format() (in case placeholders missing)
    if "{project_name}" not in base_prompt:
        system_prompt = f"You are building {project_name}.\n\n" + system_prompt

    user_prompt = f'''Project: {project_name}
Tech stack: {tech_stack}
This batch covers: {group} features
Key features to implement: {feature_context}
Generate tasks {task_start} through {task_end}.
Each task must create a DIFFERENT file specific to {project_name}.
Focus ONLY on {group} — setup, auth, models, routes, frontend, payments, or testing.
Do NOT generate optimization or cleanup tasks — those come after the app is built.
Use {tool_name} prompt format inside the box.'''

    return llm_call(system_prompt, user_prompt, temperature=0.3)
# -----------------------------------------------

# 7. Function: generate_deployment_guide
def generate_deployment_guide(project_name: str, tech_stack: str, tool_profile: dict) -> str:
    system_prompt = (
        'You generate a step-by-step deployment guide tailored to the provided tech stack. '
        'Include exact commands for backend and frontend deployment, '
        'environment variable setup, and domain/DNS configuration. '
        'If the stack uses Railway, include Railway CLI commands. '
        'If the stack uses Vercel, include Vercel CLI commands. '
        'If the stack uses AWS/GCP/Render, include the appropriate commands for that platform. '
        'Default to Railway (backend) + Vercel (frontend) if the stack does not specify hosting.'
    )
    user_prompt = f'Project: {project_name}. Stack: {tech_stack}. Generate the complete deployment guide.'
    return llm_call(system_prompt, user_prompt)

# Helper functions for run_devguide_agent
def extract_tech_stack(technical_rd: str) -> str:
    """Extracts the tech stack from the technical R&D report."""
    if not technical_rd:
        return "Node.js, Express, MongoDB, React (Generic Fallback)"
        
    # Try common headers
    for header in ["Tech Stack Summary", "Chosen Tech Stack", "Recommended Stack", "Core Tech Stack"]:
        if header.lower() in technical_rd.lower():
            try:
                # Get text after header until next major header or double newline
                after_header = re.split(header, technical_rd, flags=re.IGNORECASE)[1].strip()
                # Take first 500 chars or until next header
                summary = re.split(r'\n#{1,3}\s', after_header)[0].strip()
                # If too long, take first few lines
                if len(summary) > 500:
                    summary = "\n".join(summary.split("\n")[:10])
                return summary
            except IndexError:
                continue
                
    # Fallback to scanning for keywords if no header found
    known_tech = ['react', 'vue', 'angular', 'next.js', 'node', 'express', 'fastapi', 'flask', 'django', 'spring', 'mongodb', 'postgresql', 'supabase', 'firebase', 'sqlite', 'redis', 'docker', 'aws', 'vercel', 'railway', 'flutter', 'react native', 'swift', 'kotlin']
    found = [t.title() for t in known_tech if t.lower() in technical_rd.lower()]
    if found:
        return ", ".join(list(set(found))[:8])
        
    return "Full-stack Web Architecture"

def extract_features_from_context(project_context: dict, project_type: str = 'general_startup') -> list:
    features = []
    tech_rd = project_context.get('technical_rd', '')
    idea = project_context.get('idea_analysis', '')

    # Try extracting from technical_rd FEATURE: pattern
    feature_matches = re.findall(
        r'FEATURE[:\s]+([^\n]+)',
        tech_rd, re.IGNORECASE)
    features.extend([f.strip() for f in feature_matches if f.strip()])

    # Try numbered list pattern: '1. **User Authentication**'
    numbered = re.findall(
        r'\d+\.\s+\*{0,2}([A-Z][^\n*]+)\*{0,2}',
        tech_rd + idea)
    features.extend([f.strip() for f in numbered if len(f.strip()) > 5])

    # Deduplicate preserving order
    seen = set()
    unique = []
    for f in features:
        fl = f.lower()
        if fl not in seen:
            seen.add(fl)
            unique.append(f)

    # If still empty, use type-specific defaults
    if not unique:
        unique = DEFAULT_FEATURES_BY_TYPE.get(project_type, DEFAULT_FEATURES_BY_TYPE['general_startup'])
        
    return unique[:15]  # max 15 features

# 8. Main Function: run_devguide_agent
def run_devguide_agent(project_context: dict, tool_name: str = 'gemini_cli', team_size: int = 1) -> str:
    tool_profile = TOOL_PROFILES.get(tool_name, TOOL_PROFILES['gemini_cli'])
    
    idea_analysis = project_context.get('idea_analysis', '')
    technical_rd = project_context.get('technical_rd', '')
    project_slug = project_context.get('project_slug', 'my-startup')
    
    # 0. Detect Project Type
    project_type = detect_project_type(idea_analysis)
    safe_print(f"Detected project type: {project_type}")

    # --- FIX 1: Enhanced project name extraction ---
    project_name = project_context.get('project_name')
    if not project_name:
        # 2. Check idea_analysis for patterns like 'called TITConnect' or 'named CampusConnect'
        name_match = re.search(r'(?:called|named|platform for)\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)', idea_analysis)
        if name_match:
            project_name = name_match.group(1).strip()
    
    if not project_name:
        # 3. Check technical_rd for project name mentions
        name_match_rd = re.search(r'(?:called|named|platform for)\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)', technical_rd)
        if name_match_rd:
            project_name = name_match_rd.group(1).strip()

    if not project_name:
        # 4. FALLBACK: use first meaningful noun from idea_analysis
        skip_words = {'i', 'am', 'a', 'an', 'the', 'is', 'we', 'my', 'our', 'to', 'for', 'and', 'in', 'at', 'of', 'startup', 'idea', 'project'}
        words = re.findall(r'\b\w+\b', idea_analysis.lower())
        meaningful = [w for w in words if w not in skip_words and len(w) > 3]
        if meaningful:
            project_name = meaningful[0].title() + "System"
    
    if not project_name:
        # 5. Default based on slug or generic
        project_name = project_slug.replace('-', ' ').title() if project_slug != 'my-startup' else "VisionaryProject"
    # -----------------------------------------------

    tech_stack = extract_tech_stack(technical_rd)
    feature_list = extract_features_from_context(project_context, project_type)
    
    # Header
    header = (
        f"# {project_name} - Development Guide\n"
        f"Generated: {datetime.now().strftime('%d %B %Y')}\n"
        f"Project Type: {project_type.replace('_',' ').title()}\n"
        f"Tool Profile: {tool_profile['name']}\n\n"
        "---"
    )
    
    safe_print("Generating Folder Structure...")
    folder_structure = "## 1. Folder Structure\n" + generate_folder_structure(project_name, tech_stack, feature_list)
    
    safe_print("Generating .env.example...")
    env_file = "## 2. Environment Variables\n" + generate_env_file(tech_stack)
    
    # Task Batches
    safe_print("Generating Task Batches...")
    tasks = "## 3. Implementation Tasks\n"
    batch_ranges = list(BATCH_TO_GROUP.keys())
    
    # Divide features among batches (roughly)
    f_chunks = [feature_list[i:i + 3] for i in range(0, len(feature_list), 3)]
    
    for i, (start, end) in enumerate(batch_ranges):
        safe_print(f"  Batch {start}-{end}...")
        relevant_features = f_chunks[i] if i < len(f_chunks) else ["Final cleanup and optimization"]
        tasks += generate_task_batch(start, end, project_name, tech_stack, relevant_features, tool_profile, project_type)
    
    safe_print("Generating Deployment Guide...")
    deployment = "## 4. Deployment Guide\n" + generate_deployment_guide(project_name, tech_stack, tool_profile)
    
    sections = [header, folder_structure, env_file, tasks, deployment]
    return "\n\n---\n\n".join(sections)

# 9. Function: save_devguide
def save_devguide(content: str, project_slug: str, tool_name: str) -> str:
    output_path = Path(f"outputs/{project_slug}/devguide_{tool_name}.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return str(output_path)

# 10. if __name__ == '__main__': test
if __name__ == '__main__':
    dummy_context = {
        'project_slug': 'ai-report-generator',
        'idea_analysis': 'An AI-powered tool that auto-generates weekly engineering team reports from Git commits and Jira tickets.',
        'technical_rd': 'FEATURE: GitHub API Integration\nFEATURE: Report Generation\nFEATURE: Dashboard\nTech Stack Summary: Next.js, FastAPI, Supabase, Railway, Vercel'
    }
    safe_print("Testing devguide_agent standalone...")
    try:
        # Note: This will only work if Ollama is running locally
        # Otherwise it will timeout or fail connection
        guide = run_devguide_agent(dummy_context, 'gemini_cli')
        safe_print("\n--- TEST RESULT PREVIEW ---")
        safe_print("\n".join(guide.split("\n")[:30]))
    except Exception as e:
        safe_print(f"Test run failed (expected if Ollama is offline): {e}")
