# Inception42 / HCS-01: Policy & Leave Concierge

An enterprise-grade, bilingual (English & Arabic) AI Policy & Leave Concierge combining **Deterministic SQL Database Grounding** with **Multimodal Policy Document RAG**.

---

## 🌟 Key Architecture & Features

1. **Deterministic Relational Grounding (SQL)**:
   * Connects to SQLite / PostgreSQL (`omni_hr.db`) via **SQLAlchemy 2.0 ORM**.
   * Exact personal records (remaining leave days, manager transition history, probation status) with zero hallucination.
2. **Multimodal Policy Ingestion**:
   * Reads official PDF policy documents page-by-page using **PyMuPDF**.
   * Understands embedded visual decision trees & approval flowcharts on Page 2 of policies.
3. **Conversational Memory**:
   * The last few turns are kept in the conversation's own **LangGraph** checkpointed
     state, so a follow-up like "what about sick leave?" is resolved against what was
     actually said — and survives a restart, as the clarification pause already did.
4. **Dual-Source Attribution & Verification**:
   * Interactive citation drawer showing **Live SQL Database Records** and **Direct PDF Page Deep-links** (`#page=2`).
5. **Modern Bilingual UI**:
   * Built with **React 18**, **TypeScript**, **TailwindCSS**, and **Radix UI**.

---

## 🚀 Quick Start Guide

### Option 1: 1-Click Launcher (Windows)

Simply run:
```powershell
.\start_all.bat
```
This automatically starts both the **FastAPI Backend (port 8000)** and the **React Frontend (port 5173)**.

---

### Option 2: Manual Start

#### 1. Backend Setup (FastAPI)
```powershell
cd Backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# Configure environment variables in Backend/.env
# GEMINI_API_KEY=your_key_here

python -m uvicorn app.main:app --reload --port 8000
```
* **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Health Check**: [http://localhost:8000/api/v1/hcs01/health](http://localhost:8000/api/v1/hcs01/health)

#### 2. Frontend Setup (React + Vite)
```powershell
cd Frontend
npm install
npm run dev
```
* **Frontend Web App**: [http://localhost:5173](http://localhost:5173)

---

## 🧪 Evaluation

Two levels of testing:

| | What it measures | Cost |
|---|---|---|
| `Backend/app/evaluation/benchmark_cases.py` | 36 single questions, asked one at a time. Shown at `GET /api/v1/hcs01/eval` | free, no AI calls |
| [`CONVERSATION_SCENARIOS.md`](CONVERSATION_SCENARIOS.md) | Seven real conversations, 58 questions, every answer scored. Finds what only breaks mid-chat | 58 AI calls |

```powershell
cd Backend
python scripts/run_taxonomy_scenarios.py        # the 36 single questions
python scripts/run_conversation_scenarios.py    # the seven conversations
```

`CONVERSATION_SCENARIOS.md` is also the client demo script. It includes a twelve-minute
walkthrough and a list of what not to show.

---

## 📁 Repository Structure

```
HCS_01/
├── .gitignore                   # Root gitignore (protects secrets & virtualenvs)
├── README.md                    # Project documentation
├── start_all.bat                # 1-Click Windows fullstack launcher
├── start_backend.bat            # Backend runner
├── start_frontend.bat           # Frontend runner
├── Backend/                     # FastAPI Python Backend
│   ├── app/
│   │   ├── main.py              # Application entrypoint & routes
│   │   ├── rag_engine.py        # Hybrid SQL + Vector RAG Engine (LangChain)
│   │   ├── vector_store.py      # PyMuPDF ingestion + Qdrant vector index
│   │   ├── prompts.py           # Bilingual prompt templates with SQL context
│   │   ├── db/                  # SQLAlchemy models, session & SQL query tools
│   │   │   ├── models.py
│   │   │   ├── session.py
│   │   │   └── sql_tool.py
│   │   └── mock_omni.py         # SQL-backed employee endpoints
│   ├── data/
│   │   ├── omni_hr.db           # SQLite Relational Database
│   │   └── policies_pdf/        # Official HR Policy PDFs (Multimodal)
│   └── requirements.txt
└── Frontend/                    # React 18 + Vite + TailwindCSS UI
    ├── src/
    │   ├── routes/              # TanStack router pages
    │   ├── components/          # UI components & verified sources drawer
    │   └── lib/api/             # Typed API clients
    ├── package.json
    └── vite.config.ts
```
