from pydantic import BaseModel
from typing import Optional, List


class ServiceResolution(BaseModel):
    """One resolved infra service decision."""
    infra_need: str
    recommended_service: str
    current_free_tier: str
    signup_url: str
    sdk_install_cmd: str
    api_key_location: str
    env_var_name: str
    free_tier_limit_warning: Optional[str] = None
    tavily_search_query: str


class ServiceBundle(BaseModel):
    """Collection of resolved services for an idea."""
    failed: bool = False
    error: bool = False
    error_message: str = ""
    services: List[ServiceResolution]
    cache_key: str  # md5 hash of idea_title + sorted(infra_needs)
