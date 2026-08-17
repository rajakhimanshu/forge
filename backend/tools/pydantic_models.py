from tools.llm_router import safe_print
from pydantic import BaseModel, Field, model_validator, field_validator
from typing import Literal, Optional, List, Annotated
from datetime import datetime


# ── Shared sub-models ─────────────────────────────────────────────────────────

class GraveyardExample(BaseModel):
    product_name: str
    what_they_built: str
    why_they_died: str
    lesson: str = ""
    source_url: Optional[str] = None

    @field_validator('source_url', mode='before')
    @classmethod
    def graveyard_source_check(cls, v):
        return v


class CompetitorPricingDetail(BaseModel):
    competitor_name: str = ""
    free_tier_limits: str = ""
    paid_tiers: List[str] = Field(default_factory=list)

class CompetitorInfo(BaseModel):
    name: str = ""
    url: str = ""
    pricing: str = ""
    pricing_model: str = ""
    monthly_traffic_estimate: str = ""
    main_weakness: str = ""
    why_users_complain: str = ""
    why_users_leave: str = ""
    regional_presence: str = ""
    is_funded: bool = False  # True if VC, YC, Series A/B evidence found in search

    @field_validator('url', mode='before')
    @classmethod
    def url_must_be_real(cls, v):
        # Soften: accept empty or placeholder URLs to avoid killing the whole competitor list
        if not v or not str(v).startswith('http'):
            return ''
        return v


class CommunityInfo(BaseModel):
    platform: str = ""
    name_or_url: str = ""
    why_target_users_are_here: str = ""
    best_post_time: str = ""
    red_flag: Optional[str] = None


# ── IdeaOutput — Extended with Layer 1 fields ─────────────────────────────────

class IdeaOutput(BaseModel):
    # ── Error state ─────────────────────────────────────────────────────────
    failed: bool = False
    error: bool = False
    error_message: str = ""
    # ── Core fields ──────────────────────────────────────────────────────────
    project_name: str = ""
    job_to_be_done: str = ""
    primary_friction: str = ""
    target_persona_name: str = ""
    target_persona_description: str = ""
    pain_score: int = 0
    pain_reasoning: str = ""
    ai_native_potential: str = ""
    market_size_estimate: str = ""
    is_universal_problem: bool = False
    # ── Layer 1 upgrade fields ────────────────────────────────────────────────
    regional_specific_insight: str = ""
    technical_feasibility: str = ""   # can solo 2nd-year build in 4 weeks + 3 hardest challenges
    first_week_validation: str = ""   # one action to validate demand before writing code
    graveyard: List[GraveyardExample] = Field(default_factory=list)


# ── MarketOutput — Extended with Layer 1 upgraded research fields ─────────────

class ComplaintItem(BaseModel):
    quote: str = ""
    source_url: str = ""

    @field_validator('source_url', mode='before')
    @classmethod
    def must_have_url(cls, v):
        # Soften: accept empty or placeholder URLs to avoid killing complaints
        # The LLM is instructed to provide real URLs but we don't hard-reject
        if v and not v.startswith('http'):
            return ''   # wipe invalid URLs instead of raising
        return v or ''

    @field_validator('quote', mode='before')
    @classmethod
    def quote_must_be_real(cls, v):
        if not v or len(str(v).strip()) < 10:
            return str(v) or "No detailed quote provided"
        return v


class MarketOutput(BaseModel):
    # ── Error state ──────────────────────────────────────────────────────────
    failed: bool = False
    error: bool = False
    error_message: str = ""
    # ── Research Status (New) ────────────────────────────────────────────────
    is_partial_research: bool = False
    research_note: str = ""
    # ── Core fields ────────────────────────────────────────────────────────
    competitors: List[CompetitorInfo] = Field(default_factory=list)
    open_source_alternatives: List[str] = Field(default_factory=list)
    main_user_complaints: List[str] = Field(default_factory=list)
    market_gap_summary: str = ""
    first_50_users_communities: List[CommunityInfo] = Field(default_factory=list)
    regional_specific_insight: str = ""
    # ── Layer 1 upgrade fields ─────────────────────────────────────────────
    pricing_signals: str = ""           # what users currently pay for this problem
    user_complaints: List[ComplaintItem] = Field(default_factory=list)  # quoted with source
    regional_pricing_ceiling: str = ""     # max realistic pricing based on user demographic
    competitor_graveyard_lessons: List[str] = Field(default_factory=list)
    market_gap: str = ""                # specific thing missing from all products
    competitor_pricing_detail: List[CompetitorPricingDetail] = Field(default_factory=list)


# ── VerdictOutput ─────────────────────────────────────────────────────────────

class VerdictOutput(BaseModel):
    # ── Error state ──────────────────────────────────────────────────────────
    failed: bool = False
    error: bool = False
    error_message: str = ""
    # ── Normal fields ────────────────────────────────────────────────────────
    verdict: Literal['BUILD', 'PIVOT', 'SKIP'] = 'SKIP'
    uniqueness_score: int = 0
    market_gap_score: int = 0
    feasibility_score: int = 0
    timing_score: int = 0
    reasoning: str = ""
    bottom_line: str = ""
    differentiator: str = ""
    graveyard: List[GraveyardExample] = Field(default_factory=list)
    pivot_suggestion: Optional[str] = None
    scores: dict = Field(default_factory=dict)


# ── Simple Output Models for Fallback Routing ───────────────────────────────────

class CompetitorNamesOutput(BaseModel):
    names: list[str]

class IntakeQuestionsOutput(BaseModel):
    q1: str
    q2: str
    q3: str

class SharpenIdeaOutput(BaseModel):
    sharpened_idea: str

# ── USPOutput ─────────────────────────────────────────────────────────────────

class USPOutput(BaseModel):
    gap_found: bool = False
    uncovered_complaint: str = ''   # the raw complaint quote that nobody addresses
    usp_sentence: str = ''          # 'Your USP: X for Y.'
    confidence: str = 'LOW'         # HIGH / MEDIUM / LOW
    failed: bool = False
    error: bool = False
    error_message: str = ''


# ── KillConditionOutput ───────────────────────────────────────────────────────

class KillConditionOutput(BaseModel):
    # ── Error state ──────────────────────────────────────────────────────────
    failed: bool = False
    error: bool = False
    error_message: str = ""
    # ── Normal fields ────────────────────────────────────────────────────────
    kill_event: str = ""
    kill_timeline: str = 'Unknown'
    kill_probability: str = "LOW"
    survival_move: str = ""
    source_url: Optional[str] = None


# ── FinalVerdict ──────────────────────────────────────────────────────────────

class FinalVerdict(BaseModel):
    decision: str                 # BUILD / PIVOT / SKIP
    decision_reason: str          # max 2 sentences, must cite real data
    your_edge: str                # USP — one sentence
    kill_condition: str           # from kill_condition_agent
    kill_timeline: str
    build_first: str              # one specific thing, this week
    do_tomorrow: str              # exact action with exact words
    score: int                    # out of 100
    confidence: str               # HIGH / MEDIUM / LOW


# ── TechOutput ────────────────────────────────────────────────────────────────

class FeatureSpec(BaseModel):
    name: str
    recommended_approach: str
    alternative_approach: Optional[str] = None
    is_free: bool
    pricing_detail: str
    limitation: str


class TechOutput(BaseModel):
    # ── Error state ──────────────────────────────────────────────────────────
    failed: bool = False
    error: bool = False
    error_message: str = ""
    # ── Normal fields ────────────────────────────────────────────────────────
    architecture_type: Literal['standard_web_app', 'vps_ai_processing', 'mobile_app', 'bot_service'] = 'standard_web_app'
    features: List[FeatureSpec] = Field(default_factory=list)
    tech_stack: dict = Field(default_factory=dict)
    mvp_cost_inr_monthly: str = ""
    production_cost_inr_monthly: str = ""


# ── BlueprintOutput ───────────────────────────────────────────────────────────

class TaskItem(BaseModel):
    task_number: int = 1
    title: str
    time_estimate: str = "30 min"
    file_path: str = ""
    what_it_does: str = ""
    gemini_cli_prompt: str = ""
    test_command: str = ""
    success_check: str = ""
    commit_message: str = ""
    tier: Literal['MVP', 'Phase2', 'Never'] = 'MVP'


class BlueprintOutput(BaseModel):
    # ── Error state ──────────────────────────────────────────────────────────
    failed: bool = False
    error: bool = False
    error_message: str = ""
    # ── Normal fields ────────────────────────────────────────────────────────
    mvp_definition: str = ""
    folder_structure: str = ""
    mvp_tasks: List[TaskItem] = Field(default_factory=list)
    phase2_features: List[str] = Field(default_factory=list)
    never_features: List[str] = Field(default_factory=list)


# ── GTMOutput ─────────────────────────────────────────────────────────────────

class CommunityPost(BaseModel):
    platform: str
    community_name: str
    post_content: Optional[str] = None
    best_day_time: str

    @field_validator('post_content', mode='before')
    @classmethod
    def post_content_must_exist(cls, v):
        """Reject empty or placeholder post content so gtm_agent post-process fills it."""
        if not v or len(str(v).strip()) < 20:
            return None
        return str(v).strip()


class GTMOutput(BaseModel):
    # ── Error state ──────────────────────────────────────────────────────────
    failed: bool = False
    error: bool = False
    error_message: str = ""
    # ── Normal fields ────────────────────────────────────────────────────────
    first_50_users_plan: List[CommunityPost] = Field(default_factory=list)
    cold_outreach_script: str = ""
    week1_actions: List[str] = Field(default_factory=list)
    week2_actions: List[str] = Field(default_factory=list)
    week3_actions: List[str] = Field(default_factory=list)
    week4_money_ask: List[str] = Field(default_factory=list)
    primary_channel: str = ""
    viral_mechanic: str = ""

    @model_validator(mode="after")
    def enforce_script_length(self):
        if self.failed or self.error:
            return self
        words = len(self.cold_outreach_script.split())
        if words < 5:
            self.cold_outreach_script = "I noticed you might be interested in this solution: " + self.cold_outreach_script
        return self


# ── BusinessOutput ────────────────────────────────────────────────────────────

class PricingTier(BaseModel):
    name: str
    price_inr: str
    what_is_included: List[str]
    hard_limit: str
    target_user: str


class BusinessOutput(BaseModel):
    # ── Error state ──────────────────────────────────────────────────────────
    failed: bool = False
    error: bool = False
    error_message: str = ""
    # ── Normal fields ────────────────────────────────────────────────────────
    paid_market_exists: bool = False
    paid_market_evidence: str = ""
    pricing_tiers: List[PricingTier] = Field(default_factory=list)
    upgrade_trigger: str = ""
    revenue_milestone_week4: str = ""
    revenue_milestone_month2: str = ""
    revenue_milestone_month6: str = ""
    pricing_too_low_warning: Optional[str] = None

    @field_validator('pricing_tiers', mode='before')
    @classmethod
    def pricing_tiers_fallback(cls, v):
        if not v or len(v) == 0:
            return [
                {"name": "Free", "price_inr": "₹0", "what_is_included": ["Basic limited functionality"], "hard_limit": "1 use/day", "target_user": "Try before buy"},
                {"name": "Basic", "price_inr": "₹99/month", "what_is_included": ["Core unlocked features"], "hard_limit": "30 uses", "target_user": "New users"},
                {"name": "Pro", "price_inr": "₹299/month", "what_is_included": ["All features + Priority"], "hard_limit": "Unlimited", "target_user": "Power users"},
            ]
        return v

    @model_validator(mode="after")
    def fix_empty_milestones(self):
        if self.failed or self.error:
            return self
        if not self.revenue_milestone_week4:
            self.revenue_milestone_week4 = "₹5,000 MRR from first 50 early adopters"
        if not self.revenue_milestone_month2:
            self.revenue_milestone_month2 = "₹20,000 MRR with organic growth"
        if not self.revenue_milestone_month6:
            self.revenue_milestone_month6 = "₹1,00,000 MRR as a sustainable micro-business"
        return self

    @model_validator(mode="after")
    def fix_paid_contradiction(self):
        if self.failed or self.error:
            return self
        signals = ["$","₹","/month","subscription","pricing","plan","paid"]
        if not self.paid_market_exists and any(
            s in self.paid_market_evidence.lower() for s in signals
        ):
            self.paid_market_exists = True
        return self


# ── RoadmapOutput ─────────────────────────────────────────────────────────────

class DayAction(BaseModel):
    day: int = Field(ge=1, le=30)
    action: str
    platform_or_method: str
    exact_message_template: Optional[str] = None


class RoadmapOutput(BaseModel):
    # ── Error state ──────────────────────────────────────────────────────────
    failed: bool = False
    error: bool = False
    error_message: str = ""
    # ── Normal fields ────────────────────────────────────────────────────────
    days_1_7: List[DayAction] = Field(default_factory=list)
    user_call_script: str = ""
    build_rule: str = ""
    money_ask_message: str = ""
    day30_success_definition: str = ""
    day30_decision_tree: str = ""

    @model_validator(mode="after")
    def no_past_dates(self):
        if self.failed or self.error:
            return self
        current_year = datetime.now().year
        past_years = [str(y) for y in range(current_year - 4, current_year)]
        for past_yr in past_years:
            if past_yr in self.money_ask_message:
                self.money_ask_message = self.money_ask_message.replace(past_yr, str(current_year))
        return self

    @model_validator(mode="after")
    def validate_money_ask_message(self):
        if self.failed or self.error:
            return self
        if not self.money_ask_message or len(self.money_ask_message) < 30:
            self.money_ask_message = "Hi! I noticed you have this problem. I built a tool to solve it. Would you be willing to pay $10/month for it?"
        return self


if __name__ == '__main__':
    safe_print('schemas OK')
    v = VerdictOutput(verdict='BUILD', bottom_line='test')
    safe_print(f'VerdictOutput OK: {v.verdict}')
    i = IdeaOutput(project_name='Test', pain_score=8)
    safe_print(f'IdeaOutput OK: graveyard={i.graveyard}')