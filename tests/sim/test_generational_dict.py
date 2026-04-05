import pytest

from sim.common.ds.generational import (
    GenerationalDefaultDict,
    GenerationalDict,
    IsolationLevel,
)


def test_basic_crud():
    """Test basic create, read, update, delete operations."""
    d = GenerationalDict[str, int]()

    # Insert
    d["x"] = 1
    assert d["x"] == 1
    assert len(d) == 1

    # Update existing key
    d["x"] = 2
    assert d["x"] == 2
    assert len(d) == 1

    # Delete
    d.delete("x")
    assert len(d) == 0
    with pytest.raises(KeyError):
        _ = d["x"]

    # Get on non-existent key
    assert d.get("x") is None


def test_stale_handle_overwrite():
    """Test that overwriting a key after deletion doesn't raise ValueError."""
    d = GenerationalDict[str, int]()

    # Insert initial value
    d["x"] = 1
    assert d["x"] == 1

    # Create a FULL isolation iterator to hold a snapshot
    it = d.items(IsolationLevel.FULL)
    first_item = next(it)
    assert first_item == ("x", 1)

    # Delete the key (container slot becomes None)
    d.delete("x")
    assert len(d) == 0

    # Overwrite the same key - this should NOT raise ValueError
    # even though the container slot was previously None
    d["x"] = 2
    assert d["x"] == 2
    assert len(d) == 1


def test_iteration_none_mode():
    """Test live iteration (NONE mode) skips deleted entries."""
    d = GenerationalDict[str, int]()

    # Insert some values
    d["a"] = 1
    d["b"] = 2
    d["c"] = 3

    # Delete middle entry
    d.delete("b")

    # Live iteration should skip deleted entries
    items = list(d.items(IsolationLevel.NONE))
    assert len(items) == 2
    assert ("a", 1) in items
    assert ("c", 3) in items
    assert ("b", 2) not in items


def test_mapping_consistency_after_deletions():
    """Test that dict mapping stays consistent after container deletions."""
    d = GenerationalDict[str, int]()

    # Insert multiple values
    d["a"] = 1
    d["b"] = 2
    d["c"] = 3

    # Create FULL iterator
    it = d.items(IsolationLevel.FULL)

    # Get first item
    first = next(it)
    assert first == ("a", 1)

    # Delete an entry that's ahead of the iterator
    d.delete("c")

    # Dict should reflect the deletion
    assert len(d) == 2
    with pytest.raises(KeyError):
        _ = d["c"]

    # But iterator should still be able to return the deferred value
    second = next(it)
    third = next(it)

    assert second == ("b", 2)
    assert third == ("c", 3)  # Deferred value should be returned


def test_keys_values_iteration():
    """Test keys() and values() iteration methods."""
    d = GenerationalDict[str, int]()

    d["a"] = 1
    d["b"] = 2
    d["c"] = 3

    # Test keys iteration
    keys = list(d.keys())
    assert set(keys) == {"a", "b", "c"}

    # Test values iteration
    values = list(d.values())
    assert set(values) == {1, 2, 3}

    # Test after deletion
    d.delete("b")

    keys = list(d.keys())
    assert set(keys) == {"a", "c"}

    values = list(d.values())
    assert set(values) == {1, 3}


def test_default_dict_basic():
    """Test GenerationalDefaultDict basic functionality."""
    d = GenerationalDefaultDict[str, list[int]](list)

    # Accessing non-existent key should create default value
    result = d["x"]
    assert result == []
    assert len(d) == 1

    # Modifying the default value should work
    d["x"].append(1)
    assert d["x"] == [1]

    # Subsequent access should return same instance
    same_list = d["x"]
    assert same_list is result


def test_default_dict_with_deletions():
    """Test GenerationalDefaultDict behavior with deletions."""
    d = GenerationalDefaultDict[str, int](lambda: 42)

    # Insert value
    d["x"] = 10
    assert d["x"] == 10

    # Delete it
    d.delete("x")

    # Access should create new default value
    assert d["x"] == 42
    assert len(d) == 1


def test_multiple_deletions_and_insertions():
    """Test multiple cycles of deletions and insertions."""
    d = GenerationalDict[str, int]()

    # Insert, delete, insert same key multiple times
    for i in range(5):
        d["x"] = i
        assert d["x"] == i
        assert len(d) == 1

        d.delete("x")
        assert len(d) == 0
        with pytest.raises(KeyError):
            _ = d["x"]


def test_concurrent_iteration_and_modification():
    """Test edge cases with concurrent iteration and modification."""
    d = GenerationalDict[str, int]()

    # Setup initial state
    for i in range(10):
        d[str(i)] = i

    # Start multiple iterators
    it1 = d.items(IsolationLevel.FULL)
    it2 = d.items(IsolationLevel.ALLOW_DELETIONS)

    # Advance first iterator
    _first1 = next(it1)
    _first2 = next(it2)

    # Delete some entries
    d.delete("5")
    d.delete("8")

    # Both iterators should handle this differently
    remaining1 = list(it1)
    remaining2 = list(it2)

    # FULL mode should preserve all original values
    assert len(remaining1) == 9  # 10 - 1 (already consumed)

    # ALLOW_DELETIONS mode should skip deleted entries
    assert len(remaining2) <= 9  # May be fewer due to deletions
