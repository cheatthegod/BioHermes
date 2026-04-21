"""biohermes/splash.py — neofetch-style splash with glitch reveal,
activity sparkline, and skill-category bar chart.

Visual inspiration drawn from popular cool-terminal projects:
  - neofetch / fastfetch / hyfetch — 2-column logo + info
  - btop / bpytop — sparklines, gauges, dense meters
  - cmatrix / Mr. Robot aesthetic — glitch character cycling
  - lazygit / k9s — multi-pane dashboards
  - starship / powerlevel10k — segmented prompts with colored separators
  - gum / glow (charmbracelet) — elegant panels with consistent styling

Layout:
  - Title (glitch-revealed): BIOHERMES wordmark cycles random chars
    into place over ~500ms
  - Left column: gradient vertical DNA helix
  - Right column: status rows with ● reveal animation
  - Below panel: activity sparkline (last 14 days of sessions)
    + skill category distribution with inline bar chart

Env:
  BIOHERMES_NO_ANIMATION=1 → skip animations, render static
  BIOHERMES_NO_SPARKLINE=1 → skip the activity sparkline block
"""
from __future__ import annotations

import os
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


# ── Gateway env vars ───────────────────────────────────────────────────────
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

# ── Visual assets ──────────────────────────────────────────────────────────

# Vertical DNA double helix, 11 rows × 11 cols
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

# Gradient colors walking down the helix: teal → green → cyan → purple → teal
_HELIX_PALETTE = [
    "#00d9b2", "#00d9b2", "#00ffaa", "#00ff9c", "#00ff9c",
    "#00d4ff", "#7c5cff", "#7c5cff", "#00d4ff", "#00d9b2", "#00d9b2",
]

# Compact inline BIOHERMES title — 1 line, small footprint
_TITLE = "BIOHERMES"

# Characters the glitch animation cycles through before "locking in"
_GLITCH_ALPHABET = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$%&*+?!<>[]{}")

# Sparkline block chars, 8 levels low → high
_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"

# Bar chart block chars, 9 levels (includes full + space)
_BAR_BLOCKS = " ▏▎▍▌▋▊▉█"


# ── Skill classifier → category counts (cheap static categorization) ───────

# Prefix / contains substring → category.  Matches the 6 categories in
# README.  Order matters for overlap (manuscript checked before bio-*).
_SKILL_CATEGORIES = [
    ("manuscript", "bio-manuscript"),
    ("manuscript", "report-template"),
    ("manuscript", "bio-figure-design"),
    ("manuscript", "bio-ppt-generate"),
    ("sequence db", "query-"),
    ("sequence db", "pubmed"),
    ("genomics",   "atac-seq"),
    ("genomics",   "chip-seq"),
    ("genomics",   "scrna"),
    ("genomics",   "cell-annotation"),
    ("genomics",   "differential-expression"),
    ("genomics",   "metagenomics"),
    ("genomics",   "sequence-analysis"),
    ("genomics",   "blast-search"),
    ("structural", "structural-biology"),
    ("structural", "query-alphafold"),
    ("proteomics", "proteomics"),
    ("proteomics", "sec-report"),
    ("proteomics", "sds-gel-review"),
]


def _classify(skill_name: str) -> str:
    n = skill_name.lower()
    for cat, needle in _SKILL_CATEGORIES:
        if needle in n:
            return cat
    return "meta"


# ── Rich import guard ──────────────────────────────────────────────────────

def _try_import_rich():
    try:
        from rich.console import Console, Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        from rich.align import Align
        from rich.live import Live
        return {
            "Console": Console, "Group": Group, "Panel": Panel,
            "Table": Table, "Text": Text, "Align": Align, "Live": Live,
        }
    except ImportError:
        return None


# ── Data collection ───────────────────────────────────────────────────────

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


def _bio_skills(checkout_root: Path) -> list[str]:
    for d in [checkout_root / "optional-skills" / "bioinformatics"]:
        if d.is_dir():
            return [p.name for p in d.iterdir()
                    if p.is_dir() and (p / "SKILL.md").is_file()]
    return []


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


def _session_activity(profile_dir: Path, days: int = 14) -> list[int]:
    """Count sessions per day for the last `days` days.  Reads session
    JSON filenames (format: session_YYYYMMDD_HHMMSS_xxxxxx.json).
    Returns a list length `days`, oldest first.
    """
    sessions_dir = profile_dir / "sessions"
    counts = [0] * days
    if not sessions_dir.is_dir():
        return counts
    today = datetime.now().date()
    pat = re.compile(r"session_(\d{8})_")
    for f in sessions_dir.iterdir():
        m = pat.match(f.name)
        if not m:
            continue
        try:
            d = datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            continue
        age = (today - d).days
        if 0 <= age < days:
            counts[days - 1 - age] += 1
    return counts


def _sparkline(values: list[int]) -> str:
    if not values:
        return ""
    peak = max(values)
    if peak == 0:
        return _SPARK_BLOCKS[0] * len(values)
    out = []
    for v in values:
        if v == 0:
            out.append(" ")
        else:
            idx = min(len(_SPARK_BLOCKS) - 1, int(v / peak * (len(_SPARK_BLOCKS) - 1)))
            out.append(_SPARK_BLOCKS[idx])
    return "".join(out)


def _skill_category_bars(skill_names: list[str]) -> list[tuple[str, int, str]]:
    """Bucket bio skills into categories + render a tiny bar chart.
    Returns list of (category, count, bar_string)."""
    buckets: dict[str, int] = {}
    for n in skill_names:
        c = _classify(n)
        buckets[c] = buckets.get(c, 0) + 1
    if not buckets:
        return []
    total = sum(buckets.values())
    order = ["sequence db", "genomics", "structural", "proteomics", "manuscript", "meta"]
    out = []
    for cat in order:
        n = buckets.get(cat, 0)
        if n == 0:
            continue
        # 12-column bar width; each column is 8 subpixel levels via _BAR_BLOCKS
        sub = (n / total) * 12 * (len(_BAR_BLOCKS) - 1)
        full = int(sub // (len(_BAR_BLOCKS) - 1))
        rem = int(sub % (len(_BAR_BLOCKS) - 1))
        bar = "█" * full + _BAR_BLOCKS[rem]
        out.append((cat, n, bar))
    return out


# ── Status rows ────────────────────────────────────────────────────────────

def _collect_status_rows(profile_dir: Path, skill_names: list[str]) -> list[tuple[str, str]]:
    cfg = _read_config(profile_dir)
    model = cfg.get("model") or {}
    prov = model.get("provider", "?")
    mdl = model.get("default", "?")
    prov_model = f"{prov} · {mdl}"
    if len(prov_model) > 42:
        prov_model = prov_model[:41] + "…"

    sr = cfg.get("smart_model_routing") or {}
    if sr.get("enabled"):
        cheap = sr.get("cheap_model") or {}
        smart = f"→ {cheap.get('model', '?')}"
    else:
        smart = "off"

    ap = cfg.get("approvals") or {}
    approvals = ap.get("mode", "manual")

    cp = cfg.get("checkpoints") or {}
    ckpt = "enabled" if cp.get("enabled", False) else "off"

    # MC-MOTD-style counts: "N/M" or "N/∞"
    bio_n = len(skill_names)
    bio_str = f"{bio_n}/{bio_n} workflows" if bio_n else "0/0 (not bundled)"

    mcp_servers = list((cfg.get("mcp_servers") or {}).keys())
    mcp_str = f"{len(mcp_servers)}/∞  {', '.join(mcp_servers)}" if mcp_servers else "0/∞  (none)"

    gws = _active_gateways()
    total_gws = len(_GATEWAY_VARS)
    if not gws:
        gw = f"0/{total_gws}  ⊘ CLI-only"
    elif len(gws) == 1:
        gw = f"1/{total_gws}  ● {gws[0]}"
    else:
        gw = f"{len(gws)}/{total_gws}  ● {', '.join(gws[:3])}" + (" …" if len(gws) > 3 else "")

    obn = _count_outbox(profile_dir)

    # Ping-bar indicators ▮▮▮▮▯ (MC server status style)
    provider_bars = _ping_bars(4)   # assume healthy default
    smart_bars = _ping_bars(5 if sr.get("enabled") else 0)
    gw_bars = _ping_bars(min(5, len(gws)))

    return [
        ("Runtime",      "Hermes Agent · in-process", ""),
        ("Provider",     prov_model, provider_bars),
        ("Smart route",  smart, smart_bars),
        ("Approvals",    approvals, ""),
        ("Checkpoints",  ckpt, ""),
        ("Bio skills",   bio_str, ""),
        ("MCP tools",    mcp_str, ""),
        ("Gateway",      gw, gw_bars),
        ("Profile",      _shorten_path(profile_dir), ""),
        ("Outbox",       f"{obn} files", ""),
    ]


def _ping_bars(strength: int) -> str:
    """MC-style ping indicator: 5 vertical bars, filled by strength 0-5."""
    strength = max(0, min(5, strength))
    return "▮" * strength + "▯" * (5 - strength)


# ── Rendering primitives ───────────────────────────────────────────────────

def _colored_helix(R):
    t = R["Text"]()
    for i, line in enumerate(DNA_HELIX):
        color = _HELIX_PALETTE[i % len(_HELIX_PALETTE)]
        t.append(line, style=f"bold {color}")
        if i < len(DNA_HELIX) - 1:
            t.append("\n")
    return t


def _status_frame(R, rows: list[tuple[str, str, str]], revealed: int):
    Table = R["Table"]
    Text = R["Text"]
    grid = Table.grid(padding=(0, 1))
    grid.add_column(no_wrap=True, width=1)
    grid.add_column(no_wrap=True, width=12, style="bold #00d4ff")
    grid.add_column(overflow="ellipsis")
    grid.add_column(no_wrap=True, width=5)  # ping bars

    spinner_chars = "◐◓◑◒"
    phase = int(time.time() * 10) % len(spinner_chars)
    for i, row in enumerate(rows):
        label, value, bars = row if len(row) == 3 else (row[0], row[1], "")
        if i < revealed:
            dot = Text("●", style="bold #00ff9c")
            val = Text(value, style="#e0fff8")
            # colorize ping bars: filled=green, empty=dim
            bar_text = Text()
            for ch in bars:
                if ch == "▮":
                    bar_text.append(ch, style="bold #00ff9c")
                else:
                    bar_text.append(ch, style="dim #334444")
        else:
            dot = Text(spinner_chars[phase], style="dim #5a8a8a")
            val = Text("checking…", style="dim italic #5a8a8a")
            bar_text = Text("▯▯▯▯▯", style="dim #334444")
        grid.add_row(dot, Text(label, style="bold #00d4ff"), val, bar_text)
    return grid


def _glitch_title(R, locked_mask: list[bool], rng: random.Random) -> "object":
    """Render BIOHERMES with unlocked chars showing random cycling glyphs."""
    Text = R["Text"]
    t = Text()
    t.append("  🧬  ", style="bold #00ff9c")
    for i, ch in enumerate(_TITLE):
        if locked_mask[i]:
            t.append(ch, style="bold #00ff9c")
        else:
            # unlocked: pick a random glyph, flicker dim
            g = rng.choice(_GLITCH_ALPHABET)
            t.append(g, style="bold #5a8a8a")
    return t


def _motd_header(R, console_width: int, version: str):
    """MC-MOTD-style two-line header: rainbow bracketed title + subtitle.
    Rendered above the main panel.  Centered to the console width.
    """
    Text = R["Text"]
    Align = R["Align"]
    Group = R["Group"]

    # Line 1: » ★ B I O H E R M E S ★ «   (gradient colors across letters)
    title_palette = [
        "#00ff9c", "#00ffaa", "#00d9b2", "#00d4ff",
        "#00d4ff", "#7c5cff", "#a07fff", "#00d9b2", "#00ff9c",
    ]
    line1 = Text()
    line1.append("» ", style="bold #00d9b2")
    line1.append("★ ", style="bold #ffd24d")
    for i, ch in enumerate(_TITLE):
        color = title_palette[i % len(title_palette)]
        line1.append(ch, style=f"bold {color}")
        if i < len(_TITLE) - 1:
            line1.append(" ", style="")
    line1.append(" ★", style="bold #ffd24d")
    line1.append(" «", style="bold #00d9b2")

    # Line 2: subtitle — dim gray, MC server-description style
    line2 = Text()
    line2.append("A ", style="dim #5a8a8a")
    line2.append("bioinformatics", style="bold #00ffaa")
    line2.append(" edition  ·  ", style="dim #5a8a8a")
    line2.append("built on ", style="dim #5a8a8a")
    line2.append("BioClaw", style="bold #7c5cff")
    line2.append("  ·  ", style="dim #5a8a8a")
    line2.append("powered by ", style="dim #5a8a8a")
    line2.append("Hermes Agent", style="bold #00d4ff")
    line2.append(f"  v{version}", style="dim italic #5a8a8a")

    return Group(Align.center(line1), Align.center(line2))


def _full_title(R, version: str, install_mode: str):
    # Compact panel title — the MC-MOTD header above carries the brand.
    Text = R["Text"]
    t = Text()
    t.append("  🧬 ", style="bold #00ff9c")
    t.append("server status", style="bold #00d4ff")
    t.append("  ·  ", style="dim #5a8a8a")
    t.append(install_mode, style="dim italic #5a8a8a")
    t.append("  ")
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


def _activity_block(R, activity: list[int]):
    """Return a Text line with sparkline + stat summary."""
    Text = R["Text"]
    spark = _sparkline(activity)
    total = sum(activity)
    t = Text()
    t.append("  ", style="")
    t.append("activity ", style="bold #00d4ff")
    t.append("last 14 days  ", style="dim #5a8a8a")
    t.append(spark, style="bold #00ff9c")
    t.append(f"   {total} sessions", style="dim #00d4ff")
    return t


def _category_block(R, bars: list[tuple[str, int, str]]):
    """Return a Group of per-category bar chart rows."""
    Text = R["Text"]
    Table = R["Table"]
    grid = Table.grid(padding=(0, 1))
    grid.add_column(no_wrap=True, width=12, style="bold #00d4ff")
    grid.add_column(no_wrap=True, style="bold #7c5cff")   # count
    grid.add_column(style="bold #00ffaa")                 # bar
    for cat, n, bar in bars:
        grid.add_row(
            Text(cat, style="bold #00d4ff"),
            Text(f"{n:>2}", style="bold #e0fff8"),
            Text(bar, style="bold #00ffaa"),
        )
    return grid


def _build_panel(R, revealed: int, title_widget, rows, activity, bars):
    Table = R["Table"]
    Group = R["Group"]
    Panel = R["Panel"]
    Text = R["Text"]

    helix = _colored_helix(R)
    status = _status_frame(R, rows, revealed)
    layout = Table.grid(padding=(0, 3))
    layout.add_column(no_wrap=True)
    layout.add_column(ratio=1)
    layout.add_row(helix, status)

    body_parts = [Text(""), layout]
    if activity is not None:
        body_parts += [Text(""), _activity_block(R, activity)]
    if bars:
        body_parts += [
            Text("  skill categories", style="bold #00d4ff"),
            _category_block(R, bars),
        ]
    body_parts += [Text(""), _footer_text(R)]

    return Panel(
        Group(*body_parts),
        border_style="#00d9b2",
        padding=(0, 2),
        title=title_widget,
        title_align="left",
        subtitle=Text(
            "type /skills · /help · or describe your bio task",
            style="dim italic #5a8a8a",
        ),
        subtitle_align="right",
    )


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
    Live = R["Live"]

    console = Console(stderr=True, force_terminal=True)
    if console.size.width < 70:
        return

    skill_names = _bio_skills(checkout_root)
    rows = _collect_status_rows(profile_dir, skill_names)
    show_spark = os.environ.get("BIOHERMES_NO_SPARKLINE", "").strip() not in {"1", "true", "yes"}
    activity = _session_activity(profile_dir) if show_spark else None
    bars = _skill_category_bars(skill_names) if skill_names else []

    animate = os.environ.get("BIOHERMES_NO_ANIMATION", "").strip() not in {"1", "true", "yes"}
    final_title = _full_title(R, version, install_mode)
    motd = _motd_header(R, console.size.width, version)

    try:
        console.print()
        console.print(motd)
        console.print()
        if animate:
            rng = random.Random(42)  # deterministic glitch for nicer feel
            # Glitch-reveal phase: title locks in char-by-char,
            # status rows reveal in sync
            locked = [False] * len(_TITLE)
            n_title = len(_TITLE)
            n_rows = len(rows)
            # total frames: max(title_reveal_frames, rows_reveal_frames)
            frames = max(n_title * 3, n_rows + 3)
            with Live(
                _build_panel(R, 0, _glitch_title(R, locked, rng), rows, activity, bars),
                console=console,
                refresh_per_second=24,
                transient=False,
            ) as live:
                for f in range(frames):
                    # Title: lock one more char every 3 frames
                    if f % 3 == 0:
                        # lock the leftmost unlocked slot
                        for i in range(n_title):
                            if not locked[i]:
                                locked[i] = True
                                break
                    # Status rows: reveal one per frame
                    revealed = min(n_rows, f + 1)
                    # When all locked, use the full styled title
                    if all(locked):
                        title = final_title
                    else:
                        title = _glitch_title(R, locked, rng)
                    live.update(_build_panel(R, revealed, title, rows, activity, bars))
                    time.sleep(1 / 24)
        else:
            console.print(_build_panel(R, len(rows), final_title, rows, activity, bars))
        console.print()
    except Exception:
        return


def should_show(argv_rest: list[str]) -> bool:
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
