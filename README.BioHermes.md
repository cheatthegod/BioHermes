# BioHermes

> **A downstream distribution of [Hermes Agent](https://github.com/NousResearch/hermes-agent) for bioinformatics research.**
> Same relationship [BioClaw](https://github.com/Runchuan-BU/BioClaw) has to [NanoClaw](https://github.com/qwibitai/nanoclaw): hard fork of the upstream, plus a domain-specific bio layer on top.
> Upstream Hermes README (unchanged) lives at [README.md](README.md).

## Why this exists

BioClaw is a TypeScript/Node agent for bio research with a polished skill library and Slack / WeChat / Feishu / WhatsApp / Telegram channels. Hermes Agent is a Python agent with a deeper feature surface — `memory` tool + USER.md / MEMORY.md auto-injection, smart model routing, shadow-git checkpoints, smart approvals, 20+ channels, 6 terminal backends (local / ssh / docker / singularity / daytona / modal), trajectory format + batch runner for RL, etc.

BioHermes is **BioClaw's skill library running on Hermes's runtime**. Fork of Hermes (inherits the full codebase), with a bio layer added on top:

```
BioHermes (fork of NousResearch/hermes-agent)
├── <full Hermes Agent tree — preserved>
├── optional-skills/bioinformatics/         ← 40 BioClaw skills (Hermes-normalized)
├── biohermes/                              ← shim + dev tools
│   ├── bin/biohermes                        wrapper that auto-loads the bio config preset
│   ├── mcp_bioclaw_server.py                MCP shim: send_image / send_file → outbox/
│   ├── mcp_probe_server.py                  Phase 0 MCP discovery probe (kept for reference)
│   ├── skill_migrator.py                    BioClaw SKILL.md → Hermes frontmatter + PATH_MAPPINGS
│   └── skill_classifier.py                  4-dimension complexity tier scorer
├── config-examples/
│   └── biohermes-cli-config.yaml           ← Tier B preset + mcp_bioclaw registration
└── docs/biohermes/
    ├── BIOCLAW_HERMES_PLAN_ZH.md           v10 design doc (Chinese)
    ├── PHASE0_RESULTS.md                   Phase 0 + 0.5 execution report
    └── PHASE1_PROGRESS.md                  Phase 1 execution report
```

BioHermes **does not rebrand the Hermes CLI**. The `hermes` binary keeps its identity; BioHermes adds a `biohermes` convenience wrapper that launches `hermes` with the bio config preset pre-loaded.

## Quick start

```bash
git clone https://github.com/cheatthegod/BioHermes.git
cd BioHermes

# 1. Install Hermes Agent from this fork (preserves our bio additions)
pip install -e .                       # or: pip install -e .[all]

# 2. Configure credentials
cp .env.example ~/.hermes/.env         # add OPENROUTER_API_KEY or similar

# 3. Edit config-examples/biohermes-cli-config.yaml — replace
#    <path-to-biohermes-checkout> with your actual checkout path
#    (or set BIOHERMES_REPO env and substitute at startup)

# 4. Launch with the bio preset
./biohermes/bin/biohermes chat -q "hello"
./biohermes/bin/biohermes mcp list        # verify mcp_bioclaw registered
./biohermes/bin/biohermes skills list     # see 40 bioinformatics skills + Hermes defaults
```

## What's verified end-to-end

Per `docs/biohermes/PHASE1_PROGRESS.md`:

- `hermes chat` smoke test via OpenRouter + `anthropic/claude-opus-4.6`
- `hermes mcp test bioclaw` — 2 tools (`send_image`, `send_file`) discovered in 834ms
- 4-dim agent-loop spot check: trivial API (`query-uniprot`) / moderate D1 bin (`blast-search`) / moderate D2 Python (`proteomics`) / moderate D3 cross-skill (`skills-hub`) all PASS
- **Full closed loop**: agent consumes `sec-report` skill → `pip install` deps → runs `sec_pipeline.py` on test data → emits 7-page PDF via `mcp_bioclaw_send_image` → lands in outbox (31s, 11 tool calls)
- **Tier B** all three active: `smart_model_routing` routes simple turns to `gemini-2.5-flash`; `approvals.mode: smart` auto-approves safe ops via auxiliary LLM; `checkpoints.enabled` creates shadow-git snapshots before destructive file ops

## Relationship to BioClaw

| Aspect | BioClaw | BioHermes |
|---|---|---|
| **Runtime** | TypeScript / Node.js / Anthropic Agents SDK | Python / Hermes Agent (fork of NousResearch/hermes-agent) |
| **Skills** | `container/skills/` (40 files, authoritative) | `optional-skills/bioinformatics/` (derived via migrator) |
| **File I/O** | `container/agent-runner/src/ipc-mcp-stdio.ts` `send_image` / `send_file` → IPC → channels | `biohermes/mcp_bioclaw_server.py` → stdio MCP → outbox or channel backend |
| **Memory** | Implicit conversation window | `memory` tool + MEMORY.md + USER.md auto-injected |
| **Smart routing** | N/A | `smart_model_routing` — cheap model on simple turns |
| **Safety rails** | Approval prompts per BioClaw channel | `approvals.mode: smart` + shadow-git `checkpoints` |
| **Channels** | WhatsApp-first, later QQ / Feishu / Slack | 20+ via `hermes gateway` (Telegram / Discord / Slack / WhatsApp / Signal / …) |

BioClaw is the **source of skills**. BioHermes consumes them via `biohermes/skill_migrator.py` — re-run whenever BioClaw adds or updates a skill.

## Syncing from upstream Hermes

```bash
# Pull latest Hermes Agent changes while keeping the bio layer on top:
git fetch upstream
git merge upstream/main          # or: git rebase upstream/main

# Expect zero conflicts on pure-additive bio paths; resolve as needed
# if upstream touches files we also touched (NOTICE, README.BioHermes.md).
```

## Known v0.1-alpha limitations

1. **`<path-to-biohermes-checkout>` placeholder** in `config-examples/biohermes-cli-config.yaml` must be edited by hand. Templating via `BIOHERMES_REPO` is planned.
2. **`terminal.backend: local`** — the agent's `pip install` lands in the host Python env. Run under a throwaway venv if you want hard isolation; Docker / Singularity backends work too (just flip the config knob).
3. **Gateway channels not wired** — `send_image` / `send_file` deliver to `~/.hermes/outbox/`. Re-enable IPC mode when connecting a messaging gateway.
4. **Small-sample Phase 1 calibration** — 6 of 40 bio skills were end-to-end validated; the rest are mechanically migrated but not runtime-tested.
5. **`bio-tools` and `bio-manuscript-common`** are resource skills expecting certain binaries / other bio-manuscript-* skills to be available; see their SKILL.md for details.

## Attribution

Hermes Agent © 2025 Nous Research, MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
BioClaw skills © Runchuan-BU and contributors, MIT. Skill derivative work relationship detailed in `biohermes/skill_migrator.py`.
BioHermes additions © BioHermes contributors, MIT.
