#  Technical Blueprint: Advanced Enterprise Architecture for HCS-01

This technical document outlines the complete architectural roadmap and advanced AI/RAG strategies for scaling the **HCS-01 Policy & Leave Concierge** into an enterprise-grade multimodal intelligence platform.

---

##  Table of Contents
1. [0 & 1. Complex Multimodality & Input Source Layouts](#0--1-complex-multimodality--input-source-complexity)
2. [2. Advanced Chunking Strategy: Sizing, Overlap & Techniques](#2-advanced-chunking-strategy-sizing-overlap--techniques)
3. [3. Deep-Dive: Embedding Model Rationale & Benchmarks](#3-deep-dive-embedding-model-rationale--benchmarks)
4. [4. Continuous Learning, Feedback Loops & Drift Detection](#4-continuous-learning-feedback-loops--drift-detection)
5. [5. Query Expansion, Corrective RAG (CRAG) & Self-RAG](#5-query-expansion-corrective-rag-crag--self-rag)
6. [6. Proactive Onboarding & Intent Orchestration on Greeting (`"Hi"`)](#6-proactive-onboarding--intent-orchestration-on-greeting-hi)
7. [7. System Latency & Performance Optimization Blueprint](#7-system-latency--performance-optimization-blueprint)
8. [8. Phased Implementation Roadmap](#8-phased-implementation-roadmap)

---

## 0 & 1. Complex Multimodality & Input Source Complexity

### The Challenge:
Enterprise HR documents are rarely plain text. They contain:
* **Multi-tiered tables** with merged cells (e.g. *Years of Service vs. Notice Period vs. Gratuity Multipliers*).
* **Multi-column magazine layouts** where naive text parsers read horizontally across columns, breaking sentence structure.
* **Complex Flowcharts & Visual Decision Trees** (e.g. *Probation PIP failure pathways, Bradford Factor escalation*).

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           COMPLEX MULTIMODAL INGESTION                          │
├──────────────────────────────────┬──────────────────────────────────────────────┤
│ 1. Vision Layout Decomposition   │ 2. Dual-Layer Semantic Synthesis             │
│   (LayoutLMv3 / Document AI)     │   (VLM: Gemini 2.5 Flash Vision / Claude 3.5)│
│                                  │                                              │
│ [PDF Page]                       │ ├── [Tables] ──▶ Strict Markdown Grid +      │
│   ├── Bounding Box: Table Grid   │ │                JSON Metadata Prepend       │
│   ├── Bounding Box: 2-Col Text   │ ├── [Images] ──▶ Step-by-Step Decision Logic │
│   └── Bounding Box: Visual Chart │ └── [Text]   ──▶ Semantic Hierarchy Heading  │
└──────────────────────────────────┴──────────────────────────────────────────────┘
```

### Proposed Solutions & Architecture:
1. **Layout-Aware PDF De-structuring**:
   * Integrate **`Unstructured.io`** with **`LayoutLMv3`** or **Google Document AI** to segment raw PDFs into typed structural elements: `Header`, `Paragraph`, `Table`, `Image/Chart`, and `Footnote`.
   * Reconstruct reading order vertically within column bounding boxes to prevent cross-column text scrambling.
2. **Table-to-JSON Serialization**:
   * Instead of flattening tables into lossy text, run a Vision-Language Model (VLM) to convert tables into **HTML/Markdown Tables with JSON Schema descriptors** (e.g. `{ "min_service_years": 3, "notice_period_days": 30 }`).
   * Prepend table headers to every individual row chunk so row-level context is never detached from column definitions.
3. **Patch-Level Visual Retrieval (ColPali)**:
   * Adopt **`ColPali`** (ColBERT + PaliGemma), which embeds the raw rendered visual image of PDF pages without relying on error-prone OCR.
   * Enables the vector database to compute multi-vector similarity directly against flowchart boxes and visual graphics.

---

## 2. Advanced Chunking Strategy: Sizing, Overlap & Techniques

| Chunking Strategy | Target Chunk Size | Token Overlap | Best Used For |
| :--- | :--- | :--- | :--- |
| **Hierarchical (Parent-Child)** | Child: 128 tokens<br>Parent: 1,024 tokens | Child: 20 tokens<br>Parent: 100 tokens | **Policy clauses with broad caveats**: Child matches the specific question; Parent supplies the full legal context. |
| **Late Chunking (Contextual)** | 256–512 tokens | 0% (Uses global cross-attention) | **Multi-step HR processes**: Eliminates semantic detachment across sentence boundaries. |
| **Table-Atomic Chunking** | Variable (1 Entire Table) | 0% (Single unit) | **Financial limits, leave matrices, salary grades**. Never splits table rows. |
| **Semantic Boundary Splitting** | Dynamic (Cosine drop $\Delta > 0.35$) | 15% | **Narrative policy introductions, guidelines, and FAQs**. |

```
                       HIERARCHICAL PARENT-CHILD CHUNKING
┌─────────────────────────────────────────────────────────────────────────────┐
│ PARENT CHUNK (1,024 Tokens): Section 1.4 - Annual Leave Approval Governance │
│ ┌───────────────────────┐ ┌───────────────────────┐ ┌─────────────────────┐ │
│ │ Child Chunk 1 (128 T) │ │ Child Chunk 2 (128 T) │ │ Child Chunk 3 (128T)│ │
│ │ "Notice: 1-2 days..." │ │ "Notice: 3-9 days..." │ │ "Emergency leave..."│ │
│ └───────────────────────┘ └───────────────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
          │                                                    ▲
          ▼ (Search Index Matches Child 1)                     │
          └────────────────────────────────────────────────────┘
                     (Returns Full Parent Context to LLM)
```

### 1. Hierarchical Parent-Document Retrieval:
* **The Problem**: Small chunks (100 tokens) yield accurate vector similarity but lack context. Large chunks (1,000 tokens) contain full context but suffer from noisy embedding averages.
* **The Fix**: Store small child chunks in the vector index. When a child chunk is retrieved, resolve its parent ID from the database and pass the full **Parent Section** to the LLM.

### 2. Late Chunking:
* Pass the full multi-page document into a long-context transformer (e.g. `jina-embeddings-v3` with 8,192 token window).
* Extract token-level embeddings where every token attends to the entire document, then mean-pool them into sub-chunk vectors. This ensures sub-chunks maintain global document awareness.

---

## 3. Deep-Dive: Embedding Model Rationale & Benchmarks

### Comparison of Modern Embedding Models:

| Model | Dimensions | Context Window | Multilingual (EN/AR) | Matryoshka Loss Support | Why / Why Not |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Google `text-embedding-004`** *(Current)* | **768** *(flexible)* | **2,048 tokens** | ⭐⭐⭐⭐⭐ (Exceptional) | ✅ Yes | **Top Pick**: Lowest latency on Vertex/Gemini, high Arabic-English cross-lingual alignment, native Matryoshka support. |
| **`jina-embeddings-v3`** | **1,024 / 512** | **8,192 tokens** | ⭐⭐⭐⭐ (Very High) | ✅ Yes | **Best for Late Chunking**: Task-specific LoRA adapters (`retrieval.query`, `retrieval.passage`). |
| **`BAAI/bge-m3`** | **1,024** | **8,192 tokens** | ⭐⭐⭐⭐⭐ (Exceptional) | ❌ No | **Best Multi-Vector Model**: Produces dense, sparse (lexical), and multi-vector ColBERT representations in a single pass. |
| **OpenAI `text-embedding-3-large`** | **3,072 / 1,536** | **8,191 tokens** | ⭐⭐⭐⭐ (High) | ✅ Yes | High dimensional cost; slower indexing speed than Gemini/Jina. |

### Architectural Recommendation: Matryoshka Representation Learning (MRL)
* Use **Matryoshka Embeddings** (`text-embedding-004` or `jina-v3`): Truncate 3,072-dim embeddings down to **512 or 768 dimensions** without losing retrieval quality.
* **Benefit**: Reduces Qdrant memory consumption by **75%** and accelerates approximate nearest-neighbor (HNSW) search by **3.8x**.

---

## 4. Continuous Learning, Feedback Loops & Drift Detection

```
┌──────────────┐     ┌──────────────┐     ┌────────────────┐     ┌───────────────┐
│ User Queries │ ──▶ │ RAG Engine   │ ──▶ │ User Thumbs    │ ──▶ │ Active Data   │
│ & Responses  │     │ Execution    │     │ Up / Down (UI) │     │ Flywheel Curation
└──────────────┘     └──────────────┘     └────────────────┘     └───────────────┘
                                                                         │
    ┌────────────────────────────────────────────────────────────────────┘
    ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ 1. Hard Negative Mining: Queries with low thumbs-down -> Fine-tune Reranker    │
│ 2. Synthetic Q&A Generation: Auto-generate 500 test questions per new PDF      │
│ 3. Semantic Policy Drift: Detect when HR policies diverge from SQL database    │
└────────────────────────────────────────────────────────────────────────────────┘
```

1. **User Feedback Flywheel (DPO / Reranker Tuning)**:
   * Log every interaction with `thumbs_up`, `thumbs_down`, and citation click telemetry in PostgreSQL.
   * Format low-scoring turns as **Hard Negative triplets** `(Query, Irrelevant Chunk, Correct Policy Chunk)` to fine-tune a lightweight local Cross-Encoder re-ranker quarterly.
2. **Automated Synthetic Benchmark Generation**:
   * When HR uploads a new policy PDF, a background pipeline generates 50 multi-hop questions and expected answers using `Gemini 2.5 Pro`.
   * Runs automated regression testing via **Ragas** to ensure new policy uploads do not break existing answers.
3. **Semantic Drift & Policy Discrepancy Detection**:
   * Automated integrity checks: If the policy PDF states *"Carry-over is capped at 5 days"* but the SQL table schema contains employees with `carry_over_days > 5`, trigger an alert to HR Operations.

---

## 5. Query Expansion, Corrective RAG (CRAG) & Self-RAG

Standard RAG assumes the retriever always fetches the correct documents. **Corrective RAG (CRAG)** introduces self-reflective grading to verify relevance *before* answering.

```
                             CORRECTIVE RAG (CRAG) WORKFLOW
                                   ┌───────────────┐
                                   │  User Query   │
                                   └───────┬───────┘
                                           │
                                           ▼
                               ┌───────────────────────┐
                               │ Query Expansion / HyDE│
                               └───────────┬───────────┘
                                           │
                                           ▼
                               ┌───────────────────────┐
                               │ Vector Retrieval (k=5)│
                               └───────────┬───────────┘
                                           │
                                           ▼
                               ┌───────────────────────┐
                               │  Chunk Quality Grader │
                               └───────────┬───────────┘
                                           │
                 ┌─────────────────────────┼─────────────────────────┐
                 ▼                         ▼                         ▼
         [High Confidence]        [Ambiguous / Partial]      [Zero Relevance / Out]
                 │                         │                         │
                 ▼                         ▼                         ▼
         Generate Grounded         Query Decomposition +     Polite Fallback or
         Synthesized Answer        Fallback Secondary Search Trigger Human Ticket
```

### 1. Multi-Query Expansion & HyDE (Hypothetical Document Embeddings):
* **HyDE**: Before querying the vector database, an ultralight model generates a hypothetical policy excerpt. Searching with this hypothetical text matches the legal terminology in policy PDFs significantly better than raw user questions.
* **Sub-Query Decomposition**: For compound questions (*"How much annual leave do I have and what happens if I resign during probation?"*), split into two isolated vector queries and merge the context.

### 2. Retrieval Evaluator (Self-RAG Grading):
* An internal evaluation layer scores retrieved chunks from 0.0 to 1.0 on:
  1. **Relevance**: Does this clause address the query intent?
  2. **Completeness**: Does it contain all necessary conditional clauses?
* If the average chunk confidence is $< 0.40$, the engine avoids hallucinating and seamlessly triggers a fallback: *"This specific scenario is not explicitly defined in the standard HR policies. Would you like me to submit an HR inquiry to your HR Business Partner?"*

---

## 6. Proactive Onboarding & Intent Orchestration on Greeting (`"Hi"`)

When a user simply types `"Hi"`, `"Hello"`, or switches personas, rather than responding with a generic *"How can I help you?"*, execute an **Intelligent Pre-Fetch Pipeline**:

```
[User triggers "Hi" or switches to Ahmed Abdullah Al Mansoori (EMP001)]
                           │
                           ▼
           [Background Pre-Fetch Orchestrator]
                           │
  ┌────────────────────────┼────────────────────────┐
  ▼                        ▼                        ▼
[SQL Query: Balances]   [SQL Query: Manager]    [Policy Calendar Check]
18 days annual leave    Fatima Maryam Al Qubaisi Upcoming Public Holiday
3 carry-over expiring   (VP, People & Culture)   (Eid / National Day in 12d)
  └────────────────────────┬────────────────────────┘
                           │
                           ▼
[Proactive Intelligent Dashboard Digest Card Rendered in Chat]
```

### Dynamic Welcome Payload Structure:
1. **Personalized Snapshot**:
   > *"Good morning, Ahmed! Here is your quick HR status overview:*
   > * *🌴 **18 Days Annual Leave Available** (+3 carry-over days expiring Dec 31)*
   > * *👔 **Line Manager**: Fatima Maryam Al Qubaisi (VP, People & Culture)*
   > * *📅 **Upcoming Holiday**: UAE National Day in 12 days*
2. **Context-Aware Quick Action Pills**:
   * `[Request Annual Leave]`
   * `[Download Expense Claim Form]`
   * `[Review Remote Work Policy for National Day Week]`

---

## 7. System Latency & Performance Optimization Blueprint

To achieve **Sub-500ms End-to-End Latency** at scale:

```
┌───────────────────────────┬───────────────────────────────┬───────────────────────────────┐
│ Optimization Technique    │ Mechanism                     │ Target Latency Reduction      │
├───────────────────────────┼───────────────────────────────┼───────────────────────────────┤
│ **Semantic Cache (Redis)**│ Cosine similarity match >0.96 │ **1,200ms ──▶ 25ms**          │
│ **Server-Sent Events**    │ Chunked HTTP Streaming        │ **TTFT (First Token) < 350ms**│
│ **Async Connection Pool** │ `asyncpg` / `aiosqlite` pool  │ **DB IO from 45ms ──▶ 4ms**   │
│ **Matryoshka Truncation** │ Truncate vectors 3072 ──▶ 768 │ **ANN Search 60ms ──▶ 12ms**  │
└───────────────────────────┴───────────────────────────────┴───────────────────────────────┘
```

---

## 8. Phased Implementation Roadmap

```
Phase 1: Ingestion & Precision (Weeks 1-3)
├── Implement Layout-Aware PDF Parser (Unstructured.io / Document AI)
├── Deploy Hierarchical Parent-Child Chunking in Qdrant
└── Integrate Hybrid Search (Dense + BM25) + Cohere Rerank v3

Phase 2: Corrective Intelligence & Speed (Weeks 4-6)
├── Deploy Redis Semantic Caching & Server-Sent Events (SSE) Streaming
├── Implement Corrective RAG (CRAG) with Self-Reflection Graders
└── Build Multi-Query Expansion & HyDE pipeline

Phase 3: Proactive Engine & Active Learning (Weeks 7-9)
├── Implement Proactive Onboarding Digest for "Hi" triggers
├── Build Automated Synthetic Q&A Benchmark generator
└── Deploy Ragas automated evaluation CI/CD pipeline
```
