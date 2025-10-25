from shi.arrg import arrg

# Global variables
a = 100
b = 200


@arrg
def my_function(a, b, c=300):
    """
    An example function using the @arrg decorator.
    a will try to resolve from various scopes.
    b will try to resolve from various scopes.
    c has a default value.
    """
    return f"a: {a}, b: {b}, c: {c}"


@arrg
def nested_function(x, y):
    """
    A nested function to demonstrate parent @arrg context.
    """
    return f"x: {x}, y: {y}"


@arrg
def caller_function(x=10, y=20):
    # These local variables should be available to nested_function
    print(f"Calling nested_function from caller_function with x={x}, y={y}")
    return nested_function()


if __name__ == "__main__":
    print("--- Example 1: Basic usage with global variables ---")
    # a and b should resolve to global a and b
    print(f"Result: {my_function()}")  # Expected: a: 100, b: 200, c: 300

    print("\n--- Example 2: Overriding with keyword arguments ---")
    # a and b are overridden by kwargs
    print(f"Result: {my_function(a=1, b=2)}")  # Expected: a: 1, b: 2, c: 300

    print("\n--- Example 3: Overriding with positional arguments ---")
    # a and b are overridden by positional args
    print(f"Result: {my_function(10, 20)}")  # Expected: a: 10, b: 20, c: 300

    print("\n--- Example 4: Using default parameter value ---")
    # c uses its default value
    print(f"Result: {my_function(a=1, b=2)}")  # Expected: a: 1, b: 2, c: 300

    print("\n--- Example 5: Nested @arrg functions and caller's local scope ---")
    # nested_function should pick up x and y from caller_function's scope
    print(f"Result: {caller_function()}")  # Expected: x: 10, y: 20

    print("\n--- Example 6: Nested @arrg functions with overridden caller locals ---")
    # y is overridden when calling caller_function
    print(f"Result: {caller_function(y=2000)}")  # Expected: x: 10, y: 2000

    print(
        "\n--- Example 7: Extra keyword arguments (ignored by the function itself) ---"
    )
    print(
        f"Result: {my_function(a=1, b=2, extra_arg=999)}"
    )  # Expected: a: 1, b: 2, c: 300
