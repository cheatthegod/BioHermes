# BioHermes 🧬

> **An AI research assistant for bioinformatics — skills for SEC chromatography, ATAC-seq, BLAST, scRNA-seq, differential expression, mass-spec proteomics, structural biology, manuscript drafting, and 30+ more bio workflows — running on a production-grade agent runtime.**

```
You:    I have SEC data for six protein constructs; analyze them and send me a PDF.
Agent:  [loads sec-report skill] → [runs sec_pipeline.py on your data]
        → [mcp_bioclaw_send_image with the PDF]
        → [via Telegram / Slack / Discord / WhatsApp / Signal / your CLI]
You:    📄 SEC_Analysis_Report.pdf (7 pages)
        Top candidate: Monomer_Only_09 (Q=10.0, monodisperse)
```

## What BioHermes gives you

**A curated bioinformatics skill library** — 40 procedures carried over from [BioClaw](https://github.com/Runchuan-BU/BioClaw) and normalized to Hermes's skill format:

| Category | Skills |
|----------|--------|
| **Sequence databases** | query-pdb, query-uniprot, query-alphafold, query-ensembl, query-geo, query-clinvar, query-interpro, query-kegg, query-reactome, query-stringdb, query-opentarget |
| **Genomics pipelines** | atac-seq, chip-seq, scrna-preprocessing-clustering, cell-annotation, differential-expression, metagenomics, sequence-analysis, blast-search |
| **Structural biology** | structural-biology, query-alphafold |
| **Proteomics / biochem** | proteomics, sec-report, sds-gel-review |
| **Manuscript / reporting** | bio-manuscript-pipeline, bio-manuscript-text, bio-manuscript-refine, bio-manuscript-common, bio-figure-design, bio-ppt-generate, report-template |
| **Meta / orchestration** | skills-hub, bio-task-system, bio-analysis-system, bio-dataset-search, bio-innovation-check, bio-human-feedback, bio-metric-system, bio-tools, agent-browser, pubmed-search |

**A BioClaw-compatible file-I/O shim** (`biohermes/mcp_bioclaw_server.py`) — preserves the `send_image` / `send_file` semantics BioClaw skills rely on, with a `send_message` hand-off so outputs flow through any of Hermes's 7+ messaging platforms (Telegram, Slack, Discord, WhatsApp, Signal, Matrix, WeChat).

**Full Hermes Agent runtime underneath** — memory tool with auto-injected MEMORY.md / USER.md, smart model routing (simple turns → cheap model), shadow-git checkpoints before destructive ops, smart approvals via auxiliary LLM, 6 terminal backends (local / docker / ssh / singularity / daytona / modal), FTS5 session search, Atropos RL environments, cron scheduling.

## Quick start

```bash
git clone https://github.com/cheatthegod/BioHermes.git
cd BioHermes
pip install -e .                       # exposes `biohermes`, `hermes`, etc.

# First biohermes invocation creates .biohermes-profile/ (gitignored)
# and seeds its config from config-examples/biohermes-cli-config.yaml.
biohermes --version

# Put provider credentials in the PROFILE's .env — not ~/.hermes/.env,
# because BioHermes uses HERMES_HOME=<repo>/.biohermes-profile/
cat > .biohermes-profile/.env <<'EOF'
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
EOF

biohermes chat -q "what SEC analysis workflows do you have?"
biohermes mcp test bioclaw              # verify the file-I/O shim is up
biohermes skills list                   # 74 bundled + 40 bioinformatics = 114
```

## How it reaches BioClaw's closed loop

BioClaw's user experience is: chat → agent runs bio workflow → PDF / image returns in the chat. BioHermes gets there using Hermes's native messaging gateway + `send_message` tool:

```
 User on Telegram / Slack / Discord / WhatsApp / Signal / Matrix / WeChat
      │ chat
      ▼
 Hermes gateway  (sets TELEGRAM_HOME_CHANNEL etc. in the agent subprocess env)
      │ spawn
      ▼
 BioHermes agent  — loads sec-report / atac-seq / blast-search / … skill
      │ invoke
      ▼
 skill script  — produces PDF / figure / CSV
      │
      ▼
 mcp_bioclaw_send_image  — writes outbox/<ts>.pdf  +  returns:
                          "GATEWAY ACTIVE: call send_message(
                            target='telegram:<chat_id>',
                            media_files=['/…/outbox/<ts>.pdf'],
                            text='…')"
      │ follow-up tool call
      ▼
 Hermes send_message tool  — dispatches via platform API
      │
      ▼
 User receives the PDF in their chat, same as BioClaw on WhatsApp
```

To run it end-to-end with a real channel:

```bash
biohermes gateway setup                 # interactive — e.g., Telegram bot token
biohermes gateway start                 # leave running in one shell
# From the chat client, send `/sethome` once so the gateway records your chat_id.
biohermes chat -q "run sec-report on <attachment> and send me the PDF"
```

When no gateway is running, `send_image` / `send_file` fall back to the outbox directory — useful for local CLI dogfooding.

## How BioHermes relates to the projects around it

```
                         NousResearch/hermes-agent          qwibitai/nanoclaw
                          (Python · MIT)                    (TypeScript · MIT)
                                   │                               │
                         fork ─────┤                               ├───── fork
                                   │                               │
                                   ▼                               ▼
 cheatthegod/BioHermes  ◀── ships ──  same fork pattern  ── ships ──▶  Runchuan-BU/BioClaw
 (this repo)                                                           (skill source of truth)
```

- **vs [Hermes Agent](https://github.com/NousResearch/hermes-agent)**: BioHermes is a hard fork of Hermes Agent at commit `4b6ff0eb` with a bio layer added on top. The upstream Hermes README is preserved unchanged as [`HERMES_UPSTREAM_README.md`](HERMES_UPSTREAM_README.md). To pull upstream improvements: `git fetch upstream && git merge upstream/main` (bio layer is pure-additive, conflicts only where upstream happens to touch `README.md` / `NOTICE` / `pyproject.toml`).

- **vs [BioClaw](https://github.com/Runchuan-BU/BioClaw)**: BioClaw owns the bio skills. BioHermes consumes them via `biohermes/skill_migrator.py`, rewriting BioClaw's SKILL.md frontmatter into Hermes's schema and mapping `send_image` / `send_file` to the MCP shim. Re-run the migrator whenever BioClaw updates a skill.

## Layout

```
BioHermes/
├── biohermes/                              BioHermes bio layer (new on top of Hermes)
│   ├── cli.py                               `biohermes` console script entry
│   ├── bin/biohermes                        equivalent bash wrapper
│   ├── mcp_bioclaw_server.py                send_image / send_file (gateway-aware)
│   ├── mcp_probe_server.py                  Phase 0 MCP discovery probe
│   ├── skill_migrator.py                    BioClaw → Hermes SKILL.md migrator
│   └── skill_classifier.py                  4-dimension skill complexity scorer
│
├── optional-skills/
│   └── bioinformatics/                      40 migrated BioClaw skills (bundled)
│
├── config-examples/
│   └── biohermes-cli-config.yaml            Tier B preset + mcp_bioclaw registration
│
├── docs/biohermes/                          Plan + execution reports
│   ├── BIOCLAW_HERMES_PLAN_ZH.md            design doc v10 (Chinese, 775 lines)
│   ├── PHASE0_RESULTS.md                    Phase 0 + 0.5 execution report
│   └── PHASE1_PROGRESS.md                   Phase 1 execution report
│
├── HERMES_UPSTREAM_README.md                upstream Hermes README, preserved
├── NOTICE                                   MIT attribution for Hermes + BioClaw + BioHermes
├── LICENSE                                  MIT (Nous Research 2025 + BioHermes additions)
└── … full Hermes Agent tree (unchanged) …
```

## Verified end-to-end

Per [`docs/biohermes/PHASE1_PROGRESS.md`](docs/biohermes/PHASE1_PROGRESS.md):

- `biohermes chat` smoke test via OpenRouter + `anthropic/claude-opus-4.6`
- `biohermes mcp test bioclaw` — 2 tools (`send_image`, `send_file`) discovered in 834ms
- 4-dimension spot check: trivial API (`query-uniprot` → real UniProt API → P00533 = EGFR / Homo sapiens), moderate D1 external binary (`blast-search` → blastn / blastp), moderate D2 heavy Python (`proteomics` → pyopenms / pandas), moderate D3 cross-skill (`skills-hub` → atac-seq + scrna-preprocessing) — all 4 PASS
- **sec-report full loop**: agent consumes SKILL.md → `pip install` deps → runs `sec_pipeline.py` on test dataset → emits 7-page PDF via `mcp_bioclaw_send_image` → lands in outbox (31s, 11 tool calls)
- **Tier B** all three active: `smart_model_routing` routes simple turns to `gemini-2.5-flash`; `approvals.mode: smart` auto-approves safe ops; `checkpoints.enabled` creates shadow-git snapshots before destructive file ops
- **Gateway mode** verified in simulation (`TELEGRAM_HOME_CHANNEL=-1001234567890` forced): shim emits `GATEWAY ACTIVE: call send_message(target='telegram:-1001234567890', media_files=['<path>'], text='…')` — the hand-off the agent uses to dispatch through Hermes's native platform API

## Known v0.1-alpha limitations

1. **Telegram / Discord / … e2e not yet run with a real bot token.** Gateway mode is verified in simulation; a real messaging e2e (chat → agent → PDF returned in chat) is the next validation.
2. **`terminal.backend: local`** — the agent's `pip install` lands in the host Python env. Run under a throwaway venv if you want hard isolation; Docker / Singularity backends work too.
3. **Non-editable `pip install` does NOT ship the bio skills.** The core runtime (`biohermes`, `biohermes-reseed`, `hermes` entry points, the MCP shim, the preset) does install correctly from a wheel and was verified end-to-end. But `optional-skills/bioinformatics/` (40 skills) is not in the wheel — this mirrors upstream Hermes, whose wheels also don't ship `optional-skills/`. For bio skills, use one of:
   - **Editable install** (recommended): `pip install -e .` from the checkout — bio skills are then visible via `skills.external_dirs` in the auto-seeded config.
   - **Manual copy** for non-editable users: `cp -r optional-skills/bioinformatics ~/.biohermes/skills/` after `pip install biohermes`.
   - A future `biohermes-bundle-skills` console script will fetch skills from the fork automatically.
4. **Skill runtime coverage is sampled.** 6 of 40 skills were end-to-end validated; remaining 34 are mechanically migrated but not runtime-tested.
5. **`bio-tools` and `bio-manuscript-common`** are resource skills expecting certain binaries / sibling skills to be available; see their SKILL.md for details.

## Credits

BioHermes would not exist without:

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** © 2025 [Nous Research](https://nousresearch.com), MIT — the runtime underneath. See [`HERMES_UPSTREAM_README.md`](HERMES_UPSTREAM_README.md) for Hermes's own README, preserved as shipped.
- **[BioClaw](https://github.com/Runchuan-BU/BioClaw)** © Runchuan-BU and contributors, MIT — the bioinformatics skill library.

BioHermes additions are © BioHermes contributors, MIT. See [`NOTICE`](NOTICE) and [`LICENSE`](LICENSE).
