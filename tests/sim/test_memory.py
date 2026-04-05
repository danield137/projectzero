from sim.ai.memory import MemoryData, MemoryFact, MemQuery, PerfectMemory


def test_memory_fact_creation():
    """Test creating and accessing memory facts."""
    # Arrange & Act
    fact = MemoryFact(uid="food1", tag="food", t0=10, value={"id": "food1", "location": (5, 10), "owned": True})

    # Assert
    assert fact.uid == "food1"
    assert fact.tag == "food"
    assert fact.t0 == 10
    assert fact.value["id"] == "food1"
    assert fact.value["location"] == (5, 10)
    assert fact.value["owned"] is True


def test_memory_data_storage():
    """Test storing and retrieving facts in memory data."""
    # Arrange
    memory = MemoryData()
    fact1 = MemoryFact(uid="food1", tag="food", t0=10, value={"type": "apple"})
    fact2 = MemoryFact(uid="animal1", tag="animal", t0=15, value={"type": "dog"})

    # Act
    memory.ltm["food1"] = fact1
    memory.ltm["animal1"] = fact2
    memory.stm.append(fact1)
    memory.stm.append(fact2)

    # Assert
    assert len(memory.ltm) == 2
    assert len(memory.stm) == 2
    assert memory.ltm["food1"].value["type"] == "apple"
    assert memory.ltm["animal1"].value["type"] == "dog"
    assert memory.stm[0].uid == "food1"
    assert memory.stm[1].uid == "animal1"


def test_perfect_memory_remember():
    """Test adding facts to perfect memory."""
    # Arrange
    memory = PerfectMemory()
    memory_data = MemoryData()
    fact = MemoryFact(uid="location1", tag="location", t0=5, value={"x": 10, "y": 20})

    # Act
    memory.remember(memory_data, fact)

    # Assert
    assert "location1" in memory_data.ltm
    assert memory_data.ltm["location1"].value["x"] == 10
    assert memory_data.ltm["location1"].value["y"] == 20


def test_perfect_memory_get_facts():
    """Test retrieving facts from perfect memory."""
    # Arrange
    memory = PerfectMemory()
    memory_data = MemoryData()

    fact1 = MemoryFact(uid="food1", tag="food", t0=10, value={"type": "apple"})
    fact2 = MemoryFact(uid="food2", tag="food", t0=15, value={"type": "banana"})
    fact3 = MemoryFact(uid="animal1", tag="animal", t0=20, value={"type": "dog"})

    memory.remember(memory_data, fact1)
    memory.remember(memory_data, fact2)
    memory.remember(memory_data, fact3)

    # Act
    food_facts = memory.recall(memory_data, MemQuery.tag_eq("food"), 1)
    animal_facts = memory.recall(memory_data, MemQuery.tag_eq("animal"), 1)
    all_facts = list(memory_data.all())

    # Assert
    assert len(food_facts) == 2
    assert len(animal_facts) == 1
    assert len(all_facts) == 3

    food_types = [fact.value["type"] for fact in food_facts]
    assert "apple" in food_types
    assert "banana" in food_types

    assert animal_facts[0].value["type"] == "dog"


def test_perfect_memory_forget_fact():
    """Test that perfect memory never forgets facts."""
    # Arrange
    memory = PerfectMemory()
    memory_data = MemoryData()
    fact = MemoryFact(uid="test1", tag="test", t0=5, value={"data": "important"})
    memory.remember(memory_data, fact)

    # Act
    # PerfectMemory should not forget anything, but if it were to try:
    memory.forget(memory_data, "test1")

    # Assert
    assert "test1" not in memory_data.ltm  # Fact should be forgotten
    assert len(list(memory_data.all())) == 0  # No facts should remain in STM or LTM
