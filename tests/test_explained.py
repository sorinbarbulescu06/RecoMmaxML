import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.query.query import Condition, Field, Operator, Query


def covered(text, *spans_conditions):
    q = Query(text)
    for field_, op, value, span in spans_conditions:
        q.add_condition(Condition(field_, op, value, span=span))
    return q


class TestFullyExplained(unittest.TestCase):
    def test_only_filler_and_punctuation_left(self):
        # "Public companies with more than 1,000 employees."  -> "companies with ." is left
        text = "Public companies with more than 1,000 employees."
        q = covered(text,
                    (Field.IS_PUBLIC, Operator.EQ, True, (0, 6)),
                    (Field.EMPLOYEE_COUNT, Operator.GT, 1000, (21, 47)))
        self.assertEqual(q.remainder, "companies with .")
        self.assertTrue(q.is_fully_explained)

    def test_meaningful_word_left_means_api_is_needed(self):
        text = "Public software companies with more than 1,000 employees."
        q = covered(text,
                    (Field.IS_PUBLIC, Operator.EQ, True, (0, 6)),
                    (Field.EMPLOYEE_COUNT, Operator.GT, 1000, (30, 56)))
        self.assertIn("software", q.remainder)
        self.assertFalse(q.is_fully_explained)

    def test_nothing_covered_is_not_explained(self):
        self.assertFalse(Query("packaging for cosmetics brands").is_fully_explained)

    def test_non_english_words_are_not_ignored(self):
        self.assertFalse(Query("firme de logistica în România").is_fully_explained)

    def test_remainder_text_keeps_the_filler_words(self):
        q = Query("packaging for cosmetics")
        self.assertEqual(q.remainder, "packaging for cosmetics")   # the API still sees 'for'


if __name__ == "__main__":
    unittest.main()
