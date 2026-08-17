from pydantic import BaseModel
from typing import List


class FeatureSpec(BaseModel):
    """Full technical decomposition of one product feature."""
    feature_name: str
    user_value: str                       # what the student gains from this
    infra_needs: List[str] = []           # ["OTP", "MongoDB collection", "Cloudinary"]
    frontend_components: List[str] = []   # ["RegisterForm", "OTPInput"]
    backend_routes: List[str] = []        # ["POST /api/auth/register"]
    db_collections: List[str] = []        # ["users"]
    depends_on: List[str] = []            # other feature names that must be built first
    mvp_priority: int = 1                 # 1=must have, 2=should have, 3=nice to have
    build_time_hours: float = 4.0


class FeatureBundle(BaseModel):
    """Dependency-ordered collection of features for the project."""
    failed: bool = False
    error: bool = False
    error_message: str = ""
    features: List[FeatureSpec]
    build_order: List[str]    # feature names in dependency order
    mvp_features: List[str]   # only priority-1 feature names
