import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.base.naics import get_naics_for_text


class TestNaicsWholeWords(unittest.TestCase):
    def test_it_is_not_found_inside_with(self):
        self.assertNotIn("5415", get_naics_for_text("Companies with more than 1,000 employees"))

    def test_ai_is_not_found_inside_chain_or_retail(self):
        self.assertNotIn("5417", get_naics_for_text("supply chain and retail firms"))

    def test_gis_is_not_found_inside_logistics(self):
        codes = get_naics_for_text("logistics companies")
        self.assertIn("481", codes)
        self.assertNotIn("5413", codes)

    def test_hr_and_erp_are_not_found_inside_other_words(self):
        self.assertEqual(get_naics_for_text("three enterprise buyers"), [])

    def test_real_keywords_still_match(self):
        self.assertIn("5415", get_naics_for_text("IT services"))
        self.assertIn("5613", get_naics_for_text("B2B SaaS providing HR solutions"))
        self.assertIn("4541", get_naics_for_text("e-commerce companies using Shopify"))
        self.assertIn("3254", get_naics_for_text("Pharmaceutical companies"))

    def test_plural_forms_still_match(self):
        self.assertIn("3254", get_naics_for_text("pharmaceuticals"))   # "pharmaceutical" + s
        self.assertIn("3121", get_naics_for_text("local breweries"))


if __name__ == "__main__":
    unittest.main()
