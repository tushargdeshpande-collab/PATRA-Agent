import unittest
import urllib.error
from unittest import mock

from patra.tools import research


class ResearchFallbackTests(unittest.TestCase):
    def test_local_knowledge_used_when_online_lookup_fails(self):
        with mock.patch.object(research, "_try_online_summary", return_value=None):
            result = research.research_company("Northstar Digital")
        self.assertEqual(result["status"], "local_knowledge")
        self.assertEqual(result["company"], "Northstar Digital")

    def test_unavailable_when_online_fails_and_no_local_record(self):
        with mock.patch.object(research, "_try_online_summary", return_value=None):
            result = research.research_company("Some Company That Does Not Exist Anywhere")
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("note", result)

    def test_network_timeout_falls_back_gracefully(self):
        def raise_timeout(*args, **kwargs):
            raise TimeoutError("simulated network timeout")

        with mock.patch("urllib.request.urlopen", side_effect=raise_timeout):
            result = research.research_company("Northstar Digital")
        self.assertEqual(result["status"], "local_knowledge")

    def test_dns_failure_falls_back_gracefully(self):
        def raise_url_error(*args, **kwargs):
            raise urllib.error.URLError("simulated DNS failure")

        with mock.patch("urllib.request.urlopen", side_effect=raise_url_error):
            result = research.research_company("Unknown Company Xyz")
        self.assertEqual(result["status"], "unavailable")

    def test_malformed_online_response_falls_back_gracefully(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b"not valid json"

        with mock.patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = research.research_company("Northstar Digital")
        self.assertEqual(result["status"], "local_knowledge")

    def test_online_disabled_via_config_skips_straight_to_offline(self):
        with mock.patch.object(research, "RESEARCH_ONLINE_ENABLED", False):
            result = research.research_company("Northstar Digital")
        self.assertEqual(result["status"], "local_knowledge")

    def test_no_company_name_is_transparent(self):
        self.assertEqual(research.research_company("   ")["status"], "unavailable")

    def test_role_research_offline_only_never_raises(self):
        # role research has no network dependency at all
        result = research.research_role("QA Automation Engineer")
        self.assertIn(result["status"], {"role_baseline_available", "role_baseline_unavailable"})


if __name__ == "__main__":
    unittest.main()
