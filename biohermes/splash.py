"""biohermes/splash.py — pre-launch BioHermes splash screen.

Shows a bio-themed ASCII DNA helix + live status panel before handing
control to Hermes's chat TUI.  Reads the active profile config to show
provider / model / smart-routing / MCP / outbox / gateway state.

Designed to be:
  - Quick (renders once, no blocking sleep)
  - Skipped silently for non-interactive invocations
    (`-q`, piped stdin, `--no-splash` flag)
  - Forgiving — if anything fails (missing config, no Rich, etc.)
    splash silently aborts; the agent still launches
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


# Hermes gateway env vars the shim watches; used here to summarize gateway state.
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


# ASCII DNA helix art — six "rungs" of base pairs with curving phosphate
# backbone.  Renders with foreground colors for visual depth.
DNA_ART = [
    "  G═══C ╲╱",
    "        ╳ ",
    "  T═══A ╱╲",
    "        ╳ ",
    "  C═══G ╲╱",
    "        ╳ ",
    "  A═══T ╱╲",
]


# Big BIOHERMES letters in a thin stylized form (uses box-drawing characters,
# no extra deps).  Rendered with a horizontal color gradient.
WORDMARK = [
    "  ┌─┐ ┬ ┌─┐ ┬ ┬ ┌─┐ ┬─┐ ┌┬┐ ┌─┐ ┌─┐",
    "  ├┴┐ │ │ │ ├─┤ ├┤  ├┬┘ │││ ├┤  └─┐",
    "  └─┘ ┴ └─┘ ┴ ┴ └─┘ ┴└─ ┴ ┴ └─┘ └─┘",
]


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
    """Read the seeded config.yaml; tolerate missing or invalid YAML."""
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
    """Count migrated bio skills if visible from this layout."""
    candidates = [
        checkout_root / "optional-skills" / "bioinformatics",
        # In some layouts the bio skills could be elsewhere; only count
        # what we can see, no guesswork.
    ]
    for d in candidates:
        if d.is_dir():
            return sum(1 for p in d.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    return 0


def _gateway_status() -> str:
    """Return a short string about which gateways are wired."""
    active = []
    for var, label in _GATEWAY_VARS:
        value = os.environ.get(var, "").strip()
        if value and not value.startswith("${"):
            active.append(label)
    if not active:
        return "⊘  CLI-only (no gateway env detected)"
    if len(active) == 1:
        return f"●  {active[0]} channel ready"
    return f"●  {len(active)} channels ready ({', '.join(active[:3])}{'…' if len(active) > 3 else ''})"


def _gradient(text: str, start: str, end: str):
    """Horizontal color gradient across a single line.  Returns Rich Text."""
    from rich.text import Text
    from rich.color import Color

    out = Text()
    n = max(1, len(text) - 1)
    sr, sg, sb = bytes.fromhex(start.lstrip("#"))
    er, eg, eb = bytes.fromhex(end.lstrip("#"))
    for i, ch in enumerate(text):
        t = i / n
        r = int(sr + (er - sr) * t)
        g = int(sg + (eg - sg) * t)
        b = int(sb + (eb - sb) * t)
        out.append(ch, style=f"bold #{r:02x}{g:02x}{b:02x}")
    return out


def render(
    profile_dir: Path,
    checkout_root: Path,
    *,
    install_mode: str = "editable",
    version: str = "0.1.0a0",
) -> None:
    """Render the splash to stderr (so it doesn't pollute stdout pipes).

    Silently aborts on any rendering error.
    """
    rich = _try_import_rich()
    if rich is None:
        return  # No rich available — degrade silently
    Console, Panel, Table, Text, Align, Group = rich

    console = Console(stderr=True, force_terminal=True)
    if console.size.width < 60:
        # Terminal too narrow for the splash; skip
        return

    cfg = _read_config(profile_dir)
    model = (cfg.get("model") or {})
    provider = model.get("provider", "?")
    default_model = model.get("default", "?")

    smart_routing = (cfg.get("smart_model_routing") or {})
    smart_enabled = smart_routing.get("enabled", False)
    cheap = (smart_routing.get("cheap_model") or {})
    cheap_str = (
        f"{cheap.get('provider', '?')}/{cheap.get('model', '?')}"
        if smart_enabled
        else "off"
    )

    approvals = (cfg.get("approvals") or {})
    approvals_mode = approvals.get("mode", "?")

    checkpoints = (cfg.get("checkpoints") or {})
    checkpoints_on = checkpoints.get("enabled", False)

    mcp_servers = list((cfg.get("mcp_servers") or {}).keys())
    mcp_str = ", ".join(mcp_servers) if mcp_servers else "(none)"

    bio_skill_count = _count_bio_skills(checkout_root)
    outbox_n = _count_outbox(profile_dir)
    gateway = _gateway_status()

    # ── Wordmark ───────────────────────────────────────────────────────────
    wordmark = Text()
    for line in WORDMARK:
        wordmark.append_text(_gradient(line, "#00d9b2", "#7c5cff"))
        wordmark.append("\n")
    wordmark.append(_gradient("        bio skills × Hermes runtime", "#5a8a8a", "#00d4ff"))

    # ── DNA helix art on the side ──────────────────────────────────────────
    helix = Text()
    for i, line in enumerate(DNA_ART):
        # Alternate between teal and cyan for "AT/GC" feel
        color = "#00ff9c" if i % 2 == 0 else "#00d4ff"
        helix.append(line, style=f"bold {color}")
        helix.append("\n")

    # Layout: wordmark left, helix right (use a Table)
    head = Table.grid(padding=(0, 4), expand=True)
    head.add_column(ratio=2)
    head.add_column(justify="right", ratio=1)
    head.add_row(wordmark, helix)

    # ── Status grid ────────────────────────────────────────────────────────
    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold #00ffaa", no_wrap=True, width=14)
    grid.add_column(style="#e0fff8")

    def row(label: str, value: str) -> None:
        grid.add_row(f"{label}", value)

    row("🔬  Provider", f"{provider} · {default_model}")
    row("🧪  Smart route", f"cheap → {cheap_str}")
    row("🛡   Approvals",  f"mode = {approvals_mode}")
    row("💾  Checkpoints", "enabled" if checkpoints_on else "off")
    row("🧬  Bio skills",  f"{bio_skill_count} workflows under optional-skills/bioinformatics/")
    row("⚗   MCP shim",    mcp_str)
    row("📡  Gateway",     gateway)
    row("🗂   Outbox",      f"{profile_dir / 'outbox'}  ({outbox_n} files)")
    row("🏠  Profile",     str(profile_dir))
    row("📦  Install",     f"{install_mode} · v{version}")

    # ── Compose panel ──────────────────────────────────────────────────────
    body = Group(
        Align.center(head),
        Text(""),
        Align.left(grid),
        Text(""),
        Align.center(_gradient("                  Loading agent…", "#5a8a8a", "#00ff9c")),
    )

    panel = Panel(
        body,
        border_style="#00d9b2",
        padding=(1, 3),
        title=Text("BIOHERMES", style="bold #00ff9c"),
        title_align="left",
        subtitle=Text("type /skills, /help, or just describe what you want", style="dim #5a8a8a"),
        subtitle_align="right",
    )

    try:
        console.print()
        console.print(panel)
        console.print()
    except Exception:
        return  # Best-effort; never fail the launch over splash


def should_show(argv_rest: list[str]) -> bool:
    """Decide whether to render splash for this invocation.

    Show splash when:
      - the first non-flag argument is `chat` (or argv is empty meaning chat)
      - the user is on a TTY (interactive)
      - `-q` / `--query` is NOT present (those are one-shot mode)
      - `--no-splash` is NOT in argv
    """
    if "--no-splash" in argv_rest:
        return False
    if not sys.stderr.isatty():
        return False

    # First positional that isn't a flag
    cmd = None
    for arg in argv_rest:
        if arg.startswith("-"):
            continue
        cmd = arg
        break

    # Empty argv → default chat (Hermes drops you into chat with no args)
    if cmd is None:
        # Suppress splash for explicit pass-throughs that take no command
        # (e.g. `--version`, `--help`)
        if any(a in argv_rest for a in ("--version", "-V", "--help", "-h")):
            return False
        return True

    if cmd != "chat":
        return False

    # `chat -q "..."` is one-shot, skip splash
    return not any(a in argv_rest for a in ("-q", "--query"))
