import unittest
import inspect
from shi.cli import (
    extract_global_args_from_list,
    normalize_debug,
    normalize_time,
    normalize_money,
    normalize_effort,
    process_globals,
    inject_globals,
)


class TestGlobalArgs(unittest.TestCase):
    def test_extract_global_args_from_list(self):
        # Equality syntax
        argv = ["msg=hello", "debug=info", "--time=5s", "--money=$10", "effort=coffee"]
        raw, clean = extract_global_args_from_list(argv)
        self.assertEqual(
            raw, {"debug": "info", "time": "5s", "money": "$10", "effort": "coffee"}
        )
        self.assertEqual(clean, ["msg=hello"])

        # Standalone flags
        argv = [
            "--debug",
            "info",
            "-t",
            "10ms",
            "--money",
            "$100",
            "-e",
            "beer",
            "some_pos",
        ]
        raw, clean = extract_global_args_from_list(argv)
        self.assertEqual(
            raw, {"debug": "info", "time": "10ms", "money": "$100", "effort": "beer"}
        )
        self.assertEqual(clean, ["some_pos"])

        # Standalone flags (boolean defaults)
        argv = ["--debug", "-t", "--money", "-e"]
        raw, clean = extract_global_args_from_list(argv)
        self.assertEqual(
            raw, {"debug": True, "time": True, "money": True, "effort": True}
        )
        self.assertEqual(clean, [])

        # Postfix operators
        argv = ["d++", "t-", "m~", "e++"]
        raw, clean = extract_global_args_from_list(argv)
        self.assertEqual(
            raw, {"debug": True, "time": False, "money": None, "effort": True}
        )
        self.assertEqual(clean, [])

    def test_normalize_debug(self):
        self.assertIsNone(normalize_debug(0))
        self.assertIsNone(normalize_debug("0"))
        self.assertIsNone(normalize_debug("none"))
        self.assertIsNone(normalize_debug("false"))
        self.assertEqual(normalize_debug(5), 5)
        self.assertEqual(normalize_debug("info"), "info")
        self.assertTrue(normalize_debug(True))

    def test_normalize_time(self):
        self.assertIsNone(normalize_time(0))
        self.assertIsNone(normalize_time("0"))
        self.assertIsNone(normalize_time("none"))
        self.assertEqual(normalize_time("5s"), 5.0)
        self.assertEqual(normalize_time("10ms"), 0.01)
        self.assertEqual(normalize_time("1.5h"), 5400.0)
        self.assertEqual(normalize_time("2 days"), 172800.0)
        self.assertEqual(normalize_time("10"), 10)

    def test_normalize_money(self):
        self.assertIsNone(normalize_money(0))
        self.assertIsNone(normalize_money("0"))
        self.assertIsNone(normalize_money("none"))
        self.assertEqual(normalize_money("$100"), 100.0)
        self.assertEqual(normalize_money("$5.50"), 5.5)
        self.assertEqual(normalize_money("10"), 10)

    def test_normalize_effort(self):
        self.assertIsNone(normalize_effort(0))
        self.assertIsNone(normalize_effort("0"))
        self.assertIsNone(normalize_effort("none"))
        self.assertEqual(normalize_effort("coffee"), "coffee")
        self.assertEqual(normalize_effort("beer"), "beer")
        self.assertEqual(normalize_effort(5), 5)

    def test_process_globals_formula(self):
        # Scalar effort sets time (hours) and money (10x effort)
        raw = {"effort": 5}
        processed = process_globals(raw)
        self.assertEqual(processed["time"], 18000.0)
        self.assertEqual(processed["money"], 50.0)

        # Contextual coffee effort sets 1 hour time and $5 money
        raw = {"effort": "coffee"}
        processed = process_globals(raw)
        self.assertEqual(processed["time"], 3600.0)
        self.assertEqual(processed["money"], 5.00)

        # Contextual beer effort sets 2 hours time and $8 money
        raw = {"effort": "beer"}
        processed = process_globals(raw)
        self.assertEqual(processed["time"], 7200.0)
        self.assertEqual(processed["money"], 8.00)

        # Explicit overrides formula
        raw = {"effort": "coffee", "time": "10s", "money": "$100"}
        processed = process_globals(raw)
        self.assertEqual(processed["time"], 10.0)
        self.assertEqual(processed["money"], 100.0)

    def test_inject_globals(self):
        # 1. Function has **kwargs, should receive all variations
        def func_with_kwargs(**kwargs):
            pass

        sig = inspect.signature(func_with_kwargs)
        final_args = {}
        normalized = {"debug": "info", "time": 5.0}
        inject_globals(sig, final_args, normalized)

        self.assertEqual(final_args["debug"], "info")
        self.assertEqual(final_args["DEBUG"], "info")
        self.assertEqual(final_args["d"], "info")
        self.assertEqual(final_args["D"], "info")
        self.assertEqual(final_args["time"], 5.0)
        self.assertEqual(final_args["TIME"], 5.0)
        self.assertEqual(final_args["t"], 5.0)
        self.assertEqual(final_args["T"], 5.0)

        # 2. Function has explicit parameters and no **kwargs
        def func_explicit(debug=None, t=None):
            pass

        sig = inspect.signature(func_explicit)
        final_args = {}
        normalized = {"debug": "warning", "time": 10.0}
        inject_globals(sig, final_args, normalized)

        self.assertEqual(final_args["debug"], "warning")
        self.assertEqual(final_args["t"], 10.0)
        self.assertNotIn("d", final_args)
        self.assertNotIn("time", final_args)


if __name__ == "__main__":
    unittest.main()
