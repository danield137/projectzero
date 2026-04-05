from dataclasses import dataclass, field

import pyperf


@dataclass(slots=True)
class DirectSlot:
    value: float = 0.0
    rounded: int = 0


@dataclass(slots=True)
class PropertySlot:
    _value: float = field(default=0.0, init=False)
    rounded: int = 0

    def __init__(self, val: float = 0.0) -> None:
        self._value = val

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, v: float) -> None:
        self._value = v
        self.rounded = int(v)


# Benchmark functions
def benchmark_direct_access() -> float:
    obj = DirectSlot(1.23)
    acc = 0.0
    for i in range(1000):
        obj.value = float(i)
        obj.rounded = int(obj.value)
        acc += obj.rounded
    return acc  # ensure the result is used


def benchmark_property_access() -> float:
    obj = PropertySlot(1.23)
    acc = 0.0
    for i in range(1000):
        obj.value = float(i)
        acc += obj.rounded
    return acc  # ensure the result is used


# Wrapper functions for pyperf
def run_direct_access():
    benchmark_direct_access()


def run_property_access():
    benchmark_property_access()


# Run benchmarks
def main() -> None:
    runner = pyperf.Runner()
    runner.bench_func("Direct attribute access", run_direct_access)  # type: ignore
    runner.bench_func("Property access", run_property_access)  # type: ignore


if __name__ == "__main__":
    main()
