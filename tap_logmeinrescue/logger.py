import logging
import singer

logging.captureWarnings(True)

warning_logger = logging.getLogger('py.warnings')
warning_logger.setLevel(logging.CRITICAL)

LOGGER = singer.get_logger()
