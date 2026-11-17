import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.base.config import Config
from src.query.call import APIConditionExtractor
from src.query.query import Query


class FakeError(Exception):
    def __init__(self, code):
        super().__init__(f"{code} ERROR")
        self.code = code


def make_extractor(generate_results=(), list_error=None):
    """An extractor whose Gemini client is fake. generate_results: errors to raise, or 'ok'."""
    with patch.object(Config, "API_KEY", "key"), patch("src.query.call.genai.Client") as client_cls:
        client = client_cls.return_value
        if list_error:
            client.models.list.side_effect = list_error
        else:
            client.models.list.return_value = iter([object()])
        ext = APIConditionExtractor()
    ext.sleeps = []
    ext._sleep = ext.sleeps.append
    results = iter(generate_results)

    def fake_generate(**kwargs):
        r = next(results)
        if isinstance(r, Exception):
            raise r
        return SimpleNamespace(parsed=SimpleNamespace(conditions=[]))

    ext.client.models.generate_content = fake_generate
    return ext


class TestRetry(unittest.TestCase):
    def run_query(self, results):
        ext = make_extractor(results)
        q = ext.process(Query("software companies"))
        return ext, q

    def test_succeeds_after_two_429(self):
        ext, q = self.run_query([FakeError(429), FakeError(429), "ok"])
        self.assertIsNone(q.api_error)
        self.assertEqual(q.api_retries, 2)
        self.assertEqual(ext.sleeps, [1, 2])

    def test_gives_up_after_the_last_retry(self):
        ext, q = self.run_query([FakeError(429)] * 3)
        self.assertEqual(q.api_error, "429")
        self.assertEqual(q.api_retries, 2)

    def test_503_is_retried_too(self):
        ext, q = self.run_query([FakeError(503), "ok"])
        self.assertEqual((q.api_error, q.api_retries), (None, 1))

    def test_bad_request_is_not_retried(self):
        ext, q = self.run_query([FakeError(400)])
        self.assertEqual((q.api_error, q.api_retries, ext.sleeps), ("400", 0, []))

    def test_timeouts_are_not_retried(self):
        for code in (504,):
            ext, q = self.run_query([FakeError(code)])
            self.assertEqual((q.api_error, q.api_retries, ext.sleeps), ("504", 0, []))
        ext, q = self.run_query([TimeoutError("The read operation timed out")])
        self.assertEqual((q.api_error, q.api_retries), ("other", 0))


class TestKeyValidation(unittest.TestCase):
    def test_valid_key_stays_active(self):
        self.assertTrue(make_extractor().is_active)

    def test_invalid_key_switches_the_api_off(self):
        for code in (400, 401, 403):
            self.assertFalse(make_extractor(list_error=FakeError(code)).is_active, code)

    def test_temporary_error_does_not_disable_a_good_key(self):
        for code in (429, 503):
            self.assertTrue(make_extractor(list_error=FakeError(code)).is_active, code)

    def test_missing_key_means_inactive(self):
        with patch.object(Config, "API_KEY", ""):
            self.assertFalse(APIConditionExtractor().is_active)


if __name__ == "__main__":
    unittest.main()
