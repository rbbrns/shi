#!/usr/bin/env python3

import inspect
import re
import sys
import functools

try:
    from . import dprint
except ImportError:
    # Fallback for when cli.py is run directly as a script
    import dprint

from typing import Any, Callable, Dict, List, Tuple, get_args, get_origin

try:
    from typing import Literal
except ImportError:
    # Python < 3.8
    Literal = None

from enum import Enum
from rich.console import Console
from rich.syntax import Syntax
from rich.markup import escape

# Dictionary to store (wrapped_func, original_func) tuples
cli_commands: Dict[str, Tuple[Callable, Callable]] = {}
console = Console()


def _register_aliases():
    """Scan the module globals of registered functions for any aliases."""
    aliases = {}
    for cmd_name, (wrapped_func, original_func) in list(cli_commands.items()):
        module_name = original_func.__module__
        if module_name == "__main__" or module_name in sys.modules:
            mod = sys.modules.get(module_name)
            if mod:
                for name, val in mod.__dict__.items():
                    if name.startswith("_"):
                        continue
                    if (
                        val is wrapped_func or val is original_func
                    ) and name not in cli_commands:
                        aliases[name] = (wrapped_func, original_func)
    cli_commands.update(aliases)


def convert_value(value_str: str, target_type: Any) -> Any:
    """Attempt to convert a string value to a target type.

    Falls back to the original string if conversion fails.
    """

    if target_type is inspect.Parameter.empty:
        try:
            return int(value_str, 10)
        except ValueError:
            pass
        try:
            if value_str.startswith("0x"):
                return int(value_str, 16)
        except ValueError:
            pass
        try:
            return float(value_str)
        except ValueError:
            pass
        if value_str in ("True", "False", "None") or (
            value_str.startswith("[") and value_str.endswith("]")
        ) or (
            value_str.startswith("{") and value_str.endswith("}")
        ):
            try:
                return eval(value_str)
            except Exception:
                pass
        return value_str # Fallback if no conversion works

    # Enum support
    if isinstance(target_type, type) and issubclass(target_type, Enum):
        # First try direct lookup (case-sensitive)
        if value_str in target_type.__members__:
            return target_type[value_str]

        # Try case-insensitive lookup
        upper_val = value_str.upper()
        if upper_val in target_type.__members__:
            return target_type[upper_val]

        valid_options = [e.name for e in target_type]
        console.print(
            f"[bold red]Error: Invalid value '{escape(value_str)}' for {target_type.__name__}.[/bold red]"
        )
        console.print(f"Valid options: [green]{', '.join(valid_options)}[/green]")
        sys.exit(1)

    # Literal support
    if Literal is not None and get_origin(target_type) is Literal:
        valid_options = get_args(target_type)
        for option in valid_options:
            # Check string match
            if str(option) == value_str:
                return option
            # Check case-insensitive match for strings/bools
            if str(option).lower() == value_str.lower():
                return option

        console.print(
            f"[bold red]Error: Invalid value '{escape(value_str)}'.[/bold red]"
        )
        console.print(
            f"Valid options: [green]{', '.join(map(str, valid_options))}[/green]"
        )
        sys.exit(1)

    if target_type is bool:
        return value_str.lower() in ("true", "1", "t", "y", "yes")
    if target_type is int:
        try:
            return int(value_str, 10)
        except ValueError:
            try:
                return int(value_str, 16)
            except ValueError:
                return value_str  # Fallback to string if int conversion fails
    elif target_type is float:
        try:
            return float(value_str)
        except ValueError:
            return value_str  # Fallback to string if float conversion fails
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
        and p.name not in ["self", "cls", "."]
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
        elif match := re.match(
            r"^([a-zA-Z_][a-zA-Z0-9_]*)(\+\+|--|!~~|!~|\+|-|~~~|~~|~)$", arg_str
        ):
            # Handle Loh postfix operators
            key, op = match.groups()
            is_valid_op = True
            if op in ("+", "++", "-", "--"):
                if key in sig.parameters:
                    param = sig.parameters[key]
                    if param.annotation != bool and not (
                        param.annotation == inspect.Parameter.empty
                        and isinstance(param.default, bool)
                    ):
                        is_valid_op = False

            if is_valid_op:
                if op in ("+", "++"):
                    parsed_args[key] = True
                elif op in ("-", "--"):
                    parsed_args[key] = False
                elif op in ("~", "~~", "~~~"):
                    parsed_args[key] = None
                elif op in ("!~", "!~~"):
                    parsed_args[key] = True
            else:
                # Not a boolean parameter, treat as positional argument
                if pos_param_idx < len(positional_params):
                    param = positional_params[pos_param_idx]
                    parsed_args[param.name] = convert_value(arg_str, param.annotation)
                    pos_param_idx += 1
                else:
                    print(
                        f"Warning: Unmatched positional argument '{arg_str}' for function '{func.__name__}'"
                    )
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


class CliDecorator:
    """Decorator to register a function, module, or class, with support for dynamic attribute access to registered commands."""

    def __call__(self, thing: Any) -> Any:
        if inspect.isclass(thing):
            thing_instance = thing()
            # It's a class, wrap all public methods
            for name, func in inspect.getmembers(thing, inspect.isfunction):
                if name.startswith("_"):
                    continue
                func = getattr(thing_instance, name)
                original_func = (
                    func.__wrapped__ if hasattr(func, "__wrapped__") else func
                )
                cli_commands[name] = (func, original_func)

                import shi.main

                shi.main.register_active_module(original_func.__module__)
            return thing
        elif inspect.ismodule(thing):
            # Register all public functions of the module
            for name, func in inspect.getmembers(thing, inspect.isfunction):
                if name.startswith("_"):
                    continue
                # Ensure it is defined in that module (not imported)
                if getattr(func, "__module__", None) != thing.__name__:
                    continue
                if getattr(func, "__shi_nocli__", False):
                    continue
                original_func = (
                    func.__wrapped__ if hasattr(func, "__wrapped__") else func
                )
                cli_commands[original_func.__name__] = (func, original_func)

            import shi.main

            shi.main.register_active_module(thing.__name__)
            return thing
        else:
            # It's a function, register it directly
            func = thing
            original_func = func.__wrapped__ if hasattr(func, "__wrapped__") else func
            cli_commands[original_func.__name__] = (func, original_func)

            import shi.main

            shi.main.register_active_module(original_func.__module__)
            return func

    def __getattr__(self, name: str) -> Any:
        if name in cli_commands:
            return cli_commands[name][0]  # Return the wrapped function
        raise AttributeError(f"module/decorator 'cli' has no attribute '{name}'")


cli = CliDecorator()


def nocli(func: Any) -> Any:
    """Decorator to mark a function to be excluded from auto-CLI registration."""
    if func is not None:
        try:
            func.__shi_nocli__ = True
        except AttributeError:
            pass
    return func


class AutoCliSentinel:
    def __repr__(self) -> str:
        return "<AutoCliSentinel>"


def __getattr__(name: str) -> Any:
    if name == "auto":
        import sys

        for frame_info in inspect.stack():
            module = inspect.getmodule(frame_info.frame)
            if module is None:
                continue
            mod_name = module.__name__
            if mod_name in (
                "shi",
                "shi.cli",
                "shi.main",
                "importlib._bootstrap",
                "importlib._bootstrap_external",
            ):
                continue
            if mod_name.startswith("importlib"):
                continue
            import shi.main

            shi.main.register_autocli_module(module)
            break
        return AutoCliSentinel()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def show_command_help(cmd_name: str):
    _register_aliases()
    if cmd_name not in cli_commands:
        console.print(
            f"[bold red]Error: Unknown command '{escape(cmd_name)}'[/bold red]"
        )
        show_usage(exit_code=1)

    wrapped_func, original_func = cli_commands[cmd_name]
    sig = inspect.signature(original_func)
    sig_str = str(sig)
    sig_str = re.sub(r"=[^,\)]*_LOH_SENTINEL[^,\)]*", "=~", sig_str)
    console.print(
        f"[bold magenta]Command:[/bold magenta] [bold green]{escape(cmd_name)}[/bold green]"
    )
    console.print(
        f"[bold magenta]Usage:[/bold magenta] {escape(cmd_name)}{escape(sig_str)}"
    )
    if original_func.__doc__:
        console.print(f"\n[bold magenta]Description:[/bold magenta]")
        console.print(f"[cyan]{escape(inspect.getdoc(original_func))}[/cyan]")

    console.print(f"\n[bold magenta]Source:[/bold magenta]")
    try:
        source = inspect.getsource(original_func)
        syntax = Syntax(source, "python", theme="monokai", line_numbers=True)
        console.print(syntax)
    except OSError:
        console.print("[yellow](Source unavailable)[/yellow]")
    sys.exit(0)


def show_usage(exit_code: int = 1):
    _register_aliases()
    console.print(
        f"[bold magenta]Usage:[/bold magenta] {escape(sys.argv[0])} <command> {escape('[args...]')}"
    )
    console.print(f"       {escape(sys.argv[0])} <command> ... ?   (for command help)")
    console.print(f"[bold magenta]Available commands:[/bold magenta]")
    for cmd_name, (wrapped_func, original_func) in cli_commands.items():
        sig = inspect.signature(original_func)
        sig_str = str(sig)
        sig_str = re.sub(r"=[^,\)]*_LOH_SENTINEL[^,\)]*", "=~", sig_str)
        console.print(f"  [bold green]{escape(cmd_name)}[/bold green]{escape(sig_str)}")
    sys.exit(exit_code)


cli_run_called = False


def run_cli(argv: List[str] = None, debug: bool = False) -> None:
    """Dispatch CLI commands based on argv.

    If argv is None, defaults to sys.argv[1:].
    """
    global cli_run_called
    cli_run_called = True
    _register_aliases()
    if argv is None:
        argv = sys.argv[1:]

    if debug:
        print(f"Debug mode enabled. argv: {argv}")

    if len(argv) < 1:
        show_usage(exit_code=1)

    if argv[-1] == "?":
        if len(argv) == 1:
            show_usage(exit_code=0)
        else:
            show_command_help(argv[0])

    command_name = argv[0]
    if command_name not in cli_commands:
        console.print(
            f"[bold red]Error: Unknown command '{escape(command_name)}'[/bold red]"
        )
        show_usage(exit_code=1)

    wrapped_func, original_func = cli_commands[command_name]
    parsed_args = parse_cli_args(original_func, argv[1:])
    final_args = {**parsed_args}

    sig = inspect.signature(original_func)
    if debug and "debug" in sig.parameters and "debug" not in final_args:
        final_args["debug"] = True

    for name, parameter in sig.parameters.items():
        if name not in final_args:
            if parameter.default != inspect.Parameter.empty:
                final_args[name] = parameter.default
            # Else: leave required parameters without default values out of final_args

    try:
        rtn = wrapped_func(**final_args)
        if rtn is not None:
            print(rtn)
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

    run_cli(sys.argv[1:])
