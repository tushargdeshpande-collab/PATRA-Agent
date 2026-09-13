import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from patra.agent.controller import ApplicationAgent
from patra.config import DATA_DIR


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.profile = json.loads((DATA_DIR / "sample_candidate.json").read_text())
        self.jd = (DATA_DIR / "sample_job_description.txt").read_text()

    def tearDown(self):
        self.temp.cleanup()

    def run_agent(self, max_iterations=3, **kwargs):
        return ApplicationAgent(self.output).run(
            self.profile, self.jd, "Northstar Digital", "QA Automation Engineer",
            max_iterations, persist=False, **kwargs,
        )

    def test_agent_replans_after_failure(self):
        result = self.run_agent()
        self.assertEqual(result["summary"]["failed_candidates"], 1)
        self.assertEqual(result["summary"]["iterations"], 2)
        self.assertFalse(result["candidates"][0]["evaluation"]["passed"])
        self.assertTrue(result["candidates"][1]["evaluation"]["passed"])

    def test_candidates_genuinely_differ(self):
        result = self.run_agent()
        self.assertNotEqual(result["candidates"][0]["resume_markdown"], result["candidates"][1]["resume_markdown"])

    def test_trace_has_agentic_phases(self):
        phases = {x["phase"] for x in self.run_agent()["trace"]}
        self.assertTrue({"Observe", "Decide", "Action", "Validate", "Adapt", "Evaluate", "Approval"}.issubset(phases))

    def test_pdf_is_valid(self):
        pdf = Path(self.run_agent()["final"]["pdf_path"])
        self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
        self.assertGreaterEqual(len(PdfReader(str(pdf)).pages), 1)

    def test_change_report_exists(self):
        result = self.run_agent()
        report = json.loads(Path(result["change_report_path"]).read_text())
        self.assertEqual(report["selected_candidate"], "Candidate 2")
        self.assertTrue(report["claim_ledger"])

    def test_iteration_limit_is_respected(self):
        result = self.run_agent(max_iterations=1)
        self.assertEqual(result["summary"]["iterations"], 1)
        self.assertEqual(result["summary"]["final_status"], "HUMAN_REVIEW_REQUIRED")

    def test_run_record_exported(self):
        self.run_agent()
        self.assertTrue((self.output / "run_record.json").exists())

    def test_no_fabricated_claim_reaches_final_resume(self):
        """The single hard safety invariant: nothing in the final resume's
        claim ledger that is present in the rendered text may be unverified."""
        result = self.run_agent()
        final_markdown = result["final"]["resume_markdown"]
        for row in result["final"]["claim_ledger"]:
            if row.get("included_in_resume") and row["claim"] in final_markdown:
                self.assertEqual(row["status"], "Verified", f"Unverified claim reached final resume: {row['claim']}")

    def test_agent_accepts_uploaded_evidence(self):
        """A candidate with no structured evidence ledger can still pass if
        an uploaded supporting document semantically backs their claims."""
        profile = json.loads((DATA_DIR / "sample_candidate.json").read_text())
        # Strip the structured evidence ledger entirely.
        for job in profile["experience"]:
            for bullet in job["bullets"]:
                bullet["evidence_id"] = None
        profile["evidence"] = []
        uploaded = [{
            "id": "UP-001", "source": "project_writeup.txt",
            "text": (
                "Built and maintained Selenium test suites for web-based regression testing. "
                "Created Python and Pytest checks for API and data-validation workflows. "
                "Used SQL, Git and Jira while collaborating with developers in Agile delivery cycles."
            ),
        }]
        result = ApplicationAgent(self.output).run(
            profile, self.jd, "Northstar Digital", "QA Automation Engineer",
            max_iterations=3, uploaded_evidence=uploaded, persist=False,
        )
        final_ledger = result["final"]["claim_ledger"]
        verified_from_upload = [r for r in final_ledger if r["status"] == "Verified" and r["source"] == "project_writeup.txt"]
        self.assertTrue(verified_from_upload)


if __name__ == "__main__":
    unittest.main()
