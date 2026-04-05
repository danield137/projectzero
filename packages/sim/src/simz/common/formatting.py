def human_readable_time_measurement(duration: float) -> str:
    """
    Format a duration in seconds to a human readable format.
    :param duration: The duration in seconds
    :return: A human readable string
    """
    small_units = ["ms", "μs", "ns"]
    if duration < 1:
        next_part = duration
        current_unit = small_units.pop(0)
        while next_part < 1 and small_units:
            current_unit = small_units.pop(0)
            next_part *= 1000.0

        return f"{next_part:.2f}{current_unit}"
    if duration < 60.0:
        return f"{duration:.2f}s"
    if duration < 3600.0:
        return f"{duration / 60.0:.2f}m"

    return f"{duration / 3600.0:.2f}h"


def human_readable_bytes(size: int) -> str:
    """
    Format a size in bytes to a human readable format.
    :param size: The size in bytes
    :return: A human readable string
    """
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size_float = float(size)

    while size_float >= 1024.0 and unit_index < len(units) - 1:
        size_float /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{int(size_float)} {units[unit_index]}"

    return f"{size_float:.1f} {units[unit_index]}"
