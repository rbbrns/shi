#!/usr/bin/env python3

import inspect
import sys
import re
from dprint import dprint
from typing import Any, Callable, Dict, List, Tuple

# Dictionary to store (wrapped_func, original_func) tuples
cli_commands: Dict[str, Tuple[Callable, Callable]] = {}


def convert_value(value_str: str, target_type: Any) -> Any:
    """Attempt to convert a string value to a target type.

    Falls back to the original string if conversion fails.
    """
    dprint(value_str, target_type)

    if target_type is inspect.Parameter.empty:
        try:
            return int(value_str, 10)
        except ValueError:
            pass
        try:
            return int(value_str, 16)
        except ValueError:
            pass
        try:
            return float(value_str)
        except ValueError:
            pass
        try:
            return eval(value_str)
        except Exception as e:
            dprint(e)

    if target_type is bool:
        return value_str.lower() in ("true", "1", "t", "y", "yes")
    if target_type is int:
        try:
            return int(value_str, 10)
        except ValueError:
            return int(value_str, 16)
    elif target_type is float:
        return float(value_str)
    elif target_type is str:
        return value_str
    # Handle list types
    elif getattr(target_type, "__origin__", None) is list:
        item_type = target_type.__args__[0]
        items = re.split(r",\s*", value_str)
        return [convert_value(item, item_type) for item in items]
    return value_str


def parse_cli_args(func: Callable, cli_args_raw: List[str]) -> Dict[str, Any]:
    """Parse command-line arguments for a given function.

    Supports var=val, --key value --key=value, key++ and key--, and positional args with basic type conversion.
    """

    sig = inspect.signature(func)
    parsed_args: Dict[str, Any] = {}

    positional_params = [
        p
        for p in sig.parameters.values()
        if (
            p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
            or p.kind == inspect.Parameter.POSITIONAL_ONLY
        )
        and p.default == inspect.Parameter.empty
    ]

    cli_args_iter = iter(cli_args_raw)
    pos_param_idx = 0

    for arg_str in cli_args_iter:

        if match := re.match(r"^--([^=\s]+)(=(.+))?$", arg_str):
            # Handle --key=value and --key value formats
            key, _, value_str = match.groups()
            if key in sig.parameters:
                param = sig.parameters[key]
                if value_str is None:
                    # Value is in the next argument
                    try:
                        value_str = next(cli_args_iter)
                    except StopIteration:
                        print(f"Error: Expected value after '{arg_str}'")
                        sys.exit(1)
                parsed_args[key] = convert_value(value_str, param.annotation)
            else:
                if value_str is None:
                    # Value is in the next argument
                    try:
                        value_str = next(cli_args_iter)
                    except StopIteration:
                        print(f"Error: Expected value after '{arg_str}'")
                        sys.exit(1)
                parsed_args[key] = value_str
        elif match := re.match(r"^([^=\s]+)=(.+)$", arg_str):
            # Hanlde var=val format (no leading dashes)
            key, value_str = match.groups()
            if key in sig.parameters:
                param = sig.parameters[key]
                parsed_args[key] = convert_value(value_str, param.annotation)
            else:
                parsed_args[key] = value_str
        elif match := re.match(r"^([^+\s]+)(\+\+|--)$", arg_str):
            # Handle key++ and key-- for boolean flags
            key, op = match.groups()
            if key in sig.parameters and sig.parameters[key].annotation == bool:
                parsed_args[key] = op == "++"
        else:
            # Positional argument
            if pos_param_idx < len(positional_params):
                param = positional_params[pos_param_idx]
                parsed_args[param.name] = convert_value(arg_str, param.annotation)
                pos_param_idx += 1
            else:
                print(
                    f"Warning: Unmatched positional argument '{arg_str}' for function '{func.__name__}'"
                )

    return parsed_args


def cli(func: Callable) -> Callable:
    """Decorator to register a function as a CLI command.

    If the function is wrapped (has __wrapped__), the original function is used
    for signature inspection.
    """

    original_func = func.__wrapped__ if hasattr(func, "__wrapped__") else func
    cli_commands[original_func.__name__] = (func, original_func)
    return func


def show_usage():
    print(f"Usage: {sys.argv[0]} <command> [args...]")
    print("Available commands:")
    for cmd_name, (wrapped_func, original_func) in cli_commands.items():
        sig = inspect.signature(original_func)
        print(f"  {cmd_name}{sig}")
    sys.exit(1)


def run_cli() -> None:
    """Dispatch CLI commands based on sys.argv."""

    if len(sys.argv) < 2:
        show_usage()

    command_name = sys.argv[1]
    if command_name not in cli_commands:
        print(f"Error: Unknown command '{command_name}'")
        show_usage()

    wrapped_func, original_func = cli_commands[command_name]
    parsed_args = parse_cli_args(original_func, sys.argv[2:])
    final_args = {**parsed_args}

    for name, parameter in inspect.signature(original_func).parameters.items():
        if name not in final_args and parameter.default != inspect.Parameter.empty:
            final_args[name] = parameter.default
        else:
            final_args.setdefault(name, None)

    try:
        wrapped_func(**final_args)
    except TypeError as e:
        print(f"Error calling command '{command_name}': {e}")
        show_usage()


if __name__ == "__main__":

    @cli
    def greet(name: str, greeting: str = "Hello", repeat: int = 1):
        """Greet a name with an optional greeting repeated multiple times."""
        for _ in range(repeat):
            print(f"{greeting}, {name}!")

    @cli
    def add(a: int, b: int):
        """Add two numbers and print the result."""
        result = a + b
        print(f"The sum of {a} and {b} is {result}")
        return result

    @cli
    def echo(message: str, loud: bool = False):
        """Echo a message; uppercase if --loud is provided."""
        if loud:
            print(message.upper())
        else:
            print(message)

    @cli
    def todo(foo, tasks: List[int], urgent: bool = False):
        """Print a list of tasks, marking them as urgent if specified."""
        for task in tasks:
            if urgent:
                print(f"!{task}")
            else:
                print(task)
            print(foo)

    run_cli()
