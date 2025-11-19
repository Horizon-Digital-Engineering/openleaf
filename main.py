"""Entry point for running the OpenLeaf state server."""

from __future__ import annotations

import uvicorn

from openleaf.config import load_config
from openleaf.server import LeafStateServer


def run() -> None:
    """Run the OpenLeaf server using the default configuration file."""

    config = load_config("config.yaml")
    server = LeafStateServer(config)
    server.start_background_loop()
    uvicorn.run(server.app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    run()
