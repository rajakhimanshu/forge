<div align="center">
  <h1>🛠️ Forge</h1>
  <p><b>Your Local AI R&D Co-Pilot for Startup Idea Validation & Technical Architecture</b></p>
  
  <p>
    <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11+-blue.svg" />
    <img alt="LangChain" src="https://img.shields.io/badge/LangChain-Enabled-blue" />
    <img alt="Ollama" src="https://img.shields.io/badge/Local_AI-Ollama-purple" />
    <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-green" />
  </p>
</div>

<br />

Forge is a locally-running AI agent system designed to validate startup ideas and generate comprehensive technical development plans. By orchestrating a team of specialized agents, it transforms raw concepts into structured market research, feasibility verdicts, and developer-ready blueprints.

## ✨ What Forge Does
Forge automates the initial R&D phase of product development. 
- **Understands your idea:** Deconstructs the core problem and solution.
- **Researches the market:** Analyzes the competitive landscape using live web data.
- **Evaluates feasibility:** Provides an honest "build/no-build" verdict.
- **Architects the product:** Generates a full technical requirements document and implementation blueprint.

## 🏗️ Technology Stack

| Component | Tool | Cost |
| :--- | :--- | :--- |
| **LLM Engine** | Ollama (Llama 3.1 8B) | Free (Local) |
| **Orchestration** | LangChain & LangGraph | Open Source |
| **Web Search** | Tavily API | Freemium |
| **Vector DB** | ChromaDB | Open Source |
| **Embeddings** | Nomic-Embed-Text | Free (Local) |
| **UI Framework** | Gradio | Open Source |

## 🚀 The Multi-Agent Pipeline & Data Outputs

Forge utilizes a multi-step LangGraph workflow to process your idea. Each phase generates highly specific operational data and architectural components, ultimately yielding a complete project dossier:

### 1. 📝 Intake Phase
- **What it does:** Deconstructs your raw idea into actionable mechanics.
- **Data Yield in Depth:**
  - **Core Value Proposition**: A crystalized summary of the exact problem being solved.
  - **Target Audience Profiles**: Specific user personas and their pain points.
  - **Monetization Mechanisms**: Potential pathways to revenue (e.g., subscription vs. transaction fees).

### 2. 🕵️‍♂️ Research Phase
- **What it does:** Uses live web searching via Tavily to analyze the real-world market.
- **Data Yield in Depth:**
  - **Direct Competitors**: Names, business models, and feature sets of existing platforms.
  - **Whitespace Analysis**: Identification of gaps in the current market that your idea can fill.
  - **SEO & Search Trends**: Real-world user demand and search intent data related to your product.

### 3. ⚖️ Verdict Phase
- **What it does:** Weighs market saturation against the technical feasibility of your idea.
- **Data Yield in Depth:**
  - **Go / No-Go Decision**: A brutally honest verdict on whether the idea is worth building.
  - **Risk Identification**: Highlighting the biggest technical, regulatory, or market hurdles.
  - **Critical Pivot Suggestions**: Direct recommendations on how to alter the idea if the original concept is fundamentally flawed or overly saturated.

### 4. 🛠️ Technical R&D Phase
- **What it does:** Architects the actual software needed to bring the idea to life, cross-referencing best practices via local RAG (ChromaDB).
- **Data Yield in Depth:**
  - **Technology Stack**: Specific recommendations for Frontend, Backend, Database, and Deployment.
  - **Database Schema Planning**: Structural mapping of SQL/NoSQL tables, collections, and relationships.
  - **API Architecture**: Outlines of core conceptual routes, endpoints, and data flows.
  - **Security Considerations**: Authentication strategies, encryption necessities, and compliance requirements.

### 5. 🏗️ Developer Blueprint Phase
- **What it does:** Creates an execution master-plan for a developer to follow.
- **Data Yield in Depth:**
  - **Step-by-Step Build Sprints**: A phased, agile implementation plan (e.g., Sprint 1: Setup & Auth, Sprint 2: Core Logic).
  - **Project Folder Structure**: A literal `tree` format layout mapping exactly where every configuration, source file, component, and utility should go.
  - **Component Breakdown**: Specific UI components, system hooks, and state management requirements.

## ⚙️ Prerequisites
- **Python:** 3.11 or 3.12
- **Node.js:** (Optional, for advanced tooling)
- **Git:** For version control
- **Ollama:** Installed and running locally

## 🛠️ Quick Start

Follow these steps to setup and deploy Forge onto your machine:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rajakhimanshu/forge.git
   cd forge
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   
   # Windows:
   venv\Scripts\activate
   
   # Mac/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   - Copy `.env.example` to `.env`
   - Open `.env` and add your [Tavily API Key](https://tavily.com/)
   - Ensure `OLLAMA_MODEL=llama3.1:8b` is set

5. **Pull the required Ollama models:**
   ```bash
   ollama pull llama3.1:8b
   ollama pull nomic-embed-text
   ```

6. **Launch Forge:**
   ```bash
   python app.py
   ```

7. **Access the UI:**
   Open your browser and navigate to `http://localhost:7860`

## 📁 Project Structure

```text
forge/
├── agents/             # Logic for the specialized AI agents
├── app.py              # Main Gradio Web UI entry point
├── chroma_db/          # Local vector database storage
├── knowledge_base/     # Local documents for RAG (Markdown, PDF)
├── main.py             # Simple CLI entry point
├── outputs/            # Generated project reports and blueprints
├── prompts/            # System prompt templates for each agent
├── scripts/            # Utility and testing scripts
└── tools/              # Shared utilities (web search, RAG, formatting)
```

## 🎯 How to Use

1. **Input your Idea:** Enter your startup or project idea into the primary text box in the Web UI.
2. **Execute:** Click **"Run Forge Analysis"**. 
3. **Monitor Progress:** Watch the status log display real-time progress across all agent phases (Idea Analysis, Market Research, Verdict, Technical R&D, and Development Blueprint). 
4. **Review:** Once complete, navigate through the tabs in the UI to review the detailed reports.
5. **Export:** Click the **"Save All Reports"** button to export the intelligence directly to your local `outputs/` directory.

## 📄 License
This project is licensed under the MIT License.
