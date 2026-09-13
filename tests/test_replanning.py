import unittest

from patra.agent.strategies import describe, initial_strategy, select_next_strategy


class StrategySelectionTests(unittest.TestCase):
    def test_initial_strategy_has_no_fixes_applied(self):
        strategy = initial_strategy()
        self.assertEqual(strategy["name"], "broad-first-pass")
        self.assertEqual(strategy["applied_fixes"], [])
        self.assertFalse(any([
            strategy["evidence_first"], strategy["keyword_boost"],
            strategy["trim_long_bullets"], strategy["fix_contradictions"],
        ]))

    def test_single_reason_turns_on_matching_flag_only(self):
        strategy = select_next_strategy(initial_strategy(), ["UNSUPPORTED_CLAIMS"])
        self.assertTrue(strategy["evidence_first"])
        self.assertFalse(strategy["keyword_boost"])
        self.assertFalse(strategy["trim_long_bullets"])
        self.assertFalse(strategy["fix_contradictions"])
        self.assertEqual(strategy["applied_fixes"], ["evidence_first"])

    def test_multiple_simultaneous_reasons_combine_into_one_strategy(self):
        strategy = select_next_strategy(
            initial_strategy(), ["ATS_LOW", "UNSUPPORTED_CLAIMS", "FORMAT_FAIL", "FACTUAL_CONTRADICTION"],
        )
        self.assertTrue(strategy["evidence_first"])
        self.assertTrue(strategy["keyword_boost"])
        self.assertTrue(strategy["trim_long_bullets"])
        self.assertTrue(strategy["fix_contradictions"])
        self.assertEqual(len(strategy["applied_fixes"]), 4)

    def test_fixes_accumulate_across_iterations_instead_of_resetting(self):
        strategy = select_next_strategy(initial_strategy(), ["UNSUPPORTED_CLAIMS"])
        strategy = select_next_strategy(strategy, ["ATS_LOW"])
        self.assertTrue(strategy["evidence_first"])
        self.assertTrue(strategy["keyword_boost"])
        self.assertEqual(strategy["applied_fixes"], ["evidence_first", "keyword_boost"])

    def test_reapplying_same_reason_does_not_duplicate_fix(self):
        strategy = select_next_strategy(initial_strategy(), ["UNSUPPORTED_CLAIMS"])
        strategy = select_next_strategy(strategy, ["UNSUPPORTED_CLAIMS"])
        self.assertEqual(strategy["applied_fixes"], ["evidence_first"])

    def test_unknown_reason_code_is_ignored_safely(self):
        strategy = select_next_strategy(initial_strategy(), ["SOME_FUTURE_REASON_CODE"])
        self.assertEqual(strategy["applied_fixes"], [])
        self.assertEqual(strategy["name"], "broad-first-pass")

    def test_describe_is_human_readable(self):
        self.assertIn("Broad first pass", describe(initial_strategy()))
        strategy = select_next_strategy(initial_strategy(), ["FORMAT_FAIL"])
        self.assertIn("shorten oversized bullets", describe(strategy))


if __name__ == "__main__":
    unittest.main()
