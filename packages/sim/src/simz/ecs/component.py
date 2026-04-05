import abc
import json
from dataclasses import asdict, dataclass, field
from typing import Generic, TypeVar

from simz.common.math import EPSILON


@dataclass(slots=True)
class Component(abc.ABC):
    def type_name(self) -> str:
        return self.__class__.__name__


@dataclass(slots=True)
class ClassComponent(Component):
    def __str__(self) -> str:
        return json.dumps(asdict(self))


T = TypeVar("T")


@dataclass(slots=True)
class ScalarComponent(Component, Generic[T], abc.ABC):
    value: T

    def __str__(self) -> str:
        short_name = self.type_name().replace("Component", "")
        return f"{short_name}({self.value})"


@dataclass(slots=True)
class IntComponent(ScalarComponent[int]): ...


@dataclass(slots=True)
class BoolComponent(ScalarComponent[bool]): ...


@dataclass(slots=True)
class FloatComponent(ScalarComponent[float]): ...


@dataclass(slots=True)
class ClampedFloatComponent(FloatComponent):
    min: float
    max: float

    def is_min(self) -> bool:
        # since these are floats, we need to use a tolerance
        return abs(self.value - self.min) < EPSILON

    def is_max(self) -> bool:
        # since these are floats, we need to use a tolerance
        return abs(self.value - self.max) < EPSILON

    def set_clamped_value(self, value: float):
        if value < self.min:
            self.value = self.min
        elif value > self.max:
            self.value = self.max
        else:
            self.value = value


@dataclass(slots=True)
class ZeroToTenFloatComponent(ClampedFloatComponent):
    # Hide min/max parameters from class signature using default_factory
    min: float = field(default=0.0, repr=False)
    max: float = field(default=10.0 - 1e-9, repr=False)

    def __init__(self, value: float):
        # Clamp the initial value
        clamped_value = max(0.0, min(value, 10.0 - EPSILON))
        super().__init__(value=clamped_value, min=0.0, max=10.0 - EPSILON)


@dataclass(slots=True)
class StringComponent(ScalarComponent[str]): ...
