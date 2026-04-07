from tigen.common.enum import MonotonicEnum


# Create a test enum class that inherits from MonotonicEnum
class DemoEnum(MonotonicEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


def test_monotonic_enum_bounds():
    """Test the bounds of MonotonicEnum through from_float method."""
    # We can test the bounds indirectly through the from_float method
    assert DemoEnum.from_float(0) == DemoEnum.LOW, "Lower bound should clamp to LOW"
    assert DemoEnum.from_float(4) == DemoEnum.HIGH, "Upper bound should clamp to HIGH"


def test_monotonic_enum_from_float():
    """Test converting float values to enum instances."""
    # Test exact values
    assert DemoEnum.from_float(1.0) == DemoEnum.LOW
    assert DemoEnum.from_float(2.0) == DemoEnum.MEDIUM
    assert DemoEnum.from_float(3.0) == DemoEnum.HIGH

    # Test values between enum values (should round down)
    assert DemoEnum.from_float(1.5) == DemoEnum.LOW
    assert DemoEnum.from_float(2.7) == DemoEnum.MEDIUM

    # Test out of bounds values (should clamp)
    assert DemoEnum.from_float(0.5) == DemoEnum.LOW
    assert DemoEnum.from_float(4.0) == DemoEnum.HIGH


def test_monotonic_enum_value_under():
    """Test the value_under method."""
    # Test with exact enum values
    assert DemoEnum.MEDIUM.value_under(2.0) is True
    assert DemoEnum.MEDIUM.value_under(3.0) is False

    # Test with values between enum values
    assert DemoEnum.MEDIUM.value_under(1.9) is True
    assert DemoEnum.MEDIUM.value_under(2.1) is True  # 2.1 // 1 = 2
    assert DemoEnum.MEDIUM.value_under(2.9) is True  # 2.9 // 1 = 2

    # Test with out of bounds values
    assert DemoEnum.LOW.value_under(0.5) is True  # Clamped to 1
    assert DemoEnum.HIGH.value_under(4.0) is True  # Clamped to 3, which is equal to HIGH.value


def test_monotonic_enum_value_over():
    """Test the value_over method."""
    # Test with exact enum values
    assert DemoEnum.MEDIUM.value_over(2.0) is True
    assert DemoEnum.MEDIUM.value_over(1.0) is False  # 1.0 is less than MEDIUM.value (2)

    # Test with values between enum values
    assert DemoEnum.MEDIUM.value_over(2.1) is True  # 2.1 // 1 = 2
    assert DemoEnum.MEDIUM.value_over(1.9) is False  # 1.9 // 1 = 1, which is less than MEDIUM.value (2)

    # Test with out of bounds values
    assert DemoEnum.HIGH.value_over(4.0) is True  # Clamped to 3, which is equal to HIGH.value
    assert DemoEnum.LOW.value_over(0.5) is True  # Clamped to 1, which is equal to LOW.value
