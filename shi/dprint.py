"""
dprint - A debug print library with runtime reflection
Provides human-readable debugging output with variable names, types, and values.
"""

import inspect
import sys
import gc
from typing import Any
from pathlib import Path
from rich.console import Console

console = Console()

def dprint(*args, hide_wrappers=True, **kwargs):
    """
    Debug print with runtime reflection.

    Prints detailed information about variables including:
    - Filename and line number where dprint was called
    - Function/scope name
    - Variable names, types, and values

    Args:
            *args: Positional arguments to print
            **kwargs: Keyword arguments to print

    Example:
            x = 42
            dprint(x)
            # Output:
            # example.py:10 main()
            #   x: int = 42
    """
    # Get the caller's frame
    frame = inspect.currentframe()
    if frame is None:
        print("dprint: Unable to get frame information")
        return

    try:
        caller_frame = frame.f_back
        if caller_frame is None:
            print("dprint: Unable to get caller frame")
            return

        # Extract caller information
        filename = caller_frame.f_code.co_filename
        line_number = caller_frame.f_lineno

        # Print backtrace
        depth = _print_backtrace(caller_frame, hide_wrappers=hide_wrappers)

        # If no arguments, dump all local variables from caller's scope
        if not args and not kwargs:
            for var_name, var_value in caller_frame.f_locals.items():
                if not var_name.startswith("_"):
                    type_name = type(var_value).__name__
                    _print_variable(var_name, type_name, var_value, depth)
            return

        # For positional arguments, try to extract variable names
        if args:
            # Get the source code line
            try:
                import linecache

                source_line = linecache.getline(filename, line_number).strip()

                # Extract the argument expressions from the source
                # This is a simplified parser - looks for content between dprint()
                if "dprint(" in source_line:
                    start = source_line.index("dprint(") + 7
                    # Find matching closing paren
                    paren_count = 1
                    end = start
                    for i, char in enumerate(source_line[start:], start):
                        if char == "(":
                            paren_count += 1
                        elif char == ")":
                            paren_count -= 1
                            if paren_count == 0:
                                end = i
                                break

                    args_str = source_line[start:end]
                    # Split by commas (simple split, doesn't handle nested structures perfectly)
                    var_names = [
                        arg.strip() for arg in args_str.split(",") if arg.strip()
                    ]
                else:
                    var_names = [f"arg{i}" for i in range(len(args))]
            except:
                var_names = [f"arg{i}" for i in range(len(args))]

            # Print each positional argument
            for i, (value, name) in enumerate(zip(args, var_names)):
                type_name = type(value).__name__
                _print_variable(name, type_name, value, depth)

        # Print keyword arguments
        for key, value in kwargs.items():
            type_name = type(value).__name__
            _print_variable(key, type_name, value, depth)

    finally:
        # Clean up frame references to avoid reference cycles
        del frame
        if "caller_frame" in locals():
            del caller_frame


def _print_backtrace(caller_frame, hide_wrappers=True):
    """Print the call stack backtrace."""
    stack = []
    frame = caller_frame

    # Collect stack frames with their local variables
    while frame is not None:
        func_obj = next(
            (f for f in gc.get_referrers(frame.f_code) if inspect.isfunction(f)),
            None,
        )

        if hide_wrappers and func_obj and hasattr(func_obj, "__wrapped__"):
            frame = frame.f_back
            continue

        filename = frame.f_code.co_filename
        line_number = frame.f_lineno
        function_name = frame.f_code.co_name
        short_filename = Path(filename).name

        # Collect all frames including module level for context
        if function_name == "<module>":
            # For module level, just store basic info
            stack.append((short_filename, line_number, None, None, False))
        else:
            # Get function arguments (parameters)
            is_method = False
            func_obj = next(
                (f for f in gc.get_referrers(frame.f_code) if inspect.isfunction(f)),
                None,
            )
            if func_obj and "." in func_obj.__qualname__:
                arginfo = inspect.getargvalues(frame)
                if arginfo.args:
                    first_arg_name = arginfo.args[0]
                    if first_arg_name in arginfo.locals:
                        first_arg_value = arginfo.locals[first_arg_name]
                        if hasattr(first_arg_value, "__class__"):
                            class_name = first_arg_value.__class__.__name__
                            if class_name in func_obj.__qualname__.split("."):
                                is_method = True

            arginfo = inspect.getargvalues(frame)
            args_dict = {
                arg: arginfo.locals[arg] for arg in arginfo.args if arg in arginfo.locals
            }
            stack.append((short_filename, line_number, function_name, args_dict, is_method))

        frame = frame.f_back

    # Print stack from oldest to newest (reverse order)
    if stack:
        console.print()
        module_level_count = 0
        function_depth = 0

        for i, (filename, line_num, func_name, args_dict, is_method) in enumerate(
            reversed(stack)
        ):
            # Adjust index to account for module level entries
            if func_name is None:
                # Module level call
                location = f"[cyan]{filename}[/cyan]:[yellow]{line_num}[/yellow]"
                console.print(location)
                module_level_count += 1
            else:
                # Function call
                depth = i - module_level_count
                function_depth = depth + 1

                # Build prefix with proper continuation lines
                prefix = "   " * (depth + 1)

                location = f"[cyan]{filename}[/cyan]:[yellow]{line_num}[/yellow]"

                # Format function with arguments
                if args_dict:
                    args_str_parts = []
                    for j, (k, v) in enumerate(args_dict.items()):
                        if is_method and j == 0:
                            args_str_parts.append(f"[green]{k}[/green]")
                        else:
                            args_str_parts.append(
                                f"[green]{k}[/green]={_format_value(v)}"
                            )
                    args_str = ", ".join(args_str_parts)
                    function = f"[magenta]{func_name}[/magenta]({args_str})"
                else:
                    function = f"[magenta]{func_name}()[/magenta]"

                console.print(f"{prefix}{location} {function}")

        # Return the depth for consistent variable indentation
        return function_depth
    else:
        # No function context, just print a simple header
        filename = caller_frame.f_code.co_filename
        line_number = caller_frame.f_lineno
        short_filename = Path(filename).name
        location = f"[cyan]{short_filename}[/cyan]:[yellow]{line_number}[/yellow]"
        console.print()
        console.print(location)
        return 0  # No depth


def _print_variable(name: str, type_name: str, value: Any, depth: int = 0):
    """Print a single variable with color formatting."""
    # Match the call graph indentation: 2 spaces per depth level, then a tab
    indent = "   " * (depth + 1)
    prefix = f"{indent}[green]{name}[/green]: [blue]{type_name}[/blue] = "
    console.print(prefix, end="")
    console.print(value)


def _format_value(value: Any) -> str:
    """
    Format a value for display, with intelligent truncation.

    Args:
            value: The value to format

    Returns:
            Formatted string representation of the value
    """
    from rich.pretty import pretty_repr

    return pretty_repr(value, max_length=1000, max_string=100)


def dprint_vars(**variables):
    """
    Print variables with explicit names (useful when expression extraction fails).

    Example:
            x = 42
            y = "hello"
            dprint_vars(x=x, y=y)
    """
    dprint(**variables)


def dprint_frame(levels_up: int = 1, hide_wrappers=True):
    """
    Print information about the call stack.

    Args:
            levels_up: Number of frames to go up the stack (default: 1)

    Example:
            def my_function():
                    dprint_frame()
    """
    frame = inspect.currentframe()
    if frame is None:
        print("dprint_frame: Unable to get frame information")
        return

    try:
        target_frame = frame
        for _ in range(levels_up):
            target_frame = target_frame.f_back
            if target_frame is None:
                print("dprint_frame: Not enough frames in stack")
                return

        # Print backtrace
        depth = _print_backtrace(target_frame, hide_wrappers=hide_wrappers)

        for var_name, var_value in target_frame.f_locals.items():
            if not var_name.startswith("_"):
                type_name = type(var_value).__name__
                _print_variable(var_name, type_name, var_value, depth)

    finally:
        del frame
        if "target_frame" in locals():
            del target_frame


# Example usage and tests
if __name__ == "__main__":
    pass
