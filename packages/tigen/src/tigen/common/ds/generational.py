from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Generic,
    TypeVar,
    cast,
)

# --- Generic type declarations ---
T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

# A handle is a tuple: (index, generation)
Handle = tuple[int, int]


class IsolationLevel(Enum):
    """
    Enum controlling iteration mode.
    NONE:       Live iteration (all modifications are visible).
    ALLOW_DELETIONS: Fixed-range iteration—new insertions are ignored, deletions show as gaps.
    FULL:       "Immutable" iteration: snapshot range is locked; new insertions are ignored;
                    deletions in indices beyond the current iterator position are deferred.
    """

    NONE = 1
    ALLOW_DELETIONS = 2
    FULL = 3


@dataclass(slots=True)
class _ImmutableIterationContext(Generic[T]):
    """
    Per-iterator context for FULL mode. Records:
      - snapshot_length: the container length at iterator creation.
      - current_position: updated during iteration (the last index yielded).
      - deferred: a dict mapping slot indices (within the snapshot) to the value
                  that was present at the time of deletion.
    """

    snapshot_length: int
    current_position: int = 0
    deferred: dict[int, T] = field(default_factory=dict)


@dataclass(slots=True)
class GenerationalContainer(Generic[T]):
    """
    A generic container that stores items in a list with per-slot generation counters.
    Insertions reuse free slots (bumping the generation), and deletions mark a slot as None.

    The smart_iter() method returns an iterator that obeys one of the three modes
    as controlled by IsolationLevel.

    For FULL mode, each iterator creates its own _ImmutableIterationContext,
    and the container keeps a list of active contexts. In remove(), if a deletion occurs
    at an index that is greater than the context’s current_position (and within its snapshot),
    then the current (old) value is recorded in that context’s deferred buffer.
    """

    _items: list[T | None] = field(default_factory=list)
    _generations: list[int] = field(default_factory=list)
    _free_indices: list[int] = field(default_factory=list)
    _immutable_contexts: list[_ImmutableIterationContext[T]] = field(default_factory=list)

    def insert(self, item: T) -> Handle:
        if self._free_indices:
            idx = self._free_indices.pop()
            self._items[idx] = item
            self._generations[idx] += 1  # Invalidate any old handle.
        else:
            idx = len(self._items)
            self._items.append(item)
            self._generations.append(0)

        return (idx, self._generations[idx])

    def remove(self, handle: Handle) -> None:
        idx, gen = handle
        if idx >= len(self._items) or self._generations[idx] != gen:
            raise ValueError("Invalid or stale handle")
        if self._items[idx] is None:
            raise ValueError("Item already deleted")
        # For each active immutable context, only record deletion if the slot is within the snapshot
        # and if the deletion index is beyond the current iteration position.
        for ctx in self._immutable_contexts:
            if ctx.current_position < idx < ctx.snapshot_length:
                if self._items[idx] is not None and idx not in ctx.deferred:
                    ctx.deferred[idx] = cast(T, self._items[idx])
        self._items[idx] = None
        self._free_indices.append(idx)

    def get(self, handle: Handle) -> T | None:
        idx, gen = handle
        if idx >= len(self._items) or self._generations[idx] != gen:
            return None
        return self._items[idx]

    def smart_iter(
        self,
        allowed_mutation: IsolationLevel = IsolationLevel.NONE,
        skip_empty: bool = True,
    ) -> Iterator[T | None]:
        if allowed_mutation == IsolationLevel.NONE:
            # Live iteration: yield items from the current list.
            for item in self._items:
                if skip_empty and item is None:
                    continue
                yield item
        elif allowed_mutation == IsolationLevel.ALLOW_DELETIONS:
            # Fixed-range iteration: snapshot the length and free-slot set.
            snapshot_length = len(self._items)
            frozen_free = {i for i, item in enumerate(self._items) if item is None}
            for i in range(snapshot_length):
                if i in frozen_free:
                    continue
                item = self._items[i]
                if skip_empty and item is None:
                    continue
                yield item
        elif allowed_mutation == IsolationLevel.FULL:
            # Create a new immutable iteration context.
            snapshot_length = len(self._items)
            local_ctx = _ImmutableIterationContext[T](snapshot_length)
            self._immutable_contexts.append(local_ctx)
            try:
                for i in range(snapshot_length):
                    local_ctx.current_position = i  # Update current position.
                    # If the live slot is None, try to fetch deferred value.
                    item = self._items[i]
                    if item is None and i in local_ctx.deferred:
                        item = local_ctx.deferred[i]
                    if skip_empty and item is None:
                        continue
                    yield item
            finally:
                if local_ctx in self._immutable_contexts:
                    self._immutable_contexts.remove(local_ctx)
        else:
            raise ValueError("Unknown mutation allowance mode")

    def __iter__(self) -> Iterator[T | None]:
        # Default __iter__ uses NONE (live iteration).
        return self.smart_iter(allowed_mutation=IsolationLevel.NONE)

    def __len__(self) -> int:
        # Return the number of used slots.
        return len(self._items) - len(self._free_indices)


@dataclass(slots=True, frozen=True)
class Entry(Generic[K, V]):
    key: K
    value: V


class GenerationalDict(Generic[K, V]):
    __slots__ = ("_container", "_key_to_handle")
    _container: GenerationalContainer[Entry[K, V]]
    _key_to_handle: dict[K, Handle]
    """
    A dictionary that uses a GenerationalContainer to store Entry(key, value) objects.
    It maintains a mapping from external keys to handles (for O(1) lookups). The smart_iter()
    method delegates to the container`s smart_iter() to yield (key, value) pairs.
    Default iteration value_over the dict yields keys using NONE mode.
    """

    def __init__(self) -> None:
        self._container: GenerationalContainer[Entry[K, V]] = GenerationalContainer()
        self._key_to_handle: dict[K, Handle] = {}

    def __setitem__(self, key: K, value: V) -> None:
        # To maintain correct generation, we remove the old entry if it exists, and then add the new one.
        if key in self._key_to_handle:
            existing = self._container.get(self._key_to_handle[key])
            if existing is not None and value == existing:
                # optimization: if the value is the same, do nothing.
                return
            self.delete(key)  # Remove old entry if it exists.
        self.add(key, value)

    def __getitem__(self, key: K) -> V:
        try:
            idx, gen = self._key_to_handle[key]  # O(1) hash-lookup
            if self._container._generations[idx] == gen:  # generation still valid
                entry = self._container._items[idx]
                if entry is not None:  # slot not deleted
                    return entry.value  # ➊ no extra calls
        except (KeyError, IndexError):
            pass  # fall through to slow path
        # slow path keeps old invariants
        raise KeyError(key)

    def add(self, key: K, value: V) -> None:
        entry = Entry(key, value)
        handle = self._container.insert(entry)
        self._key_to_handle[key] = handle

    def delete(self, key: K) -> None:
        handle = self._key_to_handle.pop(key, None)
        if handle is not None:
            self._container.remove(handle)

    def get(self, key: K) -> V | None:
        try:
            return self[key]
        except KeyError:
            return None

    def items(
        self,
        allowed_mutation: IsolationLevel = IsolationLevel.NONE,
        skip_empty: bool = True,
    ) -> Iterator[tuple[K, V]]:
        for entry in self._container.smart_iter(allowed_mutation=allowed_mutation, skip_empty=skip_empty):
            if entry is not None:
                yield (entry.key, entry.value)

    def keys(
        self,
        allowed_mutation: IsolationLevel = IsolationLevel.NONE,
        skip_empty: bool = True,
    ) -> Iterator[K]:
        for entry in self.items(allowed_mutation=allowed_mutation, skip_empty=skip_empty):
            yield entry[0]

    def values(
        self,
        allowed_mutation: IsolationLevel = IsolationLevel.NONE,
        skip_empty: bool = True,
    ) -> Iterator[V]:
        for entry in self.items(allowed_mutation=allowed_mutation, skip_empty=skip_empty):
            yield entry[1]

    def __iter__(self) -> Iterator[K]:
        for key, _ in self.items(allowed_mutation=IsolationLevel.NONE, skip_empty=True):
            yield key

    def __len__(self) -> int:
        return len(self._key_to_handle)

    def __contains__(self, key: K) -> bool:
        return key in self._key_to_handle


class GenerationalDefaultDict(GenerationalDict[K, V]):
    __slots__ = ("default_factory",)
    """
    A dictionary based on GenerationalDict that supports a default factory.
    When a key is missing, the default_factory is called to provide a default value,
    the value is inserted into the dictionary, and then returned.
    """

    def __init__(self, default_factory: Callable[[], V]) -> None:
        super().__init__()
        self.default_factory = default_factory

    def __getitem__(self, key: K) -> V:
        if key in self._key_to_handle:
            return super().__getitem__(key)

        default_value = self.default_factory()
        self.__setitem__(key, default_value)
        return default_value
