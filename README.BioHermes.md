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

# 2. First `biohermes` invocation auto-creates .biohermes-profile/ and
#    seeds its config.yaml from config-examples/biohermes-cli-config.yaml
#    with <path-to-biohermes-checkout> substituted to your checkout.
./biohermes/bin/biohermes --version    # triggers the seed

# 3. Put your provider credentials in the PROFILE'S .env — not ~/.hermes/.env,
#    because the wrapper sets HERMES_HOME to the project-local profile.
cat > .biohermes-profile/.env <<'EOF'
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
EOF

# 4. Launch
./biohermes/bin/biohermes chat -q "hello"
./biohermes/bin/biohermes mcp list        # verify mcp_bioclaw registered
./biohermes/bin/biohermes skills list     # 40 bioinformatics skills + Hermes defaults = 114
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

## How to reach BioClaw-style closed loop

BioClaw's full loop is: user chats on WhatsApp → agent runs bio workflow → PDF/image comes back on WhatsApp. BioHermes reaches the same shape using Hermes's native gateway + `send_message` tool:

```
User (Telegram / Discord / Slack / WhatsApp / Signal / Matrix / WeChat)
      │ chat
      ▼
Hermes gateway  —— sets {PLATFORM}_HOME_CHANNEL in agent env
      │ spawn
      ▼
BioHermes agent  —— loads sec-report / atac-seq / etc. skill
      │ invoke
      ▼
skill script  —— produces PDF / figure
      │ invoke
      ▼
mcp_bioclaw_send_image  —— writes outbox/<ts>.pdf (record)
                          returns "GATEWAY ACTIVE: call send_message(...)"
      │ follow-up tool call
      ▼
send_message (built-in)  —— dispatches the attachment through the platform API
      │
      ▼
User receives PDF in their chat
```

The mcp_bioclaw_send_image tool auto-detects gateway context via `*_HOME_CHANNEL` env vars. In CLI-only use it falls back to the outbox being the final delivery.

To wire a platform end-to-end:

```bash
# 1. Pick a platform and set its credentials (one-time)
./biohermes/bin/biohermes gateway setup           # interactive — Telegram bot token etc.

# 2. Start the gateway in one shell
./biohermes/bin/biohermes gateway start

# 3. Send `/sethome` from the connected account so the gateway learns which
#    chat to send cross-platform messages to (sets {PLATFORM}_HOME_CHANNEL).

# 4. In another shell, chat with bio skills — outputs flow back via send_message.
./biohermes/bin/biohermes chat -q "run sec-report on the attached ZIP and send me the PDF"
```

See `tools/send_message_tool.py:644` for Telegram photo dispatch, `:469` for Discord attachments.

## Known v0.1-alpha limitations

1. **Config placeholder auto-substituted**: `<path-to-biohermes-checkout>` in `config-examples/biohermes-cli-config.yaml` is replaced by the wrapper at first launch — no manual edit needed.
2. **`terminal.backend: local`** — the agent's `pip install` lands in the host Python env. Run under a throwaway venv if you want hard isolation; Docker / Singularity backends work too (just flip the config knob).
3. **Gateway delivery requires running `hermes gateway`** alongside the agent and setting a home channel. Without a running gateway, outbox is the final delivery. The shim detects this automatically.
4. **Small-sample Phase 1 calibration** — 6 of 40 bio skills were end-to-end validated; the rest are mechanically migrated but not runtime-tested.
5. **`bio-tools` and `bio-manuscript-common`** are resource skills expecting certain binaries / other bio-manuscript-* skills to be available; see their SKILL.md for details.

## Attribution

Hermes Agent © 2025 Nous Research, MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
BioClaw skills © Runchuan-BU and contributors, MIT. Skill derivative work relationship detailed in `biohermes/skill_migrator.py`.
BioHermes additions © BioHermes contributors, MIT.
