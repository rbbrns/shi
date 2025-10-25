import unittest
import io
import sys
from unittest.mock import patch

from shi.cli import cli, run_cli, _parse_cli_args, _convert_value, _cli_commands

class TestCli(unittest.TestCase):

    def setUp(self):
        # Clear registered commands before each test
        _cli_commands.clear()
        # Capture stdout for testing print statements
        self.held_stdout = sys.stdout
        self.mock_stdout = io.StringIO()
        sys.stdout = self.mock_stdout

    def tearDown(self):
        # Restore stdout
        sys.stdout = self.held_stdout

    def test_convert_value(self):
        self.assertEqual(_convert_value("123", int), 123)
        self.assertEqual(_convert_value("3.14", float), 3.14)
        self.assertEqual(_convert_value("true", bool), True)
        self.assertEqual(_convert_value("False", bool), False)
        self.assertEqual(_convert_value("hello", str), "hello")
        self.assertEqual(_convert_value("123", str), "123") # Fallback to str
        self.assertEqual(_convert_value("not_a_number", int), "not_a_number") # Fallback to str

    def test_parse_cli_args_positional(self):
        @cli
        def test_func(arg1: str, arg2: int):
            pass
        
        cli_args = ["value1", "123"]
        parsed = _parse_cli_args(test_func, cli_args)
        self.assertEqual(parsed, {"arg1": "value1", "arg2": 123})

    def test_parse_cli_args_quoted_string(self):
        @cli
        def test_func(message: str):
            pass
        
        cli_args = ["\"hello world\""]
        parsed = _parse_cli_args(test_func, cli_args)
        self.assertEqual(parsed, {"message": "hello world"})

        cli_args = ["'another message'"]
        parsed = _parse_cli_args(test_func, cli_args)
        self.assertEqual(parsed, {"message": "another message"})

    def test_parse_cli_args_keyword_value(self):
        @cli
        def test_func(name: str, age: int):
            pass
        
        cli_args = ["--name", "Alice", "--age", "30"]
        parsed = _parse_cli_args(test_func, cli_args)
        self.assertEqual(parsed, {"name": "Alice", "age": 30})

    def test_parse_cli_args_keyword_equals(self):
        @cli
        def test_func(name: str, age: int):
            pass
        
        cli_args = ["--name=Bob", "--age=25"]
        parsed = _parse_cli_args(test_func, cli_args)
        self.assertEqual(parsed, {"name": "Bob", "age": 25})

    def test_parse_cli_args_mixed(self):
        @cli
        def test_func(pos1: str, pos2: int, kw1: bool, kw2: float):
            pass
        
        cli_args = ["first_pos", "10", "--kw1", "True", "--kw2=3.14"]
        parsed = _parse_cli_args(test_func, cli_args)
        self.assertEqual(parsed, {"pos1": "first_pos", "pos2": 10, "kw1": True, "kw2": 3.14})

    def test_run_cli_greet_command(self):
        @cli
        def greet(name: str, greeting: str = "Hello", repeat: int = 1):
            for _ in range(repeat):
                print(f"{greeting}, {name}!")
        
        # Simulate command line arguments
        sys.argv = ["cli.py", "greet", "John", "--greeting", "Hi", "--repeat", "2"]
        run_cli()
        output = self.mock_stdout.getvalue()
        self.assertIn("Hi, John!\nHi, John!", output)

    def test_run_cli_add_command(self):
        @cli
        def add(a: int, b: int):
            result = a + b
            print(f"The sum of {a} and {b} is {result}")
        
        sys.argv = ["cli.py", "add", "5", "10"]
        run_cli()
        output = self.mock_stdout.getvalue()
        self.assertIn("The sum of 5 and 10 is 15", output)

    def test_run_cli_echo_command(self):
        @cli
        def echo(message: str, loud: bool = False):
            if loud:
                print(message.upper())
            else:
                print(message)
        
        sys.argv = ["cli.py", "echo", "test message", "--loud", "True"]
        run_cli()
        output = self.mock_stdout.getvalue()
        self.assertIn("TEST MESSAGE", output)

        self.mock_stdout = io.StringIO() # Reset stdout for next assertion
        sys.stdout = self.mock_stdout
        sys.argv = ["cli.py", "echo", "another message"]
        run_cli()
        output = self.mock_stdout.getvalue()
        self.assertIn("another message", output)

    def test_run_cli_unknown_command(self):
        sys.argv = ["cli.py", "unknown_cmd"]
        with self.assertRaises(SystemExit) as cm:
            run_cli()
        self.assertEqual(cm.exception.code, 1)
        output = self.mock_stdout.getvalue()
        self.assertIn("Error: Unknown command 'unknown_cmd'", output)

    def test_run_cli_missing_required_argument(self):
        @cli
        def required_arg_func(param1: str, param2: int):
            pass
        
        sys.argv = ["cli.py", "required_arg_func", "value1"]
        with self.assertRaises(SystemExit) as cm:
            run_cli()
        self.assertEqual(cm.exception.code, 1)
        output = self.mock_stdout.getvalue()
        self.assertIn("Error: Missing required argument 'param2' for command 'required_arg_func'", output)

    def test_run_cli_no_command(self):
        sys.argv = ["cli.py"]
        with self.assertRaises(SystemExit) as cm:
            run_cli()
        self.assertEqual(cm.exception.code, 1)
        output = self.mock_stdout.getvalue()
        self.assertIn("Usage: python cli.py <command> [args...]", output)

if __name__ == '__main__':
    unittest.main()
