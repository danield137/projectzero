from tigen_core import Counter


def test_counter_starts_at_zero():
    c = Counter("test")
    assert c.value == 0
    assert c.label == "test"


def test_counter_increment():
    c = Counter("score")
    c.increment(5)
    assert c.value == 5
    c.increment(3)
    assert c.value == 8


def test_counter_negative_increment():
    c = Counter("hp")
    c.increment(10)
    c.increment(-3)
    assert c.value == 7


def test_counter_reset():
    c = Counter("timer")
    c.increment(100)
    c.reset()
    assert c.value == 0


def test_counter_repr():
    c = Counter("entities")
    c.increment(42)
    assert repr(c) == "Counter('entities', value=42)"
