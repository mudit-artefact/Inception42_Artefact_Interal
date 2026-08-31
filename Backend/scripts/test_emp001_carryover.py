import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.main import app

with TestClient(app) as client:
    resp = client.post(
        "/api/v1/hcs01/query",
        json={
            "query": "what is my leave balance?",
            "employee_id": "EMP001",
            "conversation_id": "test-emp001-carryover"
        }
    )
    print("STATUS:", resp.status_code)
    data = resp.json()
    print("=" * 60)
    print("EMP001 ANSWER (Has 3 Carry-over days):")
    print("=" * 60)
    print(data.get("answer"))
    print("=" * 60)
