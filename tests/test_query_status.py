import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.query.query import Condition, Field, Operator, Query


class TestStatus(unittest.TestCase):
    def test_no_active_conditions_is_failed(self):
        q = Query("clean energy startups")
        q.fill_phantom_conditions()          # only phantom conditions, nothing active
        self.assertEqual(q.status, "failed")

    def test_api_error_with_local_conditions_is_partial(self):
        q = Query("public software companies")
        q.add_condition(Condition(Field.IS_PUBLIC, Operator.EQ, True, span=(0, 6)))
        q.api_called = True
        q.api_error = "503"
        self.assertEqual(q.status, "partial")

    def test_normal_run_is_understood(self):
        q = Query("public software companies")
        q.add_condition(Condition(Field.IS_PUBLIC, Operator.EQ, True, span=(0, 6)))
        self.assertEqual(q.status, "understood")

    def test_record_has_the_notes(self):
        q = Query("public")
        q.add_condition(Condition(Field.IS_PUBLIC, Operator.EQ, True, span=(0, 6)))
        q.api_called, q.api_error, q.api_ms = True, "429", 1234.5678
        r = q.to_record()
        self.assertEqual((r["status"], r["api_called"], r["api_error"]), ("partial", True, "429"))
        self.assertEqual(r["conditions"][0]["field"], "is_public")


if __name__ == "__main__":
    unittest.main()
