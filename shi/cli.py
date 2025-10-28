import inspect
import sys
from typing import Any, Callable, Dict, List, Tuple

# Dictionary to store (wrapped_func, original_func) tuples
_cli_commands: Dict[str, Tuple[Callable, Callable]] = {}


def _convert_value(value_str: str, target_type: Any) -> Any:
    """Attempt to convert a string value to a target type.

    Falls back to the original string if conversion fails.
    """

    if target_type == inspect.Parameter.empty or target_type is str:
        return value_str

    try:
        if target_type is bool:
            return value_str.lower() in ("true", "1", "t", "y", "yes")
        return target_type(value_str)
    except ValueError:
        return value_str


def _parse_cli_args(func: Callable, cli_args_raw: List[str]) -> Dict[str, Any]:
    """Parse command-line arguments for a given function.

    Supports var=val, --key value, and positional args with basic type conversion.
    """

    sig = inspect.signature(func)
    parsed_args: Dict[str, Any] = {}

    positional_params = [
        p
        for p in sig.parameters.values()
        if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
        and p.default == inspect.Parameter.empty
    ]

    cli_args_iter = iter(cli_args_raw)
    pos_param_idx = 0

    for arg_str in cli_args_iter:
        # var=val format (no leading dashes)
        if "=" in arg_str and not arg_str.startswith("--"):
            key, value_str = arg_str.split("=", 1)
            if key in sig.parameters:
                param = sig.parameters[key]
                parsed_args[key] = _convert_value(value_str, param.annotation)
            else:
                parsed_args[key] = value_str

        elif arg_str.startswith("--"):
            # --key=value or --key value
            key_value_pair = arg_str[2:].split("=", 1)
            key = key_value_pair[0]

            if len(key_value_pair) == 2:
                value_str = key_value_pair[1]
            else:
                try:
                    value_str = next(cli_args_iter)
                except StopIteration:
                    print(f"Error: Missing value for argument --{key}")
                    sys.exit(1)

            if key in sig.parameters:
                param = sig.parameters[key]
                parsed_args[key] = _convert_value(value_str, param.annotation)
            else:
                parsed_args[key] = value_str

        else:
            # Positional argument
            if pos_param_idx < len(positional_params):
                param = positional_params[pos_param_idx]
                parsed_args[param.name] = _convert_value(arg_str, param.annotation)
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
    _cli_commands[original_func.__name__] = (func, original_func)
    return func


def run_cli() -> None:
    """Dispatch CLI commands based on sys.argv."""

    if len(sys.argv) < 2:
        print("Usage: python cli.py <command> [args...]")
        print("Available commands:")
        for cmd_name, (wrapped_func, original_func) in _cli_commands.items():
            sig = inspect.signature(original_func)
            print(f"  {cmd_name}{sig}")
        sys.exit(1)

    command_name = sys.argv[1]
    if command_name not in _cli_commands:
        print(f"Error: Unknown command '{command_name}'")
        print("Available commands:", ", ".join(_cli_commands.keys()))
        sys.exit(1)

    wrapped_func, original_func = _cli_commands[command_name]
    parsed_args = _parse_cli_args(original_func, sys.argv[2:])
    final_args = {**parsed_args}

    for name, parameter in inspect.signature(original_func).parameters.items():
        if name not in final_args and parameter.default != inspect.Parameter.empty:
            final_args[name] = parameter.default

    try:
        wrapped_func(**final_args)
    except TypeError as e:
        print(f"Error calling command '{command_name}': {e}")
        print(f"Usage: {command_name}{inspect.signature(original_func)}")
        sys.exit(1)


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

    run_cli()
