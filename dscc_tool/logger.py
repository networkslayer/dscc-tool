import logging
import os

logger = logging.getLogger(__name__)

LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()

logging.basicConfig(
    level=LOGLEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("dscc")
