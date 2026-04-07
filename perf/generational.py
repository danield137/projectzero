# insert the current path so that I can import the GenerationalContainer class
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from typing import List

import pyperf

from tigen.common.ds.generational import GenerationalContainer


# Benchmark functions
def benchmark_primitive_list() -> float:
    lst: List[int] = []

    N = 10000
    half = N // 2
    for i in range(N):
        lst.append(i)

    for i in range(half):
        lst.remove(i)

    for i in range(half):
        lst.append(i)
    return len(lst)  # ensure the result is used


def benchmark_generational() -> float:
    lst: GenerationalContainer[int] = GenerationalContainer()

    N = 10000
    half = N // 2
    for i in range(N):
        lst.insert(i)

    for i in range(half):
        lst.remove((i, 0))

    for i in range(half):
        lst.insert(i)
    return len(lst)  # ensure the result is usedd


# Wrapper functions for pyperf
def run_benchmark_primitive_list():
    benchmark_primitive_list()


def run_benchmark_generational():
    benchmark_generational()


# Run benchmarks
def main() -> None:
    runner = pyperf.Runner()
    runner.bench_func("run_benchmark_primitive_list", run_benchmark_primitive_list)  # type: ignore
    runner.bench_func("run_benchmark_generational", run_benchmark_generational)  # type: ignore


if __name__ == "__main__":
    main()
