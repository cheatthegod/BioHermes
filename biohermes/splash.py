"""biohermes/splash.py — hero-style splash: big figlet banner + BIOS-POST
boot sequence with cyber-glitch reveal.

Visual grammar drawn from:
  - ANSI Shadow figlet font (the "official" cyberpunk CLI aesthetic)
  - BIOS POST / systemd boot ([  OK  ] / [ WARN ] status tags)
  - cmatrix / glitch-art — scramble-to-lock character reveal
  - Minecraft MOTD — » ★ decorative bracketing + ▮▮▮▮▯ ping bars
  - btop / bpytop — sparkline meters, bracketed section headers

Layout (top-to-bottom):
  1. GIANT ANSI-Shadow BIOHERMES banner — vertical gradient, column-sweep
     scramble-to-lock animation (~1.2s)
  2. Centered MC-MOTD subtitle
  3. ━━━ ⟦ SYSTEM BOOT · v0.1.0a0 ⟧ ━━━ cyber-separator
  4. BIOS-POST boot sequence — each line spins then locks to
     [  OK  ] / [ WARN ] tag, typed out sequentially
  5. ━━━ ⟦ READY ⟧ ━━━ closing separator
  6. Centered footer: ● READY ▸ /skills ▸ /help ▸ describe

Env:
  BIOHERMES_NO_ANIMATION=1 → skip animations, render static
  BIOHERMES_NO_SPARKLINE=1 → skip the activity sparkline line
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


# ── ANSI Shadow figlet banner (BIOHERMES) ─────────────────────────────────

_BANNER_LINES = (
    " ██████╗ ██╗ ██████╗ ██╗  ██╗███████╗██████╗ ███╗   ███╗███████╗███████╗",
    " ██╔══██╗██║██╔═══██╗██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝██╔════╝",
    " ██████╔╝██║██║   ██║███████║█████╗  ██████╔╝██╔████╔██║█████╗  ███████╗",
    " ██╔══██╗██║██║   ██║██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══╝  ╚════██║",
    " ██████╔╝██║╚██████╔╝██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗███████║",
    " ╚═════╝ ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝",
)
_BANNER_WIDTH = max(len(L) for L in _BANNER_LINES)

# Vertical gradient for banner rows: neon green → teal → cyan → purple
_BANNER_PALETTE = (
    "#00ff9c",
    "#00ffaa",
    "#00d9b2",
    "#00d4ff",
    "#5da8ff",
    "#7c5cff",
)

# Cyber-glitch scramble characters shown for unlocked cells during reveal
_SCRAMBLE_CHARS = "█▓▒░#@$%*+◼◻▪▫"

# Sparkline block chars (8 levels)
_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


# ── Skill classifier → 6 canonical categories ─────────────────────────────

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
        from rich.align import Align
        from rich.console import Console, Group
        from rich.live import Live
        from rich.text import Text
        return {
            "Console": Console, "Group": Group, "Text": Text,
            "Align": Align, "Live": Live,
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


def _shorten_path(p: Path, max_len: int = 46) -> str:
    s = str(p)
    home = str(Path.home())
    if s.startswith(home):
        s = "~" + s[len(home):]
    if len(s) <= max_len:
        return s
    return s[: max_len // 2 - 1] + "…" + s[-(max_len - max_len // 2):]


def _session_activity(profile_dir: Path, days: int = 14) -> list[int]:
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


def _category_counts(skill_names: list[str]) -> list[tuple[str, int]]:
    buckets: dict[str, int] = {}
    for n in skill_names:
        c = _classify(n)
        buckets[c] = buckets.get(c, 0) + 1
    order = ["sequence db", "genomics", "structural", "proteomics", "manuscript", "meta"]
    return [(c, buckets[c]) for c in order if buckets.get(c, 0) > 0]


def _ping_bars(strength: int) -> str:
    strength = max(0, min(5, strength))
    return "▮" * strength + "▯" * (5 - strength)


# ── Figlet banner renderer ────────────────────────────────────────────────

def _figlet_banner(R, progress: float, rng: random.Random):
    """ANSI Shadow BIOHERMES with column-sweep reveal.
    progress=0.0 → all scramble; progress=1.0 → all locked.
    Locked cells use per-row gradient color; unlocked flicker dim scramble.
    """
    Text = R["Text"]
    lock_col = int(progress * _BANNER_WIDTH) + 1
    t = Text(no_wrap=True)
    for row_idx, line in enumerate(_BANNER_LINES):
        color = _BANNER_PALETTE[row_idx]
        for col_idx, ch in enumerate(line):
            if ch == " ":
                t.append(" ")
                continue
            if col_idx < lock_col:
                t.append(ch, style=f"bold {color}")
            else:
                t.append(rng.choice(_SCRAMBLE_CHARS), style="#2a4444")
        if row_idx < len(_BANNER_LINES) - 1:
            t.append("\n")
    return t


# ── Section separators ────────────────────────────────────────────────────

def _section_separator(R, label: str, width: int, accent: str = "#00ff9c"):
    Text = R["Text"]
    inner = f" ⟦ {label} ⟧ "
    pad = max(6, width - len(inner))
    left = pad // 2
    right = pad - left
    t = Text(no_wrap=True)
    t.append("━" * left, style="#00d9b2")
    t.append(" ⟦ ", style="#00d4ff")
    t.append(label, style=f"bold {accent}")
    t.append(" ⟧ ", style="#00d4ff")
    t.append("━" * right, style="#00d9b2")
    return t


# ── Subtitle (MC-MOTD style) ──────────────────────────────────────────────

def _subtitle(R, version: str, install_mode: str):
    Text = R["Text"]
    Align = R["Align"]
    t = Text(no_wrap=True)
    t.append("» ", style="bold #ffd24d")
    t.append("bioinformatics edition", style="bold #00ffaa")
    t.append("  ·  ", style="dim #5a8a8a")
    t.append("built on ", style="dim #5a8a8a")
    t.append("BioClaw", style="bold #7c5cff")
    t.append("  ·  ", style="dim #5a8a8a")
    t.append("powered by ", style="dim #5a8a8a")
    t.append("Hermes Agent", style="bold #00d4ff")
    t.append(f"  v{version}", style="dim #5a8a8a")
    t.append("  ·  ", style="dim #5a8a8a")
    t.append(install_mode, style="dim italic #5a8a8a")
    t.append(" «", style="bold #ffd24d")
    return Align.center(t)


# ── Footer ────────────────────────────────────────────────────────────────

def _footer(R):
    Text = R["Text"]
    Align = R["Align"]
    t = Text(no_wrap=True)
    t.append("● ", style="bold #00ff9c")
    t.append("READY", style="bold #00ff9c")
    t.append("  ▸  ", style="#5a8a8a")
    t.append("/skills", style="bold #00ffaa")
    t.append("  ▸  ", style="#5a8a8a")
    t.append("/help", style="bold #00ffaa")
    t.append("  ▸  ", style="#5a8a8a")
    t.append("or just describe what you want", style="italic #00d4ff")
    return Align.center(t)


# ── BIOS-POST boot lines ──────────────────────────────────────────────────

def _boot_lines(profile_dir, cfg, skill_names, activity, cat_counts):
    """Generate BIOS POST style (status, message) tuples."""
    lines = []

    lines.append(("OK", f"mount profile      {_shorten_path(profile_dir)}"))
    lines.append(("OK", "load runtime       Hermes Agent · in-process"))

    n_skills = len(skill_names)
    if n_skills:
        abbr = {"sequence db": "seq", "genomics": "gen", "structural": "str",
                "proteomics": "prot", "manuscript": "ms", "meta": "meta"}
        cat_summary = " · ".join(f"{abbr.get(c, c)} {n}" for c, n in cat_counts)
        lines.append(("OK", f"register skills    {n_skills}/{n_skills}  ·  {cat_summary}"))
    else:
        lines.append(("WARN", "register skills    0 (optional-skills/bioinformatics missing)"))

    mcps = list((cfg.get("mcp_servers") or {}).keys())
    if mcps:
        mcp_str = ", ".join(mcps) if len(mcps) <= 3 else f"{', '.join(mcps[:3])} …"
        lines.append(("OK", f"register MCP       {len(mcps)}/∞  ·  {mcp_str}"))
    else:
        lines.append(("OK", "register MCP       0/∞  (none configured)"))

    gws = _active_gateways()
    total = len(_GATEWAY_VARS)
    if not gws:
        lines.append(("WARN",
            f"gateway            0/{total}  ·  CLI-only (set *_HOME_CHANNEL to relay)"))
    else:
        gw_str = ", ".join(gws[:4]) + (" …" if len(gws) > 4 else "")
        lines.append(("OK", f"gateway            {len(gws)}/{total}  ·  {gw_str}"))

    sr = cfg.get("smart_model_routing") or {}
    if sr.get("enabled"):
        cheap = (sr.get("cheap_model") or {}).get("model", "?")
        lines.append(("OK", f"smart routing      → {cheap}"))
    else:
        lines.append(("OK", "smart routing      disabled"))

    model = cfg.get("model") or {}
    prov = model.get("provider", "?")
    mdl = model.get("default", "?")
    lines.append(("OK", f"provider           {prov} · {mdl}  ▮▮▮▮▯"))

    ap = cfg.get("approvals") or {}
    cp = cfg.get("checkpoints") or {}
    lines.append(("OK",
        f"policy             approvals {ap.get('mode', 'manual')}  ·  "
        f"checkpoints {'on' if cp.get('enabled') else 'off'}"))

    if activity is not None and sum(activity) > 0:
        spark = _sparkline(activity)
        total_sessions = sum(activity)
        lines.append(("OK", f"activity 14d       {spark}   {total_sessions} sessions"))

    obn = _count_outbox(profile_dir)
    if obn > 0:
        lines.append(("OK", f"outbox             {obn} file{'s' if obn != 1 else ''} pending delivery"))

    return lines


# ── BIOS-POST row rendering + animation ───────────────────────────────────

_BOOT_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_STATUS_COLOR = {"OK": "#00ff9c", "WARN": "#ffd24d", "FAIL": "#ff4d6d"}
_STATUS_TAG   = {"OK": "  OK  ",  "WARN": " WARN ", "FAIL": " FAIL "}


def _render_boot_row(R, row, done: bool, spinner_phase: int):
    Text = R["Text"]
    status, msg = row
    t = Text(no_wrap=True)
    if done:
        t.append("  [", style="#5a8a8a")
        t.append(_STATUS_TAG[status], style=f"bold {_STATUS_COLOR[status]}")
        t.append("]  ", style="#5a8a8a")
        t.append(msg, style="#e0fff8")
    else:
        t.append("  [ ", style="#5a8a8a")
        t.append(_BOOT_SPINNER[spinner_phase % len(_BOOT_SPINNER)], style="bold #00d4ff")
        t.append(" .. ", style="dim #00d4ff")
        t.append("]  ", style="#5a8a8a")
        t.append(msg, style="dim italic #5a8a8a")
    return t


def _render_boot_anim(R, console, lines):
    Live = R["Live"]
    Group = R["Group"]

    done_count = 0

    def frame():
        phase = int(time.time() * 12) % len(_BOOT_SPINNER)
        return Group(*[
            _render_boot_row(R, row, i < done_count, phase)
            for i, row in enumerate(lines)
        ])

    with Live(frame(), console=console, refresh_per_second=24,
              transient=False) as live:
        for _ in range(len(lines)):
            for _f in range(3):
                live.update(frame())
                time.sleep(1 / 24)
            done_count += 1
            live.update(frame())
            time.sleep(1 / 60)


# ── Figlet animation ──────────────────────────────────────────────────────

def _render_figlet_anim(R, console):
    Live = R["Live"]
    Align = R["Align"]
    rng = random.Random(0xB1053)

    frames = 28
    with Live(Align.center(_figlet_banner(R, 0.0, rng)),
              console=console, refresh_per_second=24,
              transient=False) as live:
        for f in range(frames + 1):
            progress = min(1.0, f / frames)
            live.update(Align.center(_figlet_banner(R, progress, rng)))
            time.sleep(1 / 24)


# ── Main entry ────────────────────────────────────────────────────────────

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
    Align = R["Align"]

    console = Console(stderr=True, force_terminal=True)
    w = console.size.width
    # Figlet banner is ~73 cols — bail on narrow terminals
    if w < 80:
        return

    skill_names = _bio_skills(checkout_root)
    cfg = _read_config(profile_dir)
    show_spark = os.environ.get("BIOHERMES_NO_SPARKLINE", "").strip() not in {"1", "true", "yes"}
    activity = _session_activity(profile_dir) if show_spark else None
    cat_counts = _category_counts(skill_names) if skill_names else []
    boot = _boot_lines(profile_dir, cfg, skill_names, activity, cat_counts)
    animate = os.environ.get("BIOHERMES_NO_ANIMATION", "").strip() not in {"1", "true", "yes"}

    try:
        console.print()
        if animate:
            _render_figlet_anim(R, console)
        else:
            rng = random.Random(0xB1053)
            console.print(Align.center(_figlet_banner(R, 1.0, rng)))
        console.print()
        console.print(_subtitle(R, version, install_mode))
        console.print()
        console.print(_section_separator(R, f"SYSTEM BOOT · v{version}", w))
        if animate:
            _render_boot_anim(R, console, boot)
        else:
            for row in boot:
                console.print(_render_boot_row(R, row, True, 0))
        console.print(_section_separator(R, "READY", w, accent="#00ff9c"))
        console.print()
        console.print(_footer(R))
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
