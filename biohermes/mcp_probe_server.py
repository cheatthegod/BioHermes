#!/usr/bin/env python3
"""B1-A MCP probe server.

Verifies that Hermes can discover and invoke a tool exposed by an external
stdio MCP server registered via ~/.hermes/config.yaml `mcp_servers:`.

Single tool: `ping(message)` — returns an echo string plus a timestamp.

Runs on the hermes venv's Python because that venv has `mcp` pre-installed.
"""
from __future__ import annotations

import os
import time

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("probe")


@mcp.tool()
def ping(message: str = "") -> str:
    """Echo a message back with a server-side timestamp.

    Used purely to verify MCP discovery and invocation. No side effects.
    """
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    pid = os.getpid()
    return f"[probe pid={pid} ts={ts}] pong: {message!r}"


if __name__ == "__main__":
    mcp.run()
