import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.process.filter import HardFilterProcessor
from src.query.query import Condition, Field, Operator, Query

COMPANIES = [
    {"operational_name": "A", "employee_count": 50, "address": {"country_code": "ro"}},
    {"operational_name": "B", "employee_count": None, "address": None},
    {"operational_name": "C", "employee_count": 5000, "address": {"country_code": "de"}},
]


def run_filter(query):
    out = os.path.join(tempfile.mkdtemp(), "candidates.jsonl")
    with HardFilterProcessor(query, out) as p:
        for c in COMPANIES:
            p.process_company(c, raw_json_line=json.dumps(c))
    return p, open(out, encoding="utf-8").read()


class TestFailedQuery(unittest.TestCase):
    def test_failed_query_lets_nothing_through(self):
        q = Query("something we could not understand")
        q.fill_phantom_conditions()                       # zero active conditions
        p, written = run_filter(q)
        self.assertEqual(q.status, "failed")
        self.assertEqual((p.total_seen, p.total_passed, p.total_dropped), (3, 0, 3))
        self.assertEqual(written, "")

    def test_query_with_only_semantic_conditions_is_not_failed(self):
        q = Query("packaging for cosmetics")
        q.add_condition(Condition(Field.CORE_OFFERINGS, Operator.IN, ["packaging"], source="api"))
        q.fill_phantom_conditions()
        p, _ = run_filter(q)
        self.assertEqual(q.status, "understood")
        self.assertEqual(p.total_passed, 3)               # no hard filter, all pass, as intended

    def test_normal_query_is_still_filtered(self):
        q = Query("more than 1000 employees")
        q.add_condition(Condition(Field.EMPLOYEE_COUNT, Operator.GT, 1000, span=(0, 24)))
        q.fill_phantom_conditions()
        p, _ = run_filter(q)
        self.assertEqual(p.total_passed, 2)               # C (5000) and B (missing value, benefit of the doubt)


if __name__ == "__main__":
    unittest.main()
