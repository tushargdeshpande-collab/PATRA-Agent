import json
import tempfile
import unittest
from pathlib import Path

from patra.agent.controller import ApplicationAgent
from patra.config import DATA_DIR
from patra.tools import persistence


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.db_path = self.output / "test_history.sqlite3"
        self.profile = json.loads((DATA_DIR / "sample_candidate.json").read_text())
        self.jd = (DATA_DIR / "sample_job_description.txt").read_text()

    def tearDown(self):
        self.temp.cleanup()

    def _run(self):
        return ApplicationAgent(self.output).run(
            self.profile, self.jd, "Northstar Digital", "QA Automation Engineer", persist=False,
        )

    def test_save_and_list_run(self):
        result = self._run()
        run_id = persistence.save_run(result, db_path=self.db_path)
        runs = persistence.list_runs(db_path=self.db_path)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["run_id"], run_id)
        self.assertEqual(runs[0]["company"], "Northstar Digital")

    def test_get_run_returns_full_record(self):
        result = self._run()
        run_id = persistence.save_run(result, db_path=self.db_path)
        fetched = persistence.get_run(run_id, db_path=self.db_path)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["goal"]["role"], "QA Automation Engineer")
        self.assertEqual(len(fetched["candidates"]), len(result["candidates"]))

    def test_get_unknown_run_returns_none(self):
        self.assertIsNone(persistence.get_run("does-not-exist", db_path=self.db_path))

    def test_save_approval_and_retrieve(self):
        result = self._run()
        run_id = persistence.save_run(result, db_path=self.db_path)
        persistence.save_approval(run_id, "Approve", "Looks good", db_path=self.db_path)
        approvals = persistence.get_approvals(run_id, db_path=self.db_path)
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0]["decision"], "Approve")

    def test_multiple_runs_are_ordered_most_recent_first(self):
        result_a = self._run()
        run_id_a = persistence.save_run(result_a, db_path=self.db_path)
        result_b = self._run()
        run_id_b = persistence.save_run(result_b, db_path=self.db_path)
        runs = persistence.list_runs(db_path=self.db_path)
        self.assertEqual(runs[0]["run_id"], run_id_b)
        self.assertEqual(runs[1]["run_id"], run_id_a)

    def test_history_persists_across_separate_connections(self):
        result = self._run()
        run_id = persistence.save_run(result, db_path=self.db_path)
        # Simulate a fresh app restart: a brand new call still sees it.
        fetched = persistence.get_run(run_id, db_path=self.db_path)
        self.assertIsNotNone(fetched)

    def test_controller_persist_flag_writes_to_default_db(self):
        result = ApplicationAgent(self.output).run(
            self.profile, self.jd, "Northstar Digital", "QA Automation Engineer", persist=True,
        )
        self.assertIn("run_id", result)
        fetched = persistence.get_run(result["run_id"])
        self.assertIsNotNone(fetched)


if __name__ == "__main__":
    unittest.main()
