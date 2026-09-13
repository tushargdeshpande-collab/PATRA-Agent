import copy
import json
import unittest

from patra.agent.strategies import initial_strategy
from patra.config import DATA_DIR
from patra.tools.drafter import draft_resume
from patra.tools.evaluators import evaluate_resume
from patra.tools.evidence import build_evidence_index


class ContradictionDetectionTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((DATA_DIR / "sample_candidate.json").read_text())
        self.jd = {"role": "QA Automation Engineer", "requirements": ["selenium", "python", "sql"], "word_count": 50}

    def _draft_and_evaluate(self, profile):
        evidence = build_evidence_index(profile)
        draft = draft_resume(profile, self.jd, evidence, initial_strategy())
        return evaluate_resume(draft, self.jd, profile)

    def test_unsupported_numeric_claim_flagged_as_contradiction(self):
        evaluation = self._draft_and_evaluate(self.profile)
        self.assertIn("FACTUAL_CONTRADICTION", evaluation["reason_codes"])
        self.assertTrue(any("40%" in c or "Numeric claim" in c for c in evaluation["contradictions"]))

    def test_invalid_date_range_flagged(self):
        profile = copy.deepcopy(self.profile)
        profile["experience"][0]["period"] = "2024–2019"  # ends before it starts
        evaluation = self._draft_and_evaluate(profile)
        self.assertIn("FACTUAL_CONTRADICTION", evaluation["reason_codes"])
        self.assertTrue(any("end year before its start year" in c for c in evaluation["contradictions"]))

    def test_valid_ongoing_role_not_flagged_for_dates(self):
        profile = copy.deepcopy(self.profile)
        profile["experience"][0]["period"] = "2022–Present"
        evaluation = self._draft_and_evaluate(profile)
        date_contradictions = [c for c in evaluation["contradictions"] if "end year before" in c]
        self.assertEqual(date_contradictions, [])

    def test_clean_evidence_backed_resume_has_no_contradictions(self):
        profile = copy.deepcopy(self.profile)
        # Remove the one deliberately-unsupported bullet.
        profile["experience"][0]["bullets"] = [
            b for b in profile["experience"][0]["bullets"] if b["evidence_id"] != "EV-999"
        ]
        evaluation = self._draft_and_evaluate(profile)
        self.assertEqual(evaluation["contradictions"], [])
        self.assertNotIn("FACTUAL_CONTRADICTION", evaluation["reason_codes"])

    def test_dropped_claim_not_double_counted_as_contradiction_after_fix(self):
        """Once evidence-first/contradiction-fix strategies remove a claim
        from the visible resume, it must not keep being reported as a
        live contradiction — only claims that are actually still present
        in the resume are relevant to a human reviewer."""
        from patra.agent.strategies import select_next_strategy

        evidence = build_evidence_index(self.profile)
        first_draft = draft_resume(self.profile, self.jd, evidence, initial_strategy())
        first_eval = evaluate_resume(first_draft, self.jd, self.profile)
        strategy = select_next_strategy(initial_strategy(), first_eval["reason_codes"])
        second_draft = draft_resume(self.profile, self.jd, evidence, strategy)
        second_eval = evaluate_resume(second_draft, self.jd, self.profile)
        self.assertEqual(second_eval["contradictions"], [])


if __name__ == "__main__":
    unittest.main()
