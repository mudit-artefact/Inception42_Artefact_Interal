import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.main import app

with TestClient(app) as client:
    resp1 = client.post(
        "/api/v1/hcs01/query",
        json={
            "query": "what is my leave balance?",
            "employee_id": "EMP001",
            "conversation_id": "test-emp001-carryover-1"
        }
    )
    print("=" * 60)
    print("QUERY 1: what is my leave balance?")
    print("=" * 60)
    print(resp1.json().get("answer"))

    resp2 = client.post(
        "/api/v1/hcs01/query",
        json={
            "query": "How many annual leave days do I have left this year?",
            "employee_id": "EMP001",
            "conversation_id": "test-emp001-carryover-2"
        }
    )
    print("=" * 60)
    print("QUERY 2: How many annual leave days do I have left this year?")
    print("=" * 60)
    print(resp2.json().get("answer"))
    print("=" * 60)
