import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from query import Condition, Field, Operator, Query


class TestRemainder(unittest.TestCase):  # bug 1
    def test_shrinks_when_condition_added(self):
        q = Query("public software companies")
        q.add_condition(Condition(Field.IS_PUBLIC, Operator.EQ, True, span=(0, 6)))
        self.assertEqual(q.remainder, "software companies")
        self.assertFalse(q.is_fully_explained)

    def test_fully_explained_when_everything_covered(self):
        q = Query("public")
        q.add_condition(Condition(Field.IS_PUBLIC, Operator.EQ, True, span=(0, 6)))
        self.assertTrue(q.is_fully_explained)

    def test_overlapping_spans_are_safe(self):
        q = Query("more than 1000 employees")
        q.add_condition(Condition(Field.EMPLOYEE_COUNT, Operator.GT, 1000, span=(0, 24)))
        q.add_condition(Condition(Field.EMPLOYEE_COUNT, Operator.GTE, 1001, span=(10, 24)))
        self.assertTrue(q.is_fully_explained)

    def test_api_condition_without_span_keeps_remainder(self):
        q = Query("companies competing with banks")
        q.add_condition(Condition(Field.DESCRIPTION, Operator.EQ, "competes with banks", source="api"))
        self.assertEqual(q.remainder, "companies competing with banks")


class TestEmptyQuery(unittest.TestCase):  # bug 2
    def test_empty_rejected(self):
        for text in ["", "   ", "\n\t"]:
            with self.assertRaises(ValueError):
                Query(text)


class TestValidation(unittest.TestCase):  # bug 3
    def test_unknown_field_rejected(self):
        with self.assertRaises(ValueError):
            Field("employe_count")

    def test_confidence_out_of_range_rejected(self):
        for conf in [-0.1, 1.5, 7]:
            with self.assertRaises(ValueError):
                Condition(Field.REVENUE, Operator.GT, 1, confidence=conf)

    def test_span_outside_text_rejected(self):
        q = Query("abc")
        with self.assertRaises(ValueError):
            q.add_condition(Condition(Field.REVENUE, Operator.GT, 1, span=(0, 10)))


class TestDuplicates(unittest.TestCase):  # bug 4
    def test_duplicate_ignored(self):
        q = Query("x")
        self.assertTrue(q.add_condition(Condition(Field.IS_PUBLIC, Operator.EQ, True, source="local")))
        self.assertFalse(q.add_condition(Condition(Field.IS_PUBLIC, Operator.EQ, True, source="api")))
        self.assertEqual(len(q.conditions), 1)

    def test_duplicate_with_list_value(self):
        q = Query("x")
        q.add_condition(Condition(Field.ADDRESS, Operator.IN, ["RO", "BG"]))
        self.assertFalse(q.add_condition(Condition(Field.ADDRESS, Operator.IN, ["RO", "BG"])))


if __name__ == "__main__":
    unittest.main()
