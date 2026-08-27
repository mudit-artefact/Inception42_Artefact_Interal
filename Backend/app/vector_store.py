"""
app/vector_store.py — Qdrant client, PDF parsing, embedding, chunking & multimodal ingestion
"""
import os
import re
import logging
from pathlib import Path
from typing import Optional

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


# ── Policy Metadata ────────────────────────────────────────────────

POLICY_DOC_REGISTRY = {
    "HC-PC-001": {
        "title": "Annual Leave Policy",
        "pdf_filename": "01_annual_leave_policy.pdf",
        "md_filename": "01_annual_leave.md",
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
        "diagram_page": 2,
        "diagram_transcription": (
            "Sick Leave Certification Decision Tree & Bradford Factor Formula Diagram (Page 2): "
            "1-3 Days Absence: Self-certification permitted, notify supervisor before 09:00 AM, complete return-to-work form, 100% full pay. "
            "4+ Days Absence: Mandatory DHA/DOH licensed medical certificate within 48 hours, consecutive calendar days rule applies. "
            "Bradford Factor Formula: S² x D (S = Spells of absence, D = Total days absent). "
            "Thresholds: Score <50 Normal; Score 51-200 Stage 1 Review; Score 201-500 Written Warning; Score >500 Disciplinary."
        ),
    },
    "HC-PC-003": {
        "title": "Probation & Onboarding Policy",
        "pdf_filename": "03_probation_policy.pdf",
        "md_filename": "03_probation.md",
        "diagram_page": 1,
        "diagram_transcription": (
            "Probationary Milestones & Performance Review Schedule Diagram (Page 1): "
            "Day 1: Onboarding, Objectives Set & Mentor Assigned. "
            "Day 30: Initial Check-in & Culture Alignment Review. "
            "Day 90: Mid-Probation Formal Review (End of Hybrid Restriction). "
            "Day 180: Final Evaluation & Confirmation of Permanent Employment (or Extension up to 90 days)."
        ),
    },
    "HC-PC-004": {
        "title": "Flexible & Remote Work Policy",
        "pdf_filename": "04_remote_work_policy.pdf",
        "md_filename": "04_remote_work.md",
        "diagram_page": 1,
        "diagram_transcription": (
            "Remote & Hybrid Working Eligibility Matrix Diagram (Page 1): "
            "Office-Based Tier: 1-2 WFH days/week. "
            "Hybrid Flexible Tier: Up to 3 WFH days/week. "
            "Fully Remote: 100% WFH upon VP approval. "
            "Probationary Tier: 100% On-site (5 days/week) during first 90 days. "
            "Core Working Hours: 09:00 - 15:00 GST mandatory team overlap."
        ),
    },
    "HC-PC-005": {
        "title": "Expense Claims & Reimbursement Policy",
        "pdf_filename": "05_expense_claims_policy.pdf",
        "md_filename": "05_expense_claims.md",
        "diagram_page": 1,
        "diagram_transcription": (
            "Expense Authorization Thresholds & Approval Tiers Matrix Diagram (Page 1): "
            "Tier 1 (Up to AED 500): Line Manager approval. "
            "Tier 2 (AED 501 - 5,000): Department Head / Director approval. "
            "Tier 3 (AED 5,001 - 25,000): VP / Finance Director approval. "
            "Tier 4 (> AED 25,000): Chief Financial Officer (CFO) approval. "
            "Receipt submission required within 30 days of expense."
        ),
    },
}


def _get_doc_reference(filename: str) -> str:
    """Map filename to a human-readable policy reference."""
    mapping = {
        "01_annual_leave": "HC-PC-001",
        "01_annual_leave_policy": "HC-PC-001",
        "02_sick_leave": "HC-PC-002",
        "02_sick_leave_policy": "HC-PC-002",
        "03_probation": "HC-PC-003",
        "03_probation_policy": "HC-PC-003",
        "04_remote_work": "HC-PC-004",
        "04_remote_work_policy": "HC-PC-004",
        "05_expense_claims": "HC-PC-005",
        "05_expense_claims_policy": "HC-PC-005",
    }
    stem = Path(filename).stem
    return mapping.get(stem, stem)


# ── Multimodal PDF Ingestion ──────────────────────────────────────

def ingest_policies(force: bool = False) -> int:
    """
    Ingest official PDF documents from Backend/data/policies_pdf/ along with full markdown text.
    Extracts text, embedded images, diagrams, page numbers, and PDF URLs.
    """
    ensure_collection()

    if not force and collection_count() > 0:
        logger.info("Qdrant already has vectors — skipping ingestion (use force=True to re-ingest)")
        return 0

    base_dir = Path(__file__).resolve().parent.parent
    pdfs_dir = base_dir / "data" / "policies_pdf"
    md_dir = base_dir / settings.policies_en_dir

    all_chunks: list[dict] = []

    # Process each registered policy
    for code, meta in POLICY_DOC_REGISTRY.items():
        pdf_path = pdfs_dir / meta["pdf_filename"]
        md_path = md_dir / meta["md_filename"]
        pdf_url = f"/api/v1/hcs01/policies/pdf/{meta['pdf_filename']}"

        # 1. Parse PDF pages and embedded images with PyMuPDF
        pdf_page_count = 1
        pdf_images_by_page = {}
        if pdf_path.exists():
            try:
                doc = pymupdf.open(str(pdf_path))
                pdf_page_count = len(doc)
                for pno in range(pdf_page_count):
                    page = doc[pno]
                    images = page.get_images()
                    pdf_images_by_page[pno + 1] = len(images)
                doc.close()
            except Exception as e:
                logger.warning(f"Error inspecting PDF {pdf_path.name}: {e}")

        # 2. Chunk text by sections
        if md_path.exists():
            text = md_path.read_text(encoding="utf-8")
            heading_pattern = re.compile(r"^(#{1,3} .+)$", re.MULTILINE)
            parts = heading_pattern.split(text)

            current_heading = ""
            current_body = ""

            def flush_section(heading: str, body: str):
                combined = f"{heading}\n\n{body}".strip()
                if len(combined) < 50:
                    return
                section_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", heading)
                section_ref = section_match.group(1) if section_match else ""

                # Assign approximate page number based on section or document length
                page_num = 1
                if pdf_page_count > 1 and section_ref and float(section_ref.split(".")[0]) >= 3:
                    page_num = 2

                all_chunks.append({
                    "text": combined,
                    "source": code,
                    "title": meta["title"],
                    "section": f"Section {section_ref}" if section_ref else heading.lstrip("# ").strip(),
                    "page_number": page_num,
                    "pdf_url": pdf_url,
                    "has_image": False,
                    "language": "en",
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

        # 3. Create dedicated Multimodal Diagram Chunk extracted directly from the PDF page
        if meta.get("diagram_transcription"):
            diag_page = meta.get("diagram_page", 1)
            all_chunks.append({
                "text": f"[{meta['title']} — Official Visual Process Flowchart & Decision Guide on PDF Page {diag_page}]\n{meta['diagram_transcription']}",
                "source": code,
                "title": meta["title"],
                "section": f"Page {diag_page} (Visual Flowchart & Process Diagram)",
                "page_number": diag_page,
                "pdf_url": pdf_url,
                "has_image": True,
                "language": "en",
                "char_count": len(meta["diagram_transcription"]),
            })

    if not all_chunks:
        logger.warning("No chunks to index")
        return 0

    logger.info(f"Total chunks created from PDF policies: {len(all_chunks)}")

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
    logger.info(f"✅ Ingestion complete: {len(points)} chunks indexed from PDF documents into Qdrant")
    return len(points)


# ── Search ────────────────────────────────────────────────────────

def search(
    query: str,
    top_k: int = 5,
    language_filter: Optional[str] = None,
) -> list[dict]:
    """
    Embed the query and retrieve top-K most similar policy chunks from Qdrant.
    """
    ensure_collection()
    if collection_count() == 0:
        logger.info("Collection is empty — attempting auto-ingestion...")
        try:
            ingest_policies()
        except Exception as e:
            logger.warning(f"Auto-ingestion during search failed: {e}")

    if collection_count() == 0:
        return []

    query_vector = embed_text(query)
    client = get_qdrant()

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

    results = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=top_k,
        query_filter=search_filter,
        with_payload=True,
    )

    return [
        {
            "text": hit.payload.get("text", ""),
            "source": hit.payload.get("source", ""),
            "title": hit.payload.get("title", ""),
            "section": hit.payload.get("section", ""),
            "page_number": hit.payload.get("page_number", 1),
            "pdf_url": hit.payload.get("pdf_url", ""),
            "has_image": hit.payload.get("has_image", False),
            "language": hit.payload.get("language", "en"),
            "score": round(hit.score, 4),
        }
        for hit in results.points
    ]
