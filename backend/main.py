"""
FORGE Backend — Entry Point
============================
Run with:  python main.py
Or via uvicorn: uvicorn api:app --reload --port 8000
"""
from tools.llm_router import safe_print
import os
import sys

if sys.version_info >= (3, 13):
    print("❌ ERROR: FORGE requires Python 3.11 or 3.12.")
    print("You are running Python 3.13+. Many core data-science/AI libraries (like pydantic-core, xxhash, ormsgpack) do not yet have stable C-extension wheels for this version, which will cause obscure 'ModuleNotFoundError' crashes.")
    print("Please downgrade to Python 3.12 and recreate your virtual environment.")
    sys.exit(1)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    safe_print(f"[FORGE] Starting API server on http://0.0.0.0:{port}")
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_excludes=["*.db", "outputs/*", "__pycache__/*"],
    )