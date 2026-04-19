"""biohermes CLI entry point.

Python counterpart to `biohermes/bin/biohermes` (the bash wrapper).  Both
do the same thing: set `HERMES_HOME` to a project-local profile that has
the BioHermes bio preset seeded, then exec `hermes`.  The Python entry is
what `pip install -e .` exposes as the `biohermes` console script, so
users who install the fork get `biohermes` on PATH alongside `hermes`.

Seeding policy (updated after the "preset auto-reseed" finding):
  - First launch — profile config absent → seed from the preset.
  - Subsequent launches — profile config present → NEVER overwrite.
    The user may have edited `config.yaml` (e.g. `hermes config set`,
    `/memory` changes, personal additions) and silent re-seeding on
    every `git pull` that happens to touch the preset would clobber
    those edits.
  - Explicit reseed — pass `--reseed-biohermes` as the first argument,
    or run `biohermes-reseed` (same package).  This is how a user
    intentionally picks up preset updates after a `git pull`.

Path resolution:
  - Repo root:  `Path(__file__).resolve().parents[1]` — works for editable
                installs (`pip install -e .`) and for running directly from
                the checkout.
  - Preset:     `<repo>/config-examples/biohermes-cli-config.yaml`
  - Profile:    `<repo>/.biohermes-profile/` (gitignored)

v0.1-alpha assumption: installed via `pip install -e .` so the `biohermes`
package is still symlinked to the repo tree.  Non-editable installs need
a package-data copy of the preset — tracked as a follow-up.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


_PLACEHOLDER = "<path-to-biohermes-checkout>"
_RESEED_FLAG = "--reseed-biohermes"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _preset_path(repo_root: Path) -> Path:
    preset = repo_root / "config-examples" / "biohermes-cli-config.yaml"
    if not preset.is_file():
        sys.stderr.write(
            f"biohermes: expected preset at {preset}; is this an editable "
            "install of the BioHermes fork?\n"
        )
        sys.exit(1)
    return preset


def _seed_config(preset: Path, target: Path, repo_root: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    text = preset.read_text().replace(_PLACEHOLDER, str(repo_root))
    target.write_text(text)


def _ensure_seeded(repo_root: Path, profile_dir: Path, *, force: bool) -> bool:
    """Seed the profile config from the preset iff it doesn't exist yet,
    or if `force` is True.  Returns True if a (re)seed happened."""
    target = profile_dir / "config.yaml"
    preset = _preset_path(repo_root)
    if target.is_file() and not force:
        return False
    _seed_config(preset, target, repo_root)
    return True


def _find_hermes_bin() -> str:
    override = os.environ.get("HERMES_BIN")
    if override:
        return override
    found = shutil.which("hermes")
    if found:
        return found
    sys.stderr.write(
        "biohermes: `hermes` not found on PATH.  Install the fork with "
        "`pip install -e .` from the BioHermes repo root, or set HERMES_BIN.\n"
    )
    sys.exit(1)


def main() -> int:
    repo_root = _repo_root()
    profile_dir = repo_root / ".biohermes-profile"

    # Strip our sentinel flag from argv before handing off to hermes —
    # hermes does not know this flag and would reject it.
    argv_rest = list(sys.argv[1:])
    force_reseed = False
    if argv_rest and argv_rest[0] == _RESEED_FLAG:
        force_reseed = True
        argv_rest = argv_rest[1:]

    if _ensure_seeded(repo_root, profile_dir, force=force_reseed):
        if force_reseed:
            sys.stderr.write(
                f"biohermes: reseeded {profile_dir}/config.yaml from preset.\n"
            )

    os.environ["BIOHERMES_REPO"] = str(repo_root)
    os.environ["HERMES_HOME"] = str(profile_dir)

    hermes_bin = _find_hermes_bin()
    os.execv(hermes_bin, [hermes_bin, *argv_rest])


def reseed_main() -> int:
    """Standalone entry: `biohermes-reseed` reseeds the profile config
    from the current preset, preserving nothing.  Backs up the old
    config to `config.yaml.bak-<ts>` first so edits are not lost outright.
    """
    import time
    repo_root = _repo_root()
    profile_dir = repo_root / ".biohermes-profile"
    target = profile_dir / "config.yaml"
    if target.is_file():
        backup = profile_dir / f"config.yaml.bak-{int(time.time())}"
        target.rename(backup)
        sys.stderr.write(f"biohermes-reseed: backed up existing config to {backup}\n")
    _ensure_seeded(repo_root, profile_dir, force=True)
    sys.stderr.write(f"biohermes-reseed: wrote fresh config from preset to {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
