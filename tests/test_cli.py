import unittest
import io
import sys
from unittest.mock import patch

from shi.cli import cli, run_cli, parse_cli_args, convert_value, cli_commands


class TestCli(unittest.TestCase):

    def setUp(self):
        # Clear registered commands before each test
        cli_commands.clear()
        # Capture stdout for testing print statements
        self.held_stdout = sys.stdout
        self.mock_stdout = io.StringIO()
        sys.stdout = self.mock_stdout

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

    def test_parse_cli_args_positional(self):
        @cli
        def test_func(arg1: str, arg2: int):
            pass

        cli_args_raw = ["value1", "123"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed, {"arg1": "value1", "arg2": 123})

    def test_parse_cli_args_quoted_string(self):
        @cli
        def test_func(message: str):
            pass

        # sys.argv already handles unquoting, so we pass the unquoted string
        cli_args_raw = ["hello world with spaces"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed, {"message": "hello world with spaces"})

        cli_args_raw = ["another message with spaces"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed, {"message": "another message with spaces"})

        cli_args_raw = ["--message", "quoted value"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed, {"message": "quoted value"})

    def test_parse_cli_args_var_equals_val(self):
        @cli
        def test_func(name: str, age: int, is_active: bool):
            pass

        cli_args_raw = ["name=Bob", "age=25", "is_active=True"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed, {"name": "Bob", "age": 25, "is_active": True})

    def test_parse_cli_args_keyword_value(self):
        @cli
        def test_func(name: str, age: int):
            pass

        cli_args_raw = ["--name", "Alice", "--age", "30"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed, {"name": "Alice", "age": 30})

    def test_parse_cli_args_keyword_equals(self):
        @cli
        def test_func(name: str, age: int):
            pass

        cli_args_raw = ["--name=Bob", "--age=25"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed, {"name": "Bob", "age": 25})

    def test_parse_cli_args_mixed(self):
        @cli
        def test_func(pos1: str, pos2: int, kw1: bool, kw2: float):
            pass

        cli_args_raw = ["first_pos", "10", "kw1=True", "--kw2=3.14"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(
            parsed, {"pos1": "first_pos", "pos2": 10, "kw1": True, "kw2": 3.14}
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
        self.assertIn("Error calling command 'required_arg_func':", output)
        self.assertIn("missing 1 required positional argument: 'param2'", output)

    def test_run_cli_no_command(self):
        with self.assertRaises(SystemExit) as cm:
            run_cli([])
        self.assertEqual(cm.exception.code, 1)
        output = self.mock_stdout.getvalue()
        self.assertIn("Usage:", output)
        self.assertIn("<command> [args...]", output)


if __name__ == "__main__":
    unittest.main()
