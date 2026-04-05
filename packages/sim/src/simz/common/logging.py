import logging
from contextvars import ContextVar

from termcolor import colored

# Thread-local storage for context
sim_time_var: ContextVar[int] = ContextVar("sim_time", default=0)


class Verbosity:
    DEBUG = 5
    INFO = 4
    WARNING = 3
    ERROR = 2
    CRITICAL = 1
    NONE = 0


# Define the custom formatter
class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        "DEBUG": "grey",
        "INFO": "white",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "magenta",
    }

    def __init__(self, fmt=None, datefmt=None, max_filename_len=20, max_levelname_len=8):
        super().__init__(fmt, datefmt)
        self.max_filename_len = max_filename_len
        self.max_levelname_len = max_levelname_len

    def format(self, record):
        # Add padding to the filename
        level_color = self.LEVEL_COLORS[record.levelname.upper()]
        record.filename = f"{record.filename:<{self.max_filename_len}}"
        record.levelname = f"{record.levelname:<{self.max_levelname_len}}"
        # Apply color to the level name
        record.sim_time = f"{sim_time_var.get():<5}"
        record.levelname = f"{colored(record.levelname, level_color)}"
        return super().format(record)


initialized = False


# Setup global logging
def setup_logging():
    # Determine the maximum filename length
    max_filename_len = 14  # Set a default or calculate dynamically if needed
    max_levelname_len = 8
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)

    # Use the custom formatter with padding
    formatter = ColoredFormatter(
        "%(asctime)s | %(filename)s | %(levelname)s | %(sim_time)s | %(message)s",
        max_filename_len=max_filename_len,
        max_levelname_len=max_levelname_len,
    )
    handler.setFormatter(formatter)

    # Configure the root logger
    root_logger = logging.getLogger("zero")  # Root logger
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)
    global initialized
    initialized = True


def get_logger(name="zero"):
    if not initialized:
        setup_logging()
    return logging.getLogger(name)
