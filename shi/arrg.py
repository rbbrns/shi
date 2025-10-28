import functools
import inspect
from dprint import dprint


def is_private(key: str) -> bool:
    """
    Check if a key is considered private (starts with an underscore).
    """
    return key.startswith("_")


def filter_privates(d: dict) -> dict:
    """
    Return a new dictionary excluding keys that start with an underscore.
    """
    return {k: v for k, v in d.items() if not is_private(k)}


def get_arrg_context():
    """
    Retrieve the nearest __arrg_context__ from the call stack.
    """
    frame = inspect.currentframe()
    while frame:
        if "__arrg_context__" in frame.f_locals:
            return frame.f_locals["__arrg_context__"]
        frame = frame.f_back
    return {}


def get_frame(depth=1):
    """
    Retrieve the immediate caller's frame.
    """
    frame = inspect.currentframe()
    for _ in range(depth):
        if frame:
            frame = frame.f_back
        else:
            return None
    return frame


def get_locals(depth=1):
    """
    Retrieve the immediate caller's local variables.
    """
    frame = get_frame(depth + 1)
    return frame.f_locals if frame else {}


def get_globals(depth=1):
    """
    Retrieve the immediate caller's global variables.
    """
    frame = get_frame(depth + 1)
    return frame.f_globals if frame else {}


def arrg(func):
    """
    Decorator that automatically resolves function arguments from various scopes.

    Argument Resolution Priority (in order):
    1. Explicitly passed positional arguments
    2. Explicitly passed keyword argument
    3. Function's default parameter values
    4. Function's global scope
    5. Immediate caller's local scope
    6. Immediate caller's global scope
    7. Parent @arrg context (from __arrg_context__ up the stack)
    8. None (if not found anywhere)

    __arrg_context__ stores: parent_context + caller_locals + caller_globals + bound_args + extra_kwargs
    This makes the full calling context available to nested @arrg functions.
    """
    sig = inspect.signature(func)
    arrg_has_kwarg_var = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    func_globals = filter_privates(func.__globals__)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        caller_locals = filter_privates(get_locals(2))
        caller_globals = filter_privates(get_globals(2))
        parent_context = get_arrg_context()

        resolved_args = {}
        extra_kwargs = {}

        # Apply explicitly passed positional arguments
        for param, arg in zip(sig.parameters.values(), args):
            if param.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                resolved_args[param.name] = arg

        # Apply explicitly passed keyword arguments
        for key, value in kwargs.items():
            if key in resolved_args:
                continue  # Already set by positional args
            if key in sig.parameters:
                resolved_args[key] = value
            else:
                extra_kwargs[key] = value

        # Fill in missing arguments using arrg's resolution priority (Steps 4-7)
        for param_name, param in sig.parameters.items():
            if param_name in resolved_args:
                continue  # Already resolved
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                continue  # Skip *args
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                continue  # Skip **kwargs

            # Step 3: Function's default parameter value
            if param.default != inspect.Parameter.empty:
                resolved_args[param_name] = param.default
            # Step 4: Available in function's global scope (where function was defined)
            elif param_name in func_globals:
                resolved_args[param_name] = func_globals[param_name]
            # Step 5: Available in caller's local scope
            elif param_name in caller_locals:
                resolved_args[param_name] = caller_locals[param_name]
            # Step 6: Available in caller's global scope
            elif param_name in caller_globals:
                resolved_args[param_name] = caller_globals[param_name]
            # Step 7: Available in parent @arrg context
            elif param_name in parent_context:
                resolved_args[param_name] = parent_context[param_name]
            # Step 8: If not found anywhere, default to None
            else:
                resolved_args[param_name] = None

        # Separate resolved_args into positional and keyword arguments for sig.bind
        pos_only_values = []
        for param in sig.parameters.values():
            if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                pos_only_values.append(resolved_args[param.name])
                del resolved_args[param.name]

        # Create context for this call: parent_context + caller scopes + our args
        # Build in priority order (earlier items get overridden by later ones):
        # 1. Parent context (inherited from up the stack)
        # 2. Caller's globals
        # 3. Caller's locals (overrides globals)
        # 4. Our resolved_args (overrides caller's locals)
        # 5. Extra kwargs (overrides everything)
        __arrg_context__ = {
            **parent_context,
            **caller_globals,
            **caller_locals,
            **resolved_args,
            **extra_kwargs,
        }

        # Call the function using the BoundArguments object
        if arrg_has_kwarg_var:
            resolved_args.update(extra_kwargs)
        return func(*pos_only_values, **resolved_args)

    return wrapper


####### Unit tests for arrg ########

import unittest


class ArrgTest(unittest.TestCase):

    def test_arrg(self):
        a = 1
        b = 2

        @arrg
        def foo(a, b):
            return a, b

        # If a or b is not explicitly given, get the value from function global
        self.assertEqual(foo(), (1, 2))
        self.assertEqual(foo(a=10), (10, 2))
        self.assertEqual(foo(b=20), (1, 20))
        self.assertEqual(foo(10), (10, 2))

    def test_extra_kwargs(self):
        a = 1
        b = 2

        @arrg
        def foo(a, b):
            return a, b

        # Extra keywords args are accepted
        self.assertEqual(foo(x=1, y=2), (1, 2))

    def test_function_globals(self):
        a = 1
        b = 2

        @arrg
        def foo(a, b):
            return a, b

        self.assertEqual(foo(), (1, 2))
        a = 100
        self.assertEqual(foo(), (100, 2))

    def test_default_to_none(self):
        c = 3

        @arrg
        def foo(a, b, c):
            return a, b, c

        # Args without a global default will be None
        self.assertEqual(foo(), (None, None, 3))

        @arrg
        def foo(a, b=20):
            return a, b

        self.assertEqual(foo(), (None, 20))

        @arrg
        def foo(a, b):
            a = -1
            b = -2
            return a, b

        # Local scope always takes precedence
        self.assertEqual(foo(a=10), (-1, -2))

    def test_missing_args(self):
        a = -1
        b = -2

        @arrg
        def foo1(y):
            a = 10
            b = 20
            x = 100
            return foo2()

        @arrg
        def foo2(a, x, y):
            return a, b, x, y

        # arrgs not in function global scope or explicitly passed in
        # are pulled from caller's local scope
        self.assertEqual(foo1(), (10, -2, 100, None))
        self.assertEqual(foo1(y=200), (10, -2, 100, 200))

    def test_var_kwargs(self):
        @arrg
        def foo(a, b=1, **kwargs):
            return a, b, kwargs

        self.assertEqual(foo(10), (10, 1, {}))
        self.assertEqual(foo(10, x=1, y=2, b=20), (10, 20, {"x": 1, "y": 2}))

    def test_positional_only(self):
        a = 1
        b = 2

        @arrg
        def foo(a, /, b, *, c=3, **kwargs):
            return a, b, c, kwargs

        self.assertEqual(foo(), (1, 2, 3, {}))

    def test_dynamic_wrapper(self):
        def unwrapped_foo(a, b):
            return a, b

        wrapped_foo = arrg(unwrapped_foo)()


if __name__ == "__main__":
    unittest.main()
    print("All tests passed!")
