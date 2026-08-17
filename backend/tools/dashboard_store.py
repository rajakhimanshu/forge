from tools.llm_router import safe_print
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime

DB_PATH = Path('./outputs/forge_dashboard.db')


def init_db():
    """Initialize the SQLite database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                idea_summary TEXT DEFAULT '',
                verdict TEXT DEFAULT 'UNKNOWN',
                created_at TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                status TEXT DEFAULT 'Not Started',
                commitment TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                phase_reached INTEGER DEFAULT 0
            )
        ''')
        conn.commit()


# Auto-run on import
init_db()


def save_project(project_name: str, idea_summary: str, verdict: str,
                 phases_completed: int = 5) -> str:
    """Insert a new project row. Returns the new id."""
    project_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute('''
            INSERT INTO projects (id, project_name, idea_summary, verdict,
                                  created_at, last_updated, status, commitment, notes, phase_reached)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (project_id, project_name, idea_summary[:200], verdict,
              now, now, 'Not Started', '', '', phases_completed))
        conn.commit()
    return project_id


def update_status(project_name: str, status: str,
                  commitment: str = '', notes: str = '') -> bool:
    """Find most recent project by name and update its status."""
    valid = {'Not Started', 'In Progress', 'Achieved', 'Abandoned'}
    if status not in valid:
        status = 'Not Started'
    now = datetime.now().isoformat()
    with sqlite3.connect(str(DB_PATH)) as conn:
        cursor = conn.execute('''
            SELECT id FROM projects WHERE project_name = ?
            ORDER BY created_at DESC LIMIT 1
        ''', (project_name,))
        row = cursor.fetchone()
        if not row:
            return False
        project_id = row[0]
        conn.execute('''
            UPDATE projects SET status = ?, commitment = ?, notes = ?, last_updated = ?
            WHERE id = ?
        ''', (status, commitment, notes, now, project_id))
        conn.commit()
    return True

def update_status_by_id(project_id: str, status: str, commitment: str = '', notes: str = '') -> bool:
    """Update status using the unique project ID."""
    valid = {'Not Started', 'In Progress', 'Achieved', 'Abandoned'}
    if status not in valid:
        status = 'Not Started'
    now = datetime.now().isoformat()
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute('''
            UPDATE projects SET status = ?, commitment = ?, notes = ?, last_updated = ?
            WHERE id = ?
        ''', (status, commitment, notes, now, project_id))
        conn.commit()
    return True


def get_all_projects() -> list[dict]:
    """Return all projects sorted: Abandoned first, then In Progress, Not Started, Achieved."""
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute('''
            SELECT * FROM projects
            ORDER BY
                CASE
                    WHEN status = 'Abandoned' THEN 0
                    WHEN status = 'In Progress' THEN 1
                    WHEN status = 'Not Started' THEN 2
                    WHEN status = 'Achieved' THEN 3
                    ELSE 4
                END,
                created_at ASC
        ''')
        rows = cursor.fetchall()

    projects = []
    for row in rows:
        p = dict(row)
        try:
            created_dt = datetime.fromisoformat(p['created_at'])
            p['days_since_created'] = (datetime.now() - created_dt).days
        except Exception:
            p['days_since_created'] = 0
        projects.append(p)
    return projects


def get_summary_stats() -> dict:
    """Return summary statistics."""
    projects = get_all_projects()
    total = len(projects)
    not_started = sum(1 for p in projects if p['status'] == 'Not Started')
    in_progress = sum(1 for p in projects if p['status'] == 'In Progress')
    achieved = sum(1 for p in projects if p['status'] == 'Achieved')
    abandoned = sum(1 for p in projects if p['status'] == 'Abandoned')

    completion_rate = f'{achieved * 100 // total}%' if total > 0 else '0%'

    return {
        'total': total,
        'not_started': not_started,
        'in_progress': in_progress,
        'achieved': achieved,
        'abandoned': abandoned,
        'completion_rate': completion_rate
    }


def format_dashboard_markdown() -> str:
    """Returns a markdown string for display in the Gradio UI."""
    projects = get_all_projects()
    stats = get_summary_stats()

    md = [
        '# 🔨 Forge Founder Dashboard',
        '',
        f'**{stats["total"]} total** | ✅ {stats["achieved"]} achieved | '
        f'📈 {stats["completion_rate"]} rate | 💀 {stats["abandoned"]} abandoned',
        '',
    ]

    if stats['abandoned'] > 0:
        md.append(
            f'> ⚠️ You have **{stats["abandoned"]} abandoned project(s)**. '
            'Before starting something new, ask: what was the real reason each stopped?\n'
        )

    if not projects:
        md.append('_No projects yet. Run your first analysis to get started!_')
        return '\n'.join(md)

    md.extend([
        '| Status | Project | Verdict | Days Ago | Phases |',
        '|--------|---------|---------|----------|--------|',
    ])

    status_emojis = {
        'Achieved': '✅',
        'In Progress': '🔄',
        'Not Started': '⏳',
        'Abandoned': '💀'
    }

    for p in projects:
        emoji = status_emojis.get(p['status'], '⏳')
        name = p['project_name']
        verdict = p['verdict']
        days = p['days_since_created']
        phases = p['phase_reached']
        md.append(f'| {emoji} {p["status"]} | **{name}** | {verdict} | {days}d | {phases}/8 |')

    return '\n'.join(md)


# Legacy compatibility aliases
def load_dashboard() -> list:
    return get_all_projects()


def get_summary() -> dict:
    return get_summary_stats()


def format_dashboard_text() -> str:
    return format_dashboard_markdown()


if __name__ == '__main__':
    # Test with different statuses
    save_project('ForexSync', 'Sync forex calendar to Google Calendar', 'BUILD', 8)
    update_status('ForexSync', 'Abandoned', 'No distribution', 'Could not find users')

    save_project('TITConnect', 'Campus marketplace for TIT Bhopal', 'BUILD', 8)
    update_status('TITConnect', 'In Progress', 'Getting 10 beta users by May 1')

    save_project('Capso', 'AI video captioning with Whisper', 'BUILD', 5)

    save_project('TodoAI', 'AI to-do app', 'SKIP', 3)
    update_status('TodoAI', 'Abandoned', 'Market too saturated')

    safe_print(format_dashboard_markdown())

    projects = get_all_projects()
    safe_print(f'\nFirst project status: {projects[0]["status"]} (should be Abandoned)')
    safe_print(f'DB created at: {DB_PATH}')