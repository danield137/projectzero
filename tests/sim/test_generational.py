import pytest

# These imports assume that the provided implementation is placed in a module,
# for example in a file named generational.py.
# Adjust the module name below as needed.
from sim.common.ds.generational import GenerationalContainer, IsolationLevel


def test_insert_and_get():
    gc = GenerationalContainer[str]()
    handle = gc.insert("foo")
    # Getting the item using its handle should return "foo"
    assert gc.get(handle) == "foo"


def test_remove_and_get():
    gc = GenerationalContainer[str]()
    handle = gc.insert("bar")
    # Remove the item and then check that getting it yields None.
    gc.remove(handle)
    assert gc.get(handle) is None
    # Attempting to remove it again should raise a ValueError.
    with pytest.raises(ValueError):
        gc.remove(handle)


def test_invalid_handle_operations():
    gc = GenerationalContainer[str]()
    # Test get() on an invalid handle; should return None.
    invalid_handle = (999, 0)
    assert gc.get(invalid_handle) is None
    # Removing using an invalid handle should raise a ValueError.
    with pytest.raises(ValueError):
        gc.remove(invalid_handle)


def test_live_iteration_none_mode():
    gc = GenerationalContainer[str]()
    handles = [gc.insert(x) for x in ["A", "B", "C"]]
    # Remove the middle element so that the live list contains a hole.
    gc.remove(handles[1])
    # Live iteration (IsolationLevel.NONE) should visit the current list state.
    # With skip_empty=True (the default), only "A" and "C" will be returned.
    result = list(gc.smart_iter(allowed_mutation=IsolationLevel.NONE))
    assert result == ["A", "C"]


def test_allow_deletions_iteration_mode():
    gc = GenerationalContainer[str]()
    handles = [gc.insert(x) for x in ["A", "B", "C", "D"]]
    # Remove some elements.
    gc.remove(handles[1])  # Remove "B"
    gc.remove(handles[3])  # Remove "D"
    # Fixed-range iteration (ALLOW_DELETIONS) should visit all indices that were valid at start.
    # With skip_empty=True (the default), only "A" and "C" will be returned.
    result = list(gc.smart_iter(allowed_mutation=IsolationLevel.ALLOW_DELETIONS))
    assert result == ["A", "C"], "regular deletion"

    # During iteration, remove an item
    it = gc.smart_iter(allowed_mutation=IsolationLevel.ALLOW_DELETIONS)
    next(it)  # "A"
    gc.remove(handles[2])  # Remove "C"
    try:
        # When deletions are allowed, they are applied on the iterator as is
        assert next(it, None) is None
    except StopIteration:
        ...  # expected, sine it is done


def test_full_isolation_mode():
    gc = GenerationalContainer[str]()
    handles = [gc.insert(x) for x in ["A", "B", "C"]]

    # Get iterator with full isolation
    it = gc.smart_iter(allowed_mutation=IsolationLevel.FULL)

    # Get first item
    assert next(it) == "A"

    # Remove first element
    gc.remove(handles[0])

    # Remove second element
    gc.remove(handles[1])

    # Iterator should still see the original snapshot
    assert next(it) == "B"
    assert next(it) == "C"

    # Iterator should be exhausted
    with pytest.raises(StopIteration):
        next(it)


def test_container_length():
    gc = GenerationalContainer[str]()

    # Empty container
    assert len(gc) == 0

    # Add items
    handles = [gc.insert(x) for x in ["A", "B", "C"]]
    assert len(gc) == 3

    # Remove an item
    gc.remove(handles[1])
    assert len(gc) == 2

    # Add another item
    gc.insert("D")
    assert len(gc) == 3
