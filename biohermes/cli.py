"""biohermes CLI entry point.

Python counterpart to `biohermes/bin/biohermes` (the bash wrapper).  Both
do the same thing: set `HERMES_HOME` to a BioHermes-scoped profile that
has the preset seeded, then exec `hermes`.  The Python entry is what
`pip install` exposes as the `biohermes` console script; it works for
both editable installs (`pip install -e .`) and non-editable installs
(`pip install .` / wheel).

Install layout resolution:
  - Editable install (`pip install -e .`) — the `biohermes` package
    lives inside the checkout.  `Path(__file__).parents[1]` resolves to
    the repo root, which has `config-examples/` and `optional-skills/`
    alongside the package.  The profile lives at
    `<repo>/.biohermes-profile/` (gitignored).
  - Non-editable install (`pip install .` or installed wheel) — the
    package lives in site-packages with no surrounding repo.  We read
    the preset from `biohermes/_preset_config.yaml` (package data) and
    put the profile at `~/.biohermes/` so it's always user-writable.

Seeding policy:
  - First launch — profile config absent → seed from the preset.
  - Subsequent launches — profile config present → NEVER overwrite.
  - Explicit reseed — pass `--reseed-biohermes` as the first argument,
    or run `biohermes-reseed` (same package).  Both back up the old
    config to `config.yaml.bak-<ts>` before re-emitting.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


_RESEED_FLAG = "--reseed-biohermes"

# Preset placeholders (templated at seed time).
_P_MCP_SHIM = "<biohermes-mcp-shim>"        # absolute path to mcp_bioclaw_server.py
_P_OUTBOX = "<biohermes-outbox>"             # absolute path to outbox dir
_P_SKILLS_DIR = "<biohermes-skills-dir>"     # absolute path to bundled bio skills


def _package_dir() -> Path:
    """Directory containing cli.py — `<repo>/biohermes/` in editable
    installs, `<site-packages>/biohermes/` in non-editable installs."""
    return Path(__file__).resolve().parent


def _resolve_layout() -> dict:
    """Figure out where the preset lives, where to seed the profile,
    and what absolute paths each placeholder expands to.

    Two install modes:
      - Editable (`pip install -e .`) or direct-checkout use — the
        repo root sits one level above the `biohermes/` package, and
        has `config-examples/` + `optional-skills/bioinformatics/`
        alongside it.  Profile is repo-local.
      - Non-editable (`pip install .` / installed wheel) — the
        package lives in site-packages with no surrounding repo and
        no `optional-skills/` dir (wheels don't ship that tree).
        Profile lives at `~/.biohermes/`.

    Returns a dict with keys:
      preset:        Path to the preset yaml to seed from
      profile_dir:   Path to the profile dir (HERMES_HOME)
      mcp_shim:      Path to mcp_bioclaw_server.py (always exists)
      outbox:        Path to the outbox dir (always inside profile)
      skills_dir:    Path to bundled bio skills, or None if not bundled
    """
    package_dir = _package_dir()
    repo_root_candidate = package_dir.parent
    dev_preset = repo_root_candidate / "config-examples" / "biohermes-cli-config.yaml"
    mcp_shim = package_dir / "mcp_bioclaw_server.py"

    if dev_preset.is_file():
        profile_dir = repo_root_candidate / ".biohermes-profile"
        skills_dir = repo_root_candidate / "optional-skills" / "bioinformatics"
        return {
            "preset": dev_preset,
            "profile_dir": profile_dir,
            "mcp_shim": mcp_shim,
            "outbox": profile_dir / "outbox",
            "skills_dir": skills_dir if skills_dir.is_dir() else None,
        }

    # Non-editable install — read preset from package data.
    package_preset = package_dir / "_preset_config.yaml"
    if not package_preset.is_file():
        sys.stderr.write(
            "biohermes: preset not found in repo checkout "
            f"({dev_preset}) nor in package data ({package_preset}).  "
            "Is this a broken install?\n"
        )
        sys.exit(1)
    profile_dir = Path.home() / ".biohermes"
    return {
        "preset": package_preset,
        "profile_dir": profile_dir,
        "mcp_shim": mcp_shim,
        "outbox": profile_dir / "outbox",
        "skills_dir": None,  # optional-skills/ not shipped in wheel
    }


def _seed_config(layout: dict) -> None:
    preset: Path = layout["preset"]
    target: Path = layout["profile_dir"] / "config.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)

    text = preset.read_text()
    text = text.replace(_P_MCP_SHIM, str(layout["mcp_shim"]))
    text = text.replace(_P_OUTBOX, str(layout["outbox"]))

    if layout["skills_dir"]:
        text = text.replace(_P_SKILLS_DIR, str(layout["skills_dir"]))
    else:
        # Strip the whole `skills.external_dirs:` block because the only
        # entry (our bundled bio skills dir) does not exist in this
        # install mode.  Regex: remove the `external_dirs:` line plus
        # any immediately-following `    - <biohermes-skills-dir>` line.
        import re
        text = re.sub(
            r"^[ \t]+external_dirs:\n[ \t]+-[ \t]*<biohermes-skills-dir>\n",
            "",
            text,
            flags=re.MULTILINE,
        )

    target.write_text(text)


def _ensure_seeded(layout: dict, *, force: bool) -> bool:
    """Seed the profile config from the preset iff it doesn't exist yet,
    or if `force` is True.  Returns True if a (re)seed happened."""
    target = layout["profile_dir"] / "config.yaml"
    if target.is_file() and not force:
        return False
    _seed_config(layout)
    return True


def _find_hermes_bin() -> str:
    """Prefer the `hermes` binary that belongs to this Python prefix —
    in a venv `sys.prefix/bin/hermes` is the one that matches this
    install's hermes-agent.  Using `sys.prefix` (not `sys.executable`)
    avoids following the venv's Python symlink out to the base install,
    which would miss the venv-local hermes.  Fall back to PATH search,
    and honor HERMES_BIN for unusual layouts.
    """
    override = os.environ.get("HERMES_BIN")
    if override:
        return override
    sibling = Path(sys.prefix) / "bin" / "hermes"
    if sibling.is_file() and os.access(sibling, os.X_OK):
        return str(sibling)
    found = shutil.which("hermes")
    if found:
        return found
    sys.stderr.write(
        "biohermes: `hermes` not found in this Python prefix "
        f"({sibling}) nor on PATH.  Install the BioHermes fork with "
        "`pip install .` (or `-e .`) from the repo root, or set HERMES_BIN.\n"
    )
    sys.exit(1)


def main() -> int:
    layout = _resolve_layout()

    argv_rest = list(sys.argv[1:])
    force_reseed = False
    if argv_rest and argv_rest[0] == _RESEED_FLAG:
        force_reseed = True
        argv_rest = argv_rest[1:]

    if _ensure_seeded(layout, force=force_reseed):
        if force_reseed:
            sys.stderr.write(
                f"biohermes: reseeded {layout['profile_dir']}/config.yaml from preset.\n"
            )

    os.environ["BIOHERMES_REPO"] = str(layout["profile_dir"].parent)
    os.environ["HERMES_HOME"] = str(layout["profile_dir"])

    hermes_bin = _find_hermes_bin()
    os.execv(hermes_bin, [hermes_bin, *argv_rest])


def reseed_main() -> int:
    """Standalone entry: `biohermes-reseed` reseeds the profile config
    from the current preset.  Backs up the old config to
    `config.yaml.bak-<ts>` first so edits are not lost outright.
    """
    import time
    layout = _resolve_layout()
    target = layout["profile_dir"] / "config.yaml"
    if target.is_file():
        backup = layout["profile_dir"] / f"config.yaml.bak-{int(time.time())}"
        target.rename(backup)
        sys.stderr.write(f"biohermes-reseed: backed up existing config to {backup}\n")
    _ensure_seeded(layout, force=True)
    sys.stderr.write(f"biohermes-reseed: wrote fresh config from preset to {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
