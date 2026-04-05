from sim.common.ds.running_stats import RunningDistribution, RunningMean


def test_running_mean():
    """Test running mean calculation and reset."""
    mean = RunningMean()

    # Test empty
    assert mean.value() == 0.0

    # Test single value
    mean.add(5.0)
    assert mean.value() == 5.0

    # Test multiple values
    mean.add(7.0)
    mean.add(9.0)
    assert mean.value() == 7.0  # (5 + 7 + 9) / 3

    # Test reset
    mean.reset()
    assert mean.value() == 0.0
    mean.add(3.0)
    assert mean.value() == 3.0


def test_running_distribution():
    """Test probability distribution tracking."""
    dist = RunningDistribution()

    # Test empty
    assert dist.prob("A") == 0.0
    assert list(dist.keys()) == []

    # Test single category
    dist.add("A")
    assert dist.prob("A") == 1.0
    assert dist.prob("B") == 0.0

    # Test multiple categories
    dist.add("B", 2)  # Add B twice
    assert dist.prob("A") == 1 / 3  # 1 out of 3 total
    assert dist.prob("B") == 2 / 3  # 2 out of 3 total
    assert sorted(dist.keys()) == ["A", "B"]

    # Test reset
    dist.reset()
    assert dist.prob("A") == 0.0
    assert dist.prob("B") == 0.0
    assert list(dist.keys()) == []
