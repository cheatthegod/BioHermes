"""biohermes/splash.py — neofetch-style splash screen with animated status.

Inspired by neofetch / fastfetch / starship — compact 2-column layout
with an iconic DNA helix on the left and a dense status grid on the
right.  Each status row "checks in" one at a time (~60ms per row) so
the splash feels alive instead of static.

Reads profile config for provider / smart-routing / MCP / gateway /
outbox state.  Renders to stderr.  All errors caught silently so the
agent always launches.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any


# Gateway env vars the bio shim watches; used for "● Gateway" status.
_GATEWAY_VARS = (
    ("TELEGRAM_HOME_CHANNEL", "Telegram"),
    ("DISCORD_HOME_CHANNEL", "Discord"),
    ("SLACK_HOME_CHANNEL", "Slack"),
    ("WHATSAPP_HOME_CHANNEL", "WhatsApp"),
    ("SIGNAL_HOME_CHANNEL", "Signal"),
    ("MATRIX_HOME_CHANNEL", "Matrix"),
    ("FEISHU_HOME_CHANNEL", "Feishu"),
    ("DINGTALK_HOME_CHANNEL", "DingTalk"),
    ("WEIXIN_HOME_CHANNEL", "WeChat"),
    ("WECOM_HOME_CHANNEL", "WeCom"),
    ("QQBOT_HOME_CHANNEL", "QQ"),
    ("MATTERMOST_HOME_CHANNEL", "Mattermost"),
    ("BLUEBUBBLES_HOME_CHANNEL", "iMessage"),
    ("EMAIL_HOME_CHANNEL", "Email"),
)


# Vertical DNA double helix — 11 rows, 7 cols wide.  Base pair rungs
# alternate AT and GC; phosphate backbone curves ╲ ╱ ╳ ╱ ╲.  Carefully
# hand-laid so backbone diagonals meet at the ╳ crossover.
DNA_HELIX = [
    "   A═══T   ",
    "    ╲ ╱    ",
    "     ╳     ",
    "    ╱ ╲    ",
    "   G═══C   ",
    "    ╲ ╱    ",
    "     ╳     ",
    "    ╱ ╲    ",
    "   T═══A   ",
    "    ╲ ╱    ",
    "     ╳     ",
]

# Rainbow-ish gradient down the helix (teal → green → cyan → purple → teal).
_HELIX_PALETTE = [
    "#00d9b2", "#00d9b2", "#00ffaa", "#00ff9c", "#00ff9c",
    "#00d4ff", "#7c5cff", "#7c5cff", "#00d4ff", "#00d9b2", "#00d9b2",
]


def _try_import_rich():
    try:
        from rich.console import Console, Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        from rich.align import Align
        from rich.columns import Columns
        from rich.live import Live
        return {
            "Console": Console, "Group": Group, "Panel": Panel,
            "Table": Table, "Text": Text, "Align": Align,
            "Columns": Columns, "Live": Live,
        }
    except ImportError:
        return None


def _read_config(profile_dir: Path) -> dict[str, Any]:
    config_path = profile_dir / "config.yaml"
    if not config_path.is_file():
        return {}
    try:
        import yaml
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _count_outbox(profile_dir: Path) -> int:
    outbox = profile_dir / "outbox"
    if not outbox.is_dir():
        return 0
    return sum(1 for p in outbox.iterdir() if p.is_file())


def _count_bio_skills(checkout_root: Path) -> int:
    for d in [checkout_root / "optional-skills" / "bioinformatics"]:
        if d.is_dir():
            return sum(1 for p in d.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    return 0


def _active_gateways() -> list[str]:
    out = []
    for var, label in _GATEWAY_VARS:
        v = os.environ.get(var, "").strip()
        if v and not v.startswith("${"):
            out.append(label)
    return out


def _shorten_path(p: Path, max_len: int = 42) -> str:
    s = str(p)
    home = str(Path.home())
    if s.startswith(home):
        s = "~" + s[len(home):]
    if len(s) <= max_len:
        return s
    return s[: max_len // 2 - 1] + "…" + s[-(max_len - max_len // 2):]


# ── Status rows assembled from config ──────────────────────────────────────

def _collect_status_rows(profile_dir: Path, checkout_root: Path) -> list[tuple[str, str]]:
    cfg = _read_config(profile_dir)

    # Runtime / provider
    model = cfg.get("model") or {}
    provider = model.get("provider", "?")
    default_model = model.get("default", "?")
    # Shorten provider/model string if too long
    prov_model = f"{provider} · {default_model}"
    if len(prov_model) > 42:
        prov_model = prov_model[:41] + "…"

    # Smart routing
    sr = cfg.get("smart_model_routing") or {}
    if sr.get("enabled"):
        cheap = sr.get("cheap_model") or {}
        smart = f"→ {cheap.get('model', '?')}"
    else:
        smart = "off"

    # Approvals
    ap = cfg.get("approvals") or {}
    approvals = ap.get("mode", "manual")

    # Checkpoints
    cp = cfg.get("checkpoints") or {}
    ckpt = "enabled" if cp.get("enabled", False) else "off"

    # Bio skills
    bio_n = _count_bio_skills(checkout_root)
    bio_str = f"{bio_n} workflows" if bio_n else "(not bundled)"

    # MCP
    mcp_servers = list((cfg.get("mcp_servers") or {}).keys())
    mcp_str = ", ".join(mcp_servers) if mcp_servers else "(none)"

    # Gateway
    gws = _active_gateways()
    if not gws:
        gw = "⊘ CLI-only"
    elif len(gws) == 1:
        gw = f"● {gws[0]}"
    else:
        gw = f"● {len(gws)} channels"

    # Outbox
    obn = _count_outbox(profile_dir)
    outbox_str = f"{obn} files in outbox"

    # Profile
    prof = _shorten_path(profile_dir)

    return [
        ("Runtime",      "Hermes Agent · in-process"),
        ("Provider",     prov_model),
        ("Smart route",  smart),
        ("Approvals",    approvals),
        ("Checkpoints",  ckpt),
        ("Bio skills",   bio_str),
        ("MCP tools",    mcp_str),
        ("Gateway",      gw),
        ("Profile",      prof),
        ("Outbox",       outbox_str),
    ]


# ── Rendering primitives ───────────────────────────────────────────────────

def _colored_helix(R):
    """Return a Rich Text of the DNA helix with gradient colors."""
    t = R["Text"]()
    for i, line in enumerate(DNA_HELIX):
        color = _HELIX_PALETTE[i % len(_HELIX_PALETTE)]
        t.append(line, style=f"bold {color}")
        if i < len(DNA_HELIX) - 1:
            t.append("\n")
    return t


def _status_frame(R, rows: list[tuple[str, str]], revealed: int):
    """Build a status grid where only `revealed` rows show values.

    Unrevealed rows show a dim "checking…" placeholder with a spinner
    dot; revealed rows show "●" indicator in bright green and the
    real value.
    """
    Table = R["Table"]
    Text = R["Text"]
    grid = Table.grid(padding=(0, 1))
    grid.add_column(no_wrap=True, width=1)   # dot indicator
    grid.add_column(no_wrap=True, width=12, style="bold #00d4ff")  # label
    grid.add_column(overflow="ellipsis")     # value

    # Simple rotating spinner for unrevealed rows
    spinner_chars = "◐◓◑◒"
    phase = int(time.time() * 10) % len(spinner_chars)

    for i, (label, value) in enumerate(rows):
        if i < revealed:
            dot = Text("●", style="bold #00ff9c")
            val = Text(value, style="#e0fff8")
        else:
            dot = Text(spinner_chars[phase], style="dim #5a8a8a")
            val = Text("checking…", style="dim italic #5a8a8a")
        grid.add_row(dot, Text(label, style="bold #00d4ff"), val)

    return grid


def _header_text(R, version: str, install_mode: str):
    """Title for the outer panel."""
    Text = R["Text"]
    t = Text()
    t.append("  🧬  ", style="bold #00ff9c")
    t.append("BIOHERMES ", style="bold #00ff9c")
    t.append(f"v{version}", style="dim #00d4ff")
    t.append("  ·  ", style="dim #5a8a8a")
    t.append(install_mode, style="dim italic #5a8a8a")
    t.append("  ·  ", style="dim #5a8a8a")
    t.append("built on ", style="dim #5a8a8a")
    t.append("BioClaw", style="bold #7c5cff")
    t.append(" · powered by ", style="dim #5a8a8a")
    t.append("Hermes Agent", style="bold #00d4ff")
    t.append("  ", style="")
    return t


def _footer_text(R):
    Text = R["Text"]
    t = Text()
    t.append("● ready  ·  ", style="bold #00ff9c")
    t.append("/skills", style="bold #00ffaa")
    t.append("  ·  ", style="dim #5a8a8a")
    t.append("/help", style="bold #00ffaa")
    t.append("  ·  ", style="dim #5a8a8a")
    t.append("or just describe what you want", style="italic #00d4ff")
    return t


def _build_layout(R, helix, status_grid):
    """Combine helix + status into a 2-column Table (neofetch-style)."""
    Table = R["Table"]
    Text = R["Text"]
    layout = Table.grid(padding=(0, 3))
    layout.add_column(no_wrap=True)  # helix column (fixed width)
    layout.add_column(ratio=1)       # status column (flex)
    layout.add_row(helix, status_grid)
    return layout


def render(
    profile_dir: Path,
    checkout_root: Path,
    *,
    install_mode: str = "editable",
    version: str = "0.1.0a0",
) -> None:
    R = _try_import_rich()
    if R is None:
        return
    Console = R["Console"]
    Panel = R["Panel"]
    Group = R["Group"]
    Live = R["Live"]
    Text = R["Text"]

    console = Console(stderr=True, force_terminal=True)
    width = console.size.width
    if width < 70:
        return

    rows = _collect_status_rows(profile_dir, checkout_root)

    def _panel_for(revealed: int):
        helix = _colored_helix(R)
        status = _status_frame(R, rows, revealed)
        layout = _build_layout(R, helix, status)
        body = Group(Text(""), layout, Text(""), _footer_text(R))
        return Panel(
            body,
            border_style="#00d9b2",
            padding=(0, 2),
            title=_header_text(R, version, install_mode),
            title_align="left",
            subtitle=Text(
                "type /skills · /help · or describe your bio task",
                style="dim italic #5a8a8a",
            ),
            subtitle_align="right",
        )

    try:
        console.print()
        animate = os.environ.get("BIOHERMES_NO_ANIMATION", "").strip() not in {"1", "true", "yes"}
        if animate:
            with Live(
                _panel_for(0),
                console=console,
                refresh_per_second=20,
                transient=False,  # keep the final state on screen
            ) as live:
                for i in range(len(rows) + 1):
                    live.update(_panel_for(i))
                    time.sleep(0.055)  # ~60ms per row
        else:
            console.print(_panel_for(len(rows)))
        console.print()
    except Exception:
        return


def should_show(argv_rest: list[str]) -> bool:
    """Decide whether to render splash for this invocation."""
    if "--no-splash" in argv_rest:
        return False
    if not sys.stderr.isatty():
        return False

    cmd = None
    for arg in argv_rest:
        if arg.startswith("-"):
            continue
        cmd = arg
        break

    if cmd is None:
        if any(a in argv_rest for a in ("--version", "-V", "--help", "-h")):
            return False
        return True

    if cmd != "chat":
        return False

    return not any(a in argv_rest for a in ("-q", "--query"))
