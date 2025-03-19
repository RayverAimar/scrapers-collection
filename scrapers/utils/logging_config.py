import logging
import os

os.makedirs("logs", exist_ok=True)


def setup_logging(log_file: str, level: int = logging.INFO) -> logging.Logger:
    """Set up logging configuration for a scraper.

    Args:
        log_file (str): Name of the log file
        level (int): Logging level (default: logging.INFO)

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(log_file)

    # Only add handlers if the logger doesn't already have them
    if not logger.handlers:
        logger.setLevel(level)

        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        file_handler = logging.FileHandler(f"logs/{log_file}.log", mode="w")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
