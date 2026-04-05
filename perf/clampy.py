from typing import List

import numpy as np
import pyperf


def clamp1(value: float, min_value: float, max_value: float) -> int:
    """Clamp a value to a specified range."""
    return int(max(min(value, max_value), min_value))


def clamp2(value: float, min_value: float, max_value: float) -> int:
    """Clamp a value to a specified range."""
    if value < min_value:
        return int(min_value)
    elif value > max_value:
        return int(max_value)
    return int(value)


# Benchmark functions
def benchmark_clamp1() -> float:
    arr: List[int] = []
    for i in range(1000):
        r = clamp1(i + 0.1, 0, 10)
        arr.append(r)
    return sum(arr)  # ensure the result is used


def benchmark_clamp2() -> float:
    arr: List[int] = []
    for i in range(1000):
        r = clamp2(i + 0.1, 0, 10)
        arr.append(r)
    return sum(arr)  # ensure the result is used


def benchmark_clip() -> float:
    arr: List[int] = []
    for i in range(1000):
        r = np.clip(i + 0.1, 0, 10)
        arr.append(r)
    return sum(arr)  # ensure the result is used


# Wrapper functions for pyperf
def run_clamp1():
    benchmark_clamp1()


def run_clamp2():
    benchmark_clamp2()


def run_clip():
    benchmark_clip()


# Run benchmarks
def main() -> None:
    runner = pyperf.Runner()
    runner.bench_func("clamp1", run_clamp1)  # type: ignore
    runner.bench_func("clamp2", run_clamp2)  # type: ignore
    runner.bench_func("clip", run_clip)  # type: ignore


if __name__ == "__main__":
    main()
