import unittest
import io
import sys
import re
from pathlib import Path
from unittest.mock import patch

# Assuming shi is installed in editable mode or sys.path is configured
from shi.dprint import dprint, _format_value, _print_variable, _print_backtrace


class TestDprint(unittest.TestCase):

    def setUp(self):
        # Capture stdout for testing print statements
        self.held_stdout = sys.stdout
        self.mock_stdout = io.StringIO()
        sys.stdout = self.mock_stdout

    def tearDown(self):
        # Restore stdout
        sys.stdout = self.held_stdout

    def _remove_ansi_escape_codes(self, text):
        # Regex to remove ANSI escape codes
        ansi_escape = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
        return ansi_escape.sub("", text)

    def test_dprint_basic_variable(self):
        my_var = 123
        dprint(my_var)
        output = self._remove_ansi_escape_codes(self.mock_stdout.getvalue())

        # Expected output format (adjust based on actual dprint output)
        # We'll check for key components rather than exact string match due to potential color codes/line numbers
        self.assertIn("test_dprint.py", output)
        self.assertIn("test_dprint_basic_variable(", output)
        self.assertIn("my_var: int = 123", output)

    def test_dprint_multiple_variables(self):
        a = "hello"
        b = [1, 2]
        dprint(a, b)
        output = self._remove_ansi_escape_codes(self.mock_stdout.getvalue())

        self.assertIn("test_dprint.py", output)
        self.assertIn("test_dprint_multiple_variables(", output)
        self.assertIn("a: str = hello", output)
        self.assertIn("b: list = [1, 2]", output)

    def test_dprint_keyword_arguments(self):
        val1 = 10
        val2 = "test"
        dprint(x=val1, y=val2)
        output = self._remove_ansi_escape_codes(self.mock_stdout.getvalue())

        self.assertIn("test_dprint.py", output)
        self.assertIn("test_dprint_keyword_arguments(", output)
        self.assertIn("x: int = 10", output)
        self.assertIn("y: str = test", output)

    def test_dprint_nested_functions(self):
        def inner_func(param):
            local_var = param * 2
            dprint(local_var)

        def outer_func():
            outer_var = 5
            inner_func(outer_var)

        outer_func()
        output = self._remove_ansi_escape_codes(self.mock_stdout.getvalue())

        self.assertIn("test_dprint.py", output)
        self.assertIn("outer_func(", output)
        self.assertIn("inner_func(", output)
        self.assertIn("param=5", output)
        self.assertIn("local_var: int = 10", output)

    def test_format_value_string(self):
        self.assertIn("'short'", self._remove_ansi_escape_codes(_format_value("short")))
        self.assertIn(
            "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'+120",
            self._remove_ansi_escape_codes(_format_value("a" * 150)),
        )

    def test_format_value_list(self):
        self.assertIn(
            "[1, 2, 3]", self._remove_ansi_escape_codes(_format_value([1, 2, 3]))
        )
        self.assertIn(
            "[",
            self._remove_ansi_escape_codes(_format_value(list(range(100)))),
        )

    def test_format_value_dict(self):
        self.assertIn(
            "{'a': 1}", self._remove_ansi_escape_codes(_format_value({"a": 1}))
        )
        self.assertIn(
            "{'a': 1, 'b': 2}",
            self._remove_ansi_escape_codes(_format_value({"a": 1, "b": 2})),
        )

    def test_format_value_none_bool(self):
        self.assertIn("None", self._remove_ansi_escape_codes(_format_value(None)))
        self.assertIn("True", self._remove_ansi_escape_codes(_format_value(True)))
        self.assertIn("False", self._remove_ansi_escape_codes(_format_value(False)))

    def test_dprint_bound_method_self(self):
        class MyClass:
            def my_method(self, x):
                dprint(x)

        instance = MyClass()
        instance.my_method(10)
        output = self._remove_ansi_escape_codes(self.mock_stdout.getvalue())

        # Check that the backtrace shows `my_method(self, x=10)` and not the value of self
        self.assertIn("my_method(self, x=10)", output)
        self.assertNotIn("MyClass object", output)

    def test_dprint_hide_wrappers(self):
        import functools

        def simple_decorator(f):
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                return f(*args, **kwargs)
            return wrapper

        @simple_decorator
        def wrapped_function():
            dprint(hide_wrappers=True)

        wrapped_function()
        output = self._remove_ansi_escape_codes(self.mock_stdout.getvalue())
        self.assertNotIn("wrapper()", output)
        self.assertIn("wrapped_function()", output)

        # Reset stdout
        self.mock_stdout = io.StringIO()
        sys.stdout = self.mock_stdout

        @simple_decorator
        def wrapped_function_show():
            dprint(hide_wrappers=False)

        wrapped_function_show()
        output = self._remove_ansi_escape_codes(self.mock_stdout.getvalue())
        self.assertIn("wrapper()", output)
        self.assertIn("wrapped_function_show()", output)
