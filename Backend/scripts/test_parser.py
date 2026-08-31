import re
import pandas as pd

df = pd.read_excel(r"d:\HCS_01\test_scenarios_md.xlsx")

def extract_prompts(test_id, text):
    if not isinstance(text, str) or not text.strip():
        return []
    
    text = text.strip()
    
    # Check for T1: ... T2: ... T3: ...
    if re.search(r'T\d+:', text):
        # Extract segments
        pattern = r"T\d+:\s*(?:\([^)]*\)\s*)?['\"]?([^'\"\n]+)['\"]?"
        matches = re.findall(pattern, text)
        if matches:
            return [m.strip().strip("'\"") for m in matches if m.strip()]
    
    # Check for arrow flow e.g. A → B → C
    if '→' in text or '->' in text:
        parts = re.split(r'\s*(?:->|→)\s*', text)
        return [p.strip().strip("'\"“”`") for p in parts if p.strip()]
        
    # Check for multi-line quotes e.g. "Q1"\n"Q2"
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if len(lines) > 1:
        extracted = []
        for line in lines:
            # If line has multiple comma items without quotes (like row 37 line 1)
            clean = line.strip().strip("'\"“”`")
            if clean:
                extracted.append(clean)
        return extracted
    
    # Row 38 or comma separated non-quoted list of prompts
    if test_id == 'TAX-38' and ',' in text:
        return [p.strip() for p in text.split(',') if p.strip()]
        
    return [text.strip().strip("'\"“”`")]

with open("d:/HCS_01/Backend/scripts/parsed_check.txt", "w", encoding="utf-8") as f:
    for i, r in df.iterrows():
        t_id = str(r["Test ID"])
        raw = str(r["Example User Prompts"])
        prompts = extract_prompts(t_id, raw)
        f.write(f"Row {i+1} [{t_id}] -> {len(prompts)} queries:\n")
        for idx, p in enumerate(prompts, 1):
            f.write(f"   ({idx}) {p}\n")

print("Parsed check written to parsed_check.txt")
