# Phase 1 Progress Report

> 运行日期：2026-04-19（紧接 Phase 0.5）
> 对应计划：`BIOCLAW_HERMES_PLAN_ZH.md` v10 §10 "Phase 1 — Foundation + Skills + Tier B"
> 前置报告：`PHASE0_RESULTS.md`(注意:Phase 0 / Phase 1 当时在 **pre-fork 工作根** `BioClaw-Hermes/bioclaw-hermes-py/` 下执行;后续 fork-pattern pivot 把一切搬到了 `BioHermes/`——`bhermes` → `biohermes`,`bioclaw-hermes-py/hermes-profile/` → `.biohermes-profile/`,详细 remap 见 `PHASE0_RESULTS.md` 顶部)

---

## 1. Phase 1 本次覆盖范围

本次 session 完成 Phase 1 前半段工作(大致对应 plan §10 的 Phase 1 part 1 + 半个 part 2):

- [x] `mcp_bioclaw_server.py` 替换 probe:真正实现 `send_image` / `send_file`
- [x] 全量 24 trivial + 13 moderate skill 机械迁移(+ Phase 0.5 的 2 complex = 39/39)
- [x] agent-loop spot check × 3(trivial API / moderate consult / cross-skill)
- [x] sec-report **完整闭环**:agent 读 skill → `pip install` deps → 跑 pipeline → `mcp_bioclaw_send_image` 发 PDF 到 outbox

尚未覆盖(留给 Phase 1 后半段):

- [x] ~~11 个未 spot check 的 moderate~~ **+ 1 未测 complex(bio-tools)—— 已在后续 C series 覆盖完,全部 agent-loop 通过**,详见 [`PHASE1_COVERAGE.md`](PHASE1_COVERAGE.md)。累计 moderate 13/13 + complex 2/2 在 agent-loop 层通过。
- [x] **Tier B 配置**(smart_model_routing / approvals.mode / checkpoints.enabled)—— 本次完成,见 §6.5
- [ ] Dockerfile / 多 terminal backend(留给 v1.0 路径)
- [ ] **真实 gateway e2e**(Telegram / Slack / WhatsApp / …):闭环的 send_message 环节代码层已验证(`mcp_bioclaw_send_image` gateway-aware + simulated gateway test),但真 bot token 还没跑过,详见 [`A_TELEGRAM_E2E_RUNBOOK.md`](A_TELEGRAM_E2E_RUNBOOK.md)。

## 2. mcp_bioclaw_server 实现与一个真实 bug 的发现

### 2.1 设计

| 原 BioClaw(`ipc-mcp-stdio.ts:67-102`)| mcp_bioclaw 改写 |
|---|---|
| copy 到 `FILES_DIR` + `<ts>-<rand>.<ext>` | copy 到 `<HERMES_HOME>/outbox/<ts>-<rand>.<ext>` |
| 写 IPC JSON → channel pickup | 无 channel(local backend);return 含 absolute path 的提示字符串 |
| `"Image queued for sending: ..."` | `"Image saved to outbox/... | caption: ... | absolute path: ..."` |

2 个 tool:`send_image`(PNG/JPG/其他图)、`send_file`(PDF/CSV/ZIP/其他)。在 Hermes 里自动挂成 `mcp_bioclaw_send_image` / `mcp_bioclaw_send_file` namespace。

### 2.2 真实 bug:env var 不透传,**差点污染用户 `~/.hermes`**

第一次调用 `send_image`,文件竟然落到 `/home/ubuntu/.hermes/outbox/` — **用户真实 profile**。

**根因**:`bhermes` wrapper 在 shell 层 export `HERMES_HOME`,但 Hermes 启动 stdio MCP subprocess 时**不默认透传 arbitrary env**。我的 server 代码原本用 `os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))` 做 silent fallback → 无 `HERMES_HOME` 时落到用户 home。

**修复**:
1. 清理污染(一个 PNG + 一个新建 outbox 目录)——用户 `~/.hermes` 总字节数恢复到污染前的 2980
2. 改 `mcp_bioclaw_server.py`:移除 silent fallback,改成显式要求 `BIOCLAW_OUTBOX` 或 `HERMES_HOME` 至少之一,缺失时 raise RuntimeError(fail-loud)
3. 改 `hermes-profile/config.yaml`:在 `mcp_servers.bioclaw.env:` 里显式声明 `HERMES_HOME: <project>/hermes-profile`(Hermes 支持的标准语法)

**Lesson for plan §11**:MCP server 的 env 透传规则要加进 regression checklist 第 8 条("MCP server 注册协议兼容")里——这是一个**默默会污染用户 home** 的静默失败模式,必须 fail-loud。

### 2.3 修复后的验证

- `hermes mcp test bioclaw` → 834ms 连通,2 tool discovered
- 二次 `send_image` 调用 → 文件落到 `bioclaw-hermes-py/hermes-profile/outbox/<ts>-<rand>.png`,**用户 `~/.hermes` 字节数仍为 2980(无污染)**
- 返回字符串含 absolute path,agent/user 可直接 `file` / `cp` / `open` 该路径

## 3. 批量迁移数据

39/39 BioClaw skill 全部迁完,Hermes 统一看到 **113 skill**(74 bundled + 39 migrated)。

### 3.1 机械迁移耗时

| Tier | n | 总 CPU 耗时 | PATH_MAPPINGS 命中 |
|---:|---:|---:|---:|
| trivial | 24 | **8.4ms** | 0(无一个 trivial 引用 `send_image`/`send_file`)|
| moderate | 13 | **7.5ms** | 0 |
| complex | 2 | 2.6ms(Phase 0.5)| 1(sec-report)|
| **合计** | **39** | **~19ms** | **1** |

**关键发现**:**整个 BioClaw 39 skill 里,只有 sec-report 一个 skill 在 SKILL.md 正文引用了 `send_image`**。这意味着:
- PATH_MAPPINGS 的复杂度被计划严重高估——实际只影响 1/39 = 2.6% 的 skill
- B1-A 的"批量改写"工作量几乎为零;真正的成本是 `mcp_bioclaw_server` 本体实现(已完成)

### 3.2 Hermes-level 验证

- `bhermes skills list` → 39 local 条目全部出现
- banner skill count: 80 → 113(exactly +33;前面 Phase 0.5 已算 6,新增 33 = 24 trivial + 13 moderate - 已算的 3 trivial + 2 moderate + 1 dup sec-report 在 complex 中)

### 3.3 agent-loop spot check(4 个样本,四维度全覆盖)

| Skill | Tier / 维度 | 结果 |
|---|---|---|
| `query-uniprot` | trivial(real API)| UniProt API 实时 → P00533 = "Epidermal growth factor receptor, Homo sapiens"(正确)|
| `blast-search` | moderate D1 外部 bin | 正确区分 `blastn`(nt)vs `blastp`(protein)使用场景 |
| `proteomics` | moderate D2 heavy py | 正确触发 `skill_view` 两次(SKILL.md + `technical_reference.md`)|
| `skills-hub` | moderate D3 cross-skill | 正确跨引用 atac-seq + scrna-preprocessing |

## 4. 完整闭环:sec-report 通过 Hermes + mcp_bioclaw

### 4.1 agent 轨迹(31s,11 tool calls)

```
1. skill_view(sec-report)                   0.0s  [读 SKILL.md]
2. search_files(*)                          0.8s  [找 test_dataset]
3. search_files(sec_pipeline.py)            0.8s  [定位脚本]
4. terminal $ pip install typst fpdf2 ...   1.8s  [自动装 deps!]
5. terminal $ python3 sec_pipeline.py ...   6.8s  [跑全 pipeline]
6. mcp_bioclaw_send_image(PDF 路径)         0.0s  [投 outbox]
7. reply "done"
```

### 4.2 产物

- `/tmp/sec_full_loop_output/SEC_Analysis_Report.pdf`(pipeline 原生输出)
- `bioclaw-hermes-py/hermes-profile/outbox/1776579504671-tqbwgh.pdf`(**7 页 PDF,1MB**,agent 通过 `mcp_bioclaw_send_image` 投递)
- 6 个 test sample 全部分析(Monomer_Only / Ring_Design ×2 / Dimer_Variant / Mixed_Assembly / Aggregator),Q-score、oligomer 分类、monodisperse 判断都对

### 4.3 一个值得标记的观察:agent 自主 `pip install`

Hermes 的 `terminal` 工具默认 `backend: local` 且 cwd=`.`,agent **自主**跑了:
```
pip install typst fpdf2 scipy matplotlib seaborn
```

结果:
- ✅ 成功(已有的版本满足,只补齐 fpdf2)
- ⚠️ **装到了 user 的 `miniconda/polaris-env`** 环境——跟 BioClaw-Hermes profile 是独立的,但用户其他项目会看到这个新包

**影响评估**:
- `fpdf2` 是轻量纯 Python 库,几乎零污染风险
- 但如果有 skill 装 `tensorflow` 或 `pytorch`,就是 GB 级的 env 污染
- Phase 1 后半段决策点:要不要给 `terminal.backend` 搞一个虚拟化(venv per skill 或 docker-per-run),避免 agent 自主改 host env?

暂记 Future Work;v0.1-alpha 先接受这个行为,文档里提醒用户用一个 throwaway venv 启 bhermes 就能隔离。

## 4.4 Tier B 配置生效验证

`hermes-profile/config.yaml` 追加 3 个 Tier B 段(全部对齐 plan v10 §9.2 上游真实键名):

```yaml
smart_model_routing:
  enabled: true
  max_simple_chars: 160
  max_simple_words: 28
  cheap_model:
    provider: openrouter
    model: google/gemini-2.5-flash

approvals:
  mode: smart      # auxiliary LLM auto-approves safe commands
  timeout: 60

checkpoints:
  enabled: true
  max_snapshots: 50
```

**smart_model_routing 实证生效**:向 bhermes 提一个简单问题 "What is 2+2?",日志显示:

```
🤖 AI Agent initialized with model: google/gemini-2.5-flash
```

——而不是默认的 `claude-opus-4.6`。**简单 turn 被自动路由到便宜模型**,单次 query 成本下降 ~30-50×(opus → flash)。

**`approvals.mode: smart` + `checkpoints.enabled: true` 同场验证**(让 agent 改 `/tmp/checkpoint_probe/probe.txt`):

- **smart 自动批准**:非交互 `-q` 下 `write_file` 没被 block,auxiliary LLM 把它判为低风险,自动放行(否则 `-q` 会 hang 在 approval prompt)
- **checkpoint 生成**:Hermes 先展示 `a//tmp/... → b//tmp/...` diff,然后在 `hermes-profile/checkpoints/68b8999cf5d03bff/` 新建 shadow-git repo(目录名 = sha256(abs_dir)[:16],匹配 plan v10 §9.2 描述)
- 最终 probe.txt 内容正确更改为 "modified by hermes"

**3/3 Tier B 特性全部真实生效**,不只是配置被 parse 了。

## 5. 当前仓库状态

```
bioclaw-hermes-py/
├── .gitignore                                    (profile 运行态全部 gitignore)
├── README.md
├── bin/bhermes                                    (HERMES_HOME 包装)
├── tools/
│   ├── mcp_bioclaw_server.py                      (send_image + send_file,fail-loud)
│   ├── mcp_probe_server.py                        (Phase 0 探针,保留为 reference)
│   ├── skill_migrator.py                          (含 frontmatter-less fallback)
│   └── skill_classifier.py                        (4-dim 分类)
├── hermes-profile/                                (gitignored 运行态 + 非 gitignored 配置)
│   ├── config.yaml                                (最小配置 + mcp_bioclaw.env 声明)
│   ├── .env                                       (gitignored,OpenRouter key)
│   └── skills/                                    (39 迁移 skill,gitignored 运行态)
└── logs/
```

外围产物:
- `docs/BIOCLAW_HERMES_PLAN_ZH.md` v10(未动)
- `docs/PHASE0_RESULTS.md`(Phase 0.5 revision)
- `docs/PHASE1_PROGRESS.md`(本文件)

## 6. §1 工时对照(第 3 次校准)

| 子项 | plan 原估 | Phase 0.5 估 | Phase 1 实测(本次)|
|---|---|---|---|
| skill_migrator 写成 | 隐含 | 3-5 ph | ~2 ph(含 frontmatter-less bug 修)|
| mcp_bioclaw_server 写成 | 隐含 | 3-5 ph | **~1.5 ph**(100 LoC + env var bug 发现修)|
| 全量 39 skill 机械迁移 | 推 27+ ph | 15-30 ph | **<0.1 ph**(pure CPU)+ 验证开销 |
| Runtime dep 处理 | 10-25 ph | 10-25 ph | **~0**(agent 自主 pip,sec-report 一次跑通)|
| 边界 bug buffer | 3-7 ph | 3-7 ph | 已消耗 1 次(env var 透传,~0.5 ph)|
| Tier B 配置 | 13 ph | 13 ph | 未做 |
| **Phase 1 已花** | — | — | **~4-5 ph** |
| **Phase 1 剩余** | — | — | ≤13 ph(主要是 Tier B + 收口验证)|

**Phase 1 total 预测**:**17-22 ph**(vs plan 原估 83-125 ph,**下调 70-100 ph**)。

但这个数字**极为偏乐观**,原因:
1. 本次 agent 自主 pip install 绕过了 runtime dep 问题——如果 Docker backend 是硬要求,加 15-30 ph
2. 只做了 3 spot check,其余 10 个 moderate + 1 complex 没验证——**外推风险**
3. 不包含任何 CI / 打包 / pip-package / 文档——plan §14.4 Phase 1 含这些

**真实合理估计**:**30-50 ph** 把 Phase 1 完整做完(含 Tier B + 所有 spot check + 轻 CI),仍比 plan 乐观 40-70 ph。

## 7. 下一个决策点 / 后续动作

### 7.1 立即可做(本 session 内可续)

- **Tier B 配置落地**(~2-4 ph):`smart_model_routing.cheap_model` + `approvals.mode: smart` + `checkpoints.enabled: true`——已核实 plan v10 的三个键全部正确,直接写进 `hermes-profile/config.yaml` 即可
- **剩余 moderate 的 spot check**(~1-2 ph):blast-search / atac-seq / chip-seq 任一个做一次 agent-loop,验证 D1 external binary tier 的 agent 行为
- **bio-tools 处理策略**:它按设计是 container-pre-install 的 reference skill,Hermes local backend 下它列出的 binary(blastn/blastp/bedtools/pymol)用户 host 不一定有——要不要改 SKILL.md 说"如果本地缺,agent 自主安装 OR 提示用户"?

### 7.2 需要跟你对齐再做

- **是否开始 Phase 2a(Open WebUI 文本前端)**?Phase 1 的核心能力闭环已通,Phase 2a 是 UX 层扩展,不是阻塞
- **Docker 决策**(plan §10 Phase 1 part 2 要 Dockerfile):基于 Phase 1 实测,Docker 不是 v0.1-alpha 必需——可以推迟到 v0.2 或 v1.0

### 7.3 Commit / 版本化

- 当前所有工作在 `main` 分支的 working tree,没 commit
- 建议开一个 `phase0-phase1-foundation` 分支,把 Phase 0 + 0.5 + 1 前半段的所有产物一次性 commit,然后决定是否提 PR 到 upstream BioClaw

---

## 8. 本次 session 总结(<200 字)

Phase 0 + 0.5 + 1 核心内容全部闭环:骨架 / profile 隔离 / `mcp_bioclaw_send_image` 实现 + env var 透传 bug 修复 / 39 skill 全量迁移 / 4 维度 agent-loop spot check / sec-report 完整闭环(pipeline → PDF → outbox)/ Tier B 3 项全实证激活(smart_model_routing 路由到 gemini-flash、approvals 自动批准、checkpoints shadow-git 快照)。

plan §1 工时估计进入"严重偏乐观"区间(实花 ~4-5 ph vs 原估 83-125 ph)——但这只衡量了机械迁移 + 单机验证,不含 Docker / CI / 打包 / 多 skill 深度 runtime 验证。真实 Phase 1 完整体预计 30-50 ph,仍比 plan 乐观 40-70 ph。
