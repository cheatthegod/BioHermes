#!/usr/bin/env python3
"""skill_migrator.py — minimal prototype.

Migrates a BioClaw skill directory (`<repo>/container/skills/<name>/`) into a
Hermes-compatible skill directory (`<HERMES_HOME>/skills/<name>/`), applying
two transformations:

1. Frontmatter normalization: keep `name`/`description`; add Hermes-canonical
   `version` and `author` fields; move BioClaw-specific `tool_type` and
   `primary_tool` under `metadata.bioclaw.*`.
2. PATH_MAPPINGS rewrite: replace BioClaw file-I/O tool references in
   SKILL.md body with their MCP-shim namespace equivalents
   (`send_image` → `mcp_bioclaw_send_image`, etc.).

Per-skill timing is printed so Phase 0 can calibrate the §6 tier estimates
against real numbers.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path


# BioClaw MCP-shim tool namespace mapping. Mirrors plan §7.3.
PATH_MAPPINGS: dict[str, str] = {
    "send_image": "mcp_bioclaw_send_image",
    "send_file": "mcp_bioclaw_send_file",
}


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Handles only the flat subset used by BioClaw."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    header_block = text[4:end]
    body = text[end + 5:]
    fm: dict = {}
    for line in header_block.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm, body


def render_frontmatter(fm: dict) -> str:
    """Render to Hermes-canonical YAML (flat + one nested metadata.bioclaw block)."""
    lines = ["---"]
    for key in ("name", "description", "version", "author", "license"):
        if key in fm:
            lines.append(f"{key}: {fm[key]}")
    bioclaw_meta = {
        k: fm[f"_bioclaw_{k}"]
        for k in ("tool_type", "primary_tool")
        if f"_bioclaw_{k}" in fm
    }
    if bioclaw_meta:
        lines.append("metadata:")
        lines.append("  bioclaw:")
        for k, v in bioclaw_meta.items():
            lines.append(f"    {k}: {v}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def rewrite_body(body: str) -> tuple[str, int]:
    """Apply PATH_MAPPINGS. Returns (new_body, replacement_count)."""
    count = 0
    for old, new in PATH_MAPPINGS.items():
        pattern = re.compile(rf"\b{re.escape(old)}\b")
        body, n = pattern.subn(new, body)
        count += n
    return body, count


def normalize_frontmatter(fm: dict, skill_name: str, body: str) -> dict:
    """Normalize to Hermes-canonical. Fallback fills `name`/`description` when
    the source SKILL.md has no frontmatter at all (BioClaw had a few of these)."""
    out: dict = {}
    out["name"] = fm.get("name") or skill_name
    if "description" in fm:
        out["description"] = fm["description"]
    else:
        # Fallback: first non-empty non-heading paragraph, trimmed.
        desc = ""
        for line in body.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith(">"):
                continue
            # Strip common markdown emphasis markers
            s = re.sub(r"^\*\*|\*\*$", "", s).strip()
            if len(s) >= 20:
                desc = s
                break
        out["description"] = desc or f"BioClaw skill: {skill_name}"
    out.setdefault("version", "1.0.0")
    out.setdefault("author", "BioClaw")
    out.setdefault("license", "MIT")
    for k in ("tool_type", "primary_tool"):
        if k in fm:
            out[f"_bioclaw_{k}"] = fm[k]
    return out


def migrate_skill(src_dir: Path, dst_dir: Path) -> dict:
    t0 = time.perf_counter()
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    dst_dir.mkdir(parents=True)

    file_count = 0
    for src in src_dir.rglob("*"):
        rel = src.relative_to(src_dir)
        if any(part in {"__pycache__", "tests"} for part in rel.parts):
            continue
        dst = dst_dir / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            file_count += 1
    t_copy = time.perf_counter() - t0

    skill_md = dst_dir / "SKILL.md"
    t1 = time.perf_counter()
    replacements = 0
    if skill_md.exists():
        text = skill_md.read_text()
        fm_raw, body = parse_frontmatter(text)
        fm = normalize_frontmatter(fm_raw, src_dir.name, body)
        body, replacements = rewrite_body(body)
        skill_md.write_text(render_frontmatter(fm) + body)
    t_rewrite = time.perf_counter() - t1

    return {
        "name": src_dir.name,
        "files_copied": file_count,
        "replacements": replacements,
        "copy_s": round(t_copy, 4),
        "rewrite_s": round(t_rewrite, 4),
        "total_s": round(t_copy + t_rewrite, 4),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-root", required=True, help="BioClaw container/skills dir")
    ap.add_argument("--dst-root", required=True, help="HERMES_HOME/skills target dir")
    ap.add_argument("skills", nargs="+", help="Skill names to migrate")
    args = ap.parse_args()

    src_root = Path(args.src_root).resolve()
    dst_root = Path(args.dst_root).resolve()
    dst_root.mkdir(parents=True, exist_ok=True)

    print(f"{'skill':<25} {'files':>6} {'repl':>5} {'copy_s':>8} {'rewrite_s':>10} {'total_s':>8}")
    print("-" * 68)
    total = 0.0
    for name in args.skills:
        src = src_root / name
        dst = dst_root / name
        if not src.exists():
            print(f"{name:<25} MISSING source {src}", file=sys.stderr)
            return 1
        r = migrate_skill(src, dst)
        total += r["total_s"]
        print(
            f"{r['name']:<25} {r['files_copied']:>6} {r['replacements']:>5} "
            f"{r['copy_s']:>8.4f} {r['rewrite_s']:>10.4f} {r['total_s']:>8.4f}"
        )
    print("-" * 68)
    print(f"{'TOTAL':<25} {'':>6} {'':>5} {'':>8} {'':>10} {total:>8.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
