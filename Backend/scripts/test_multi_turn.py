import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.main import app

with TestClient(app) as client:
    # 1. Test direct query
    resp1 = client.post(
        "/api/v1/hcs01/query",
        json={
            "query": "how many leaves i have?",
            "employee_id": "EMP002",
            "conversation_id": "test-session-fresh-1"
        }
    )
    print("=" * 60)
    print("DIRECT QUERY 'how many leaves i have?':")
    print("=" * 60)
    print(resp1.json().get("answer"))
    print("=" * 60)
