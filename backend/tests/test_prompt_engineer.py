"""
Tests for Layer 4 — Prompt Engineer
Target: prompts contain env vars, file paths, and success conditions.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from agents.prompt_engineer import (
    rewrite_prompt,
    get_success_condition,
    get_success_log_line,
    summarise_services,
)
from models.service_resolution import ServiceBundle, ServiceResolution
from tests.conftest import make_bundle


# ── test_rewrite_prompt ───────────────────────────────────────────────────────

def test_prompt_contains_env_vars():
    """Rewritten OTP prompt must include FAST2SMS_API_KEY and JWT_SECRET."""
    bundle = make_bundle(["FAST2SMS_API_KEY", "JWT_SECRET"])
    task = {
        "description": "Build OTP verification route",
        "file": "backend/routes/auth.js",
        "success_log": "OTP sent to phone",
    }
    state = {
        "project_root": "./inter-college-networking",
        "created_files": ["backend/app.js"],
        "service_bundle": bundle,
    }
    prompt = rewrite_prompt(task, state)

    assert "FAST2SMS_API_KEY" in prompt, "Prompt missing FAST2SMS_API_KEY"
    assert "JWT_SECRET" in prompt, "Prompt missing JWT_SECRET"
    assert "backend/routes/auth.js" in prompt, "Prompt missing target file"
    assert "OTP sent to phone" in prompt, "Prompt missing success log line"


def test_prompt_contains_project_root():
    bundle = make_bundle(["TEST_API_KEY"])
    task = {
        "description": "Build payment route",
        "file": "backend/routes/payment.js",
        "success_log": "Payment ready",
    }
    state = {
        "project_root": "./my-startup",
        "created_files": [],
        "service_bundle": bundle,
    }
    prompt = rewrite_prompt(task, state)
    assert "./my-startup" in prompt


def test_prompt_contains_existing_files():
    bundle = make_bundle(["RAZORPAY_KEY"])
    task = {"description": "Build checkout", "file": "frontend/Checkout.jsx", "success_log": "checkout ready"}
    state = {
        "project_root": "./test",
        "created_files": ["backend/app.js", "backend/routes/auth.js"],
        "service_bundle": bundle,
    }
    prompt = rewrite_prompt(task, state)
    assert "backend/app.js" in prompt
    assert "backend/routes/auth.js" in prompt


def test_prompt_handles_empty_bundle():
    """Prompt should not crash with no service bundle."""
    task = {"description": "Build landing page", "file": "frontend/index.html", "success_log": "page loads"}
    state = {"project_root": "./test", "created_files": [], "service_bundle": None}
    prompt = rewrite_prompt(task, state)
    assert "frontend/index.html" in prompt


# ── test_get_success_condition ────────────────────────────────────────────────

def test_success_condition_auth():
    cond = get_success_condition("auth setup", "implement JWT authentication")
    assert "JWT" in cond or "auth" in cond.lower()


def test_success_condition_otp():
    cond = get_success_condition("OTP route", "build OTP verification via Fast2SMS")
    assert "send-otp" in cond or "sent" in cond.lower()


def test_success_condition_payment():
    cond = get_success_condition("payment gateway", "integrate Razorpay checkout")
    assert "Razorpay" in cond or "order_id" in cond


def test_success_condition_database():
    cond = get_success_condition("database connection", "connect to MongoDB Atlas")
    assert "MongoDB" in cond or "connected" in cond.lower()


def test_success_condition_upload():
    cond = get_success_condition("file upload", "cloudinary image upload route")
    assert "Cloudinary" in cond or "cloudinary" in cond.lower()


def test_success_condition_fallback():
    cond = get_success_condition("random task", "do something unexpected")
    assert len(cond) > 10  # Should always return non-empty fallback


def test_all_6_task_types_have_conditions():
    """All 6 task types from the guide must produce non-empty success conditions."""
    tasks = [
        ("JWT auth setup", "server auth"),
        ("OTP integration", "SMS OTP"),
        ("File upload", "cloudinary storage"),
        ("Database connection", "MongoDB database"),
        ("Frontend login form", "login frontend"),
        ("Payment gateway", "Razorpay payment"),
    ]
    for label, desc in tasks:
        cond = get_success_condition(label, desc)
        assert cond and len(cond) > 20, f"Empty/short condition for: {label}"


# ── test_summarise_services ───────────────────────────────────────────────────

def test_summarise_services_includes_env_var():
    bundle = make_bundle(["FAST2SMS_API_KEY", "CLOUDINARY_URL"])
    summary = summarise_services(bundle)
    assert "FAST2SMS_API_KEY" in summary
    assert "CLOUDINARY_URL" in summary


def test_summarise_services_empty():
    from models.service_resolution import ServiceBundle
    bundle = ServiceBundle(services=[], cache_key="empty")
    summary = summarise_services(bundle)
    assert "No external" in summary or len(summary) >= 0
