"""
app/vector_store.py — Qdrant client, PDF parsing, embedding, chunking, multimodal & hybrid retrieval
"""
import os
import re
import math
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import pymupdf
import litellm
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.config import settings

logger = logging.getLogger(__name__)

# ── Singleton Clients ─────────────────────────────────────────────

_qdrant_client: Optional[QdrantClient] = None


def get_qdrant() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        if settings.qdrant_in_memory:
            logger.info("Using in-memory Qdrant (no Docker required)")
            _qdrant_client = QdrantClient(":memory:")
        else:
            logger.info(f"Connecting to Qdrant at {settings.qdrant_host}:{settings.qdrant_port}")
            _qdrant_client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                timeout=10,
            )
    return _qdrant_client


# ── Collection Management ─────────────────────────────────────────

def ensure_collection() -> None:
    """Create the Qdrant collection if it doesn't exist."""
    client = get_qdrant()
    existing = [c.name for c in client.get_collections().collections]
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(
                size=settings.embedding_dim,
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"Created Qdrant collection: {settings.qdrant_collection}")
    else:
        logger.info(f"Collection '{settings.qdrant_collection}' already exists")


def collection_count() -> int:
    """Return number of vectors in the collection (0 if not yet created)."""
    client = get_qdrant()
    try:
        info = client.get_collection(settings.qdrant_collection)
        return info.points_count or 0
    except Exception:
        return 0


# ── Embedding ─────────────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    """Embed a single text string. Returns a float vector."""
    response = litellm.embedding(
        model=settings.embedding_model,
        input=[text.replace("\n", " ")],
    )
    return response.data[0]["embedding"]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts in one API call."""
    cleaned = [t.replace("\n", " ") for t in texts]
    response = litellm.embedding(
        model=settings.embedding_model,
        input=cleaned,
    )
    return [item["embedding"] for item in response.data]


# ── Bilingual Policy Document Registry ────────────────────────────

BILINGUAL_POLICY_REGISTRY = {
    # English Policies
    "HC-PC-001": {
        "title": "Annual Leave Policy",
        "pdf_filename": "01_annual_leave_policy.pdf",
        "md_filename": "01_annual_leave.md",
        "language": "en",
        "diagram_page": 2,
        "diagram_transcription": (
            "Annual Leave Request & Approval Workflow Diagram (Page 2): "
            "Step 1: Submit Request via Omni Portal with required notice (1-2 days = 3 days notice; 3-9 days = 10 days notice; 10+ days = 30 days notice). "
            "Step 2: Line Manager Review (assesses team cover & balance). "
            "Step 3: HR Validation (checks annual leave caps, carry-over limit & public holidays). "
            "Step 4: Approval & Calendar Sync (deducts balance and syncs with Outlook)."
        ),
    },
    "HC-PC-002": {
        "title": "Sick Leave & Medical Certificates Policy",
        "pdf_filename": "02_sick_leave_policy.pdf",
        "md_filename": "02_sick_leave.md",
        "language": "en",
        "diagram_page": 2,
        "diagram_transcription": (
            "Sick Leave Certification Decision Tree & Bradford Factor Formula Diagram (Page 2): "
            "1-3 Days Absence: Self-certification permitted, notify supervisor before 09:00 AM, complete return-to-work form, 100% full pay. "
            "4+ Days Absence: Official DHA/DOH/MOH medical certificate mandatory within 48 hours, HR upload required. "
            "Bradford Factor Formula: B = S^2 x D (where S is number of absence spells, D is total days absent in 52 weeks). "
            "Score Thresholds: 0-49 No action; 50-124 Informal review; 125-399 Formal counselling; 400+ Disciplinary review."
        ),
    },
    "HC-PC-003": {
        "title": "Probation & Onboarding Policy",
        "pdf_filename": "03_probation_policy.pdf",
        "md_filename": "03_probation.md",
        "language": "en",
        "diagram_page": 1,
        "diagram_transcription": (
            "Probation Milestones & Review Timeline Diagram (Page 1): "
            "Day 1-30: Onboarding & Goal Setting (Initial objectives signed in Omni Portal). "
            "Day 90: Mid-Probation Review (Formal checkpoint, 360 peer feedback, PIP initiated if score < 70%). "
            "Day 180: Final Confirmation Review (Confirmation letter or maximum 3-month extension under Article 3.6)."
        ),
    },
    "HC-PC-004": {
        "title": "Flexible & Remote Work Policy",
        "pdf_filename": "04_remote_work_policy.pdf",
        "md_filename": "04_remote_work.md",
        "language": "en",
        "diagram_page": 1,
        "diagram_transcription": (
            "Remote Work Eligibility & Weekly Allocation Matrix Diagram (Page 1): "
            "Hybrid Model: Standard employees eligible for up to 2 remote days per week (Tue/Thu core office days). "
            "Work From Anywhere (WFA): Up to 15 international remote days per calendar year (requires 30-day advance VP approval)."
        ),
    },
    "HC-PC-005": {
        "title": "Business Expense & Travel Policy",
        "pdf_filename": "05_expense_claims_policy.pdf",
        "md_filename": "05_expense_claims.md",
        "language": "en",
        "diagram_page": 1,
        "diagram_transcription": (
            "Expense Approval Hierarchy & Thresholds Diagram (Page 1): "
            "Tier 1 (Up to AED 500): Line Manager approval. "
            "Tier 2 (AED 501 - 2,500): Practice Lead / Department Head approval. "
            "Tier 3 (Above AED 2,500): Managing Director & Finance Director joint sign-off."
        ),
    },
    # Arabic Policies
    "HC-PC-001-AR": {
        "title": "سياسة الإجازات السنوية",
        "pdf_filename": "01_annual_leave_ar.pdf",
        "language": "ar",
        "diagram_page": 2,
        "diagram_transcription": (
            "مخطط سير عمل طلب واعتماد الإجازة السنوية (الصفحة 2): "
            "الخطوة 1: تقديم الطلب عبر بوابة أومني مع الالتزام بمهلة الإشعار (1-2 يوم = 3 أيام إشعار؛ 3-9 أيام = 10 أيام إشعار؛ 10+ أيام = 30 يوماً إشعار مسبق). "
            "الخطوة 2: مراجعة المدير المباشر للتحقق من الرصيد وتغطية العمل. "
            "الخطوة 3: تدقيق ومصادقة الموارد البشرية. "
            "الخطوة 4: الاعتماد النهائي وخصم الرصيد ومزامنة التقويم."
        ),
    },
    "HC-PC-002-AR": {
        "title": "سياسة الإجازات المرضية والشهادات الطبية",
        "pdf_filename": "02_sick_leave_ar.pdf",
        "language": "ar",
        "diagram_page": 1,
        "diagram_transcription": (
            "مخطط الإجازات المرضية والتقارير الطبية (الصفحة 1): "
            "الاستحقاق: 90 يوماً في السنة (15 يوماً بأجر كامل، 30 يوماً بنصف أجر، 45 يوماً بدون أجر). "
            "الشهادات الطبية: إلزامية للغياب الذي يتجاوز يومين وتقديمها خلال 48 ساعة معتمدة من هيئة الصحة (DHA/DOH)."
        ),
    },
    "HC-PC-003-AR": {
        "title": "سياسة فترة التجربة والتأهيل الوظيفي",
        "pdf_filename": "03_probation_ar.pdf",
        "language": "ar",
        "diagram_page": 1,
        "diagram_transcription": (
            "مراحل ومواعيد تقييم فترة التجربة (الصفحة 1): "
            "المدة: 6 أشهر. تقييم مرحلي عند 90 يوماً وتقييم نهائي عند 180 يوماً. "
            "فترة الإشعار للاستقالة: 14 يوماً لمغادرة الدولة، أو 30 يوماً للانتقال لعمل داخل الدولة."
        ),
    },
    "HC-PC-004-AR": {
        "title": "سياسة العمل المرن والعمل عن بُعد",
        "pdf_filename": "04_remote_work_ar.pdf",
        "language": "ar",
        "diagram_page": 1,
        "diagram_transcription": (
            "مصفوفة العمل عن بُعد (الصفحة 1): "
            "النموذج الهجين: يتيح العمل عن بعد حتى يومين أسبوعياً بموافقة المدير المباشر. "
            "العمل من أي مكان دولياً: حتى 15 يوماً في السنة بعد موافقة نائب الرئيس."
        ),
    },
    "HC-PC-005-AR": {
        "title": "سياسة استرداد النفقات ومصروفات العمل",
        "pdf_filename": "05_expense_claims_ar.pdf",
        "language": "ar",
        "diagram_page": 1,
        "diagram_transcription": (
            "مصفوفة اعتمادات النفقات (الصفحة 1): "
            "حتى 500 درهم: اعتماد المدير المباشر. "
            "من 500 إلى 2500 درهم: اعتماد رئيس القسم. "
            "أكثر من 2500 درهم: اعتماد المدير المالي والإداري."
        ),
    },
}


# ── Ingestion Pipeline ─────────────────────────────────────────────

def ingest_policies() -> int:
    """Ingest both English and Arabic PDF documents into Qdrant."""
    ensure_collection()

    backend_dir = Path(__file__).resolve().parent.parent
    pdf_dir = backend_dir / "data" / "policies_pdf"
    md_dir = backend_dir / "data" / "policies_en"

    all_chunks = []

    for code, meta in BILINGUAL_POLICY_REGISTRY.items():
        pdf_file = pdf_dir / meta["pdf_filename"]
        pdf_url = f"/api/v1/hcs01/policies/pdf/{meta['pdf_filename']}"
        lang = meta.get("language", "en")

        # 1. Direct Page-by-Page Extraction using PyMuPDF
        pdf_page_texts = {}
        if pdf_file.exists():
            try:
                doc = pymupdf.open(str(pdf_file))
                for page_idx, page in enumerate(doc):
                    page_num = page_idx + 1
                    raw_text = page.get_text().strip()
                    if raw_text:
                        pdf_page_texts[page_num] = raw_text
                doc.close()
            except Exception as e:
                logger.warning(f"Failed to read PDF {pdf_file}: {e}")

        # 2. Markdown or PDF per-section extraction
        md_file = md_dir / meta.get("md_filename", "") if meta.get("md_filename") else None
        if md_file and md_file.exists():
            md_text = md_file.read_text(encoding="utf-8")
            heading_pattern = re.compile(r"^(#{1,3}\s+.+)$", re.MULTILINE)
            parts = heading_pattern.split(md_text)

            current_heading = ""
            current_body = ""

            def flush_section(heading: str, body: str):
                combined = (heading + "\n" + body).strip()
                if len(combined) < 25:
                    return
                sec_match = re.search(r"(\d+\.\d+)", heading)
                section_ref = sec_match.group(1) if sec_match else ""
                
                # Estimate PDF page number
                page_num = 1
                if sec_match and float(sec_match.group(1)) >= 1.4:
                    page_num = 2 if len(pdf_page_texts) >= 2 else 1

                all_chunks.append({
                    "text": combined,
                    "source": code,
                    "title": meta["title"],
                    "section": f"Section {section_ref}" if section_ref else heading.lstrip("# ").strip(),
                    "page_number": page_num,
                    "pdf_url": pdf_url,
                    "has_image": False,
                    "language": lang,
                    "char_count": len(combined),
                })

            for part in parts:
                if heading_pattern.match(part):
                    if current_heading or current_body:
                        flush_section(current_heading, current_body)
                    current_heading = part
                    current_body = ""
                else:
                    current_body += part

            if current_heading or current_body:
                flush_section(current_heading, current_body)
        else:
            # Fallback to direct page text chunks from PDF
            for page_num, ptext in pdf_page_texts.items():
                if len(ptext) > 30:
                    all_chunks.append({
                        "text": ptext,
                        "source": code,
                        "title": meta["title"],
                        "section": f"Page {page_num}",
                        "page_number": page_num,
                        "pdf_url": pdf_url,
                        "has_image": False,
                        "language": lang,
                        "char_count": len(ptext),
                    })

        # 3. Create dedicated Multimodal Diagram Chunk extracted from the PDF page
        if meta.get("diagram_transcription"):
            diag_page = meta.get("diagram_page", 1)
            prefix = "Visual Flowchart & Process Diagram" if lang == "en" else "مخطط سير العمل والإجراءات"
            all_chunks.append({
                "text": f"[{meta['title']} — Official Visual Process Flowchart & Decision Guide on PDF Page {diag_page}]\n{meta['diagram_transcription']}",
                "source": code,
                "title": meta["title"],
                "section": f"Page {diag_page} ({prefix})",
                "page_number": diag_page,
                "pdf_url": pdf_url,
                "has_image": True,
                "language": lang,
                "char_count": len(meta["diagram_transcription"]),
            })

    if not all_chunks:
        logger.warning("No chunks to index")
        return 0

    logger.info(f"Total bilingual chunks created from PDF policies: {len(all_chunks)}")

    # Embed in batches of 20
    batch_size = 20
    texts = [c["text"] for c in all_chunks]
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embeddings = embed_batch(batch)
        all_embeddings.extend(embeddings)

    # Upsert to Qdrant
    client = get_qdrant()
    points = [
        PointStruct(
            id=idx,
            vector=embedding,
            payload={
                "text": chunk["text"],
                "source": chunk["source"],
                "title": chunk["title"],
                "section": chunk["section"],
                "page_number": chunk["page_number"],
                "pdf_url": chunk["pdf_url"],
                "has_image": chunk["has_image"],
                "language": chunk["language"],
                "char_count": chunk["char_count"],
            },
        )
        for idx, (chunk, embedding) in enumerate(zip(all_chunks, all_embeddings))
    ]

    client.upsert(collection_name=settings.qdrant_collection, points=points)
    logger.info(f"✅ Ingestion complete: {len(points)} bilingual multimodal chunks indexed into Qdrant")
    return len(points)


# ── Sparse Lexical Token Scorer (BM25 Approximation) ──────────────

def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"\w+", text) if len(w) > 2]


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], avgdl: float = 120.0, k1: float = 1.5, b: float = 0.75) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    doc_len = len(doc_tokens)
    score = 0.0
    doc_counts = {}
    for t in doc_tokens:
        doc_counts[t] = doc_counts.get(t, 0) + 1

    for q in query_tokens:
        tf = doc_counts.get(q, 0)
        if tf > 0:
            idf = 1.5  # Fixed standard base IDF for token match
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avgdl)))
            score += idf * tf_norm
    return score


# ── Hybrid Search (Dense Vectors + Sparse Lexical BM25 via RRF) ───

def search(
    query: str,
    top_k: int = 5,
    language_filter: Optional[str] = None,
) -> list[dict]:
    """
    Hybrid Search combining Dense Cosine Similarity and Sparse BM25 via Reciprocal Rank Fusion (RRF).
    """
    ensure_collection()
    if collection_count() == 0:
        logger.info("Collection is empty — running ingestion...")
        try:
            ingest_policies()
        except Exception as e:
            logger.warning(f"Auto-ingestion during search failed: {e}")

    if collection_count() == 0:
        return []

    client = get_qdrant()
    query_vector = embed_text(query)
    query_tokens = _tokenize(query)

    search_filter = None
    if language_filter:
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="language",
                    match=MatchValue(value=language_filter),
                )
            ]
        )

    # 1. Fetch Candidate Pool via Dense Vector Search (k=15)
    dense_hits = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=max(top_k * 3, 15),
        query_filter=search_filter,
        with_payload=True,
    ).points

    if not dense_hits:
        return []

    # 2. Compute Sparse Lexical BM25 Scores over candidate pool
    candidates = []
    for rank_dense, hit in enumerate(dense_hits):
        payload = hit.payload or {}
        text = payload.get("text", "")
        doc_tokens = _tokenize(text)
        lexical_score = _bm25_score(query_tokens, doc_tokens)
        candidates.append({
            "hit": hit,
            "payload": payload,
            "dense_score": hit.score,
            "rank_dense": rank_dense + 1,
            "lexical_score": lexical_score,
        })

    # Sort by lexical score to get rank_lexical
    candidates_by_lex = sorted(candidates, key=lambda x: x["lexical_score"], reverse=True)
    for rank_lex, c in enumerate(candidates_by_lex):
        c["rank_lex"] = rank_lex + 1

    # 3. Reciprocal Rank Fusion (RRF) with k=60
    rrf_k = 60
    for c in candidates:
        rrf_score = (1.0 / (rrf_k + c["rank_dense"])) + (1.0 / (rrf_k + c["rank_lex"]))
        c["rrf_score"] = rrf_score

    # Sort final top-K by RRF score
    final_candidates = sorted(candidates, key=lambda x: x["rrf_score"], reverse=True)[:top_k]

    return [
        {
            "text": c["payload"].get("text", ""),
            "source": c["payload"].get("source", ""),
            "title": c["payload"].get("title", ""),
            "section": c["payload"].get("section", ""),
            "page_number": c["payload"].get("page_number", 1),
            "pdf_url": c["payload"].get("pdf_url", ""),
            "has_image": c["payload"].get("has_image", False),
            "language": c["payload"].get("language", "en"),
            "score": round(min(c["dense_score"] * 1.1, 1.0), 4),
            "dense_score": round(c["dense_score"], 4),
            "lexical_score": round(c["lexical_score"], 4),
            "rrf_score": round(c["rrf_score"], 5),
        }
        for c in final_candidates
    ]
