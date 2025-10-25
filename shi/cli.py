import inspect
import sys
from typing import Any, Callable, Dict, List, Tuple
from pathlib import Path

# Dictionary to store functions decorated with @cli
_cli_commands: Dict[str, Callable] = {}

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

def _parse_cli_args(func: Callable, cli_args: List[str]) -> Dict[str, Any]:
    """
    Parses command-line arguments for a given function, treating spaces as separators.
    Handles basic type conversion and quoted strings.
    """
    sig = inspect.signature(func)
    parsed_args = {}
    
    positional_params = [p for p in sig.parameters.values() if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD and p.default == inspect.Parameter.empty]
    keyword_params = [p for p in sig.parameters.values() if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD and p.default != inspect.Parameter.empty]

    i = 0
    pos_param_idx = 0
    
    while i < len(cli_args):
        arg_str = cli_args[i]
        
        # Handle quoted strings
        if arg_str.startswith('"') or arg_str.startswith("'"):
            quote_char = arg_str[0]
            end_quote_index = -1
            
            # Find the matching end quote
            for j in range(i, len(cli_args)):
                if cli_args[j].endswith(quote_char) and (j > i or len(cli_args[j]) > 1):
                    end_quote_index = j
                    break
            
            if end_quote_index != -1:
                full_arg = " ".join(cli_args[i : end_quote_index + 1])
                value_str = full_arg[1:-1] # Remove quotes
                i = end_quote_index + 1
            else:
                # Unmatched quote, treat as a regular string
                value_str = arg_str
                i += 1
        elif arg_str.startswith("--"):
            # Keyword argument: --key value or --key=value
            key_value_pair = arg_str[2:].split("=", 1)
            key = key_value_pair[0]
            
            if len(key_value_pair) == 2:
                value_str = key_value_pair[1]
            else:
                # Assume value is the next argument if not part of --key=value
                i += 1
                if i < len(cli_args):
                    value_str = cli_args[i]
                else:
                    print(f"Error: Missing value for argument --{key}")
                    sys.exit(1)
            
            # Find the parameter in the function signature
            if key in sig.parameters:
                param = sig.parameters[key]
                parsed_args[key] = _convert_value(value_str, param.annotation)
            else:
                # Store as extra kwargs if not a defined parameter
                parsed_args[key] = value_str # Keep as string for now
            i += 1
            continue # Continue to next cli_arg
        else:
            value_str = arg_str
            i += 1
        
        # Assign to positional parameters
        if pos_param_idx < len(positional_params):
            param = positional_params[pos_param_idx]
            parsed_args[param.name] = _convert_value(value_str, param.annotation)
            pos_param_idx += 1
        else:
            # Try to assign to keyword-only parameters if they haven't been set yet
            # This handles cases where positional args run out, but there are still CLI args
            # that might match keyword-only params without -- prefix.
            # This is a heuristic and might need refinement for complex cases.
            found_kw_param = False
            for kw_param in keyword_params:
                if kw_param.name not in parsed_args:
                    parsed_args[kw_param.name] = _convert_value(value_str, kw_param.annotation)
                    found_kw_param = True
                    break
            if not found_kw_param:
                print(f"Warning: Unmatched argument '{value_str}' for function '{func.__name__}'")

    return parsed_args

def cli(func: Callable) -> Callable:
    """
    Decorator to register a function as a CLI command.
    """
    _cli_commands[func.__name__] = func
    return func

def run_cli():
    """
    Dispatches CLI commands based on sys.argv.
    """
    if len(sys.argv) < 2:
        print("Usage: python cli.py <command> [args...]")
        print("Available commands:")
        for cmd_name, cmd_func in _cli_commands.items():
            sig = inspect.signature(cmd_func)
            print(f"  {cmd_name}{sig}")
        sys.exit(1)

    command_name = sys.argv[1]
    if command_name not in _cli_commands:
        print(f"Error: Unknown command '{command_name}'")
        print("Available commands:", ", ".join(_cli_commands.keys()))
        sys.exit(1)

    target_func = _cli_commands[command_name]
    # Parse arguments starting from sys.argv[2]
    parsed_args = _parse_cli_args(target_func, sys.argv[2:])
    
    # Get default values for parameters not provided by CLI
    final_args = {}
    for name, parameter in inspect.signature(target_func).parameters.items():
        if name in parsed_args:
            final_args[name] = parsed_args[name]
        elif parameter.default != inspect.Parameter.empty:
            final_args[name] = parameter.default
        elif parameter.kind == inspect.Parameter.VAR_POSITIONAL or parameter.kind == inspect.Parameter.VAR_KEYWORD:
            # Handle *args and **kwargs if necessary, for now skip
            pass
        else:
            # If a required parameter is missing and has no default
            if parameter.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD and parameter.default == inspect.Parameter.empty:
                print(f"Error: Missing required argument '{name}' for command '{command_name}'")
                sys.exit(1)

    try:
        target_func(**final_args)
    except TypeError as e:
        print(f"Error calling command '{command_name}': {e}")
        print(f"Usage: {command_name}{inspect.signature(target_func)}")
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
