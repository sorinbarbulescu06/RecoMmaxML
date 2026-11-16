import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.base.geo import load_geo
from src.process.filter import HardFilterProcessor
from src.query.local import LocalConditionExtractor
from src.query.query import Field, Query

GEO = load_geo()


def address_conditions(text, brute_mode):
    q = LocalConditionExtractor(brute_mode=brute_mode).process(Query(text))
    return [c.value for c in q.active_conditions if c.field == Field.ADDRESS]


class TestGeoTable(unittest.TestCase):
    def test_every_country_the_filter_knows_can_also_be_found_in_a_query(self):
        # The Switzerland bug: the filter knew a country, but the query side had no key for it.
        missing = [c for c in GEO["country_iso"] if c != "us" and c not in GEO["expansions"]]
        self.assertEqual(missing, [])

    def test_iso_codes_look_like_iso_codes(self):
        for name, codes in GEO["country_iso"].items():
            for code in codes:
                self.assertTrue(code.isalpha() and code == code.lower() and len(code) in (2, 3), (name, code))

    def test_both_modes_read_the_same_table(self):
        self.assertIs(LocalConditionExtractor._GEO_EXPANSIONS, GEO["expansions"])

    def test_normal_and_brute_mode_find_the_same_places(self):
        for text in ["Pharmaceutical companies in Switzerland", "Software companies in Estonia",
                     "Fintech in Europe", "Energy firms in Qatar and Thailand",
                     "Renewable energy equipment manufacturers in Scandinavia"]:
            self.assertEqual(address_conditions(text, False), address_conditions(text, True), text)
            self.assertTrue(address_conditions(text, False), text)

    def test_europe_has_one_definition(self):
        europe = GEO["expansions"]["europe"]
        for country in ["Romania", "Denmark", "Norway", "Finland", "Portugal", "Ireland", "Russia"]:
            self.assertIn(country, europe)
        self.assertEqual(GEO["expansions"]["european"], europe)

    def test_a_company_from_a_previously_missing_country_passes_the_filter(self):
        q = LocalConditionExtractor(brute_mode=False).process(Query("Software companies in Estonia"))
        q.fill_phantom_conditions()
        out = os.path.join(tempfile.mkdtemp(), "c.jsonl")
        companies = [{"operational_name": "EE Co", "address": {"country_code": "ee"}},
                     {"operational_name": "DE Co", "address": {"country_code": "de"}}]
        with HardFilterProcessor(q, out) as p:
            for c in companies:
                p.process_company(c, raw_json_line=json.dumps(c))
        self.assertEqual((p.total_passed, p.total_dropped), (1, 1))


if __name__ == "__main__":
    unittest.main()
