"""Entry point for running the OpenLeaf state server."""

from __future__ import annotations

import os
import sys

import uvicorn

from openleaf.config import load_config
from openleaf.logging.setup import configure_logging
from openleaf.server import LeafStateServer


def _resolve_config_path() -> str:
    if len(sys.argv) > 1 and sys.argv[1]:
        return sys.argv[1]
    return os.environ.get("OPENLEAF_CONFIG", "config.yaml")


def run() -> None:
    """Run the OpenLeaf server using the provided configuration file."""

    config_path = _resolve_config_path()
    config = load_config(config_path)
    configure_logging(config.logging)
    server = LeafStateServer(config)
    server.start_background_loop()
    uvicorn.run(server.app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    run()
