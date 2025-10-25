import functools
import inspect

def arrg(func):
    """
    Decorator that automatically resolves function arguments from various scopes.
    
    Argument Resolution Priority (in order):
    1. Explicitly passed positional arguments
    2. Explicitly passed keyword arguments
    3. Function's default parameter values (e.g., def foo(b=20))
    4. Function's own global scope (where function was defined)
    5. Parent @arrg context (from __arrg_context__ up the stack)
    6. Immediate caller's local scope
    7. Immediate caller's global scope
    8. None (if not found anywhere)
    
    __arrg_context__ stores: parent_context + caller_locals + caller_globals + bound_args + extra_kwargs
    This makes the full calling context available to nested @arrg functions.
    """
    sig = inspect.signature(func)
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Search up the stack for __arrg_context__
        frame = inspect.currentframe()
        parent_context = {}
        
        # Get immediate caller's frame first
        caller_frame = frame.f_back
        
        # Walk up the stack looking for __arrg_context__
        current_frame = frame.f_back
        while current_frame:
            if '__arrg_context__' in current_frame.f_locals:
                parent_context = current_frame.f_locals['__arrg_context__']
                break
            current_frame = current_frame.f_back
        
        # Always get immediate caller's locals and globals
        # These are fresh and may contain variables defined in the caller's body
        caller_locals = caller_frame.f_locals if caller_frame else {}
        caller_globals = caller_frame.f_globals if caller_frame else {}
        
        # Build the final arguments
        bound_args = {}
        param_names = list(sig.parameters.keys())
        
        # Step 1: Handle positional arguments
        for i, arg in enumerate(args):
            if i < len(param_names):
                bound_args[param_names[i]] = arg
        
        # Step 2-8: Handle each parameter with priority lookup
        for param_name, param in sig.parameters.items():
            if param_name in bound_args:
                # Already set by positional arg
                continue
            
            # Step 2: Explicitly passed as keyword arg
            if param_name in kwargs:
                bound_args[param_name] = kwargs[param_name]
            # Step 3: Has an explicit default value
            elif param.default != inspect.Parameter.empty:
                bound_args[param_name] = param.default
            # Step 4: Available in function's global scope
            elif param_name in func.__globals__:
                bound_args[param_name] = func.__globals__[param_name]
            # Step 5: Available in parent @arrg context (from stack)
            elif param_name in parent_context:
                bound_args[param_name] = parent_context[param_name]
            # Step 6: Available in caller's local scope
            elif param_name in caller_locals:
                bound_args[param_name] = caller_locals[param_name]
            # Step 7: Available in caller's global scope
            elif param_name in caller_globals:
                bound_args[param_name] = caller_globals[param_name]
            # Step 8: Not found anywhere, set to None
            else:
                bound_args[param_name] = None
        
        # Collect extra keyword arguments that aren't parameters
        extra_kwargs = {k: v for k, v in kwargs.items() if k not in sig.parameters}
        
        # Create context for this call: parent_context + caller scopes + our args
        # Build in priority order (earlier items get overridden by later ones):
        # 1. Parent context (inherited from up the stack)
        # 2. Caller's globals
        # 3. Caller's locals (overrides globals)
        # 4. Our bound args (overrides caller's locals)
        # 5. Extra kwargs (overrides everything)
        __arrg_context__ = {**parent_context, **caller_globals, **caller_locals, **bound_args, **extra_kwargs}
        
        # Call the function - nested @arrg calls will find __arrg_context__ in our frame
        return func(**bound_args)
    
    return wrapper


# Test cases
if __name__ == "__main__":
    a = 1
    b = 2

    @arrg
    def foo(a, b):
        return a, b

    # If a or b is not explicitly given, get the value from function global
    assert foo() == (1, 2)
    assert foo(a=10) == (10, 2)
    assert foo(b=20) == (1, 20)
    assert foo(10) == (10, 2)

    # Extra keywords args are accepted
    assert foo(x=1) == (1, 2)

    # Changing function globals will affect function defaults
    a = 100
    assert foo() == (100, 2)
    a = 1

    @arrg
    def foo(a, b, c):
        return a, b, c

    # Args without a global default will be None
    assert foo() == (1, 2, None)

    # Args with explicit defaults will override globals
    @arrg
    def foo(a, b=20):
        return a, b
    assert foo() == (1, 20)

    @arrg
    def foo(a, b):
        a = -1
        b = -2
        return a, b
    # Local scope always takes precedence
    assert foo(a=10) == (-1, -2)
    # Global values never change
    assert (a, b) == (1, 2)

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
    print("Testing foo1()...")
    result = foo1()
    print(f"Result: {result}")
    print(f"Expected: (1, 2, 100, None)")
    assert result == (1, 2, 100, None), f"Got {result}, expected (1, 2, 100, None)"
    
    print("Testing foo1(y=200)...")
    result = foo1(y=200)
    print(f"Result: {result}")
    print(f"Expected: (1, 2, 100, 200)")
    assert result == (1, 2, 100, 200), f"Got {result}, expected (1, 2, 100, 200)"

    print("All tests passed!")