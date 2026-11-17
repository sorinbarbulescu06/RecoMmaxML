import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.process.filter import HardFilterProcessor
from src.query.query import Condition, Field, Operator, Query


def passed(conditions, company):
    q = Query("pharmaceutical companies")
    for c in conditions:
        q.add_condition(c)
    q.fill_phantom_conditions()
    out = os.path.join(tempfile.mkdtemp(), "c.jsonl")
    with HardFilterProcessor(q, out) as p:
        p.process_company(company, raw_json_line=json.dumps(company))
    return p.total_passed == 1


NAICS = Condition(Field.PRIMARY_NAICS, Operator.IN, ["3254"], source="api", confidence=0.9)
WORDS = Condition(Field.CORE_OFFERINGS, Operator.IN, ["pharmaceutical", "drug"], source="api", confidence=0.9)
PHARMA_NAICS = {"code": "325412", "label": "Pharmaceutical Preparation Manufacturing"}
SOFTWARE_NAICS = {"code": "541511", "label": "Custom Computer Programming Services"}


class TestIndustryFilter(unittest.TestCase):
    def test_matching_naics_passes(self):
        self.assertTrue(passed([NAICS, WORDS], {"primary_naics": PHARMA_NAICS, "description": "web apps"}))

    def test_wrong_naics_but_matching_description_still_passes(self):
        company = {"primary_naics": SOFTWARE_NAICS, "description": "A pharmaceutical drug manufacturer"}
        self.assertTrue(passed([NAICS, WORDS], company))

    def test_wrong_naics_and_unrelated_description_is_dropped(self):
        company = {"primary_naics": SOFTWARE_NAICS, "description": "We build web apps for retail shops"}
        self.assertFalse(passed([NAICS, WORDS], company))

    def test_naics_only_query_does_not_drop_on_naics_alone(self):
        company = {"primary_naics": SOFTWARE_NAICS, "description": "We build web apps"}
        self.assertTrue(passed([NAICS], company))          # no words to compare: benefit of the doubt

    def test_company_with_no_data_gets_the_benefit_of_the_doubt(self):
        self.assertTrue(passed([NAICS, WORDS], {"operational_name": "Empty Co"}))

    def test_threshold_stays_inside_the_documented_range(self):
        for n_words in (1, 3, 7, 12, 40):
            q = Query("x")
            q.add_condition(Condition(Field.CORE_OFFERINGS, Operator.IN, [f"word{i}x" for i in range(n_words)], "api", 0.9))
            q.fill_phantom_conditions()
            p = HardFilterProcessor(q, os.path.join(tempfile.mkdtemp(), "c.jsonl"))
            self.assertGreaterEqual(p.industry_threshold, HardFilterProcessor.MIN_THRESHOLD)
            self.assertLessEqual(p.industry_threshold, HardFilterProcessor.MAX_THRESHOLD)
        self.assertEqual(HardFilterProcessor.MAX_THRESHOLD, 0.20)


if __name__ == "__main__":
    unittest.main()
