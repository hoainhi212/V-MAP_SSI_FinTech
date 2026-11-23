import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Ghi log ra stdout. Tuyệt đối không log token / secret."""
    logging.basicConfig(
        level=level,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
