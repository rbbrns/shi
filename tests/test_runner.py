import unittest
import subprocess
import tempfile
import os
import sys
from typing import Tuple


class TestRunner(unittest.TestCase):
    def run_script(self, code: str, args: list = None) -> Tuple[int, str, str]:
        if args is None:
            args = []

        # Create temp file
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Run using the current virtual env python
            python_bin = sys.executable
            cmd = [python_bin, temp_path] + args
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env = dict(os.environ)
            env["PYTHONPATH"] = repo_root + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=repo_root,
                env=env,
            )
            return result.returncode, result.stdout, result.stderr
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_simple_main(self):
        code = """
import shi.main

def main():
    print("HELLO MAIN")
"""
        code_status, stdout, stderr = self.run_script(code)
        self.assertEqual(code_status, 0)
        self.assertIn("HELLO MAIN", stdout)

    def test_simple_main_with_args(self):
        code = """
import shi.main

def main(args):
    print("ARGS:", args)
"""
        code_status, stdout, stderr = self.run_script(code, ["foo", "bar"])
        self.assertEqual(code_status, 0)
        self.assertIn("ARGS: ['foo', 'bar']", stdout)

    def test_explicit_decorator(self):
        code = """
import shi.main

@shi.main
def my_entry_point(args):
    print("ENTRY:", args)
"""
        code_status, stdout, stderr = self.run_script(code, ["hello"])
        self.assertEqual(code_status, 0)
        self.assertIn("ENTRY: ['hello']", stdout)

    def test_cli_mode_single_command(self):
        code = """
from shi import cli
import shi.main

@cli
def greet(name: str, repeat: int = 1):
    for _ in range(repeat):
        print(f"Hi {name}")
"""
        code_status, stdout, stderr = self.run_script(
            code, ["--name=Bob", "--repeat=2"]
        )
        self.assertEqual(code_status, 0)
        self.assertEqual(stdout.strip(), "Hi Bob\nHi Bob")

    def test_no_import_no_run(self):
        code = """
import shi  # No shi.main

def main():
    print("SHOULD NOT RUN")
"""
        code_status, stdout, stderr = self.run_script(code)
        self.assertEqual(code_status, 0)
        self.assertNotIn("SHOULD NOT RUN", stdout)

    def test_exception_suppresses_main(self):
        code = """
import shi.main

def main():
    print("SHOULD NOT RUN")

raise ValueError("Boom")
"""
        code_status, stdout, stderr = self.run_script(code)
        self.assertNotEqual(code_status, 0)
        self.assertIn("ValueError: Boom", stderr)
        self.assertNotIn("SHOULD NOT RUN", stdout)

    def test_sys_exit_suppresses_main(self):
        code = """
import sys
import shi.main

def main():
    print("SHOULD NOT RUN")

sys.exit(0)
"""
        code_status, stdout, stderr = self.run_script(code)
        self.assertEqual(code_status, 0)
        self.assertNotIn("SHOULD NOT RUN", stdout)

    def test_too_many_parameters_error(self):
        code = """
import shi.main

def main(foo, bar):
    pass
"""
        code_status, stdout, stderr = self.run_script(code)
        self.assertIn("TypeError: Function 'main' has 2 parameters", stderr)

    def test_autocli_single_command(self):
        code = """
from shi.cli import auto, nocli

def greet(name: str):
    print(f"Hello {name}!")
"""
        code_status, stdout, stderr = self.run_script(code, ["--name=Alice"])
        self.assertEqual(code_status, 0)
        self.assertEqual(stdout.strip(), "Hello Alice!")

    def test_autocli_multiple_commands(self):
        code = """
from shi.cli import auto, nocli

def add(a: int, b: int):
    print(a + b)

def sub(a: int, b: int):
    print(a - b)
"""
        # Test calling 'add'
        code_status, stdout, stderr = self.run_script(code, ["add", "5", "3"])
        self.assertEqual(code_status, 0)
        self.assertEqual(stdout.strip(), "8")

        # Test calling 'sub'
        code_status, stdout, stderr = self.run_script(code, ["sub", "5", "3"])
        self.assertEqual(code_status, 0)
        self.assertEqual(stdout.strip(), "2")

    def test_autocli_exclusions(self):
        code = """
from shi.cli import auto, nocli

def public_cmd():
    print("public")

@nocli
def excluded_cmd():
    print("excluded")

def _private_cmd():
    print("private")
"""
        # Excluded and private commands should not be registered.
        # Thus, only 'public_cmd' is registered.
        # Since only one command is registered, it runs directly.
        code_status, stdout, stderr = self.run_script(code)
        self.assertEqual(code_status, 0)
        self.assertEqual(stdout.strip(), "public")

    def test_autocli_external_imports(self):
        code = """
from shi.cli import auto, nocli
from os.path import join

def my_cmd(a: str, b: str):
    print(join(a, b))
"""
        # 'join' is imported, so it shouldn't be registered.
        # Only 'my_cmd' is registered, so it is the sole CLI command.
        code_status, stdout, stderr = self.run_script(code, ["dir", "file.txt"])
        self.assertEqual(code_status, 0)
        self.assertEqual(stdout.strip(), "dir/file.txt")

    def test_autocli_import_external_auto(self):
        code = """
import sys, os
helper_path = os.path.join(os.path.dirname(__file__), "my_helper.py")
with open(helper_path, "w") as f:
    f.write('''from shi.cli import auto
def helper_cmd():
    print("from helper")
''')

import atexit
atexit.register(lambda: os.path.exists(helper_path) and os.remove(helper_path))

from shi.cli import auto
import my_helper

def main_cmd():
    print("from main")
"""
        # Call helper_cmd
        code_status, stdout, stderr = self.run_script(code, ["helper_cmd"])
        self.assertEqual(code_status, 0)
        self.assertEqual(stdout.strip(), "from helper")

        # Call main_cmd
        code_status, stdout, stderr = self.run_script(code, ["main_cmd"])
        self.assertEqual(code_status, 0)
        self.assertEqual(stdout.strip(), "from main")

    def test_cli_decorator_module(self):
        code = """
import sys, os
helper_path = os.path.join(os.path.dirname(__file__), "my_plain_helper.py")
with open(helper_path, "w") as f:
    f.write('''def plain_cmd(a: int):
    print("plain", a)
''')

import atexit
atexit.register(lambda: os.path.exists(helper_path) and os.remove(helper_path))

from shi.cli import cli
import my_plain_helper

cli(my_plain_helper)
"""
        code_status, stdout, stderr = self.run_script(code, ["--a=42"])
        self.assertEqual(code_status, 0)
        self.assertEqual(stdout.strip(), "plain 42")

    def test_cli_decorator_imported_function(self):
        code = """
import sys, os
helper_path = os.path.join(os.path.dirname(__file__), "my_func_helper.py")
with open(helper_path, "w") as f:
    f.write('''def hello():
    print("hello from helper")
''')

import atexit
atexit.register(lambda: os.path.exists(helper_path) and os.remove(helper_path))

from shi.cli import cli
from my_func_helper import hello

cli(hello)
"""
        code_status, stdout, stderr = self.run_script(code)
        self.assertEqual(code_status, 0)
        self.assertEqual(stdout.strip(), "hello from helper")


if __name__ == "__main__":
    unittest.main()
