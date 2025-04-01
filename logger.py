import os
import logging
from logging.handlers import RotatingFileHandler
import sys

def setup_logger(name, log_file='bot.log', level=logging.INFO):
    """Set up logger with specified configuration."""

    os.makedirs('logs', exist_ok=True)

    logger = logging.getLogger(name)

    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    level_dict = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    logger.setLevel(level_dict.get(log_level, logging.INFO))

    f_handler = RotatingFileHandler(
        os.path.join('logs', log_file),
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=3
    )

    f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    f_handler.setFormatter(f_format)

    logger.addHandler(f_handler)
    
    return logger
