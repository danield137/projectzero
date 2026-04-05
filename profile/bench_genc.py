import os
import sys

# add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from line_profiler import LineProfiler

# bench_genc.py
from sim.common.ds.generational import GenerationalContainer, IsolationLevel

profile = LineProfiler()  # kernprof will call print_stats on this

# --- register target methods dynamically ---
GenerationalContainer.insert = profile(GenerationalContainer.insert)
GenerationalContainer.remove = profile(GenerationalContainer.remove)
GenerationalContainer.smart_iter = profile(GenerationalContainer.smart_iter)


@profile  # still profile the driver function
def bench():
    c = GenerationalContainer[int]()
    for i in range(200_000):
        h = c.insert(i)
        if i % 3 == 0:
            c.remove(h)
    for _ in c.smart_iter(IsolationLevel.FULL):
        pass


if __name__ == "__main__":
    bench()  # kernprof wraps this run and prints stats
    profile.print_stats()
