"""
Tests for Layer 2 — Service Resolver
Target: cache logic, infra detection, no Tavily calls on cache hit.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import patch, MagicMock
from agents.service_resolver import detect_infra_needs, resolve_services
from db.service_cache import get_cached, set_cached
from models.service_resolution import ServiceBundle, ServiceResolution


# ── test_detect_infra_needs ───────────────────────────────────────────────────

def test_detect_infra_needs_otp():
    tech_output = {"features": ["OTP login", "Cloudinary upload", "Razorpay payments"]}
    needs = detect_infra_needs(tech_output)
    assert "OTP SMS verification" in needs


def test_detect_infra_needs_payments():
    tech_output = {"tech_stack": {"payments": "Razorpay"}}
    needs = detect_infra_needs(tech_output)
    assert "payment gateway India" in needs


def test_detect_infra_needs_storage():
    tech_output = {"features": ["image upload with Cloudinary"]}
    needs = detect_infra_needs(tech_output)
    assert any("storage" in n or "upload" in n for n in needs)


def test_detect_infra_needs_no_duplication():
    """OTP and SMS both map to same category — should only appear once."""
    tech_output = {"features": ["OTP verification via SMS"]}
    needs = detect_infra_needs(tech_output)
    count = sum(1 for n in needs if "OTP" in n or "SMS" in n)
    assert count == 1, f"Expected 1, got {count} OTP/SMS needs: {needs}"


def test_detect_infra_needs_empty():
    needs = detect_infra_needs(None)
    assert needs == []


def test_detect_infra_needs_dict():
    needs = detect_infra_needs({"features": ["auth system", "database storage"]})
    assert any("auth" in n for n in needs)


def test_detect_infra_needs_fallback():
    needs = detect_infra_needs(None, fallback_text="Requires OTP verification and Razorpay integration")
    assert "OTP SMS verification" in needs
    assert "payment gateway India" in needs


# ── test_cache_hit_skips_tavily ───────────────────────────────────────────────

def test_cache_hit_skips_tavily():
    """Second resolve call on same key must NOT hit Tavily."""
    # Pre-populate cache with a valid ServiceBundle
    bundle = ServiceBundle(
        services=[
            ServiceResolution(
                infra_need="OTP SMS verification",
                recommended_service="Fast2SMS",
                current_free_tier="50 SMS free",
                signup_url="https://fast2sms.com",
                sdk_install_cmd="npm install axios",
                api_key_location="Dashboard > Dev API",
                env_var_name="FAST2SMS_API_KEY",
                tavily_search_query="best OTP SMS India 2026",
            )
        ],
        cache_key="test_cache_hit_key_99",
    )
    set_cached("test_cache_hit_key_99", bundle)

    tavily_call_count = []

    def fake_search_tavily(query):
        tavily_call_count.append(query)
        return "mocked result"

    with patch("agents.service_resolver._search_for_service", side_effect=fake_search_tavily):
        # Use a state that will hash to the same key
        # We monkeypatch detect_infra_needs to return known needs
        with patch("agents.service_resolver.detect_infra_needs", return_value=["OTP SMS verification"]):
            with patch("agents.service_resolver.hashlib") as mock_hash:
                mock_md5 = MagicMock()
                mock_md5.hexdigest.return_value = "test_cache_hit_key_99"
                mock_hash.md5.return_value = mock_md5

                state = {"user_idea": "test idea", "tech_output": {}, "idea_output": None}
                result = resolve_services(state)

    assert len(tavily_call_count) == 0, (
        f"Tavily was called {len(tavily_call_count)} time(s) despite cache hit"
    )
    assert result.get("service_bundle") is not None


def test_cache_read_write():
    """set_cached + get_cached round-trip should recover the bundle."""
    bundle = ServiceBundle(
        services=[],
        cache_key="round_trip_test",
    )
    set_cached("round_trip_test_key", bundle)
    recovered = get_cached("round_trip_test_key")
    assert recovered is not None
    assert "cache_key" in recovered


def test_resolve_services_returns_dict_with_bundle():
    """resolve_services must always return a state dict with service_bundle key."""
    with patch("agents.service_resolver.detect_infra_needs", return_value=[]):
        state = {"user_idea": "test", "tech_output": {}, "idea_output": None}
        result = resolve_services(state)
    assert "service_bundle" in result
    assert result["service_bundle"] is not None
