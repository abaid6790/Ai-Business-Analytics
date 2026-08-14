import logging
import os
from logging.handlers import RotatingFileHandler


def configure_logging(app):
    log_folder = app.config.get("LOG_FOLDER", "logs")
    os.makedirs(log_folder, exist_ok=True)

    log_level = logging.DEBUG if app.debug else logging.INFO

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    file_handler = RotatingFileHandler(
        os.path.join(log_folder, "app.log"), maxBytes=1_000_000, backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    app.logger.setLevel(log_level)
    app.logger.addHandler(file_handler)

    # Reduce noise from libraries unless explicitly debugging
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    app.logger.info("Logging configured (level=%s)", logging.getLevelName(log_level))
