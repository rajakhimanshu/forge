from pydantic import BaseModel
from typing import Literal


class EnvProfile(BaseModel):
    """User's development environment profile captured at pipeline start."""
    os: Literal['windows', 'mac', 'linux'] = 'windows'
    gpu: str = 'none'            # 'rtx2050' | 'rtx3060' | 'none' | 'mac_m_series'
    ai_cli: Literal['gemini', 'claude_code', 'cursor', 'copilot'] = 'gemini'
    experience: Literal['beginner', 'intermediate', 'advanced'] = 'intermediate'
    node_installed: bool = False
    python_installed: bool = True
