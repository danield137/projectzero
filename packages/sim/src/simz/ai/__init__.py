import abc
import functools
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActionStep(abc.ABC):
    @functools.cached_property
    def name(self):
        return self.__class__.__qualname__
