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


def is_bool_parameter(param: inspect.Parameter) -> bool:
    return param.annotation is bool or (
        param.annotation is inspect.Parameter.empty
        and isinstance(param.default, bool)
    )


def is_unannotated_none_default(param: inspect.Parameter) -> bool:
    return (
        param.annotation is inspect.Parameter.empty
        and param.default is None
    )


def parse_cli_args(func: Callable, cli_args_raw: List[str]) -> inspect.BoundArguments:
    """Parse command-line arguments for a given function and return BoundArguments.

    Supports var=val, --key value --key=value, key+, key-, key~, key~~ (and legacy
    key++, key--), and positional args with basic type conversion.
    """

    sig = inspect.signature(func)
    param_map = {normalize_arg_name(p): p for p in sig.parameters}
    raw_args: List[str] = []
    raw_kwargs: Dict[str, Any] = {}

    cli_args_iter = iter(cli_args_raw)
    for arg_str in cli_args_iter:
        if match := re.match(r"^--([^=\s]+)(=(.+))?$", arg_str):
            key, _, value_str = match.groups()
            actual_key = param_map.get(normalize_arg_name(key), key.replace("-", "_"))
            if value_str is None:
                try:
                    value_str = next(cli_args_iter)
                except StopIteration:
                    print(f"Error: Expected value after '{arg_str}'")
                    sys.exit(1)
            raw_kwargs[actual_key] = value_str
        elif match := re.match(r"^([^=\s]+)=(.+)$", arg_str):
            key, value_str = match.groups()
            actual_key = param_map.get(normalize_arg_name(key), key.replace("-", "_"))
            raw_kwargs[actual_key] = value_str
        elif match := re.match(
            r"^([a-zA-Z_][a-zA-Z0-9_]*)(\+\+|--|!~~|!~|\+|-|~~~|~~|~)$", arg_str
        ):
            # Handle Loh postfix operators
            key, op = match.groups()
            actual_key = param_map.get(normalize_arg_name(key), key.replace("-", "_"))
            is_valid_op = True
            if op in ("+", "++", "-", "--"):
                if actual_key in sig.parameters:
                    param = sig.parameters[actual_key]
                    if param.annotation != bool and not (
                        param.annotation == inspect.Parameter.empty
                        and isinstance(param.default, bool)
                    ):
                        is_valid_op = False

            if is_valid_op:
                if op in ("+", "++"):
                    raw_kwargs[actual_key] = True
                elif op in ("-", "--"):
                    raw_kwargs[actual_key] = False
                elif op in ("~", "~~", "~~~"):
                    raw_kwargs[actual_key] = None
                elif op in ("!~", "!~~"):
                    raw_kwargs[actual_key] = True
            else:
                raw_args.append(arg_str)
            else:
                is_bool = True
                if actual_key in sig.parameters:
                    param = sig.parameters[actual_key]
                    is_bool = is_bool_parameter(param) or is_unannotated_none_default(param)

                if is_bool:
                    raw_kwargs[actual_key] = op in ("++", "+")
                else:
                    raw_args.append(arg_str)
        else:
            raw_args.append(arg_str)

    # Convert types based on signature
    positional_params = [
        p
        for p in sig.parameters.values()
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    var_positional_param = next(
        (p for p in sig.parameters.values() if p.kind == inspect.Parameter.VAR_POSITIONAL),
        None
    )

    converted_args = []
    for i, arg_str in enumerate(raw_args):
        if i < len(positional_params):
            param = positional_params[i]
            converted_args.append(convert_value(arg_str, param.annotation))
        elif var_positional_param:
            converted_args.append(convert_value(arg_str, var_positional_param.annotation))
        else:
            converted_args.append(arg_str)

    converted_kwargs = {}
    for key, val in raw_kwargs.items():
        if isinstance(val, bool) or val is None:
            converted_kwargs[key] = val
        elif key in sig.parameters:
            param = sig.parameters[key]
            converted_kwargs[key] = convert_value(val, param.annotation)
        else:
            converted_kwargs[key] = convert_value(val, inspect.Parameter.empty)

    # Separate bindable kwargs from extra kwargs
    has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
    bind_kwargs = {}
    extra_kwargs = {}
    for key, val in converted_kwargs.items():
        if key in sig.parameters or has_var_keyword:
            bind_kwargs[key] = val
        else:
            extra_kwargs[key] = val

    # Bind and apply defaults
    bound = sig.bind(*converted_args, **bind_kwargs)
    bound.apply_defaults()

    # Add extra kwargs back
    for key, val in extra_kwargs.items():
        bound.arguments[key] = val

    return bound


def normalize_arg_name(name: str) -> str:
    return name.lower().replace("-", "").replace("_", "")


def check_argument_collisions(func: Callable):
    sig = inspect.signature(func)
    normalized_names = {}
    for param_name in sig.parameters:
        param = sig.parameters[param_name]
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        norm_name = normalize_arg_name(param_name)
        if norm_name in normalized_names:
            raise ValueError(
                f"Argument collision detected in command '{func.__name__}': "
                f"'{param_name}' and '{normalized_names[norm_name]}' both normalize to '{norm_name}'"
            )
        normalized_names[norm_name] = param_name


def check_command_collision(new_name: str):
    norm_new = normalize_command_name(new_name, case_insensitive=True, normalize_separators=True)
    for registered_name in cli_commands:
        norm_reg = normalize_command_name(registered_name, case_insensitive=True, normalize_separators=True)
        if norm_new == norm_reg:
            raise ValueError(
                f"Command collision detected: '{new_name}' and '{registered_name}' "
                f"both normalize to '{norm_new}'"
            )


class CliDecorator:
    """Decorator to register a function, module, or class, with support for dynamic attribute access to registered commands."""
def normalize_arg_name(name: str) -> str:
    return name.lower().replace("-", "").replace("_", "")


def check_argument_collisions(func: Callable):
    sig = inspect.signature(func)
    normalized_names = {}
    for param_name in sig.parameters:
        param = sig.parameters[param_name]
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        norm_name = normalize_arg_name(param_name)
        if norm_name in normalized_names:
            raise ValueError(
                f"Argument collision detected in command '{func.__name__}': "
                f"'{param_name}' and '{normalized_names[norm_name]}' both normalize to '{norm_name}'"
            )
        normalized_names[norm_name] = param_name


def normalize_command_name(name: str, case_insensitive: bool, normalize_separators: bool) -> str:
    if case_insensitive:
        name = name.lower()
    if normalize_separators:
        name = name.replace("-", "_")
    return name


def check_command_collision(new_name: str):
    norm_new = normalize_command_name(new_name, case_insensitive=True, normalize_separators=True)
    for registered_name in cli_commands:
        norm_reg = normalize_command_name(registered_name, case_insensitive=True, normalize_separators=True)
        if norm_new == norm_reg:
            raise ValueError(
                f"Command collision detected: '{new_name}' and '{registered_name}' "
                f"both normalize to '{norm_new}'"
            )


def cli(thing: Any) -> Any:
    """Decorator to register a function or all public methods of a class."""
>>>>>>> 6632952 (feat: shi: Add collision detection for commands and arguments)

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


def normalize_command_name(name: str, case_insensitive: bool = True, normalize_separators: bool = True) -> str:
    if case_insensitive:
        name = name.lower()
    if normalize_separators:
        name = name.replace("-", "_")
    return name


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


def run_cli(argv: List[str] = None, debug: bool = False, case_insensitive: bool = True, normalize_separators: bool = True) -> None:
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
    matched_cmd_name = None
    for registered_name in cli_commands:
        if normalize_command_name(registered_name, case_insensitive, normalize_separators) == \
           normalize_command_name(command_name, case_insensitive, normalize_separators):
            matched_cmd_name = registered_name
            break

    if matched_cmd_name is None:
        console.print(
            f"[bold red]Error: Unknown command '{escape(command_name)}'[/bold red]"
        )
        show_usage(exit_code=1)

    wrapped_func, original_func = cli_commands[matched_cmd_name]
    try:
        bound = parse_cli_args(original_func, argv[1:])
    except TypeError as e:
        print(f"Error parsing arguments for '{matched_cmd_name}': {e}")
        sys.exit(1)

    sig = inspect.signature(original_func)
    if debug and "debug" in sig.parameters and "debug" not in bound.arguments:
        bound.arguments["debug"] = True

    try:
        rtn = wrapped_func(*bound.args, **bound.kwargs)
        if rtn is not None:
            print(rtn)
    except TypeError as e:
        print(f"Error calling command '{matched_cmd_name}': {e}")
        raise e


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
