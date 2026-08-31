import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.main import app

with TestClient(app) as client:
    resp = client.post(
        "/api/v1/hcs01/query",
        json={
            "query": "How many annual-leave days do I have remaining?",
            "employee_id": "EMP001",
            "conversation_id": "quick-test-1"
        }
    )
    print("Status:", resp.status_code)
    print("Response JSON:", resp.json())
