#!/usr/bin/env python3
"""coverage_runner — agent-loop consultation test across bio skills.

For each target skill, runs:

    biohermes chat -q "Briefly consult the <skill> skill ..."

and records:
  - whether the agent invoked `skill_view` on the target skill
  - tool-call count
  - elapsed seconds
  - a trimmed one-line response preview (for spot-checking correctness)

Writes a Markdown table to stdout by default; pass `--out PATH` to also
write to a file suitable for dropping into PHASE1_COVERAGE.md.

Requires: a working BioHermes checkout with `biohermes/bin/biohermes`
already seeded (i.e. run `biohermes --version` once before this script).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


# (name, tier, one-line consult prompt)
COVERAGE_TARGETS: list[tuple[str, str, str]] = [
    ("atac-seq", "moderate", "Briefly consult the atac-seq skill. In <35 words, name the three main external binaries it expects and what each is for. Do not run any commands."),
    ("bio-innovation-check", "moderate", "Briefly consult the bio-innovation-check skill. In <35 words, summarize the evaluation dimensions it walks through. Do not run any commands."),
    ("bio-manuscript-pipeline", "moderate", "Briefly consult the bio-manuscript-pipeline skill. In <35 words, name the sibling skills it orchestrates in order. Do not run any commands."),
    ("chip-seq", "moderate", "Briefly consult the chip-seq skill. In <35 words, name the three main external binaries it expects. Do not run any commands."),
    ("differential-expression", "moderate", "Briefly consult the differential-expression skill. In <35 words, name the main DE method it recommends and two visualization tools. Do not run any commands."),
    ("metagenomics", "moderate", "Briefly consult the metagenomics skill. In <35 words, name its primary taxonomic profiler and one QC tool. Do not run any commands."),
    ("report-template", "moderate", "Briefly consult the report-template skill. In <35 words, name the rendering engine it wraps and what it outputs. Do not run any commands."),
    ("scrna-preprocessing-clustering", "moderate", "Briefly consult the scrna-preprocessing-clustering skill. In <35 words, name its core Python library and the two main preprocessing steps. Do not run any commands."),
    ("structural-biology", "moderate", "Briefly consult the structural-biology skill. In <35 words, name the primary structure source and two confidence metrics it discusses. Do not run any commands."),
    ("bio-tools", "complex", "Briefly consult the bio-tools reference skill. In <35 words, name three external binaries it documents as container pre-installed. Do not run any commands."),
]


def run_one(
    name: str,
    tier: str,
    prompt: str,
    biohermes_bin: Path,
    timeout_s: int,
) -> dict:
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            [str(biohermes_bin), "chat", "-q", prompt],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "name": name,
            "tier": tier,
            "duration_s": timeout_s,
            "tool_calls": None,
            "skill_viewed": None,
            "status": "TIMEOUT",
            "preview": "",
        }
    duration = time.perf_counter() - t0
    combined = result.stdout + result.stderr

    # Did the agent read the target skill?
    skill_viewed = bool(re.search(rf"📚\s+skill\s+{re.escape(name)}\b", combined))

    # Tool-call count comes from the trailing status: "Messages: N (1 user, M tool calls)"
    tc_match = re.search(r"(\d+)\s+tool\s+calls", combined)
    tool_calls = int(tc_match.group(1)) if tc_match else None

    # Extract the bordered response block content.
    # Hermes wraps with ╭─ ⚕ Hermes ───…╮ … ╰───╯
    response_block = ""
    block_match = re.search(
        r"╭─\s+⚕ Hermes[\s─]*╮\n([\s\S]*?)\n╰[\s─]*╯",
        combined,
    )
    if block_match:
        # Strip Rich borders from each line
        lines = block_match.group(1).splitlines()
        cleaned = [re.sub(r"^│\s?|\s*│$", "", l).strip() for l in lines]
        response_block = " ".join(l for l in cleaned if l)

    preview = (response_block[:200] + "…") if len(response_block) > 200 else response_block

    status = "PASS" if skill_viewed and response_block else "UNCERTAIN"
    if result.returncode != 0 and not response_block:
        status = "FAIL"

    return {
        "name": name,
        "tier": tier,
        "duration_s": round(duration, 1),
        "tool_calls": tool_calls,
        "skill_viewed": skill_viewed,
        "status": status,
        "preview": preview,
    }


def render_markdown(rows: list[dict]) -> str:
    lines = [
        "| Skill | Tier | Duration | Tool calls | Skill loaded | Status | Response preview |",
        "|---|---|---:|---:|:---:|:---:|---|",
    ]
    for r in rows:
        preview = r["preview"].replace("|", "\\|")
        mark = "✅" if r["skill_viewed"] else "❌" if r["skill_viewed"] is False else "—"
        lines.append(
            f"| `{r['name']}` | {r['tier']} | {r['duration_s']}s | {r['tool_calls']} "
            f"| {mark} | {r['status']} | {preview} |"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--biohermes",
        default=str(Path(__file__).resolve().parents[1] / "biohermes" / "bin" / "biohermes"),
        help="Path to the biohermes entry (bash wrapper or pip-installed script).",
    )
    ap.add_argument("--timeout", type=int, default=120, help="Per-skill timeout in seconds.")
    ap.add_argument("--out", default=None, help="Optional markdown output path.")
    ap.add_argument("--json-out", default=None, help="Optional JSON output path.")
    ap.add_argument(
        "--only",
        default=None,
        help="Comma-separated skill names to restrict to (for ad-hoc reruns).",
    )
    args = ap.parse_args()

    biohermes_bin = Path(args.biohermes).resolve()
    if not biohermes_bin.is_file():
        sys.stderr.write(f"coverage_runner: {biohermes_bin} not found\n")
        return 1

    only = set(s.strip() for s in args.only.split(",")) if args.only else None
    targets = [t for t in COVERAGE_TARGETS if not only or t[0] in only]

    rows: list[dict] = []
    for i, (name, tier, prompt) in enumerate(targets, 1):
        sys.stderr.write(f"[{i}/{len(targets)}] {name} ({tier}) …\n")
        rows.append(run_one(name, tier, prompt, biohermes_bin, args.timeout))
        last = rows[-1]
        sys.stderr.write(
            f"  → {last['status']}  (skill_viewed={last['skill_viewed']}, "
            f"{last['duration_s']}s, {last['tool_calls']} tool calls)\n"
        )

    md = render_markdown(rows)
    print(md)
    if args.out:
        Path(args.out).write_text(md + "\n")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, indent=2))
    passed = sum(1 for r in rows if r["status"] == "PASS")
    sys.stderr.write(f"\n=== {passed}/{len(rows)} PASS ===\n")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
