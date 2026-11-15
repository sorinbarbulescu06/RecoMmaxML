import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.query.local import LocalConditionExtractor
from src.query.query import Field, Query


def address_values(text, brute_mode=False):
    q = LocalConditionExtractor(brute_mode=brute_mode).process(Query(text))
    for c in q.active_conditions:
        if c.field == Field.ADDRESS:
            return q, c.value
    return q, None


class TestLocalGeography(unittest.TestCase):
    def test_country_found_without_brute_mode(self):
        q, values = address_values("Public companies with more than 1,000 employees in Germany")
        self.assertIn("Germany", values)
        self.assertIn("Berlin", values)

    def test_structured_query_no_longer_needs_the_api(self):
        q, _ = address_values("Public companies with more than 1,000 employees in Germany")
        self.assertTrue(q.is_fully_explained)

    def test_europe_is_complete_and_the_same_every_time(self):
        _, first = address_values("B2B SaaS companies in Europe")
        _, second = address_values("fintech companies in Europe")
        self.assertEqual(first, second)
        for country in ["Denmark", "Norway", "Finland", "Portugal", "Ireland", "Romania"]:
            self.assertIn(country, first)

    def test_no_place_no_address_condition(self):
        _, values = address_values("Software companies with more than 200 employees")
        self.assertIsNone(values)

    def test_the_word_us_as_pronoun_is_not_a_country(self):
        _, values = address_values("Show us software companies")
        self.assertIsNone(values)

    def test_brute_mode_still_finds_the_same_countries(self):
        _, normal = address_values("Pharmaceutical companies in Switzerland", brute_mode=False)
        _, brute = address_values("Pharmaceutical companies in Switzerland", brute_mode=True)
        self.assertEqual(normal, brute)
        self.assertIn("Switzerland", brute)


if __name__ == "__main__":
    unittest.main()
