import abc
import enum
import heapq
import math
import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from tigen.common.math import Vector, cosine


@dataclass(slots=True)
class MemoryFact:
    """
    *uid* : unique and stable identifier
    *t0*  : tick when the fact was first encoded
    *value*: **opaque payload**  (Memory never inspects this)
    *ctx* : optional context vector for similarity search
    """

    uid: str
    tag: str
    t0: int
    value: Any
    ctx: Vector | None = field(init=False, default=None)


class MemoryType(str, enum.Enum):
    PERFECT = "PERFECT"
    IMPERFECT = "IMPERFECT"


@dataclass(slots=True)
class MemoryData:
    ltm: dict[str, MemoryFact] = field(default_factory=dict[str, MemoryFact])
    stm: list[MemoryFact] = field(default_factory=list[MemoryFact])
    strength: dict[str, float] = field(default_factory=dict[str, float])
    cue: dict[str, set[str]] = field(default_factory=dict[str, set[str]])
    rng_state: int = field(default=0xDEADBEEF)  # splitmix state

    def all(self) -> Iterator[MemoryFact]:
        if self.stm:
            yield from self.stm
        if self.ltm.values():
            yield from self.ltm.values()

    def exists(self, uid: str) -> bool:
        """Check if a fact with the given UID exists in either STM or LTM."""
        return uid in self.ltm or any(fact.uid == uid for fact in self.stm)


@dataclass(slots=True, frozen=True)
class MemQuery:
    fact_type: type[MemoryFact] | None = None
    uid: str | None = None
    where: Callable[[MemoryFact], bool] | None = None
    ctx: Vector | None = None  # current context for activation boost
    k: int = 5

    @staticmethod
    def tag_eq(tag: str) -> "MemQuery":
        """Create a query for a specific tag."""
        return MemQuery(where=lambda f: f.tag == tag)


@dataclass(slots=True)
class Memory(abc.ABC):
    @abc.abstractmethod
    def remember(self, md: MemoryData, fact: MemoryFact) -> None: ...

    @abc.abstractmethod
    def recall(self, md: MemoryData, q: MemQuery, now: int) -> list[MemoryFact]: ...

    @abc.abstractmethod
    def tick(self, md: MemoryData, dt: float, now: int) -> None: ...

    @abc.abstractmethod
    def forget(self, md: MemoryData, uid: str) -> None: ...


# ———– PerfectMemory ————————————————————————————————————————
class PerfectMemory(Memory):
    def remember(self, md: MemoryData, fact: MemoryFact) -> None:
        md.ltm[fact.uid] = fact

    def recall(self, md: MemoryData, q: MemQuery, now: int) -> list[MemoryFact]:
        cand = (fact for facts in (md.ltm.values(), md.stm) for fact in facts)
        if q.where:
            cand = filter(q.where, cand)
        return list(cand)[: q.k]

    def forget(self, md: MemoryData, uid: str) -> None:
        """Forget a fact by UID."""
        md.ltm.pop(uid, None)
        md.stm = [f for f in md.stm if f.uid != uid]
        for s in md.cue.values():
            s.discard(uid)

    def tick(self, md: MemoryData, dt: float, now: int) -> None:
        # no‐op for perfect memory
        return


# ———– ImperfectMemory knobs & logic ——————————————————————————
class ImperfectMemory(Memory):
    ENCODE_NOISE_P = 0.10
    STM_SPAN_TICKS = 300
    INTERFERENCE_P = 0.40
    DECAY_HALF_LIFE = 30_000
    RETRIEVAL_NOISE_SD = 0.25

    def remember(self, md: MemoryData, fact: MemoryFact) -> None:
        rng = random.Random(md.rng_state)
        if rng.random() < self.ENCODE_NOISE_P:
            # fact = {**fact, "noisy": True}    # your distortion
            ...
        md.stm.append(fact)
        md.rng_state = rng.getrandbits(64)

    def tick(self, md: MemoryData, dt: float, now: int) -> None:
        # STM → LTM + interference
        while md.stm and now - md.stm[0].t0 >= self.STM_SPAN_TICKS:
            f = md.stm.pop(0)
            bucket = f.uid.split("-", 1)[0]
            md.cue.setdefault(bucket, set()).add(f.uid)
            md.ltm[f.uid] = f
            md.strength[f.uid] = md.strength.get(f.uid, 0.01) + 1.0

        # decay
        k = 0.5 ** (dt / self.DECAY_HALF_LIFE)
        dead: list[str] = []
        for uid, s in md.strength.items():
            s *= k
            if s < 0.02:
                dead.append(uid)
            md.strength[uid] = s
        for uid in dead:
            md.ltm.pop(uid, None)
            for s in md.cue.values():
                s.discard(uid)

    def recall(self, md: MemoryData, q: MemQuery, now: int) -> list[MemoryFact]:
        rng = random.Random(md.rng_state)
        result_heap: list[
            tuple[float, MemoryFact]
        ] = []  # Will store (-score, fact) pairs for min-heap behavior with max scores

        # Process candidates from both LTM and STM without materializing full lists
        def process_fact(f: MemoryFact):
            if q.where and not q.where(f):
                return

            base = md.strength.get(f.uid, 0.01)
            act = math.log(base / (now - f.t0 or 1e-9))
            sim = 0.0
            if q.ctx and f.ctx is not None:
                sim = cosine(q.ctx, f.ctx)
            noise = rng.gauss(0.0, self.RETRIEVAL_NOISE_SD)
            score = act + sim + noise

            # Use negative score for min-heap to function as max-heap
            if len(result_heap) < q.k:
                heapq.heappush(result_heap, (-score, f))
            elif -score > result_heap[0][0]:
                heapq.heappushpop(result_heap, (-score, f))

        # Process long-term memory
        for f in md.ltm.values():
            process_fact(f)

        # Process short-term memory
        for f in md.stm:
            process_fact(f)

        md.rng_state = rng.getrandbits(64)

        # Extract results in descending order of score
        results = [f for _, f in sorted(result_heap, key=lambda x: x[0])]
        return results

    def forget(self, md: MemoryData, uid: str) -> None:
        """Forget a fact by UID."""
        md.ltm.pop(uid, None)
        md.stm = [f for f in md.stm if f.uid != uid]
        for s in md.cue.values():
            s.discard(uid)
        md.strength.pop(uid, None)


# shared singleton instances
_perfect_memory = PerfectMemory()
_imperfect_memory = ImperfectMemory()


def get_memory(memory_type: MemoryType) -> Memory:
    if memory_type == MemoryType.PERFECT:
        return _perfect_memory
    return _imperfect_memory


# ———– façade dispatchers ——————————————————————————————————————


class MemWriter:
    @staticmethod
    def write(md: MemoryData, memory_type: str, fact: MemoryFact) -> None:
        if memory_type == MemoryType.PERFECT:
            _perfect_memory.remember(md, fact)
        elif memory_type == MemoryType.IMPERFECT:
            _imperfect_memory.remember(md, fact)


class MemReader:
    @staticmethod
    def read(md: MemoryData, memory_type: str, q: MemQuery, now: int) -> list[MemoryFact]:
        if memory_type == MemoryType.PERFECT:
            return _perfect_memory.recall(md, q, now)
        if memory_type == MemoryType.IMPERFECT:
            return _imperfect_memory.recall(md, q, now)
        return []  # empty list if memory type is unknown


class MemHousekeeping:
    @staticmethod
    def tick(md: MemoryData, memory_type: str, dt: float, now: int) -> None:
        if memory_type == MemoryType.PERFECT:
            _perfect_memory.tick(md, dt, now)
        else:
            _imperfect_memory.tick(md, dt, now)
