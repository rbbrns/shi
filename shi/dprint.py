"""
dprint - A debug print library with runtime reflection
Provides human-readable debugging output with variable names, types, and values.
"""

import inspect
import sys
from typing import Any
from pathlib import Path
from rich import pretty

try:
    from colorama import Fore, Style, init

    init(autoreset=True)
    HAS_COLOR = True
except ImportError:
    # Fallback if colorama is not available
    HAS_COLOR = False

    class Fore:
        CYAN = BLUE = GREEN = YELLOW = RED = MAGENTA = ""

    class Style:
        BRIGHT = RESET_ALL = ""


def dprint(*args, _depth=5, **kwargs):
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
    count = 0
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
        function_name = caller_frame.f_code.co_name

        # Get just the filename, not the full path
        short_filename = Path(filename).name

        # Print backtrace
        depth = _print_backtrace(caller_frame, _depth=_depth + 1)

        # If no arguments, dump all local variables from caller's scope
        if not args and not kwargs:
            for var_name, var_value in caller_frame.f_locals.items():
                if not var_name.startswith("_"):
                    type_name = type(var_value).__name__
                    value_repr = _format_value(var_value, depth=depth)
                    _print_variable(var_name, type_name, value_repr, depth)
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
                value_repr = _format_value(value, depth=depth)
                _print_variable(name, type_name, value_repr, depth)

        # Print keyword arguments
        for key, value in kwargs.items():
            type_name = type(value).__name__
            value_repr = _format_value(value, depth=depth)
            _print_variable(key, type_name, value_repr, depth)

    finally:
        # Clean up frame references to avoid reference cycles
        del frame
        if "caller_frame" in locals():
            del caller_frame


def _print_backtrace(caller_frame, _depth):
    """Print the call stack backtrace."""
    stack = []
    frame = caller_frame

    # Collect stack frames with their local variables
    while frame is not None and len(stack) < _depth:
        filename = frame.f_code.co_filename
        line_number = frame.f_lineno
        function_name = frame.f_code.co_name
        short_filename = Path(filename).name

        # Collect all frames including module level for context
        if function_name == "<module>":
            # For module level, just store basic info
            stack.append((short_filename, line_number, None, None))
        else:
            # Get function arguments (parameters)
            arginfo = inspect.getargvalues(frame)
            args_dict = {}

            # Collect argument names and values
            for arg in arginfo.args:
                if arg in arginfo.locals:
                    args_dict[arg] = arginfo.locals[arg]

            stack.append((short_filename, line_number, function_name, args_dict))

        frame = frame.f_back

    # Print stack from oldest to newest (reverse order)
    if stack:
        print()
        module_level_count = 0
        function_depth = 0

        # First pass: determine which levels will have more items after them
        function_indices = []
        for i, (filename, line_num, func_name, args_dict) in enumerate(reversed(stack)):
            if func_name is not None:
                function_indices.append(i)

        for i, (filename, line_num, func_name, args_dict) in enumerate(reversed(stack)):
            # Adjust index to account for module level entries
            if func_name is None:
                # Module level call
                location = f"{Fore.CYAN}{filename}{Style.RESET_ALL}:{Fore.YELLOW}{line_num}{Style.RESET_ALL}"
                print(f"{location}")
                module_level_count += 1
            else:
                # Function call
                depth = i - module_level_count
                function_depth = depth + 1
                is_last_function = i == function_indices[-1]

                # Build prefix with proper continuation lines
                prefix = "   " * (depth + 1)

                location = f"{Fore.CYAN}{filename}{Style.RESET_ALL}:{Fore.YELLOW}{line_num}{Style.RESET_ALL}"

                # Format function with arguments
                if args_dict:
                    args_str = ", ".join(
                        [
                            f"{Fore.GREEN}{k}{Style.RESET_ALL}={_format_value(v, depth=depth)}"
                            for k, v in args_dict.items()
                        ]
                    )
                    function = f"{Fore.MAGENTA}{func_name}{Style.RESET_ALL}({args_str})"
                else:
                    function = f"{Fore.MAGENTA}{func_name}(){Style.RESET_ALL}"

                print(f"{prefix}{location} {function}")

        # Return the depth for consistent variable indentation
        return function_depth
    else:
        # No function context, just print a simple header
        filename = caller_frame.f_code.co_filename
        line_number = caller_frame.f_lineno
        short_filename = Path(filename).name
        location = f"{Fore.CYAN}{short_filename}{Style.RESET_ALL}:{Fore.YELLOW}{line_number}{Style.RESET_ALL}"
        print(f"\n{location}")
        return 0  # No depth


def _print_variable(name: str, type_name: str, value_repr: str, depth: int = 0):
    """Print a single variable with color formatting."""
    # Match the call graph indentation: 2 spaces per depth level, then a tab
    indent = "   " * (depth + 1)
    print(
        f"{indent}{Fore.GREEN}{name}{Style.RESET_ALL}: {Fore.BLUE}{type_name}{Style.RESET_ALL} = {value_repr}"
    )


def _format_value(value: Any, depth: int = 0, max_length: int = 100) -> str:
    """
    Format a value for display, with intelligent truncation.

    Args:
            value: The value to format

    Returns:
            Formatted string representation of the value
    """
    return pretty.pretty_repr(value, indent_size=3 * depth, max_length=max_length)

    # Handle collections
    if isinstance(value, (list, tuple, set, frozenset)):
        if len(value) == 0:
            return repr(value)
        repr_val = repr(value)
        if len(repr_val) > max_length:
            type_name = type(value).__name__
            return f"{type_name}([...{len(value)} items...])"
        return repr_val

    # Handle dictionaries
    if isinstance(value, dict):
        if len(value) == 0:
            return "{}"
        repr_val = repr(value)
        if len(repr_val) > max_length:
            return f"{{...{len(value)} items...}}"
        return repr_val

    # Handle None
    if value is None:
        return f"{Fore.RED}None{Style.RESET_ALL}"

    # Handle booleans
    if isinstance(value, bool):
        color = Fore.GREEN if value else Fore.RED
        return f"{color}{value}{Style.RESET_ALL}"

    # Default representation
    repr_val = repr(value)
    if len(repr_val) > max_length:
        return repr_val[: max_length - 3] + "..."
    return repr_val


def dprint_vars(**variables):
    """
    Print variables with explicit names (useful when expression extraction fails).

    Example:
            x = 42
            y = "hello"
            dprint_vars(x=x, y=y)
    """
    dprint(**variables)


def dprint_frame(levels_up: int = 1):
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

        filename = target_frame.f_code.co_filename
        line_number = target_frame.f_lineno
        function_name = target_frame.f_code.co_name
        short_filename = Path(filename).name

        # Print backtrace
        depth = _print_backtrace(target_frame, _depth=levels_up + 1)

        for var_name, var_value in target_frame.f_locals.items():
            if not var_name.startswith("_"):
                type_name = type(var_value).__name__
                value_repr = _format_value(var_value, depth=depth)
                _print_variable(var_name, type_name, value_repr, depth)

    finally:
        del frame
        if "target_frame" in locals():
            del target_frame


# Example usage and tests
if __name__ == "__main__":
    print("=" * 60)
    print(f"{Style.BRIGHT}dprint Library Demo{Style.RESET_ALL}")
    print("=" * 60)

    # Basic usage
    x = 42
    dprint(x)

    # Multiple variables
    y = "hello world"
    z = [1, 2, 3, 4, 5]
    dprint(x, y, z)

    # Complex objects
    data = {"name": "Alice", "age": 30, "city": "New York"}
    dprint(data)

    # Boolean and None
    flag = True
    empty = None
    dprint(flag, empty)

    # Expressions
    dprint(x + 10)
    dprint(len(y))

    # Keyword arguments
    dprint(value1=x, value2=y, computed=x * 2)

    # Function context with nested calls
    def outer_function(x):
        def middle_function(y):
            def inner_function(z):
                result = x + y + z
                dprint(result)
                # Dump all local variables with no arguments
                dprint()
                return result

            return inner_function(30)

        return middle_function(20)

    outer_function(10)

    # Another nested example
    def process_data(items):
        def validate(item):
            is_valid = item > 0
            dprint(item, is_valid)
            return is_valid

        def filter_items():
            valid_items = [item for item in items if validate(item)]
            dprint(valid_items)
            return valid_items

        return filter_items()

    test_items = [1, -2, 3, -4, 5]
    dprint(test_items)
    result = process_data(test_items)

    # Long strings and collections
    long_string = "a" * 150
    dprint(long_string)

    big_list = list(range(100))
    dprint(big_list)
