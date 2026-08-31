import re
import pandas as pd

df = pd.read_excel(r"d:\HCS_01\test_scenarios_md.xlsx")

def parse_prompts(text):
    if not isinstance(text, str) or not text.strip():
        return []
    
    # Check if there are quotes or newlines or arrows
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    extracted = []
    for line in lines:
        # Check if line contains -> or → (multi-turn)
        parts = re.split(r'\s*(?:->|→)\s*', line)
        for part in parts:
            # Strip quotes and smart quotes
            clean = part.strip().strip('"\'“”`‘’')
            if clean:
                extracted.append(clean)
    return extracted

for i, r in df.iterrows():
    test_id = str(r.get("Test ID", ""))
    emp = str(r.get("employee_id", "")).replace("_", "").strip()
    raw = str(r.get("Example User Prompts", ""))
    prompts = parse_prompts(raw)
    with open("d:/HCS_01/Backend/scripts/parsed_summary.txt", "a", encoding="utf-8") as f:
        f.write(f"[{i+1}] {test_id} (Emp: {emp}) - {len(prompts)} prompts:\n")
        for p in prompts:
            f.write(f"    - {p}\n")

print("Done writing parsed_summary.txt")
