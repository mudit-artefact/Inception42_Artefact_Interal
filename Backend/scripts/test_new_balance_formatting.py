import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.main import app

with TestClient(app) as client:
    resp = client.post(
        "/api/v1/hcs01/query",
        json={
            "query": "hi, how many leaves i have?",
            "employee_id": "EMP002",
            "conversation_id": "test-generic-leaves-check"
        }
    )
    print("STATUS:", resp.status_code)
    data = resp.json()
    print("=" * 60)
    print("NEW ANSWER FOR 'hi, how many leaves i have?':")
    print("=" * 60)
    print(data.get("answer"))
    print("=" * 60)
