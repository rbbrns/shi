#!/usr/bin/env python3

import functools
import inspect
import types
from . import dprint
from dataclasses import dataclass, field


def is_private(key: str) -> bool:
    """
    Check if a key is considered private (starts with an underscore).
    """
    return key.startswith("_")


def is_wrapper_frame(frame: types.FrameType) -> bool:
    """
    Determine if a frame corresponds to a known function wrapper.
    Currently checks for the presence of '__wrapped__' in the function object.
    """
    if not frame:
        return False
    frame_locals = frame.f_locals
    if "__wrapped__" in frame_locals:
        return True
    return False


def filter_privates(d: dict) -> dict:
    """
    Return a new dictionary excluding keys that start with an underscore.
    """
    return {k: v for k, v in d.items() if not is_private(k)}


@dataclass
class ArrgContext:
    """
    Data class to hold the context for arrg resolution.
    """

    extra_kwargs: dict = field(default_factory=dict)


def get_arrg_context():
    """
    Retrieve the nearest __arrg_context__ from the call stack.
    """
    frame = inspect.currentframe()
    while frame:
        if "__arrg_context__" in frame.f_locals:
            return frame.f_locals["__arrg_context__"]
        frame = frame.f_back
    return ArrgContext()


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


def get_frames(depth=1):
    """
    Retrieve a list of frames up to the specified depth.
    """
    frames = []
    frame = get_frame(depth=2)
    while frame and len(frames) < depth:
        if not is_wrapper_frame(frame):
            frames.append(frame)
        frame = frame.f_back
    return frames


def get_locals(depth=1):
    """
    Retrieve a merged dictionary of local variables from the call stack.
    Later frames override earlier ones. Private variables and function wrappers
    are ignored.
    """
    frames = get_frames(depth + 1)[1:]  # Skip our own frame
    all_locals = {}
    for frame in reversed(frames):
        all_locals.update(filter_privates(frame.f_locals))
    return all_locals


def get_globals(depth=1):
    """
    Retrieve a dictionary of global variables from the call stack.
    Private variables are ignored.
    """
    frames = get_frames(depth + 1)[1:]  # Skip our own frame
    all_globals = {}
    for frame in reversed(frames):
        all_globals.update(filter_privates(frame.f_globals))
    return all_globals


def arrg(func_or_class):
    """
    Decorator that automatically resolves function arguments from caller scope.
    It effectively flattens the variable resolution scope. Private variables
    (those starting with an '_') are ignored.

    Argument Resolution Priority (in order):
    1. Explicitly passed positional arguments
    2. Explicitly passed keyword argument
    3. Parent Extra Arguments
    4. Function's default parameter values
    5. Call Stack Local Scope
    6. Function's global scope
    7. Call Stack Global Scope
    8. None (if not found anywhere)
    __arrg_context__ stores the full calling context available to nested @arrg functions.
    """
    if inspect.isclass(func_or_class):
        for name, method in inspect.getmembers(func_or_class, inspect.isfunction):
            if not name.startswith("_"):
                setattr(func_or_class, name, arrg(method))
        return func_or_class

    func = func_or_class
    sig = inspect.signature(func)
    arrg_has_kwarg_var = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    func_globals = filter_privates(func.__globals__)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        inspect.currentframe().f_locals["__wrapped__"] = func
        caller_locals = get_locals(10)
        caller_globals = get_globals(10)
        parent_context = get_arrg_context()

        kwargs = parent_context.extra_kwargs | kwargs

        resolved_args = {}
        extra_kwargs = {}

        # Check for too many positional arguments
        max_pos_args = sum(
            1
            for p in sig.parameters.values()
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        )
        if len(args) > max_pos_args:
            raise TypeError(
                f"{func.__name__}() takes at most {max_pos_args} positional "
                f"argument(s) but {len(args)} were given."
            )

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

            # Step 3: Parent Extra Arguments
            if param_name in parent_context.extra_kwargs:
                resolved_args[param_name] = parent_context.extra_kwargs[param_name]
                continue
            # Step 4: Function's default parameter value
            if param.default != inspect.Parameter.empty:
                resolved_args[param_name] = param.default
            # Step 5: Call Stack Local Scope
            elif param_name in caller_locals:
                resolved_args[param_name] = caller_locals[param_name]
            # Step 6: Function's global scope
            elif param_name in func_globals:
                resolved_args[param_name] = func_globals[param_name]
            # Step 7: Call Stack Global Scope
            elif param_name in caller_globals:
                resolved_args[param_name] = caller_globals[param_name]
            # Step 8: If not found anywhere, default to None
            else:
                resolved_args[param_name] = None

        # Separate resolved_args into positional and keyword arguments for sig.bind
        pos_only_values = []
        for param in sig.parameters.values():
            if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                pos_only_values.append(resolved_args[param.name])
                del resolved_args[param.name]

        __arrg_context__ = ArrgContext(extra_kwargs=extra_kwargs)

        # Call the function using the BoundArguments object
        if arrg_has_kwarg_var:
            resolved_args.update(extra_kwargs)
        return func(*pos_only_values, **resolved_args)

    return wrapper


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

    def test_extra_kwargs_fall_through(self):
        a1 = 1
        b1 = 2

        @arrg
        def foo3(a3, b3, c3=300, **kwargs):
            return a3, b3, c3, *kwargs.values()

        @arrg
        def foo2(a2, b2, c2=30):
            return a2, b2, c2, *foo3()

        @arrg
        def foo1(a1, b1, c1=3):
            return a1, b1, c1, *foo2()

        self.assertEqual(foo1(), (1, 2, 3, None, None, 30, None, None, 300))
        self.assertEqual(foo1(a3=10, b3=20), (1, 2, 3, None, None, 30, 10, 20, 300))
        self.assertEqual(
            foo1(x=-1, y=-2), (1, 2, 3, None, None, 30, None, None, 300, -1, -2)
        )
        self.assertEqual(
            foo1(c1=-3, c2=-30, c3=-300), (1, 2, -3, None, None, -30, None, None, -300)
        )
        self.assertEqual(
            foo1(a1=1, b1=2, c1=3, a3=100, b3=200, c3=300, a2=10, b2=20, c2=30),
            (1, 2, 3, 10, 20, 30, 100, 200, 300),
        )

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

    def test_class_decorator(self):
        a = 1
        b = 2

        @arrg
        class MyClass:
            def method1(self, a, b):
                return a, b

            def method2(self, a, b):
                return a * 2, b * 2

            def _private_method(self, a, b):
                return a, b

        instance = MyClass()
        self.assertEqual(instance.method1(), (1, 2))
        self.assertEqual(instance.method1(a=10), (10, 2))
        self.assertEqual(instance.method2(), (2, 4))

        # Check that private methods are not wrapped
        with self.assertRaises(TypeError):
            instance._private_method()

    def test_too_many_positional_args(self):
        @arrg
        def foo(a, b):
            return a, b

        with self.assertRaises(TypeError) as context:
            foo(1, 2, 3)
        self.assertIn(
            "takes at most 2 positional argument(s) but 3 were given",
            str(context.exception),
        )


if __name__ == "__main__":
    unittest.main()
