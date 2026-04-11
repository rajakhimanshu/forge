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

## 🚀 The Multi-Agent Pipeline

Forge utilizes a multi-step LangGraph workflow to process your idea systematically:
1. **Intake Agent**: Analyzes your input to extract core features and target audience.
2. **Research Agent**: Scours the web using Tavily for competitors, market size, and trends.
3. **Verdict Agent**: Weighs the research against the idea to deliver a clear feasibility verdict.
4. **Technical Agent**: Translates the concept into high-level requirements (stack, APIs, data schemas).
5. **Blueprint Agent**: Generates the final, developer-ready execution plan (folder structure, step-by-step tasks).

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
