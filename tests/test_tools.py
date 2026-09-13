import json
import unittest

from patra.config import DATA_DIR
from patra.agent.strategies import initial_strategy, select_next_strategy
from patra.tools.drafter import draft_resume
from patra.tools.evaluators import check_no_fabricated_metrics, evaluate_resume
from patra.tools.evidence import build_evidence_index, genuine_skills, validate_profile
from patra.tools.jd_parser import parse_job_description
from patra.tools.research import research_company, research_role


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((DATA_DIR / "sample_candidate.json").read_text())
        self.jd = parse_job_description((DATA_DIR / "sample_job_description.txt").read_text(), "QA Automation Engineer")

    def test_parse_jd_extracts_known_requirements(self):
        self.assertTrue({"selenium", "python", "pytest"}.issubset(self.jd["requirements"]))

    def test_short_jd_rejected(self):
        with self.assertRaises(ValueError):
            parse_job_description("too short", "QA")

    def test_thin_jd_uses_role_baseline_fallback(self):
        thin_jd = "We are hiring for this role. Apply now if you think you are a great fit for our growing team!"
        jd = parse_job_description(thin_jd, "QA Automation Engineer")
        self.assertTrue(jd["used_role_baseline_fallback"])
        self.assertIn("selenium", jd["requirements"])

    def test_profile_required_fields(self):
        self.assertEqual(validate_profile(self.profile)["name"], "Aarav Mehta")

    def test_missing_profile_field_rejected(self):
        del self.profile["education"]
        with self.assertRaises(ValueError):
            validate_profile(self.profile)

    def test_profile_with_non_list_skills_rejected(self):
        self.profile["skills"] = "Selenium, Python"
        with self.assertRaises(ValueError):
            validate_profile(self.profile)

    def test_evidence_index(self):
        self.assertTrue(build_evidence_index(self.profile)["EV-001"]["verified"])

    def test_genuine_skills_excludes_unsupported(self):
        skills = genuine_skills(self.profile, build_evidence_index(self.profile))
        self.assertIn("Selenium", skills)
        self.assertNotIn("Playwright", skills)

    def test_first_draft_contains_unsupported_claim(self):
        draft = draft_resume(self.profile, self.jd, build_evidence_index(self.profile), initial_strategy())
        self.assertEqual(evaluate_resume(draft, self.jd, self.profile)["unsupported_claims"], 1)

    def test_adapted_draft_removes_unsupported_claim(self):
        first = draft_resume(self.profile, self.jd, build_evidence_index(self.profile), initial_strategy())
        first_eval = evaluate_resume(first, self.jd, self.profile)
        strategy = select_next_strategy(initial_strategy(), first_eval["reason_codes"])
        draft = draft_resume(self.profile, self.jd, build_evidence_index(self.profile), strategy)
        second_eval = evaluate_resume(draft, self.jd, self.profile)
        self.assertEqual(second_eval["unsupported_claims"], 0)
        self.assertEqual(check_no_fabricated_metrics(draft), [])
        self.assertTrue(second_eval["passed"])

    def test_unknown_company_is_transparent(self):
        result = research_company("Definitely Not A Real Company 12345")
        self.assertIn(result["status"], {"unavailable", "online_summary"})
        if result["status"] == "unavailable":
            self.assertIn("note", result)

    def test_empty_company_name_is_handled(self):
        self.assertEqual(research_company("")["status"], "unavailable")

    def test_role_research_returns_baseline_for_known_role(self):
        result = research_role("QA Automation Engineer")
        self.assertEqual(result["status"], "role_baseline_available")
        self.assertIn("selenium", result["baseline_skills"])

    def test_role_research_transparent_for_unknown_role(self):
        result = research_role("Underwater Basket Weaving Specialist")
        self.assertEqual(result["status"], "role_baseline_unavailable")
        self.assertEqual(result["baseline_skills"], [])


if __name__ == "__main__":
    unittest.main()
