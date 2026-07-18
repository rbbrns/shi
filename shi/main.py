import sys
import types
import atexit
import inspect
from typing import Callable, Any, List

# Track exceptions and sys.exit calls to avoid running main on crash/early exit
_has_exception = False
_sys_exit_called = False
_in_atexit = False

_orig_excepthook = sys.excepthook


def _excepthook(type, value, traceback):
    global _has_exception
    _has_exception = True
    _orig_excepthook(type, value, traceback)


sys.excepthook = _excepthook

_orig_sys_exit = sys.exit


def _sys_exit(code=0):
    global _sys_exit_called
    if _in_atexit:
        import os

        if code is None:
            exit_code = 0
        elif isinstance(code, int):
            exit_code = code
        else:
            print(code, file=sys.stderr)
            exit_code = 1
        os._exit(exit_code)
    else:
        _sys_exit_called = True
        _orig_sys_exit(code)


sys.exit = _sys_exit

# Explicitly registered main functions (via @shi.main)
_registered_mains: List[Callable] = []
_autocli_modules = set()
_active_cli_modules = {"__main__"}


def register_autocli_module(module):
    _autocli_modules.add(module)
    _active_cli_modules.add(module.__name__)


def register_active_module(name: str):
    _active_cli_modules.add(name)


class MainModule(types.ModuleType):
    def __call__(self, func: Callable) -> Callable:
        """Allows using shi.main as a decorator: @shi.main."""
        if not callable(func):
            raise TypeError("Only callable objects can be decorated with @shi.main")
        _registered_mains.append(func)
        return func


def _is_cli_command(func: Callable) -> bool:
    from .cli import cli_commands

    for wrapped, orig in cli_commands.values():
        if func is wrapped or func is orig:
            return True
    return False


def _execute_simple_main(func: Callable):
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    params = [p for p in params if p.name not in ("self", "cls")]

    if not params:
        func()
    elif len(params) == 1:
        # Pass raw command line arguments as a list of strings
        func(sys.argv[1:])
    else:
        raise TypeError(
            f"Function '{func.__name__}' has {len(params)} parameters. "
            "To use automatic CLI parsing for multiple parameters, decorate the function with '@cli'."
        )


def _run_main_at_exit():
    global _in_atexit
    _in_atexit = True
    # If there was an unhandled exception or sys.exit was explicitly called, do not run main
    import sys
    import shi.cli

    cli_module = sys.modules.get("shi.cli")
    cli_run_called = (
        getattr(cli_module, "cli_run_called", False) if cli_module else False
    )

    if _has_exception or _sys_exit_called or cli_run_called:
        return

    main_module = sys.modules.get("__main__")
    if not main_module:
        return

    for module in list(_autocli_modules):
        from .cli import cli

        # Register all public functions of the module as cli commands
        for name, val in list(module.__dict__.items()):
            if name.startswith("_"):
                continue
            if not callable(val):
                continue
            # Ensure it is defined in the module (not imported from elsewhere)
            if getattr(val, "__module__", None) != module.__name__:
                continue
            # Ensure it's not a class
            if inspect.isclass(val):
                continue
            # Ensure it's not the MainModule class/callable itself
            if isinstance(val, MainModule):
                continue
            # Ensure it's not decorated with @nocli
            if getattr(val, "__shi_nocli__", False):
                continue

            cli(val)

    target_main = None

    # 1. Check for explicitly registered mains (via @shi.main) in the __main__ module
    for m in _registered_mains:
        if getattr(m, "__module__", None) == "__main__":
            target_main = m
            break

    # 2. If no explicitly registered main, check for a function named 'main' in __main__
    # which is NOT registered as a CLI command
    if not target_main:
        if hasattr(main_module, "main"):
            candidate = getattr(main_module, "main")
            if (
                callable(candidate)
                and not isinstance(candidate, MainModule)
                and not _is_cli_command(candidate)
            ):
                target_main = candidate

    if target_main:
        _execute_simple_main(target_main)
        return

    # 3. If no simple main function, check for cli commands registered in __main__
    from .cli import cli_commands, run_cli, parse_cli_args

    main_cli_cmds = {}
    for name, (wrapped, orig) in cli_commands.items():
        orig_mod = getattr(orig, "__module__", None)
        if orig_mod == "__main__" or orig_mod in _active_cli_modules:
            main_cli_cmds[name] = (wrapped, orig)

    if not main_cli_cmds:
        return

    if len(main_cli_cmds) == 1:
        # Run the single CLI command directly without requiring the command name
        cmd_name, (wrapped, orig) = list(main_cli_cmds.items())[0]

        # Handle help flag
        if len(sys.argv) > 1 and sys.argv[-1] == "?":
            from .cli import show_command_help

            show_command_help(cmd_name)
            return

        # Check if the command name was explicitly provided as the first argument
        if len(sys.argv) > 1 and sys.argv[1] == cmd_name:
            args_to_parse = sys.argv[2:]
        else:
            args_to_parse = sys.argv[1:]

        try:
            parsed_args = parse_cli_args(orig, args_to_parse)
            final_args = {**parsed_args}
            for name, parameter in inspect.signature(orig).parameters.items():
                if (
                    name not in final_args
                    and parameter.default != inspect.Parameter.empty
                ):
                    final_args[name] = parameter.default

            rtn = wrapped(**final_args)
            if rtn is not None:
                print(rtn)
        except TypeError as e:
            print(f"Error calling command '{cmd_name}': {e}")
            from .cli import show_usage

            show_usage()
    else:
        # Multiple CLI commands, run the dispatcher
        run_cli(sys.argv[1:])


# Register exit handler
atexit.register(_run_main_at_exit)

# Replace the module class with our callable module class
sys.modules[__name__].__class__ = MainModule
