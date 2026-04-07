# Forge — AI R&D Co-Pilot

Forge is a locally-running AI agent system designed to validate startup ideas and generate comprehensive technical development plans. By orchestrating a team of specialized agents, it transforms raw concepts into structured market research, feasibility verdicts, and developer-ready blueprints.

## What Forge Does
Forge automates the initial R&D phase of product development. It analyzes your idea's core problem, researches the competitive landscape using live web data, provides an honest "build/no-build" verdict, and generates a full technical requirements document and implementation blueprint.

## Tech Stack
| Component | Tool | Cost |
| :--- | :--- | :--- |
| **LLM Engine** | Ollama (Llama 3.1 8B) | Free (Local) |
| **Orchestration** | LangChain & LangGraph | Open Source |
| **Web Search** | Tavily API | Freemium |
| **Vector DB** | ChromaDB | Open Source |
| **Embeddings** | Nomic-Embed-Text | Free (Local) |
| **UI Framework** | Gradio | Open Source |

## Prerequisites
- **Python:** 3.11 or 3.12
- **Node.js:** (Optional, for advanced tooling)
- **Git:** For version control
- **Ollama:** Installed and running locally

## Quick Start
Follow these steps to get Forge running on your machine:

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

## Project Structure
```text
forge/
├── agents/             # Logic for the 5 specialized AI agents
├── tools/              # Shared utilities (web search, RAG, formatting)
├── prompts/            # System prompt templates for each agent
├── knowledge_base/     # Local documents for RAG (Markdown, PDF)
├── outputs/            # Generated project reports and blueprints
├── chroma_db/          # Local vector database storage
├── scripts/            # Utility and testing scripts
├── app.py              # Main Gradio Web UI entry point
└── main.py             # Simple CLI entry point
```

## How to Use
Simply enter your startup or project idea into the large text box in the Web UI and click **"Run Forge Analysis"**. You can watch the status log as Forge moves through the five phases: Idea Analysis, Market Research, Verdict, Technical R&D, and Development Blueprint. Once complete, navigate through the tabs to review the detailed reports, and use the **"Save All Reports"** button to export them to your local `outputs/` folder.

## License
MIT License
