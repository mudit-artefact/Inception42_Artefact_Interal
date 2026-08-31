import pandas as pd

df = pd.read_excel(r"d:\HCS_01\test_scenarios_md.xlsx")
with open("d:/HCS_01/Backend/scripts/all_rows_dump.txt", "w", encoding="utf-8") as f:
    for i, r in df.iterrows():
        f.write(f"=== ROW {i+1}: {r['Test ID']} ===\n")
        f.write(f"Emp ID: {r['employee_id']}\n")
        f.write(f"Aspect: {r['Aspect']}\n")
        f.write(f"Category: {r['Category']}\n")
        f.write(f"Definition: {r['Definition / Expected Behavior']}\n")
        f.write(f"Prompts: {repr(r['Example User Prompts'])}\n")
        f.write(f"Success Criteria: {r['Success Criteria']}\n\n")

print("Dumped all rows to all_rows_dump.txt")
