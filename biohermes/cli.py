"""biohermes CLI entry point.

Python counterpart to `biohermes/bin/biohermes` (the bash wrapper). Both end
up doing the same thing — set `HERMES_HOME` to a project-local profile that
has the BioHermes bio preset seeded — but the Python entry point is what
`pip install -e .` exposes as the `biohermes` console script, so users who
install the fork get `biohermes` on PATH without sourcing the checkout's
`bin/` directory.

Path resolution:
  - Repo root:  `Path(__file__).resolve().parents[1]` — works for editable
                installs (`pip install -e .`) and for running directly from
                the checkout.
  - Preset:     `<repo>/config-examples/biohermes-cli-config.yaml`
  - Profile:    `<repo>/.biohermes-profile/` (gitignored)

v0.1-alpha assumption: installed via `pip install -e .` so the `biohermes`
package is still symlinked to the repo tree.  Non-editable installs need a
package-data copy of the preset — follow-up.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


_PLACEHOLDER = "<path-to-biohermes-checkout>"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _seed_profile(repo_root: Path, profile_dir: Path) -> None:
    """Copy the preset into the profile, substituting the path placeholder."""
    preset = repo_root / "config-examples" / "biohermes-cli-config.yaml"
    if not preset.is_file():
        sys.stderr.write(
            f"biohermes: expected preset at {preset}; is this an editable "
            "install of the BioHermes fork?\n"
        )
        sys.exit(1)
    profile_dir.mkdir(parents=True, exist_ok=True)
    target = profile_dir / "config.yaml"
    # Reseed if missing or older than the preset (keeps user edits if newer).
    if target.is_file() and target.stat().st_mtime >= preset.stat().st_mtime:
        return
    text = preset.read_text()
    text = text.replace(_PLACEHOLDER, str(repo_root))
    target.write_text(text)


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
    _seed_profile(repo_root, profile_dir)

    os.environ["BIOHERMES_REPO"] = str(repo_root)
    os.environ["HERMES_HOME"] = str(profile_dir)

    hermes_bin = _find_hermes_bin()
    os.execv(hermes_bin, [hermes_bin, *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
