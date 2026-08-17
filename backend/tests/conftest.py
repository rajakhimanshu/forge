"""Shared pytest fixtures for FORGE v2.0 test suite."""
import pytest
from models.service_resolution import ServiceResolution, ServiceBundle
from models.env_profile import EnvProfile
from models.build_step import BuildStep, StepType
from models.feature_spec import FeatureSpec, FeatureBundle


@pytest.fixture
def mock_service_resolution():
    return ServiceResolution(
        infra_need="OTP SMS verification",
        recommended_service="Fast2SMS",
        current_free_tier="Trial: 50 SMS free on signup. Paid: Rs.0.40/SMS",
        signup_url="https://www.fast2sms.com/dashboard/default",
        sdk_install_cmd="npm install axios",
        api_key_location="Dashboard > Dev API > API Key",
        env_var_name="FAST2SMS_API_KEY",
        free_tier_limit_warning="Trial SMS expire in 24h. Request production access before launch.",
        tavily_search_query="best free OTP SMS service India 2026 API",
    )


@pytest.fixture
def mock_bundle(mock_service_resolution):
    return ServiceBundle(
        services=[
            mock_service_resolution,
            ServiceResolution(
                infra_need="user authentication JWT",
                recommended_service="jsonwebtoken npm package",
                current_free_tier="Free — open source library",
                signup_url="https://github.com/auth0/node-jsonwebtoken",
                sdk_install_cmd="npm install jsonwebtoken bcrypt",
                api_key_location="Set JWT_SECRET in .env — any random 32-char string",
                env_var_name="JWT_SECRET",
                tavily_search_query="JWT authentication Node.js setup 2026",
            ),
        ],
        cache_key="test_cache_key_abc123",
    )


@pytest.fixture
def mock_env_profile():
    return EnvProfile(
        os="windows",
        gpu="rtx2050",
        ai_cli="gemini",
        experience="intermediate",
        node_installed=True,
        python_installed=True,
    )


@pytest.fixture
def mock_state(mock_bundle, mock_env_profile):
    return {
        "project_root": "./inter-college-networking",
        "created_files": ["backend/app.js", "backend/.env"],
        "service_bundle": mock_bundle,
        "env_profile": mock_env_profile,
        "project_slug": "inter-college-networking",
    }


def make_bundle(env_var_names: list) -> ServiceBundle:
    """Helper: create a ServiceBundle with given env var names."""
    services = []
    for name in env_var_names:
        services.append(ServiceResolution(
            infra_need=name.lower().replace("_api_key", ""),
            recommended_service="Test Service",
            current_free_tier="Free tier",
            signup_url="https://example.com",
            sdk_install_cmd="npm install test-sdk",
            api_key_location="Dashboard > API Keys",
            env_var_name=name,
            tavily_search_query=f"best {name} service 2026",
        ))
    return ServiceBundle(services=services, cache_key="test_key")
