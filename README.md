<div align="center">
  <h1>🛠️ FORGE</h1>
  <p><b>Your Local AI R&D Co-Pilot for Startup Idea Validation & Technical Architecture</b></p>
  
  <p>
    <img alt="Next.js" src="https://img.shields.io/badge/Next.js-black?style=for-the-badge&logo=next.js&logoColor=white" />
    <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" />
    <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-Enabled-blue?style=for-the-badge" />
    <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge&logo=python" />
    <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" />
  </p>
</div>

<br />

**FORGE** is an automated, multi-agent LangGraph pipeline architected as a highly opinionated **"Founder's OS"**. It acts as a ruthless technical co-founder and product manager, systematically transforming a raw startup idea into a comprehensive, zero-ambiguity execution plan.

The system enforces accountability, demands objective validation (historical failure analysis via "Graveyards"), and forces tactical execution planning before any code is written. By integrating real-world market sentiment (Reddit/HN) with hyper-specific technical constraints, FORGE bridges the gap between high-level ideation and ground-level execution.

---

## ✨ Core Value Propositions

- **Zero-Ambiguity Blueprints:** Generates exact environment-aware instructions (Windows/Mac/Linux + Cursor/Gemini/Copilot), complete with `npm`/`pip` installation commands and file dependency trees.
- **The Honest Verdict Layer:** Implements a mathematically grounded BUILD/PIVOT/SKIP pipeline based on historical startup failures.
- **Accountability Tracking:** Immutable SQLite persistence tracking project velocity and abandonment.
- **Dynamic Execution:** Outputs continuously stream via Server-Sent Events (SSE) to a sleek Next.js UI, compiling ultimately into a `.docx` build guide.

---

## 🏗️ Architecture Stack

FORGE uses a modern decoupled architecture:

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | **Next.js (React)** | Streams Server-Sent Events (SSE) for real-time AI reasoning visualization. |
| **Backend API** | **FastAPI** | High-performance Python backend coordinating the AI agents. |
| **Orchestration** | **LangGraph** | Multi-agent state machine enforcing strict Pydantic data schemas. |
| **LLM Engine** | **Gemini / Groq / Ollama** | 3-tier fallback execution ensuring zero-downtime AI generations. |
| **Intelligence** | **Tavily API & ChromaDB** | Live web searching (market gaps) and local vector embeddings. |
| **Database** | **SQLite** | Caches API searches and persists user dashboards. |

---

## 🚀 The Multi-Agent Pipeline

FORGE utilizes a sequential multi-step workflow. Each phase generates highly specific operational data:

### 1. 📝 Intake & Idea Agent
Deconstructs your raw idea into actionable mechanics, identifying core value propositions and monetization strategies.

### 2. 🕵️‍♂️ Research Agent
Scans Reddit, HackerNews, and Google (via Tavily) to analyze the real-world market, direct competitors, whitespace gaps, and SEO intent.

### 3. ⚖️ Verdict Agent
The "Honest Verdict Layer" weighs market saturation against technical feasibility, delivering a brutal BUILD, PIVOT, or SKIP verdict.

### 4. 🛠️ Technical Architect Agents
Maps features into a concrete Tech Stack, using a Service Resolver to select optimal real-world services (e.g., Supabase, Vercel) based on constraints.

### 5. 🏗️ Developer Blueprint Agents
Generates hyper-specific OS-aware "SETUP" steps (terminal commands) and "CODING" steps (AI prompts) ready to be copy-pasted into Cursor or Copilot. Finally, everything is bundled into a `.docx` output.

---

## ⚙️ Prerequisites

- **Python:** 3.11 or 3.12
- **Node.js:** v18+ (For running the Next.js Frontend)
- **Git:** For version control
- **API Keys:** You will need a [Tavily API Key](https://tavily.com/) and optionally a Gemini/Groq API key.
- **Ollama:** Installed and running locally (if you plan to use local models as a fallback).

---

## 🛠️ Quick Start & Setup

Follow these steps to deploy FORGE locally on your machine. The system is split into two parts: Backend and Frontend.

### 1. Clone the Repository
```bash
git clone https://github.com/rajakhimanshu/forge.git
cd forge
```

### 2. Setup the Backend (FastAPI & LangGraph)

Open a new terminal and navigate to the backend directory:
```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your TAVILY_API_KEY, GROQ_API_KEY, and GEMINI_API_KEY
```
*(Optional) If using local Ollama models:*
```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

**Start the Backend Server:**
```bash
python main.py
# The API will be available at http://localhost:8000
```

### 3. Setup the Frontend (Next.js)

Open a second terminal and navigate to the frontend directory:
```bash
cd frontend

# Install Node dependencies
npm install

# Start the development server
npm run dev
# The UI will be available at http://localhost:3000
```

---

## 🎯 How to Use

1. **Access the UI:** Open your browser and navigate to `http://localhost:3000`.
2. **Input your Idea:** Provide your raw startup concept and select your target operating system/IDE preferences.
3. **Execute Pipeline:** Start the FORGE analysis.
4. **Monitor Progress:** Watch the real-time SSE stream render the agents' thought processes as markdown directly in the UI.
5. **Download Artifacts:** Once the pipeline completes, download the generated `.docx` build guide for your developer team.
6. **Track Accountability:** Check the main dashboard to view your historical ideas and their BUILD/PIVOT statuses.

---

## 🧠 Engineering Depth & Architecture
For a deep dive into how FORGE mitigates LLM hallucination, manages Pydantic context serialization across multiple agents, and orchestrates its 3-Tier Fallback Router, please read our [Engineering Architecture Guide](./ENGINEERING_DEPTH.md).

---

## 📄 License
This project is licensed under the MIT License.
