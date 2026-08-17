"""
Test scoring logic for the 3 FORGE verification cases.
No API calls -- tests pure Python deterministic scoring only.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from agents.verdict_agent import score_idea

def check(label, condition, detail=""):
    tag = "  PASS" if condition else "  FAIL"
    suffix = f": {detail}" if detail else ""
    print(f"{tag} -- {label}{suffix}")
    return condition

# TEST 1: Bad idea -- no pain signal
print("\n=== TEST 1: Another basic to-do list app (should -> SKIP) ===")
data1 = {
    "user_complaints": [],
    "competitors": [
        {"url": "http://todoist.com",   "is_funded": True},
        {"url": "http://notion.so",     "is_funded": True},
        {"url": "http://ticktick.com",  "is_funded": True},
    ]
}
s1 = score_idea(data1)
print(f"  Scores: {s1}")
check("market_proof == 0", s1["market_proof"] == 0, str(s1["market_proof"]))
check("competition == 5 (3 funded -> saturated)", s1["competition"] == 5, str(s1["competition"]))
check("Hard SKIP fires (market_proof == 0)", s1["market_proof"] == 0)

# TEST 2: Saturated market, weak pain signal
print("\n=== TEST 2: AI chatbot for customer support (should -> PIVOT) ===")
data2 = {
    "user_complaints": [
        {"quote": "The bot always gives wrong answers to my tickets", "source_url": "http://reddit.com/r/1"},
        {"quote": "Setup took weeks and still not working properly", "source_url": "http://reddit.com/r/2"},
    ],
    "competitors": [
        {"url": "http://intercom.com",   "is_funded": True},
        {"url": "http://zendesk.com",    "is_funded": True},
        {"url": "http://freshdesk.com",  "is_funded": True},
        {"url": "http://drift.com",      "is_funded": True},
    ]
}
s2 = score_idea(data2)
print(f"  Scores: {s2}")
check("market_proof == 8 (2 complaints)", s2["market_proof"] == 8, str(s2["market_proof"]))
check("competition == 5 (4 funded -> saturated)", s2["competition"] == 5, str(s2["competition"]))
check("Hard PIVOT fires (competition==5 and market_proof<16)", s2["competition"] == 5 and s2["market_proof"] < 16)

# TEST 3: Real niche idea -- clear pain, moderate competition
print("\n=== TEST 3: Hindi-English Reels caption generator (should -> BUILD) ===")
data3 = {
    "user_complaints": [
        {"quote": "CapCut captions are never accurate for Hindi-English mixed speech", "source_url": "http://reddit.com/r/1"},
        {"quote": "I spend 2 hours manually fixing auto-captions for every Reel I post", "source_url": "http://reddit.com/r/2"},
        {"quote": "No tool supports Hinglish switching in captions at all", "source_url": "http://reddit.com/r/3"},
        {"quote": "SubMagic does not understand Indian accent speech to text properly", "source_url": "http://reddit.com/r/4"},
        {"quote": "Captions.ai has no Hindi support whatsoever, unusable for my audience", "source_url": "http://reddit.com/r/5"},
    ],
    "competitors": [
        {"url": "http://capcut.com",    "is_funded": True},
        {"url": "http://submagic.co",   "is_funded": False},
    ]
}
s3 = score_idea(data3)
print(f"  Scores: {s3}")
check("market_proof == 25 (5 complaints)", s3["market_proof"] == 25, str(s3["market_proof"]))
check("competition == 15 (2 real, 1 funded -> competitive)", s3["competition"] == 15, str(s3["competition"]))
check("total >= 30 (passes into LLM zone)", s3["total"] >= 30, str(s3["total"]))
check("No hard SKIP fires", s3["market_proof"] != 0)
check("No hard PIVOT fires", s3["competition"] != 5)

# MODEL CHECK: CompetitorInfo.is_funded field
print("\n=== MODEL CHECK: CompetitorInfo.is_funded field ===")
from tools.pydantic_models import CompetitorInfo
try:
    c = CompetitorInfo(
        name="TestCo",
        url="http://testco.com",
        pricing="Free",
        main_weakness="Slow",
        why_users_complain="Too slow",
        is_funded=True
    )
    check("CompetitorInfo accepts is_funded=True", c.is_funded == True, str(c.is_funded))
    c2 = CompetitorInfo(
        name="TestCo2",
        url="http://testco2.com",
        pricing="Free",
        main_weakness="Slow",
        why_users_complain="Too slow"
    )
    check("CompetitorInfo defaults is_funded=False", c2.is_funded == False, str(c2.is_funded))
except Exception as e:
    print(f"  FAIL -- CompetitorInfo model error: {e}")

print("\n=== DONE ===\n")
