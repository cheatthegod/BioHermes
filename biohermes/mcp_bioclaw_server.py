#!/usr/bin/env python3
"""mcp_bioclaw_server — B1-A MCP shim implementing BioClaw's file-I/O tools
against a local outbox directory.

Semantics vs BioClaw original (`container/agent-runner/src/ipc-mcp-stdio.ts`):

  BioClaw original                         → This shim
  ─────────────────────────────────────────────────────────────────────────
  Copy to FILES_DIR with unique name       → Copy to HERMES_HOME/outbox/<uniq>.<ext>
  Write IPC JSON for channel to ingest     → (no channel under `terminal.backend: local`;
                                              skip IPC, emit path pointer in return string)
  Return "Image queued for sending: <x>"   → Return "Saved to outbox/<x> — tell the user
                                              where to pick it up"

Gateway/channel backends (Telegram, Slack, …) can be added later by wrapping
the IPC write back in; the tool signature stays stable.

Tools exposed (tool namespace in Hermes becomes `mcp_bioclaw_<tool>`):
  - send_image(file_path, caption=None)
  - send_file(file_path, caption=None)
"""
from __future__ import annotations

import os
import random
import shutil
import string
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP


def _outbox_dir() -> Path:
    """Resolve the outbox from an explicit source only. We never silently fall
    back to `~/.hermes/outbox` because Hermes's MCP subprocess spawn does not
    inherit the parent shell's env by default — a silent fallback would write
    under the user's real profile instead of the project profile.

    Resolution order:
      1. `BIOCLAW_OUTBOX`  — explicit override
      2. `HERMES_HOME/outbox` — only if HERMES_HOME is explicitly set via
         `mcp_servers.bioclaw.env.HERMES_HOME` in the profile config.
      3. Fail loudly — do not write anywhere.
    """
    explicit = os.environ.get("BIOCLAW_OUTBOX")
    if explicit:
        outbox = Path(explicit)
    else:
        hermes_home = os.environ.get("HERMES_HOME")
        if not hermes_home:
            raise RuntimeError(
                "mcp_bioclaw_server: neither BIOCLAW_OUTBOX nor HERMES_HOME is set. "
                "Configure one via `mcp_servers.bioclaw.env` in the Hermes profile "
                "config so this process has a target outbox directory."
            )
        outbox = Path(hermes_home) / "outbox"
    outbox.mkdir(parents=True, exist_ok=True)
    return outbox


def _unique_name(ext: str) -> str:
    ts = int(time.time() * 1000)
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{ts}-{rand}{ext}"


def _send_any(file_path: str, caption: str | None, kind: str) -> str:
    src = Path(file_path)
    if not src.exists():
        return f"ERROR: file not found: {file_path}"
    if not src.is_file():
        return f"ERROR: not a regular file: {file_path}"

    ext = src.suffix or (".png" if kind == "image" else ".bin")
    dest_name = _unique_name(ext)
    dest_path = _outbox_dir() / dest_name
    shutil.copy2(src, dest_path)

    pieces = [f"{kind.title()} saved to outbox/{dest_name}"]
    if caption:
        pieces.append(f"caption: {caption}")
    pieces.append(f"absolute path: {dest_path}")
    return " | ".join(pieces)


mcp = FastMCP("bioclaw")


@mcp.tool()
def send_image(file_path: str, caption: str = "") -> str:
    """Send an image file (PNG/JPG/etc.) to the user by saving it to the outbox.

    Use after generating figures (matplotlib/PyMOL/seaborn). The file must
    already exist on disk. Returns a short pointer the user can follow.

    Args:
        file_path: Absolute path to the image file on the host filesystem.
        caption: Optional short description of the image.
    """
    return _send_any(file_path, caption or None, "image")


@mcp.tool()
def send_file(file_path: str, caption: str = "") -> str:
    """Send a non-image file (PDF/CSV/ZIP/JSON/...) to the user via the outbox.

    Args:
        file_path: Absolute path to the file on the host filesystem.
        caption: Optional short description of the file.
    """
    return _send_any(file_path, caption or None, "file")


if __name__ == "__main__":
    mcp.run()
