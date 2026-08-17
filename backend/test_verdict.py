import os
os.environ['PYTHONPATH'] = '.'
from tools.pydantic_models import IdeaOutput, MarketOutput, CompetitorInfo
from agents.verdict_agent import run_verdict_agent

# TEST 1: BAD Idea (generic to-do list) - Expect PIVOT or SKIP
bad_idea = IdeaOutput(
    project_name="Generic To-Do List",
    job_to_be_done="Manage tasks and to-do lists",
)
bad_market = MarketOutput(
    competitors=[
        CompetitorInfo(name="Todoist", url="http://todoist.com", pricing="Free", main_weakness="Too complex", why_users_complain="Hard to use"),
        CompetitorInfo(name="Any.do", url="http://any.do", pricing="Free", main_weakness="Too simple", why_users_complain="Lacks features"),
        CompetitorInfo(name="TickTick", url="http://ticktick.com", pricing="Paid", main_weakness="Clunky", why_users_complain="Bugs"),
        CompetitorInfo(name="Things 3", url="http://things.com", pricing="Paid", main_weakness="Apple only", why_users_complain="No windows")
    ],
    user_complaints_quoted=[
        "It crashes all the time and loses my data", # 1
        "The sync is so slow it's unusable", # 2
        "I hate the new UI update, it's terrible" # 3
    ]
)
print("=== TEST 1: BAD IDEA ===")
res1 = run_verdict_agent(bad_idea, bad_market)
print(f"VERDICT: {res1.verdict}")
print(f"SCORES IN OUTPUT: {res1.scores}")

# TEST 2: GOOD Idea (AI caption generator) - Expect BUILD
good_idea = IdeaOutput(
    project_name="AI Caption Generator for Reels",
    job_to_be_done="Generate engaging captions for Instagram Reels",
)
good_market = MarketOutput(
    competitors=[
        CompetitorInfo(name="CapCut", url="http://capcut.com", pricing="Free", main_weakness="Basic", why_users_complain="Boring text"),
    ],
    user_complaints_quoted=[
        "I need dynamic captions that pop on screen but Capcut is boring",
        "It takes 2 hours to manually add emojis and animations",
        "Auto-captions are always wrong and I have to fix every word manually",
        "There's no easy way to get the exact Alex Hormozi style captions",
        "I hate paying $30/mo for a tool that only does one thing poorly"
    ]
)
print("\n=== TEST 2: GOOD IDEA ===")
res2 = run_verdict_agent(good_idea, good_market)
print(f"VERDICT: {res2.verdict}")
print(f"SCORES IN OUTPUT: {res2.scores}")

