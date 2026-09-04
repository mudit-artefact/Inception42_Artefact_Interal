"""
Integration test suite for HCS-11 Document Verification API integration.
Verifies sample test cases E0001 (Alia Al Suwaidi) and E0002 (Rashid Al Ketbi).
"""

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from app.main import app

DOCUMENTS_DIR = Path("D:/hcs-11-verification/documents")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def require_hcs11_server():
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    result = sock.connect_ex(("127.0.0.1", 8001))
    sock.close()
    if result != 0:
        pytest.skip("HCS-11 backend service is not running on localhost:8001")


def test_hcs11_health(client):
    """Test HCS-11 backend health check proxy."""
    response = client.get("/api/v1/hcs11/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["hcs11_status"] == "ok"
    assert "open_cycle" in data


def test_hcs11_list_cases_e0001(client):
    """Test retrieving cases for employee E0001 (Alia Al Suwaidi)."""
    response = client.get("/api/v1/hcs11/cases", params={"employee_id": "E0001"})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    case_ids = [c["case_id"] for c in data["cases"]]
    assert "CASE0001" in case_ids


def test_hcs11_list_cases_e0002(client):
    """Test retrieving cases for employee E0002 (Rashid Al Ketbi)."""
    response = client.get("/api/v1/hcs11/cases", params={"employee_id": "E0002"})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 1
    case_ids = [c["case_id"] for c in data["cases"]]
    assert "CASE0003" in case_ids


def test_hcs11_active_case_e0001(client):
    """Test getting current active case for E0001."""
    response = client.get("/api/v1/hcs11/active-case", params={"employee_id": "E0001"})
    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert "case" in data
    assert "status_message" in data


def test_hcs11_upload_valid_document_e0001(client):
    """
    Test uploading a valid proof of schooling for E0001 (CASE0001 - Rami Haddad).
    Expected outcome: straight-through approval.
    """
    pdf_path = DOCUMENTS_DIR / "primary" / "approved-automatically--Rami-Haddad.pdf"
    if not pdf_path.exists():
        pytest.skip("Test document not found at expected path")

    with open(pdf_path, "rb") as f:
        files = [("files", ("approved-automatically--Rami-Haddad.pdf", f, "application/pdf"))]
        response = client.post("/api/v1/hcs11/cases/CASE0001/documents", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["case_status"] == "Approved"
    assert data["payment_status"] == "Ready"
    assert "Rami Haddad" in data["message"]


def test_hcs11_upload_valid_document_e0002(client):
    """
    Test uploading a valid proof of schooling for E0002 (CASE0003 - Sara Nasser).
    Expected outcome: straight-through approval.
    """
    pdf_path = DOCUMENTS_DIR / "primary" / "approved-automatically--Sara-Nasser.pdf"
    if not pdf_path.exists():
        pytest.skip("Test document not found at expected path")

    with open(pdf_path, "rb") as f:
        files = [("files", ("approved-automatically--Sara-Nasser.pdf", f, "application/pdf"))]
        response = client.post("/api/v1/hcs11/cases/CASE0003/documents", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["case_status"] == "Approved"
    assert data["payment_status"] == "Ready"
    assert "Sara Nasser" in data["message"]


def test_hcs11_upload_edge_case_needs_review(client):
    """
    Test uploading a document with mismatched dependent name for CASE0002 (Maya Haddad).
    Expected outcome: routes to human review (Under Review).
    """
    pdf_path = DOCUMENTS_DIR / "edge_cases" / "needs-a-person--wrong-academic-year--Rami-Haddad.pdf"
    if not pdf_path.exists():
        pytest.skip("Test document not found at expected path")

    with open(pdf_path, "rb") as f:
        files = [("files", ("needs-a-person--wrong-academic-year--Rami-Haddad.pdf", f, "application/pdf"))]
        response = client.post("/api/v1/hcs11/cases/CASE0002/documents", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "needs_review"
    assert data["case_status"] == "Under Review"
    assert data["can_reupload"] is True
    assert len(data["issues"]) > 0
