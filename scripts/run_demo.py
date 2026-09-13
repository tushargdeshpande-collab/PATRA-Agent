import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from patra.agent.controller import ApplicationAgent
from patra.config import DATA_DIR

profile = json.loads((DATA_DIR / "sample_candidate.json").read_text())
jd = (DATA_DIR / "sample_job_description.txt").read_text()
result = ApplicationAgent(Path(tempfile.mkdtemp(prefix="patra_demo_"))).run(
    profile, jd, "Northstar Digital", "QA Automation Engineer", persist=False
)
print(json.dumps(result["summary"], indent=2))
print("Final PDF:", result["final"]["pdf_path"])
