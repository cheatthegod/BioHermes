#!/usr/bin/env python3
"""skill_classifier.py — 4-dimension tier classifier for BioClaw skills.

Scores each skill on four complexity signals that affect migration effort
in different ways than simple file-count:

  D1. has_external_binary       — external command-line tool required
      (samtools, macs3, blast+, typst, ...). Affects Hermes terminal
      environment setup.
  D2. has_python_heavy_stack    — >=3 non-stdlib Python imports in any .py
      file. Affects `pip install` requirements.
  D3. has_cross_skill_dep       — references another skill by name.
      Affects migration ordering (must migrate dependency first).
  D4. has_bioclaw_tool_ref      — references `send_image`, `send_file`,
      `outbox`, `inbox`, or similar BioClaw-specific tools. Affects
      PATH_MAPPINGS / MCP shim work.

Tier rule:
    sum == 0 → trivial
    sum == 1 → moderate
    sum >= 2 → complex
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Stdlib modules we won't count as "heavy stack". Pragmatic allowlist.
STDLIB = {
    "os", "sys", "re", "json", "csv", "time", "datetime", "pathlib",
    "shutil", "subprocess", "argparse", "collections", "itertools",
    "functools", "typing", "dataclasses", "logging", "io", "hashlib",
    "tempfile", "glob", "contextlib", "traceback", "warnings", "copy",
    "math", "random", "statistics", "string", "textwrap", "zipfile",
    "tarfile", "gzip", "bz2", "pickle", "struct", "enum", "abc",
    "__future__", "asyncio", "socket", "urllib", "http", "html",
    "xml", "base64", "uuid", "platform", "signal", "threading",
    "concurrent", "multiprocessing", "inspect", "pprint", "operator",
}

# Common external bio/CS binaries (shell-invocable tools). Regex-word-matched.
EXTERNAL_BINARIES = [
    "samtools", "macs3", "blastn", "blastp", "blast\\+", "bowtie2",
    "bwa", "STAR", "salmon", "kallisto", "hisat2", "featureCounts",
    "picard", "gatk", "bcftools", "vcftools", "fastqc", "trimmomatic",
    "cutadapt", "hmmer", "muscle", "mafft", "clustalo", "raxml",
    "iqtree", "phyml", "pymol", "autodock", "gromacs",
    "typst", "cellranger", "homer", "deepTools", "bamCoverage",
    "plink", "minimap2", "snakemake", "nextflow", "rosetta", "dssp",
    "mmseqs", "diamond", "seqkit", "bedtools",
    "fastp", "kraken2", "krakenuniq", "bracken", "metaphlan", "humann",
    "prokka", "spades", "megahit", "trinity",
]
EXT_BIN_RE = re.compile(
    r"(?:^|[\s`\"']|\bconda install |\bapt-get install |\bpip install )"
    r"(" + "|".join(EXTERNAL_BINARIES) + r")\b"
)

# Heavy Python libs: if declared in prose (Version Compatibility / Requirements
# blocks of SKILL.md) they count toward D2 even without .py imports,
# because migration still has to land them in the Hermes terminal env.
HEAVY_PYTHON_LIBS = [
    "pyopenms", "scanpy", "anndata", "scvi", "numpy", "pandas", "scipy",
    "matplotlib", "seaborn", "plotly", "biopython", "pysam", "pybedtools",
    "statsmodels", "scikit-learn", "sklearn", "torch", "tensorflow",
    "jax", "flax", "rdkit", "openmm", "openbabel", "mdanalysis",
    "prody", "deeppurpose", "esm", "transformers", "datasets",
    "DESeq2", "edgeR", "limma", "Seurat", "Bioconductor",
    "celltypist", "py3Dmol", "squidpy", "cellrank", "scrublet",
    "scvelo", "velocyto", "pyscenic",
]
HEAVY_PYTHON_LIBS_RE = re.compile(
    r"[\s`\"']*(" + "|".join(HEAVY_PYTHON_LIBS) + r")\b",
    re.IGNORECASE,
)
# Section headers that usually precede dep lists in BioClaw SKILL.md bodies.
DEP_SECTION_RE = re.compile(
    r"##+\s*(Version Compatibility|Dependencies|Requirements|Prerequisites|Environment|Tools? Needed).*?(?=^##+\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)

BIOCLAW_TOOL_PATTERNS = [
    r"\bsend_image\b", r"\bsend_file\b", r"\boutbox\b", r"\binbox\b",
    r"\bwrite_file\b",  # generic but used by BioClaw skills for workspace I/O
]
BIOCLAW_TOOL_RE = re.compile("|".join(BIOCLAW_TOOL_PATTERNS))

IMPORT_RE = re.compile(
    r"^(?:from\s+([A-Za-z_][A-Za-z0-9_]*)\s+import|import\s+([A-Za-z_][A-Za-z0-9_]*))",
    re.MULTILINE,
)


def scan_skill(skill_dir: Path, all_skill_names: set[str]) -> dict:
    """Return a classification record for one skill dir."""
    skill_md = skill_dir / "SKILL.md"
    md_text = skill_md.read_text(errors="ignore") if skill_md.exists() else ""

    # D1 — external binaries in SKILL.md body
    ext_bins = sorted(set(EXT_BIN_RE.findall(md_text)))

    # D2 — heavy python stack: union of non-stdlib top-level imports across .py files
    # AND heavy libs declared in prose "Version Compatibility" / "Dependencies" sections
    # of SKILL.md (BioClaw convention — many skills have no .py but declare deps in prose).
    non_stdlib_imports: set[str] = set()
    py_file_count = 0
    for py in skill_dir.rglob("*.py"):
        if any(part in {"__pycache__", "tests"} for part in py.relative_to(skill_dir).parts):
            continue
        py_file_count += 1
        try:
            text = py.read_text(errors="ignore")
        except OSError:
            continue
        for m in IMPORT_RE.finditer(text):
            mod = m.group(1) or m.group(2)
            top = mod.split(".")[0]
            if top and top not in STDLIB:
                non_stdlib_imports.add(top)

    # Prose-declared deps (BioClaw "Version Compatibility" / "Requirements" blocks)
    prose_libs: set[str] = set()
    for section_match in DEP_SECTION_RE.finditer(md_text):
        block = section_match.group(0)
        for lib_match in HEAVY_PYTHON_LIBS_RE.finditer(block):
            prose_libs.add(lib_match.group(1).lower())
    non_stdlib_imports.update(prose_libs)

    # D3 — cross-skill references: other skill names appearing in SKILL.md body,
    # excluding self-reference and substrings inside own name.
    own_name = skill_dir.name
    others = all_skill_names - {own_name}
    referenced = sorted(
        name for name in others
        if re.search(rf"\b{re.escape(name)}\b", md_text)
    )

    # D4 — BioClaw-specific tool refs (in SKILL.md body AND .py scripts)
    bioclaw_hits: list[tuple[str, int]] = []
    if BIOCLAW_TOOL_RE.search(md_text):
        bioclaw_hits.append(("SKILL.md", len(BIOCLAW_TOOL_RE.findall(md_text))))
    for py in skill_dir.rglob("*.py"):
        if any(part in {"__pycache__", "tests"} for part in py.relative_to(skill_dir).parts):
            continue
        try:
            text = py.read_text(errors="ignore")
        except OSError:
            continue
        n = len(BIOCLAW_TOOL_RE.findall(text))
        if n:
            bioclaw_hits.append((str(py.relative_to(skill_dir)), n))

    d1 = bool(ext_bins)
    # Threshold 2 — any skill declaring ≥2 heavy libs is not trivial to migrate
    # (must land each in Hermes terminal env; even scanpy+pandas is a real install).
    d2 = len(non_stdlib_imports) >= 2
    d3 = bool(referenced)
    d4 = bool(bioclaw_hits)

    score = int(d1) + int(d2) + int(d3) + int(d4)
    tier = "trivial" if score == 0 else "moderate" if score == 1 else "complex"

    return {
        "name": own_name,
        "tier": tier,
        "score": score,
        "d1_external_bins": ext_bins,
        "d2_heavy_stack_imports": sorted(non_stdlib_imports),
        "d2_non_stdlib_count": len(non_stdlib_imports),
        "d3_cross_skill_refs": referenced,
        "d4_bioclaw_tool_hits": bioclaw_hits,
        "py_file_count": py_file_count,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-root", required=True)
    ap.add_argument("--json", action="store_true", help="emit full JSON")
    args = ap.parse_args()

    root = Path(args.skills_root).resolve()
    skill_dirs = sorted(
        p for p in root.iterdir()
        if p.is_dir() and (p / "SKILL.md").exists() or (p / "README.md").exists()
    )
    # Keep only dirs with a SKILL.md (BioClaw convention); skip README-only index dirs.
    skill_dirs = [p for p in skill_dirs if (p / "SKILL.md").exists()]
    all_names = {p.name for p in skill_dirs}

    rows = [scan_skill(p, all_names) for p in skill_dirs]

    if args.json:
        print(json.dumps(rows, indent=2))
        return 0

    # Human-readable table
    header = f"{'skill':<32} {'tier':<9} {'D1':<3} {'D2':<3} {'D3':<3} {'D4':<3} {'py#':<4} notes"
    print(header)
    print("-" * len(header))
    by_tier: dict[str, list[str]] = {"trivial": [], "moderate": [], "complex": []}
    for r in rows:
        d1 = "✓" if r["d1_external_bins"] else "·"
        d2 = "✓" if r["d2_non_stdlib_count"] >= 2 else "·"
        d3 = "✓" if r["d3_cross_skill_refs"] else "·"
        d4 = "✓" if r["d4_bioclaw_tool_hits"] else "·"
        notes_parts = []
        if r["d1_external_bins"]:
            notes_parts.append("bins=" + ",".join(r["d1_external_bins"][:3]))
        if r["d2_non_stdlib_count"] >= 2:
            notes_parts.append(f"py-deps={r['d2_non_stdlib_count']}:{','.join(r['d2_heavy_stack_imports'][:3])}")
        if r["d3_cross_skill_refs"]:
            notes_parts.append("xdep=" + ",".join(r["d3_cross_skill_refs"][:2]))
        if r["d4_bioclaw_tool_hits"]:
            notes_parts.append(f"bio-io={len(r['d4_bioclaw_tool_hits'])}")
        notes = "; ".join(notes_parts)
        print(f"{r['name']:<32} {r['tier']:<9} {d1:<3} {d2:<3} {d3:<3} {d4:<3} {r['py_file_count']:<4} {notes}")
        by_tier[r["tier"]].append(r["name"])

    print()
    print("=== Tier summary ===")
    for t in ("trivial", "moderate", "complex"):
        print(f"  {t:<10} n={len(by_tier[t]):>3}   {', '.join(by_tier[t])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
