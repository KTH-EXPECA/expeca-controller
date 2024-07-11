import sys
from loguru import logger
import chi.network, chi.container, chi.network

try:
    chi.network.list_networks()
    sys.exit(0)
except Exception as e:
    logger.error(traceback.format_exc())
    sys.exit(1)
