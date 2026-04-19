#!/usr/bin/env python3
"""mcp_bioclaw_server — B1-A MCP shim for BioClaw's file-I/O tools.

Two operating modes, detected at call time:

  (1) CLI / local context — no messaging gateway is active.
      Copy the file to `HERMES_HOME/outbox/<unique>.<ext>` (or
      BIOCLAW_OUTBOX when set) and return the local path so the user can
      open it directly.  This matches BioClaw's FILES_DIR pattern
      (`container/agent-runner/src/ipc-mcp-stdio.ts`) adapted for a
      no-channel runtime.

  (2) Gateway context — Hermes's messaging gateway is running and has
      configured at least one home channel (TELEGRAM_HOME_CHANNEL,
      DISCORD_HOME_CHANNEL, SLACK_HOME_CHANNEL, WHATSAPP_HOME_CHANNEL,
      SIGNAL_HOME_CHANNEL).  Still copy to outbox (as a durable record),
      then return a hint pointing the agent at Hermes's native
      `send_message` tool which handles platform-specific photo/document
      dispatch (tools/send_message_tool.py:644 for Telegram photos, 469
      for Discord attachments, etc.).  We do not re-implement channel
      delivery here — Hermes already owns that path.

Gateway/channel backends are re-enabled by this detection; see
README.BioHermes.md and `docs/biohermes/PHASE1_PROGRESS.md` for the end-
to-end loop (agent → skill → mcp_bioclaw_send_image → outbox + hint →
send_message → user's Telegram / Slack / Discord / WhatsApp / Signal).
"""
from __future__ import annotations

import os
import random
import shutil
import string
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP


# Hermes gateway sets `<PLATFORM>_HOME_CHANNEL` in the agent subprocess's env
# when a home channel is configured for that platform (see gateway/run.py:
# 4213 / 5743 / 5756).  Presence of any of these tells us the agent has a
# meaningful delivery target that beats a local outbox.
_GATEWAY_ENV_VARS = (
    "TELEGRAM_HOME_CHANNEL",
    "DISCORD_HOME_CHANNEL",
    "SLACK_HOME_CHANNEL",
    "WHATSAPP_HOME_CHANNEL",
    "SIGNAL_HOME_CHANNEL",
    "MATRIX_HOME_CHANNEL",
    "WEIXIN_HOME_CHANNEL",
)


def _active_gateway_targets() -> list[str]:
    """Return a list of `<platform>:<chat_id>` entries for every gateway
    home channel we see in the environment.  Empty list means no gateway.

    Defensive: Hermes's MCP config `env:` block does NOT expand `${VAR}`
    when the referenced var is unset — it passes the literal string
    `${TELEGRAM_HOME_CHANNEL}` etc. through to the subprocess.  Treat
    any value that still looks like a template as unset.
    """
    targets: list[str] = []
    for var in _GATEWAY_ENV_VARS:
        value = os.environ.get(var, "").strip()
        if not value or value.startswith("${"):
            continue
        platform = var.removesuffix("_HOME_CHANNEL").lower()
        targets.append(f"{platform}:{value}")
    return targets


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

    abs_dest = str(dest_path)
    pieces = [f"{kind.title()} saved to outbox/{dest_name}"]
    if caption:
        pieces.append(f"caption: {caption}")
    pieces.append(f"absolute path: {abs_dest}")

    targets = _active_gateway_targets()
    if targets:
        # Gateway is active — tell the agent how to actually deliver this.
        quoted_targets = ", ".join(f"'{t}'" for t in targets)
        pieces.append(
            "GATEWAY ACTIVE: to deliver to the user via their chat, "
            f"now call send_message(target=<one of {quoted_targets}>, "
            f"media_files=['{abs_dest}'], text={caption!r}) — the outbox "
            "copy above is just a durable record."
        )
    else:
        pieces.append(
            "GATEWAY INACTIVE: no *_HOME_CHANNEL env var found; outbox is "
            "the final delivery. User can `open` / `cp` the absolute path."
        )

    return " | ".join(pieces)


mcp = FastMCP("bioclaw")


@mcp.tool()
def send_image(file_path: str, caption: str = "") -> str:
    """Send an image file (PNG/JPG/etc.) to the user.

    Mode depends on environment:
      - With a messaging gateway active (TELEGRAM_HOME_CHANNEL etc. set):
        saves to outbox and returns guidance for calling Hermes's built-in
        `send_message` tool with media_files=[...] to push through the
        channel.  This is how real delivery happens on Telegram / Slack /
        Discord / WhatsApp / Signal / Matrix.
      - Without a gateway (CLI-only): saves to outbox and returns the
        absolute path for local pickup.

    Args:
        file_path: Absolute path to the image file on the host filesystem.
        caption:  Optional short description of the image.
    """
    return _send_any(file_path, caption or None, "image")


@mcp.tool()
def send_file(file_path: str, caption: str = "") -> str:
    """Send a non-image file (PDF/CSV/ZIP/JSON/...) to the user.

    Same two-mode behaviour as `send_image` — in a gateway context the
    outbox copy is a record and the agent should follow up with
    `send_message` to push the file to the user's chat; otherwise the
    outbox is the final delivery.

    Args:
        file_path: Absolute path to the file on the host filesystem.
        caption:  Optional short description of the file.
    """
    return _send_any(file_path, caption or None, "file")


if __name__ == "__main__":
    mcp.run()
