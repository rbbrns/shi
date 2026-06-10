import unittest
from shi.cli import cli, parse_cli_args, cli_commands


class TestCliBooleanFlags(unittest.TestCase):
    def setUp(self):
        cli_commands.clear()

    def get_original_func(self, func_name):
        return cli_commands[func_name][1]

    def test_parse_cli_args_boolean_flag_suffix_annotated(self):
        @cli
        def test_func(android: bool = False, board: str = None):
            pass

        cli_args_raw = ["android++", "board=redrix"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"android": True, "board": "redrix"})

        cli_args_raw = ["android--", "board=redrix"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"android": False, "board": "redrix"})

    def test_parse_cli_args_boolean_flag_suffix_unannotated(self):
        @cli
        def test_func(android=False, board=None):
            pass

        cli_args_raw = ["android++", "board=redrix"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"android": True, "board": "redrix"})

    def test_parse_cli_args_boolean_flag_suffix_not_in_sig(self):
        @cli
        def test_func(board=None):
            pass

        cli_args_raw = ["android++", "board=redrix"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        # Should still be in parsed_args, just like var=val
        self.assertEqual(parsed.arguments, {"android": True, "board": "redrix"})

    def test_parse_cli_args_boolean_flag_suffix_fallback_to_positional(self):
        @cli
        def test_func(name: str):
            pass

        # 'name++' matches the regex, but 'name' is a string in sig.parameters.
        # It should fall back to being a positional argument.
        cli_args_raw = ["name++"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"name": "name++"})
    def test_parse_cli_args_loh_boolean_flags(self):
        @cli
        def test_func(android: bool = False, board: str = "default_board"):
            pass

        cli_args_raw = ["android+", "board~"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"android": True, "board": None})

        cli_args_raw = ["android+", "board~~"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"android": True, "board": None})

        cli_args_raw = ["android-"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"android": False, "board": "default_board"})

    def test_parse_cli_args_loh_boolean_flags_unannotated(self):
        @cli
        def test_func(android = False):
            pass

        cli_args_raw = ["android+"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"android": True})

        cli_args_raw = ["android-"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"android": False})

    def test_parse_cli_args_boolean_flag_suffix_unannotated_default_none(self):
        @cli
        def test_func(android = None):
            pass

        cli_args_raw = ["android+"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"android": True})

        cli_args_raw = ["android-"]
        parsed = parse_cli_args(self.get_original_func("test_func"), cli_args_raw)
        self.assertEqual(parsed.arguments, {"android": False})



if __name__ == "__main__":
    unittest.main()

