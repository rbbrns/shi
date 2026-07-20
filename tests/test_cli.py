import unittest
import io
import sys
from unittest.mock import patch

from typing import Literal, Any
from enum import Enum, auto
from shi.cli import cli, run_cli, parse_cli_args, convert_value, cli_commands, console


class Color(Enum):
    RED = auto()
    GREEN = auto()
    BLUE = auto()


class TestCli(unittest.TestCase):

    def setUp(self):
        # Clear registered commands before each test
        cli_commands.clear()
        # Capture stdout for testing print statements
        self.held_stdout = sys.stdout
        self.mock_stdout = io.StringIO()
        sys.stdout = self.mock_stdout
        # Disable colors for testing
        console.force_terminal = False
        console._color_system = None

    def tearDown(self):
        # Restore stdout
        sys.stdout = self.held_stdout

    def get_original_func(self, func_name):
        return cli_commands[func_name][1]

    def test_convert_value(self):
        self.assertEqual(convert_value("123", int), 123)
        self.assertEqual(convert_value("3.14", float), 3.14)
        self.assertEqual(convert_value("true", bool), True)
        self.assertEqual(convert_value("False", bool), False)
        self.assertEqual(convert_value("hello", str), "hello")
        self.assertEqual(convert_value("123", str), "123")  # Fallback to str
        self.assertEqual(
            convert_value("not_a_number", int), "not_a_number"
        )  # Fallback to str

    def test_convert_value_enum(self):
        self.assertEqual(convert_value("RED", Color), Color.RED)
        self.assertEqual(convert_value("green", Color), Color.GREEN)  # Case insensitive

        with self.assertRaises(SystemExit):
            convert_value("YELLOW", Color)

    def test_convert_value_literal(self):
        self.assertEqual(convert_value("foo", Literal["foo", "bar"]), "foo")
        self.assertEqual(convert_value("1", Literal[1, 2]), 1)

        with self.assertRaises(SystemExit):
            convert_value("baz", Literal["foo", "bar"])

    def test_parse_cli_args_positional(self):
        @cli
        def test_func(arg1: str, arg2: int):
            pass

        cli_args_raw = ["value1", "123"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"arg1": "value1", "arg2": 123})

    def test_parse_cli_args_quoted_string(self):
        @cli
        def test_func(message: str):
            pass

        # sys.argv already handles unquoting, so we pass the unquoted string
        cli_args_raw = ["hello world with spaces"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"message": "hello world with spaces"})

        cli_args_raw = ["another message with spaces"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"message": "another message with spaces"})

        cli_args_raw = ["--message", "quoted value"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"message": "quoted value"})

    def test_parse_cli_args_var_equals_val(self):
        @cli
        def test_func(name: str, age: int, is_active: bool):
            pass

        cli_args_raw = ["name=Bob", "age=25", "is_active=True"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"name": "Bob", "age": 25, "is_active": True})

    def test_parse_cli_args_keyword_value(self):
        @cli
        def test_func(name: str, age: int):
            pass

        cli_args_raw = ["--name", "Alice", "--age", "30"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"name": "Alice", "age": 30})

    def test_parse_cli_args_keyword_equals(self):
        @cli
        def test_func(name: str, age: int):
            pass

        cli_args_raw = ["--name=Bob", "--age=25"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"name": "Bob", "age": 25})

    def test_parse_cli_args_mixed(self):
        @cli
        def test_func(pos1: str, pos2: int, kw1: bool, kw2: float):
            pass

        cli_args_raw = ["first_pos", "10", "kw1=True", "--kw2=3.14"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(
            parsed.arguments, {"pos1": "first_pos", "pos2": 10, "kw1": True, "kw2": 3.14}
        )

    def test_parse_cli_args_var_positional(self):
        @cli
        def test_func(pos1: str, *args: str):
            pass

        cli_args_raw = ["first_pos", "extra1", "extra2"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(
            parsed.arguments, {"pos1": "first_pos", "args": ("extra1", "extra2")}
        )

    def test_run_cli_greet_command(self):
        @cli
        def greet(name: str, greeting: str = "Hello", repeat: int = 1):
            for _ in range(repeat):
                print(f"{greeting}, {name}!")

        # Simulate command line arguments
        run_cli(["greet", "John", "greeting=Hi", "repeat=2"])
        output = self.mock_stdout.getvalue()
        self.assertIn("Hi, John!\nHi, John!", output)

    def test_run_cli_add_command(self):
        @cli
        def add(a: int, b: int):
            result = a + b
            print(f"The sum of {a} and {b} is {result}")

        run_cli(["add", "5", "10"])
        output = self.mock_stdout.getvalue()
        self.assertIn("The sum of 5 and 10 is 15", output)

    def test_run_cli_echo_command(self):
        @cli
        def echo(message: str, loud: bool = False):
            if loud:
                print(message.upper())
            else:
                print(message)

        run_cli(["echo", "test message", "loud=True"])
        output = self.mock_stdout.getvalue()
        self.assertIn("TEST MESSAGE", output)

        self.mock_stdout = io.StringIO()  # Reset stdout for next assertion
        sys.stdout = self.mock_stdout
        run_cli(["echo", "another message"])
        output = self.mock_stdout.getvalue()
        self.assertIn("another message", output)

    def test_run_cli_unknown_command(self):
        with self.assertRaises(SystemExit) as cm:
            run_cli(["unknown_cmd"])
        self.assertEqual(cm.exception.code, 1)
        output = self.mock_stdout.getvalue()
        self.assertIn("Error: Unknown command 'unknown_cmd'", output)

    def test_run_cli_missing_required_argument(self):
        @cli
        def required_arg_func(param1: str, param2: int):
            pass

        with self.assertRaises(SystemExit) as cm:
            run_cli(["required_arg_func", "value1"])
        self.assertEqual(cm.exception.code, 1)
        output = self.mock_stdout.getvalue()
        self.assertIn("Error parsing arguments for 'required_arg_func':", output)
        self.assertIn("missing a required argument: 'param2'", output)

    def test_run_cli_no_command(self):
        with self.assertRaises(SystemExit) as cm:
            run_cli([])
        self.assertEqual(cm.exception.code, 1)
        output = self.mock_stdout.getvalue()
        self.assertIn("Usage:", output)
        self.assertIn("<command> [args...]", output)

    def test_run_cli_help_general(self):
        @cli
        def my_cmd(arg: int):
            """My command docstring."""
            pass

        with self.assertRaises(SystemExit) as cm:
            run_cli(["?"])
        self.assertEqual(cm.exception.code, 0)
        output = self.mock_stdout.getvalue()
        self.assertIn("Usage:", output)
        self.assertIn("my_cmd", output)
        self.assertIn("(for command help)", output)

    def test_run_cli_help_command(self):
        @cli
        def my_cmd(arg: int, default_val: str = "test"):
            """My command docstring."""
            pass

        with self.assertRaises(SystemExit) as cm:
            run_cli(["my_cmd", "?"])
        self.assertEqual(cm.exception.code, 0)
        output = self.mock_stdout.getvalue()
        self.assertIn("Command:", output)
        self.assertIn("my_cmd", output)
        self.assertIn("Usage:", output)
        self.assertIn("Description:", output)
        self.assertIn("My command docstring.", output)
        self.assertIn("Source:", output)
        # Check for signature in source
        self.assertIn("def my_cmd(arg: int", output)

    def test_run_cli_help_unknown_command(self):
        with self.assertRaises(SystemExit) as cm:
            run_cli(["unknown_cmd", "?"])
        self.assertEqual(cm.exception.code, 1)
        output = self.mock_stdout.getvalue()
        self.assertIn("Error: Unknown command 'unknown_cmd'", output)

    def test_parse_cli_args_loh_postfixes(self):
        @cli
        def test_func(
            a: bool,
            b: bool,
            c: bool,
            d: bool,
            e: Any,
            f: Any,
            g: Any,
            h: Any,
            i: Any,
        ):
            pass

        cli_args_raw = [
            "a+",
            "b++",
            "c-",
            "d--",
            "e~",
            "f~~",
            "g~~~",
            "h!~",
            "i!~~",
        ]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(
            parsed.arguments,
            {
                "a": True,
                "b": True,
                "c": False,
                "d": False,
                "e": None,
                "f": None,
                "g": None,
                "h": True,
                "i": True,
            },
        )

    def test_command_aliasing(self):
        @cli
        def foo(x: int):
            print(f"foo: {x}")

        # Set up a module-level alias in the current module
        module_name = foo.__module__
        import sys

        mod = sys.modules[module_name]

        # Define the alias
        mod.bar_alias = foo

        # Run CLI with the alias
        run_cli(["bar_alias", "42"])
        output = self.mock_stdout.getvalue()
        self.assertIn("foo: 42", output)

        # Clean up global
        if hasattr(mod, "bar_alias"):
            delattr(mod, "bar_alias")

    def test_run_cli_help_command_sentinel(self):
        # Define a sentinel class/string simulating _LOH_SENTINEL
        class MockSentinel:
            def __repr__(self):
                return "<_LOH_SENTINEL object at 0x10>"

            def __str__(self):
                return "_LOH_SENTINEL"

        mock_sentinel = MockSentinel()

        @cli
        def my_sentinel_cmd(limit=mock_sentinel):
            pass

        with self.assertRaises(SystemExit) as cm:
            run_cli(["my_sentinel_cmd", "?"])
        self.assertEqual(cm.exception.code, 0)
        output = self.mock_stdout.getvalue()
        self.assertIn("my_sentinel_cmd(limit=~)", output)


if __name__ == "__main__":
    unittest.main()
