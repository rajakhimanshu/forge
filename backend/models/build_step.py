from pydantic import BaseModel
from typing import Literal, List
from enum import Enum


class StepType(str, Enum):
    SETUP = "setup"    # terminal commands — no AI needed
    CODING = "coding"  # paste into AI CLI


class BuildStep(BaseModel):
    """One step (SETUP or CODING) in the build guide."""
    step_number: int
    step_type: StepType
    label: str
    commands: List[str] = []      # for SETUP steps
    ai_prompt: str = ""           # for CODING steps
    success_condition: str = ""
    time_estimate_minutes: int = 15
    files_created: List[str] = []
    env_vars_needed: List[str] = []
