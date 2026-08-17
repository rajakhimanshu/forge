import os
os.environ['PYTHONPATH'] = '.'
from agents.orchestrator import app
from tools.pydantic_models import IdeaOutput, MarketOutput, CompetitorInfo, ComplaintItem

# Mock inputs for test
good_idea = IdeaOutput(
    project_name="AI Caption Generator for Reels",
    job_to_be_done="Generate engaging captions for Instagram Reels",
    target_persona_name="Instagram Creator",
    pain_score=10
)
good_market = MarketOutput(
    competitors=[
        CompetitorInfo(name="CapCut", url="http://capcut.com", pricing="Free", main_weakness="Basic", why_users_complain="Boring text"),
        CompetitorInfo(name="Veed", url="http://veed.io", pricing="Paid", main_weakness="Slow", why_users_complain="Too slow")
    ],
    user_complaints=[
        ComplaintItem(quote="I need dynamic captions that pop on screen but Capcut is boring", source_url="http://reddit.com/r/1"),
        ComplaintItem(quote="It takes 2 hours to manually add emojis and animations", source_url="http://reddit.com/r/2"),
        ComplaintItem(quote="Auto-captions are always wrong and I have to fix every word manually", source_url="http://reddit.com/r/3"),
        ComplaintItem(quote="There's no easy way to get the exact Alex Hormozi style captions", source_url="http://reddit.com/r/4"),
        ComplaintItem(quote="I hate paying $30/mo for a tool that only does one thing poorly", source_url="http://reddit.com/r/5")
    ]
)

bad_idea = IdeaOutput(
    project_name="Generic To-Do List",
    job_to_be_done="Manage tasks",
    pain_score=2
)
bad_market = MarketOutput(
    competitors=[
        CompetitorInfo(name='A', url='http://a.com', pricing='Free', main_weakness='none', why_users_complain='none'),
        CompetitorInfo(name='B', url='http://b.com', pricing='Free', main_weakness='none', why_users_complain='none'),
        CompetitorInfo(name='C', url='http://c.com', pricing='Free', main_weakness='none', why_users_complain='none'),
        CompetitorInfo(name='D', url='http://d.com', pricing='Free', main_weakness='none', why_users_complain='none'),
    ],
    user_complaints=[
        ComplaintItem(quote="It crashes all the time and loses my data", source_url="http://reddit.com/r/6")
    ]
)

print("=== TEST 1: RUNNING BUILD IDEA ===")
initial_state = {
    'user_idea': 'captions app',
    'idea_output': good_idea,
    'market_output': good_market,
}
# Start execution from verdict task
# Wait, langgraph app.invoke usually starts at the entry point. We can run specific nodes manually.
from agents.orchestrator import run_verdict_node, run_kill_condition_node, route_after_verdict

# Manually step through for TEST 1
state = initial_state.copy()
state.update(run_verdict_node(state))
verdict = state.get('verdict_output')
print("VERDICT:", verdict.verdict)
next_node = route_after_verdict(state)
print("ROUTER SAID TO GO TO:", next_node)
if next_node == 'kill_condition_task':
    state.update(run_kill_condition_node(state))
    kill_out = state.get('kill_condition_output')
    print("KILL EVENT:", kill_out.kill_event)
    print("PROBABILITY:", kill_out.kill_probability)
    print("SURVIVAL MOVE:", kill_out.survival_move)


print("\n=== TEST 2: RUNNING SKIP/PIVOT IDEA ===")
state2 = initial_state.copy()
state2['idea_output'] = bad_idea
state2['market_output'] = bad_market
state2.update(run_verdict_node(state2))
verdict2 = state2.get('verdict_output')
print("VERDICT:", verdict2.verdict)
next_node2 = route_after_verdict(state2)
print("ROUTER SAID TO GO TO:", next_node2)
if next_node2 == 'kill_condition_task':
    state2.update(run_kill_condition_node(state2))
    print("Ran kill condition task!")
else:
    print("Did NOT run kill condition task.")

