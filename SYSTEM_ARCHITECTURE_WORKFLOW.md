# DalīlHR (HCS-01) & Document Verification (HCS-11) — End-to-End System Workflow

> **Executive Architecture & Backend Workflow Guide**  
> *Prepared for Management, Technical Leads, and System Architects*

---

## 🏛️ 1. High-Level System Architecture

The solution operates as a decoupled, multi-tier enterprise architecture combining **Deterministic Relational Grounding**, **LangGraph Orchestrated RAG**, and an **Autonomous Document AI Verification Microservice**.

```mermaid
graph TB
    subgraph ClientLayer ["1. Frontend Client Layer (Port 8080)"]
        UI["React 18 + TanStack Web UI"]
        Chat["Bilingual Chat Panel"]
        UploadModal["HCS-11 School Document Upload Modal"]
        Notif["Manager Notification & Calendar Center"]
    end

    subgraph HCS01 ["2. DalīlHR Backend Orchestrator (FastAPI : Port 8000)"]
        API_GW["FastAPI API Router (/api/v1/hcs01)"]
        LG["LangGraph Conversational State Machine"]
        SQL_Tool["Deterministic SQL ORM (SQLAlchemy 2.0)"]
        RAG_Tool["Vector RAG Engine (PyMuPDF + Qdrant)"]
        StateDB[("Checkpointer SQLite\n(Conversation Memory)")]
    end

    subgraph HCS11 ["3. School Verification Microservice (FastAPI : Port 8001)"]
        H11_API["HCS-11 FastAPI Router (/api/v1/hcs11)"]
        DocAI["Multimodal Document AI / Vision Extractor"]
        RuleEngine["Deterministic Education Allowance Rule Engine"]
        CaseStore[("HCS-11 Case Store & Master Tables")]
    end

    subgraph DataSources ["4. Grounding Data Sources"]
        OmniDB[("omni_hr.db (SQLite / PostgreSQL)\nEmployee, Leaves, Balances, Hierarchy")]
        PDFStore["Official HR Policy PDF Library\n(Annual Leave, Remote Work, Education)"]
        MasterRef[("Accredited Schools & KHDA/ADEK Fee Tiers")]
    end

    %% Connections
    UI -->|1. REST / SSE Streaming| API_GW
    UploadModal -->|2. Multipart Form Upload| API_GW
    API_GW --> LG
    LG <--> StateDB
    LG --> SQL_Tool
    LG --> RAG_Tool
    SQL_Tool <--> OmniDB
    RAG_Tool <--> PDFStore

    %% Cross-Service Bridge
    LG -->|3. HTTP Client RPC (Port 8001)| H11_API
    API_GW -->|Proxy / Stream| H11_API
    H11_API --> DocAI
    DocAI --> RuleEngine
    RuleEngine <--> MasterRef
    RuleEngine <--> CaseStore
```

---

## 🎯 2. End-to-End Request & LangGraph Workflow

When an employee sends a message in English or Arabic, the **LangGraph State Graph** executes the following sequence of nodes:

```mermaid
flowchart TD
    START(["👤 User Input (Text / Query)"]) --> LOAD_FACTS["1. load_employee_facts\nFetch employee profile, balances,\nmanager ID & transition history from SQL"]

    LOAD_FACTS --> UNDERSTAND["2. understand_query\nExtract intent, language (EN/AR),\nsentiment, parameters & missing entities"]

    UNDERSTAND --> INTENT_BRANCH{"3. Intent Routing"}

    %% Fast Path Greeting
    INTENT_BRANCH -->|"GREETING\n('hi', 'hello', 'صباح الخير')"| GREETING_NODE["⚡ Fast Path Greeting\nSynthesize personalized welcome\n+ HCS-11 capabilities + Quick Actions"]
    GREETING_NODE --> FINISH_TURN

    %% Ambiguous / Missing Fields
    INTENT_BRANCH -->|"AMBIGUOUS / MISSING FIELDS"| CLARIFICATION["4. clarification\nAsk clarifying question\nSave pause state to SQLite"]
    CLARIFICATION --> FINISH_TURN

    %% Policy & HR Inquiries
    INTENT_BRANCH -->|"HR_POLICY / HR_DATA / COMPOSITE"| ROUTE_SUBQUERIES["5. route_subqueries\nDecompose multi-part questions"]
    ROUTE_SUBQUERIES --> GATHER_EVIDENCE["6. gather_evidence\n• SQL Tool: Live balances, probation status\n• Vector RAG: PyMuPDF semantic chunks"]
    GATHER_EVIDENCE --> GENERATE_ANSWER["7. generate_answer\nSynthesize bilingual answer\nAttach SQL & PDF #page=X citations"]
    GENERATE_ANSWER --> VALIDATE_ANSWER["8. validate_answer\nAnti-hallucination guardrail check"]
    VALIDATE_ANSWER --> FINISH_TURN

    %% Interactive Leave Management
    INTENT_BRANCH -->|"LEAVE_ACTION\n(Apply, Check, Approve)"| HANDLE_LEAVE["9. handle_leave_action\n• Balance verification\n• Date range validation\n• Manager approval cards\n• Auto-deduct SQL balances"]
    HANDLE_LEAVE --> FINISH_TURN

    %% School Verification / Education Allowance
    INTENT_BRANCH -->|"SCHOOL_VERIFICATION / DOCUMENT_UPLOAD"| HANDLE_HCS11["10. handle_school_verification\n• Resolve child dependent\n• Query Port 8001 for active cases\n• Trigger Upload Drawer / Modal"]
    HANDLE_HCS11 --> FINISH_TURN

    FINISH_TURN["11. finish_turn\nFormat response payload, JSON cards,\ncharts & action pills"] --> END_STREAM(["🚀 Stream Response to Frontend"])
```

---

## 📊 3. Intent Classification & Trigger Matrix

| Intent Category | Triggers & Keywords (EN / AR) | Target LangGraph Node | Backend Engine / Tool | Output Card / Action |
| :--- | :--- | :--- | :--- | :--- |
| **`GREETING`** | `hi`, `hello`, `good morning`, `مرحبا`, `السلام عليكم` | `finish_turn` | FastPath template + SQL employee name | Greeting card with 5 capability bullets + unified Quick Action pills. |
| **`HR_POLICY`** | *“What is the sick leave policy?”*, *“Can I work remotely on Monday?”* | `route_subqueries` ➔ `gather_evidence` ➔ `generate_answer` | Vector RAG (`Qdrant` + `text-embedding-3-large`) | Grounded answer with direct PDF citations (e.g. `[Remote Work Policy, Page 2]`). |
| **`EMPLOYEE_RECORD`** | *“How many leave days do I have?”*, *“Who is my line manager?”* | `gather_evidence` | Deterministic SQL ORM (`omni_hr.db`) | Exact balance pill, manager name, probation status without hallucination. |
| **`COMPOSITE`** | *“Can I take 5 days annual leave given my balance?”* | `route_subqueries` ➔ `gather_evidence` | Hybrid SQL + Policy Vector Match | Cross-referenced rule analysis combining SQL data with policy thresholds. |
| **`LEAVE_ACTION`** | *“I want to apply for annual leave”*, *“Approve leave for Ahmed”* | `handle_leave_action` | SQLAlchemy Leave Service + Workflow Engine | Interactive Calendar Date Picker, Leave Confirmation card, Manager Approval card. |
| **`SCHOOL_VERIFICATION`** | *“School certificate for Zayed”*, *“Education allowance status”*, *“Upload school document”* | `handle_school_verification` | HCS-11 HTTP RPC Client (`http://localhost:8001`) | Child selector pills, active case status card, interactive Document Upload Modal. |
| **`OUT_OF_SCOPE`** | *“Write Python code”*, *“Who won the match?”* | `finish_turn` | Deterministic Abstain Guardrail | Polite refusal directing user strictly to HR-related services. |

---

## 🔍 4. HCS-11 Document Verification Deep Dive

HCS-11 operates on **Port 8001** as an autonomous compliance engine for Proof-of-Schooling claims.

```mermaid
sequenceDiagram
    autonumber
    actor Employee as 👤 Employee (Front-End)
    participant HCS01 as 🤖 DalīlHR (:8000)
    participant HCS11 as 📑 HCS-11 Service (:8001)
    participant DocAI as 👁️ Multimodal OCR / Vision
    participant Rules as ⚖️ Rule Evaluation Engine
    actor Manager as 👔 HR Reviewer

    Employee->>HCS01: "Upload school documents for Zayed"
    HCS01->>HCS11: GET /api/v1/hcs11/dependents?employee_id=E0001
    HCS11-->>HCS01: Dependent details (Zayed, Grade 4, 9 yrs)
    HCS01-->>Employee: Renders Child Card & Upload Modal Trigger

    Employee->>HCS11: POST /api/v1/hcs11/cases/{case_id}/documents (PDF / Image)
    HCS11->>DocAI: Extract document fields (School Name, Student, Academic Year, Tuition Fee)
    DocAI-->>HCS11: Extracted JSON data (Confidence score: 0.96)

    HCS11->>Rules: Evaluate Business Rules against Master Data
    Note over Rules: 1. Is child age between 4 and 18?<br/>2. Is school accredited in UAE?<br/>3. Is requested amount <= Tier Cap (AED 25,000)?<br/>4. Is this academic year duplicate?

    alt All Rules Pass (Auto-Approve)
        Rules-->>HCS11: Status: VALIDATED (100% Policy Match)
        HCS11-->>Employee: Verification Success + Reimbursement Approval
    else Discrepancy Found (E.g. Over Limit / Unclear Grade)
        Rules-->>HCS11: Status: REQUIRES_MANUAL_REVIEW
        HCS11->>Manager: Push to HR Review Queue with highlighted discrepancy
        Manager->>HCS11: POST /api/v1/hcs11/reviews/{review_id}/action (Approve / Request More Info)
        HCS11-->>Employee: Notification & Action Update
    end
```

---

## 🔄 5. Integration Architecture: How HCS-01 & HCS-11 Communicate

1. **Decoupled Deployment**:
   - Both services can be deployed on separate containers/VMs or run locally on distinct ports (`8000` vs `8001`).
2. **Asynchronous HTTP Client**:
   - DalīlHR uses `app.integrations.hcs11_client.HCS11Client` with persistent connection pooling, retries, and fallback gracefulness.
3. **Synthetic Identifier Resolution**:
   - `HCS01_TO_HCS11_EMP_MAP` automatically bridges HCS-01 IDs (`EMP011`) to HCS-11 Dependent profiles (`E0011`).
4. **Interactive Action Payloads**:
   - When HCS-11 requires documents, HCS-01 injects an `action_payload` (`SCHOOL_DOCUMENT_SUBMISSION`) which the React frontend interprets to trigger native UI components.

---

## 🛠️ 6. Service Execution Cheat Sheet

| Action | Command / Batch Script | Target Endpoint |
| :--- | :--- | :--- |
| **Run All 3 Together** | `.\start_all.bat` | [http://localhost:8080](http://localhost:8080) |
| **Run Only HCS-01 (Concierge)** | `.\start_backend.bat` | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **Run Only HCS-11 (Verification)** | `.\start_hcs11_backend.bat` | [http://localhost:8001/docs](http://localhost:8001/docs) |
| **Run Only Frontend** | `.\start_frontend.bat` | [http://localhost:8080](http://localhost:8080) |

---
*Generated by DalīlHR Architecture Team — Inception42*
