from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

required = [
    "app.py", "requirements.txt", "patra/agent/controller.py",
    "data/sample_candidate.json", "tests/test_agent.py",
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit("Missing required files: " + ", ".join(missing))

for module in ["streamlit", "pandas", "reportlab", "pypdf", "docx"]:
    __import__(module)
print("RESULT: Ready to run")
