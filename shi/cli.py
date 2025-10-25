import inspect
import sys
from typing import Any, Callable, Dict, List, Tuple
from pathlib import Path
# import shlex # Removed shlex

# Dictionary to store (wrapped_func, original_func) tuples

_cli_commands: Dict[str, Tuple[Callable, Callable]] = {}



def _convert_value(value_str: str, target_type: Any) -> Any:

    """

    Attempts to convert a string value to a target type.

    """

    if target_type == inspect.Parameter.empty or target_type is str:

        return value_str

    try:

        if target_type is bool:

            return value_str.lower() in ('true', '1', 't', 'y', 'yes')

        return target_type(value_str)

    except ValueError:

        # Fallback to string if conversion fails

        return value_str



def _parse_cli_args(func: Callable, cli_args_raw: List[str]) -> Dict[str, Any]:

    """

    Parses command-line arguments for a given function.

    Handles basic type conversion, and var=val format.

    """

    sig = inspect.signature(func)

    parsed_args = {}

    

    positional_params = [p for p in sig.parameters.values() if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD and p.default == inspect.Parameter.empty]

    

    cli_args_iter = iter(cli_args_raw) # Iterate directly over raw args from sys.argv

    

    pos_param_idx = 0

    

    for arg_str in cli_args_iter:

        # Check for var=val format (no leading dashes)

        if "=" in arg_str and not arg_str.startswith("--"):

            key, value_str = arg_str.split("=", 1)

            # Find the parameter in the function signature

            if key in sig.parameters:

                param = sig.parameters[key]

                parsed_args[key] = _convert_value(value_str, param.annotation)

            else:

                # Store as extra kwargs if not a defined parameter

                parsed_args[key] = value_str # Keep as string for now

        elif arg_str.startswith("--"):

            # Keyword argument: --key value or --key=value

            key_value_pair = arg_str[2:].split("=", 1)

            key = key_value_pair[0]

            

            if len(key_value_pair) == 2:

                value_str = key_value_pair[1]

            else:

                # Assume value is the next argument if not part of --key=value

                try:

                    value_str = next(cli_args_iter)

                except StopIteration:

                    print(f"Error: Missing value for argument --{key}")

                    sys.exit(1)

            

            # Find the parameter in the function signature

            if key in sig.parameters:

                param = sig.parameters[key]

                parsed_args[key] = _convert_value(value_str, param.annotation)

            else:

                # Store as extra kwargs if not a defined parameter

                parsed_args[key] = value_str # Keep as string for now

        else:

            # Positional argument

            if pos_param_idx < len(positional_params):

                param = positional_params[pos_param_idx]

                parsed_args[param.name] = _convert_value(arg_str, param.annotation)

                pos_param_idx += 1

            else:

                print(f"Warning: Unmatched positional argument '{arg_str}' for function '{func.__name__}'")



    return parsed_args



def cli(func: Callable) -> Callable:

    """

    Decorator to register a function as a CLI command.

    Assumes func might be wrapped by other decorators (like @arrg).

    """

    original_func = func.__wrapped__ if hasattr(func, '__wrapped__') else func

    _cli_commands[original_func.__name__] = (func, original_func)

    return func



def run_cli():

    """

    Dispatches CLI commands based on sys.argv.

    """

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

    

    # Parse arguments using the original function's signature

    parsed_args = _parse_cli_args(original_func, sys.argv[2:])

    

    # Start with parsed_args (which includes CLI-provided values and extra kwargs)

    final_args = {**parsed_args}



    # Add default values for parameters not provided by CLI, but only if they are not already in final_args

    for name, parameter in inspect.signature(original_func).parameters.items(): # Use original_func's signature

        if name not in final_args and parameter.default != inspect.Parameter.empty:

            final_args[name] = parameter.default

        # No explicit check for missing required arguments here. Python's TypeError will handle it.



    try:

        wrapped_func(**final_args) # Call the wrapped_func (which is the @arrg wrapper)

    except TypeError as e:

        print(f"Error calling command '{command_name}': {e}")

        print(f"Usage: {command_name}{inspect.signature(original_func)}") # Use original_func's signature for usage

        sys.exit(1)





if __name__ == "__main__":

    @cli

    def greet(name: str, greeting: str = "Hello", repeat: int = 1):

        """

        Greets the given name with a specified greeting, repeated multiple times.

        """

        for _ in range(repeat):

            print(f"{greeting}, {name}!")



    @cli

    def add(a: int, b: int):

        """

        Adds two numbers.

        """

        result = a + b

        print(f"The sum of {a} and {b} is {result}")

        return result



    @cli

    def echo(message: str, loud: bool = False):

        """

        Echoes a message, optionally loudly.

        """

        if loud:

            print(message.upper())

        else:

            print(message)



    run_cli()
