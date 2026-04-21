"""biohermes/splash.py — pre-launch BioHermes splash screen.

Vertical-stacked layout (no Table.grid width competition) so the title
+ DNA helix + status panel render predictably across terminal widths
70 → 200+ columns.

Renders to stderr and silently aborts on any error so the agent always
launches.  Gated by `should_show()` — skipped for `-q`, `--version`,
`--help`, `--no-splash`, or non-TTY invocations.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


# Hermes gateway env vars the shim watches; used to summarize gateway state.
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


# Compact 5-line block-letter wordmark for "BIOHERMES".  Hand-laid-out so
# total width is constant (no proportional rendering surprises).  Width:
# exactly 53 columns including the leading space.  Fits in any terminal
# ≥ 60 cols wide.
WORDMARK = [
    " ██████╗ ██╗ ██████╗ ██╗  ██╗███████╗██████╗ ███╗   ███╗███████╗███████╗",
    " ██╔══██╗██║██╔═══██╗██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝██╔════╝",
    " ██████╔╝██║██║   ██║███████║█████╗  ██████╔╝██╔████╔██║█████╗  ███████╗",
    " ██╔══██╗██║██║   ██║██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══╝  ╚════██║",
    " ██████╔╝██║╚██████╔╝██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗███████║",
    " ╚═════╝ ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝",
]


# DNA helix — 4 base-pair "rungs", rendered horizontally as a single line
# so it never wraps regardless of terminal width.
DNA_LINE = "  G═C  ╲╱  T═A  ╳  C═G  ╳  A═T  ╳  G═C  ╲╱  T═A  ╳  C═G  ╲╱  A═T  "


def _try_import_rich():
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        from rich.align import Align
        from rich.console import Group
        return Console, Panel, Table, Text, Align, Group
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
    candidates = [checkout_root / "optional-skills" / "bioinformatics"]
    for d in candidates:
        if d.is_dir():
            return sum(1 for p in d.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    return 0


def _gateway_status() -> str:
    active = []
    for var, label in _GATEWAY_VARS:
        value = os.environ.get(var, "").strip()
        if value and not value.startswith("${"):
            active.append(label)
    if not active:
        return "⊘  CLI-only"
    if len(active) == 1:
        return f"●  {active[0]}"
    return f"●  {len(active)} channels ({', '.join(active[:3])}{'…' if len(active) > 3 else ''})"


def _shorten_path(p: Path, max_len: int = 50) -> str:
    """Shorten a path with ~ for $HOME and middle ellipsis if too long."""
    s = str(p)
    home = str(Path.home())
    if s.startswith(home):
        s = "~" + s[len(home):]
    if len(s) <= max_len:
        return s
    keep = max_len - 3
    return s[: keep // 2] + "…" + s[-(keep - keep // 2):]


def render(
    profile_dir: Path,
    checkout_root: Path,
    *,
    install_mode: str = "editable",
    version: str = "0.1.0a0",
) -> None:
    rich = _try_import_rich()
    if rich is None:
        return
    Console, Panel, Table, Text, Align, Group = rich

    console = Console(stderr=True, force_terminal=True)
    width = console.size.width

    # If terminal is too narrow even for the compact wordmark, skip splash
    # entirely — Hermes's own compact banner will take over.
    if width < 70:
        return

    cfg = _read_config(profile_dir)
    model = cfg.get("model") or {}
    provider = model.get("provider", "?")
    default_model = model.get("default", "?")

    smart_routing = cfg.get("smart_model_routing") or {}
    smart_enabled = smart_routing.get("enabled", False)
    cheap = smart_routing.get("cheap_model") or {}
    cheap_str = (
        f"→ {cheap.get('provider', '?')}/{cheap.get('model', '?')}"
        if smart_enabled
        else "off"
    )

    approvals = cfg.get("approvals") or {}
    approvals_mode = approvals.get("mode", "?")

    checkpoints = cfg.get("checkpoints") or {}
    checkpoints_str = "enabled" if checkpoints.get("enabled", False) else "off"

    mcp_servers = list((cfg.get("mcp_servers") or {}).keys())
    mcp_str = ", ".join(mcp_servers) if mcp_servers else "(none)"

    bio_skill_count = _count_bio_skills(checkout_root)
    outbox_n = _count_outbox(profile_dir)
    gateway = _gateway_status()
    profile_str = _shorten_path(profile_dir, 50)
    outbox_str = f"{_shorten_path(profile_dir / 'outbox', 50)}  ({outbox_n} files)"

    # ── Build content (vertical stack — no Table.grid) ─────────────────────
    content_parts = []

    # 1. Wordmark — solid teal-green color (no gradient → predictable widths)
    wordmark = Text()
    for line in WORDMARK:
        wordmark.append(line, style="bold #00ff9c")
        wordmark.append("\n")
    wordmark.append(
        "        bio skills × Hermes runtime",
        style="dim italic #00d4ff",
    )
    content_parts.append(Align.center(wordmark))

    # 2. Spacer
    content_parts.append(Text(""))

    # 3. DNA helix — single line, alternating colors per base pair
    dna = Text()
    # Color each segment differently so it looks like a helix
    segments = DNA_LINE.split("  ")  # split on double-space gaps between rungs
    palette = ["#00ff9c", "#00d4ff", "#7c5cff", "#00d4ff"]
    for i, seg in enumerate(segments):
        if seg.strip():
            dna.append(seg, style=f"bold {palette[i % len(palette)]}")
        if i < len(segments) - 1:
            dna.append("  ")
    content_parts.append(Align.center(dna))

    # 4. Spacer
    content_parts.append(Text(""))

    # 5. Status grid (single column, simple key:value rows)
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold #00ffaa", no_wrap=True, min_width=14)
    grid.add_column(style="#e0fff8")

    grid.add_row("🔬  Provider",    f"{provider} · {default_model}")
    grid.add_row("🧪  Smart route", f"{cheap_str}")
    grid.add_row("🛡   Approvals",   f"mode = {approvals_mode}")
    grid.add_row("💾  Checkpoints", checkpoints_str)
    grid.add_row("🧬  Bio skills",  f"{bio_skill_count} workflows")
    grid.add_row("⚗   MCP shim",    mcp_str)
    grid.add_row("📡  Gateway",     gateway)
    grid.add_row("🗂   Outbox",      outbox_str)
    grid.add_row("🏠  Profile",     profile_str)
    grid.add_row("📦  Install",     f"{install_mode} · v{version}")
    content_parts.append(Align.center(grid))

    # ── Compose panel ──────────────────────────────────────────────────────
    body = Group(*content_parts)
    panel = Panel(
        body,
        border_style="#00d9b2",
        padding=(1, 2),
        title=Text(" 🧬 BIOHERMES 🧬 ", style="bold #00ff9c on #0a1f1a"),
        title_align="center",
        subtitle=Text(
            "type /skills · /help · or describe what you want",
            style="dim #5a8a8a",
        ),
        subtitle_align="center",
    )

    try:
        console.print()
        console.print(panel)
        console.print()
        if os.environ.get("BIOHERMES_NO_ANIMATION", "").strip() not in {"1", "true", "yes"}:
            _boot_animation(console)
    except Exception:
        return


def _boot_animation(console) -> None:
    """Brief 'booting' sequence shown below the static splash panel.

    Total runtime ~750ms.  Disabled by `BIOHERMES_NO_ANIMATION=1`.
    Cycles through bio emoji + status messages, then collapses to a
    one-line "ready" tick before yielding to Hermes.

    Implementation note: uses Rich's Live for in-place updates instead
    of separate prints, so the final terminal state is just one short
    "✓ ready" line — no scrollback noise.
    """
    import time
    try:
        from rich.live import Live
        from rich.text import Text
        from rich.spinner import Spinner
        from rich.console import Group
    except ImportError:
        return

    # Stages: each (emoji, message, duration_seconds)
    stages = [
        ("🧬", "initializing bioinformatics agent",  0.20),
        ("🔬", "loading 40 bio skills",              0.18),
        ("⚗",  "wiring mcp_bioclaw shim",            0.15),
        ("📡", "checking gateway channels",          0.12),
        ("🧪", "ready",                              0.05),
    ]

    def _frame(emoji: str, msg: str, dots: int) -> Text:
        out = Text()
        out.append("    ")
        out.append(f"  {emoji}  ", style="bold #00ff9c")
        out.append(msg, style="#00d4ff")
        out.append("." * dots, style="dim #5a8a8a")
        out.append(" " * (4 - dots), style="")  # avoid jitter
        return out

    try:
        with Live(
            _frame("🧬", "initializing bioinformatics agent", 0),
            console=console,
            refresh_per_second=20,
            transient=True,  # erase the live region when we exit (clean handoff)
        ) as live:
            for emoji, msg, dur in stages:
                # Animate dots growing during this stage
                steps = max(1, int(dur / 0.05))
                for i in range(steps):
                    dots = i % 4
                    live.update(_frame(emoji, msg, dots))
                    time.sleep(dur / steps)
        # After live exits, leave a single "ready" line as the final mark
        ready = Text()
        ready.append("    ")
        ready.append("  ✓  ", style="bold #00ff9c")
        ready.append("BioHermes ready", style="bold #00d4ff")
        ready.append("  →  handing off to chat", style="dim #5a8a8a")
        console.print(ready)
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
