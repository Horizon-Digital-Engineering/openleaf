"""Central logging configuration helpers."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict

from openleaf.config import LoggingConfig


def _has_handler(logger: logging.Logger, path: Path) -> bool:
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(getattr(handler, "baseFilename", "")).resolve() == path.resolve():
            return True
    return False


def _file_handler(path: Path, level: int) -> logging.FileHandler:
    # Overwrite on each start so logs are fresh.
    handler = logging.FileHandler(path, mode="w", encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    return handler


def configure_logging(config: LoggingConfig) -> Dict[str, Path]:
    """Configure root and shared transport loggers based on the provided config."""

    if not config.enabled:
        return {}

    log_dir = Path(config.path or "./logs").expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)

    server_log = log_dir / "server.log"
    transport_log = log_dir / "connection.log"
    obd_log = log_dir / "obd.log"

    level = getattr(logging, config.level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    if not _has_handler(root_logger, server_log):
        root_logger.addHandler(_file_handler(server_log, level))

    transport_logger = logging.getLogger("openleaf.transport")
    transport_logger.setLevel(logging.DEBUG)
    if not _has_handler(transport_logger, transport_log):
        transport_logger.addHandler(_file_handler(transport_log, logging.DEBUG))
    if not _has_handler(transport_logger, obd_log):
        transport_logger.addHandler(_file_handler(obd_log, logging.DEBUG))
    transport_logger.propagate = True

    return {"server": server_log, "connection": transport_log, "obd": obd_log}


def get_transport_logger(name: str, config: LoggingConfig) -> logging.Logger:
    """Return a per-transport logger with its own file."""

    if not config.enabled:
        logger = logging.getLogger("openleaf.transport.disabled")
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        logger.propagate = False
        return logger

    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "transport"
    log_dir = Path(config.path or "./logs").expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"connection_{safe_name}.log"
    obd_path = log_dir / f"obd_{safe_name}.log"

    logger = logging.getLogger(f"openleaf.transport.{safe_name}")
    logger.setLevel(logging.DEBUG)
    if not _has_handler(logger, path):
        logger.addHandler(_file_handler(path, logging.DEBUG))
    if not _has_handler(logger, obd_path):
        logger.addHandler(_file_handler(obd_path, logging.DEBUG))
    logger.propagate = True
    return logger
