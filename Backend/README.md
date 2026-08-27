# HCS-01 — Policy & Leave Concierge

> **Bilingual RAG-powered HR assistant** for HC Services employees.  
> Ask policy questions in English or Arabic — get precise, cited answers from the People Code.

---

## Architecture

```
Streamlit UI (8501)
    │
    │  POST /api/v1/hcs01/query
    ▼
FastAPI (8000)
    ├─ RAGEngine
    │   ├─ Mock Omni → Employee profile
    │   ├─ Qdrant   → Top-K policy chunks (cross-lingual)
    │   └─ GPT-4o   → Answer in target language
    └─ /api/omni/employee/{id}

Qdrant (6333) — Vector DB
```

**Cross-Lingual Flow:**
```
Arabic query  →  Multilingual Embedding  →  English policy chunks  →  GPT-4o  →  Arabic answer
English query →  Multilingual Embedding  →  English policy chunks  →  GPT-4o  →  English answer
```

---

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Docker Desktop (for Qdrant) — or set `QDRANT_IN_MEMORY=true`
- OpenAI API key

### 2. Clone & Install

```bash
cd d:\HCS01

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
copy .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
```

### 4. Start Qdrant

```bash
docker-compose up -d
```

Or use in-memory mode (no Docker): set `QDRANT_IN_MEMORY=true` in `.env`.

### 5. Ingest Policy Documents

```bash
python scripts/ingest.py
```

This embeds the 5 policy documents into Qdrant (~30 chunks total).

### 6. Start the API

```bash
uvicorn app.main:app --reload --port 8000
```

The API auto-ingests on startup if Qdrant is empty.

### 7. Start the UI

```bash
streamlit run ui/app.py
```

Open http://localhost:8501

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/hcs01/query` | Main RAG query (HCS-02 compatible) |
| `GET` | `/api/v1/hcs01/ingest?force=true` | Re-ingest policies |
| `GET` | `/api/v1/hcs01/health` | Health check + vector count |
| `GET` | `/api/omni/employee/{user_id}` | Mock Omni employee lookup |
| `GET` | `/api/omni/employees` | List all employees |
| `GET` | `/docs` | Swagger UI |

### Query Request Example

```json
POST /api/v1/hcs01/query
{
  "query": "كم يوم إجازة سنوية لدي؟",
  "employee_id": "EMP001",
  "target_language": "ar"
}
```

### Query Response Example

```json
{
  "answer": "وفقاً للسياسة HC-PC-001، يحق لكِ ...",
  "sources": [
    { "source": "HC-PC-001", "section": "Section 1.2.1", "score": 0.94, "language": "en" }
  ],
  "employee_profile": { "name": "Sarah Ahmed", ... },
  "target_language": "ar",
  "latency_ms": 1823,
  "tokens_used": 748
}
```

---

## Employees (Mock Omni)

| ID | Name | Role | Leave Balance |
|----|------|------|--------------|
| EMP001 | Sarah Ahmed | Senior Consultant | 18 days |
| EMP002 | Mohammed Al Rashidi | HR Business Partner | 7 days |
| EMP003 | Priya Nair | Associate Analyst | 21 days |
| EMP004 | Omar Khalil | Finance Manager | 24 days |
| EMP005 | Liu Yang | Project Manager | 3 days |

---

## Policy Documents

| File | Reference | Topics |
|------|-----------|--------|
| 01_annual_leave.md | HC-PC-001 | Entitlement, accrual, carry-over, encashment |
| 02_sick_leave.md | HC-PC-002 | Allowance, certificates, Bradford Factor |
| 03_probation.md | HC-PC-003 | Duration, reviews, benefits during probation |
| 04_remote_work.md | HC-PC-004 | Hybrid schedule, eligibility, security |
| 05_expense_claims.md | HC-PC-005 | Travel, per diem, entertainment, limits |

---

## HCS-02 Integration

This service exposes `POST /api/v1/hcs01/query` as a nestable REST endpoint.  
HCS-02 (Onboarding Orchestrator) can call it with:

```python
import httpx

response = httpx.post("http://hcs01-service/api/v1/hcs01/query", json={
    "query": "What leave am I entitled to in my first year?",
    "employee_id": new_employee_id,
    "target_language": "en"
})
data = response.json()
print(data["answer"])
print(data["sources"])
```

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | Your OpenAI API key |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | Embedding model |
| `EMBEDDING_DIM` | `3072` | Vector dimension |
| `LLM_MODEL` | `gpt-4o` | Chat completion model |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant REST port |
| `QDRANT_IN_MEMORY` | `false` | Use in-memory Qdrant |
| `RAG_TOP_K` | `5` | Top-K chunks to retrieve |
| `CHUNK_SIZE` | `512` | Chars per chunk |

---

## Troubleshooting

**Qdrant connection refused:**  
→ Run `docker-compose up -d` or set `QDRANT_IN_MEMORY=true`

**"OPENAI_API_KEY is not set":**  
→ Copy `.env.example` to `.env` and fill in your key

**Empty answers / "No relevant policy sections found":**  
→ Run `python scripts/ingest.py --force` to re-index documents

**Arabic text not displaying RTL:**  
→ Make sure your browser doesn't override direction styles
