import json
import unittest

from patra.config import DATA_DIR
from patra.tools.drafter import draft_resume
from patra.tools.evaluators import evaluate_resume
from patra.tools.evidence import build_evidence_index
from patra.tools.jd_parser import parse_job_description


def strategy(evidence_first: bool) -> dict:
    return {
        "name": "evidence-first" if evidence_first else "broad-first-pass",
        "evidence_first": evidence_first,
        "keyword_boost": evidence_first,
        "trim_long_bullets": False,
        "fix_contradictions": False,
        "applied_fixes": ["evidence_first"] if evidence_first else [],
    }


class SupplementaryClaimTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((DATA_DIR / "sample_candidate.json").read_text())
        self.jd = parse_job_description(
            (DATA_DIR / "sample_job_description.txt").read_text(),
            "QA Automation Engineer",
        )

    def _draft(self, evidence_first: bool):
        return draft_resume(
            self.profile,
            self.jd,
            build_evidence_index(self.profile, []),
            strategy(evidence_first),
        )

    def test_unsupported_project_is_ledgered_and_rejected(self):
        claim = "Built a nationwide platform used by 1 million users."
        self.profile["projects"] = [{"text": claim}]
        draft = self._draft(False)
        self.assertIn(claim, draft["markdown"])
        row = next(x for x in draft["claim_ledger"] if x["claim"] == claim)
        self.assertEqual(row["section"], "Projects")
        self.assertEqual(row["status"], "Unsupported")
        self.assertFalse(evaluate_resume(draft, self.jd, self.profile)["passed"])

    def test_unsupported_project_is_removed_from_final_strategy(self):
        claim = "Built a nationwide platform used by 1 million users."
        self.profile["projects"] = [{"text": claim}]
        draft = self._draft(True)
        self.assertNotIn(claim, draft["markdown"])
        row = next(x for x in draft["claim_ledger"] if x["claim"] == claim)
        self.assertFalse(row["included_in_resume"])

    def test_verified_project_reaches_resume(self):
        claim = "Created a Selenium regression automation framework."
        self.profile["projects"] = [{"text": claim, "evidence_id": "EV-PROJ"}]
        self.profile["evidence"].append({
            "id": "EV-PROJ", "source": "project report", "verified": True,
            "details": claim,
        })
        draft = self._draft(True)
        self.assertIn(claim, draft["markdown"])
        row = next(x for x in draft["claim_ledger"] if x["claim"] == claim)
        self.assertEqual(row["status"], "Verified")

    def test_certification_and_achievement_cannot_bypass_ledger(self):
        self.profile["certifications"] = [{"text": "Certified Galactic Cloud Architect"}]
        self.profile["achievements"] = [{"text": "Won 99 international awards"}]
        draft = self._draft(True)
        self.assertNotIn("Galactic", draft["markdown"])
        self.assertNotIn("99 international", draft["markdown"])
        sections = {x.get("section") for x in draft["claim_ledger"]}
        self.assertIn("Certifications", sections)
        self.assertIn("Achievements", sections)

    def test_verified_leadership_is_rendered(self):
        claim = "Led the college automation club."
        self.profile["leadership"] = [{"text": claim, "evidence_id": "EV-LEAD"}]
        self.profile["evidence"].append({
            "id": "EV-LEAD", "source": "appointment letter", "verified": True,
            "details": claim,
        })
        draft = self._draft(True)
        self.assertIn("## Leadership & Positions", draft["markdown"])
        self.assertIn(claim, draft["markdown"])

    def test_links_are_rendered_as_supplied_identifiers(self):
        self.profile["links"] = ["github.com/example/profile"]
        draft = self._draft(True)
        self.assertIn("## Links", draft["markdown"])
        self.assertIn("github.com/example/profile", draft["markdown"])


if __name__ == "__main__":
    unittest.main()
