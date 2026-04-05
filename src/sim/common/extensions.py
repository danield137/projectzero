from __future__ import annotations

import sys
from types import MappingProxyType
from typing import Any


def debug_enabled() -> bool:
    try:
        if sys.gettrace() is not None:
            return True
    except AttributeError:
        pass

    try:
        if sys.monitoring.get_tool(sys.monitoring.DEBUGGER_ID) is not None:  # type: ignore
            return True
    except AttributeError:
        pass

    return False


def equals(a: Any, b: Any) -> bool:
    """
    Compare any two variables for equality.
    For complex objects (classes, lists, dicts), this will do a deep comparison by default.
    """
    if a is b:
        return True
    if isinstance(a, (int, str, bool)):
        return a == b
    if isinstance(a, float):
        # almost equal. floats are tricky to compare due to precision issues.
        return isinstance(b, float) and abs(a - b) < 1e-6
    if isinstance(a, list):
        if not isinstance(b, list) or len(a) != len(b):
            return False
        return all(equals(a[i], b[i]) for i in range(len(a)))
    if isinstance(a, set):
        return isinstance(b, set) and a == b
    if isinstance(a, dict):
        if not isinstance(b, dict) or len(a) != len(b):
            return False
        for key in a:
            if key not in b:
                return False
            if not equals(a[key], b[key]):
                return False
        return True
    # For classes, we will compare all attributes
    if hasattr(a, "__dict__") and hasattr(b, "__dict__"):
        return equals(a.__dict__, b.__dict__)

    return a == b


def deep_freeze(obj: Any) -> Any:
    """
    Recursively freeze an object by converting mutable collections into immutable ones.

    - dicts become MappingProxyType (read-only mapping)
    - lists become tuples
    - sets become frozensets
    - tuples are re-created with frozen elements
    - primitives (int, float, str, bool, None) are returned as-is
    - custom objects are converted to their __dict__ representation
    """
    if isinstance(obj, dict):
        # Create a read-only view of the dictionary,
        # recursively freezing each value.
        return MappingProxyType({k: deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        # Convert list to a tuple of frozen items.
        return tuple(deep_freeze(item) for item in obj)
    if isinstance(obj, set):
        # Convert set to a frozenset of frozen items.
        return frozenset(deep_freeze(item) for item in obj)
    if isinstance(obj, tuple):
        # Create a new tuple with each element frozen.
        return tuple(deep_freeze(item) for item in obj)
    if isinstance(obj, (int, float, str, bool, type(None))):
        # Primitives are immutable by definition.
        return obj

    # For custom objects, convert to a dictionary representation.
    return deep_freeze(vars(obj))
