from __future__ import annotations

from enum import IntEnum
from typing import TypeVar

from tigen.common.math import clamp

T = TypeVar("T", bound="MonotonicEnum")


class MonotonicEnum(IntEnum):
    """
    Base class for enums that represent monotonically increasing levels.
    Automatically provides float comparison methods based on enum values.
    """

    @classmethod
    def _bounds(cls) -> tuple[int, int]:
        """Get the minimum and maximum values defined in the enum."""
        values = [member.value for member in cls.__members__.values()]
        return min(values), max(values)

    @classmethod
    def from_float(cls: type[T], value: float) -> T:
        """Convert float value to enum instance with bounds checking."""
        (
            min_val,
            max_val,
        ) = cls._bounds()  # Enum values represent ranges where each value covers the interval (previous_value, current_value]
        val = clamp(int(value), min_val, max_val)
        return cls(val)

    def value_under(self, value: float) -> bool:
        """Check if value is less than or equal to level."""
        min_val, max_val = self._bounds()
        val = clamp(value // 1, min_val, max_val)
        return val <= self.value

    def value_over(self, value: float) -> bool:
        """Check if value is greater than or equal to level."""
        min_val, max_val = self._bounds()
        val = clamp(value // 1, min_val, max_val)
        return val >= self.value


class TriStateEnum(IntEnum):
    """
    Enum representing a tri-state value (e.g., ON, OFF, UNKNOWN).
    Provides methods to check if the state is ON or OFF.
    """

    TRUE = 1
    FALSE = 0
    UNKNOWN = -1

    @staticmethod
    def from_bool(value: bool) -> TriStateEnum:
        """Convert a boolean to TriStateEnum."""
        return TriStateEnum.TRUE if value else TriStateEnum.FALSE

    def is_true(self) -> bool:
        """Check if the state is ON."""
        return self == TriStateEnum.TRUE

    def is_false(self) -> bool:
        """Check if the state is OFF."""
        return self == TriStateEnum.FALSE

    def is_unknown(self) -> bool:
        """Check if the state is UNKNOWN."""
        return self == TriStateEnum.UNKNOWN

    def __bool__(self) -> bool:
        """Convert TriStateEnum to boolean."""
        return self.is_true()
