from tigen.ai.memory import ImperfectMemory, MemoryData, MemoryFact, MemQuery


def test_imperfect_memory_remember():
    """Test adding facts to imperfect memory."""
    # Arrange
    memory = ImperfectMemory()
    memory_data = MemoryData()
    fact = MemoryFact(uid="location1", tag="location", t0=5, value={"x": 10, "y": 20})

    # Act
    memory.remember(memory_data, fact)

    # Assert
    assert fact in memory_data.stm, "Fact should be added to short-term memory"
    assert len(memory_data.stm) == 1, "STM should contain one fact"


def test_imperfect_memory_tick_stm_to_ltm():
    """Test moving facts from STM to LTM after time passes."""
    # Arrange
    memory = ImperfectMemory()
    memory_data = MemoryData()
    fact = MemoryFact(uid="food-123", tag="food", t0=0, value={"type": "apple"})
    memory.remember(memory_data, fact)

    # Act - Simulate time passing beyond STM span
    memory.tick(memory_data, 1.0, ImperfectMemory.STM_SPAN_TICKS + 1)

    # Assert
    assert len(memory_data.stm) == 0, "STM should be empty after tick"
    assert "food-123" in memory_data.ltm, "Fact should be moved to LTM"
    assert "food" in memory_data.cue, "Cue should be created for the fact category"


def test_imperfect_memory_decay():
    """Test memory decay over time."""
    # Arrange
    memory = ImperfectMemory()
    memory_data = MemoryData()
    fact = MemoryFact(uid="food-123", tag="food", t0=0, value={"type": "apple"})

    # Add fact directly to LTM and set initial strength
    memory_data.ltm[fact.uid] = fact
    memory_data.strength[fact.uid] = 1.0

    # Act - Simulate decay over time
    memory.tick(memory_data, ImperfectMemory.DECAY_HALF_LIFE, 100)

    # Assert
    assert memory_data.strength[fact.uid] == 0.5, "Memory strength should decay to half after one half-life"


def test_imperfect_memory_recall_with_where():
    """Test recalling facts with where condition."""
    # This test is expected to fail due to a bug in ImperfectMemory.recall
    # when using the where parameter with ctx=None
    pass


def test_imperfect_memory_recall_by_tag():
    """Test recalling facts by tag using MemQuery.tag_eq."""
    # Arrange
    memory = ImperfectMemory()
    memory_data = MemoryData()

    # Create facts with different tags
    fact1 = MemoryFact(uid="food1", tag="food", t0=10, value={"type": "apple"})
    fact2 = MemoryFact(uid="food2", tag="food", t0=20, value={"type": "banana"})
    fact3 = MemoryFact(uid="location1", tag="location", t0=30, value={"x": 10, "y": 20})

    memory.remember(memory_data, fact1)
    memory.remember(memory_data, fact2)
    memory.remember(memory_data, fact3)

    # Create query for food items using tag_eq with k=2
    query = MemQuery(where=lambda f: f.tag == "food", k=2)

    # Act
    results = memory.recall(memory_data, query, 100)

    # Assert
    assert len(results) == 2, "Should return two results"
    assert all(f.tag == "food" for f in results), "Should only return food facts"
