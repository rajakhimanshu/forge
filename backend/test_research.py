import os
import json
os.environ['PYTHONPATH'] = '.'
from tools.pydantic_models import IdeaOutput
from agents.research_agent import run_research_agent

idea_text = 'A platform that generates captions for Instagram Reels'
idea_output = IdeaOutput(
    project_name='ReelCap',
    job_to_be_done='Generate captions for Instagram Reels',
    target_persona_name='Instagram Creator',
)

print('Running research agent...')
res = run_research_agent(idea_output, idea_text)

print("\n\n=== RESEARCH RAW OUTPUT DUMP ===")
print(res.model_dump_json(indent=2))
