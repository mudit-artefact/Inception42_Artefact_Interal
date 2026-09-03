import urllib.request
import json
import sys

# Ensure utf-8 stdout on windows
sys.stdout.reconfigure(encoding='utf-8')

def main():
    print("Testing Backend APIs...")
    
    # 1. Employees list
    resp = urllib.request.urlopen("http://127.0.0.1:8000/api/omni/employees")
    employees = json.loads(resp.read().decode())
    print(f"\n[1] /api/omni/employees -> Loaded {len(employees)} personas:")
    for e in employees:
        print(f"  - {e['id']}: {e['name']} ({e['role']}) | Manager: {e['manager']}")

    # 2. Single employee
    resp = urllib.request.urlopen("http://127.0.0.1:8000/api/omni/employee/EMP001")
    emp = json.loads(resp.read().decode())
    print(f"\n[2] /api/omni/employee/EMP001 -> {emp['name']}, Dept: {emp['department']}, Balances: {len(emp['balances'])}")

    # 3. Agent Question
    payload = json.dumps({
        "message": "What is my remaining annual leave balance?",
        "employee_id": "EMP001"
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/hcs01/query",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req)
    agent_ans = json.loads(resp.read().decode())
    print(f"\n[3] Agent Query Answer for Alia Al Suwaidi (EMP001):")
    print(f"  Intent: {agent_ans.get('intent')}")
    print(f"  Answer: {agent_ans.get('answer')}")

    # 4. School Verification Query
    payload_school = json.dumps({
        "message": "What is the status of schooling verification for Zayed?",
        "employee_id": "EMP001"
    }).encode("utf-8")
    req_school = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1/hcs01/query",
        data=payload_school,
        headers={"Content-Type": "application/json"}
    )
    resp_school = urllib.request.urlopen(req_school)
    school_ans = json.loads(resp_school.read().decode())
    print(f"\n[4] School Verification Query for Child Zayed (EMP001):")
    print(f"  Intent: {school_ans.get('intent')}")
    print(f"  Answer: {school_ans.get('answer')}")

if __name__ == "__main__":
    main()
