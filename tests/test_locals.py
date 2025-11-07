import pytest
from shi import _locals as _


def test_locals():
    a = 1
    b = "hello"

    def foo(**kwargs):
        return kwargs

    result = foo(**_)

    result_copy = result.copy()

    # Clean up locals for the test
    del a, b, foo, result

    # We need to check the result against the state of locals() before we cleaned it up.
    # The `_` object should capture `a`, `b`, and `foo`.
    # It might also capture other things depending on the execution context, so we check for a subset.
    assert result_copy.get("a") == 1
    assert result_copy.get("b") == "hello"
    assert "foo" in result_copy
