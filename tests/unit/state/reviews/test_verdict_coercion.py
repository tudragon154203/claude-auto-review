import unittest

from claude_auto_review.config.utils.coercion import (
    coerce_bool,
    coerce_extensions,
    coerce_float,
    coerce_int,
)


class TestCoercionHelpers(unittest.TestCase):
    def test_coerce_bool_none_returns_default(self):
        self.assertFalse(coerce_bool(None, False))
        self.assertTrue(coerce_bool(None, True))

    def test_coerce_bool_truthy(self):
        self.assertTrue(coerce_bool(1, False))
        self.assertTrue(coerce_bool("yes", False))
        self.assertTrue(coerce_bool([1], False))

    def test_coerce_bool_falsy(self):
        self.assertFalse(coerce_bool(0, True))
        self.assertFalse(coerce_bool("", True))
        self.assertFalse(coerce_bool([], True))

    def test_coerce_float_valid(self):
        self.assertAlmostEqual(coerce_float("3.14", 0.0), 3.14)
        self.assertAlmostEqual(coerce_float(2, 0.0), 2.0)

    def test_coerce_float_invalid_returns_default(self):
        self.assertAlmostEqual(coerce_float("bad", 1.0), 1.0)
        self.assertAlmostEqual(coerce_float(None, 5.0), 5.0)

    def test_coerce_int_valid(self):
        self.assertEqual(coerce_int("42", 0), 42)
        self.assertEqual(coerce_int(7, 0), 7)

    def test_coerce_int_float_returns_default(self):
        self.assertEqual(coerce_int("3.9", 0), 0)

    def test_coerce_int_invalid_returns_default(self):
        self.assertEqual(coerce_int("bad", 5), 5)
        self.assertEqual(coerce_int(None, 10), 10)

    def test_coerce_extensions_list(self):
        self.assertEqual(coerce_extensions([".py", ".ts"]), (".py", ".ts"))

    def test_coerce_extensions_tuple(self):
        self.assertEqual(coerce_extensions((".py",)), (".py",))

    def test_coerce_extensions_non_sequence_returns_empty(self):
        self.assertEqual(coerce_extensions(".py"), ())
        self.assertEqual(coerce_extensions(None), ())
        self.assertEqual(coerce_extensions(42), ())

    def test_coerce_extensions_converts_ints(self):
        self.assertEqual(coerce_extensions([1, 2]), ("1", "2"))


if __name__ == "__main__":
    unittest.main()
