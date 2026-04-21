"""biohermes/_patch_branding.py — runtime monkey-patches that strip
remaining Hermes branding from the chat startup.

Two pieces upstream Hermes hardcodes that cannot be overridden via the
skin system:
  1. `hermes_cli.banner.format_banner_version_label()` — returns
     "Hermes Agent v0.10.0 ..." regardless of skin.
  2. `hermes_cli.banner.build_welcome_banner()` — renders the big
     panel with tools / skills / MCP listings.  Even with
     `display.compact: true` the panel still shows in some chat code
     paths (-q one-shot, parts of interactive setup) because they
     call build_welcome_banner directly without the show_banner()
     compact branch.

This module patches both at import time.  Safe to import; if the
target attributes don't exist (upstream renamed something), patches
silently no-op so launch never fails.

Apply by importing this module BEFORE hermes_cli.main runs — see
biohermes/cli.py which imports this then invokes
hermes_cli.main:main() in-process (instead of os.execv).
"""
from __future__ import annotations


def _patch_format_banner_version_label() -> None:
    """Replace the 'Hermes Agent v0.X.Y (date) · upstream <sha>' line."""
    try:
        from hermes_cli import banner as _banner_mod
    except ImportError:
        return
    if not hasattr(_banner_mod, "format_banner_version_label"):
        return

    _orig = _banner_mod.format_banner_version_label

    def _bio_label() -> str:
        # Try to keep the upstream version info as honest attribution but
        # lead with BioHermes.  If upstream raises, fall back to a static
        # BioHermes-only string.
        try:
            upstream = _orig()
        except Exception:
            upstream = ""
        # Strip the leading "Hermes Agent v..." marker; keep tail like
        # "· upstream <sha>" if present.
        tail = ""
        if "·" in upstream:
            tail = " · " + "·".join(upstream.split("·")[1:]).strip()
        return f"BioHermes v0.1.0a0 · runtime: Hermes{tail}"

    _banner_mod.format_banner_version_label = _bio_label


def _patch_build_welcome_banner() -> None:
    """Replace the big Hermes welcome panel with a single minimal status
    line.  The user already saw our splash + brand strip + boot animation;
    Hermes's tool / skill listing is redundant noise.
    """
    try:
        from hermes_cli import banner as _banner_mod
    except ImportError:
        return
    if not hasattr(_banner_mod, "build_welcome_banner"):
        return

    def _bio_banner(console, model: str = "", cwd: str = "", **_) -> None:
        # Minimal one-liner under our splash + brand strip.  Goes through
        # Rich for color but no Panel / Table — just a thin status line.
        try:
            from rich.text import Text
            t = Text()
            t.append("    ", style="")
            t.append("●", style="bold #00ff9c")
            t.append(" model ",   style="dim #5a8a8a")
            t.append(model or "?", style="bold #00d4ff")
            t.append("  ·  ",     style="dim #5a8a8a")
            t.append("/skills",   style="bold #00ffaa")
            t.append(" — list bio workflows  ·  ", style="dim #5a8a8a")
            t.append("/help",     style="bold #00ffaa")
            t.append(" — commands  ·  ",          style="dim #5a8a8a")
            t.append("type to start",             style="dim italic #5a8a8a")
            console.print()
            console.print(t)
            console.print()
        except Exception:
            # If rendering fails, print absolutely nothing rather than
            # leaking partial Hermes output.
            return

    _banner_mod.build_welcome_banner = _bio_banner


def apply() -> None:
    """Apply all branding patches.  Call once before hermes_cli.main:main()."""
    _patch_format_banner_version_label()
    _patch_build_welcome_banner()
