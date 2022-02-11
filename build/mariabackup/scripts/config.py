import os


class LoggingConfig:
    """
    Python logging configuration
    """
    dict = {
        "version": 1,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "docker": {
                "format": "[%(levelname)s] %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.FileHandler",
                "filename": "/root/out.log",
                "formatter": "docker",
            },
        },
        "root": {
            "level": os.getenv("BACKUP_LOG_LEVEL", "INFO"),
            "handlers": ["console", "file"],
        },
    }
