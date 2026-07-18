"""
Exposes the `locals()` of the calling frame for keyword argument expansion.

Usage:
    from shi.experimental import _locals as _

    def foo(**kwargs):
        return kwargs

    a = 1
    b = 2

    foo(**_) # -> {'a': 1, 'b': 2}
"""

import sys
import inspect


class _LocalsModule(object):
    """
    A meta class that allows for something like:

    from shi.experimental import _locals as _

    def foo(**kwargs):
       return kwargs

    a = 1
    b = 2

    foo(**_) # -> {'a': 1, 'b': 2}
    """

    def _get_locals(self):
        frame = inspect.currentframe()
        while frame:
            if frame.f_globals.get("__name__") != __name__:
                return frame.f_locals
            frame = frame.f_back
        return {}

    def __iter__(self):
        return iter(self._get_locals())

    def __getitem__(self, key):
        return self._get_locals()[key]

    def keys(self):
        return self._get_locals().keys()


# To allow `from shi import _locals as _`, we replace the module with an instance.
# This is a bit of a hack, but it's what allows the desired syntax.
sys.modules[__name__] = _LocalsModule()
