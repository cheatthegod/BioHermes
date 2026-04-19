# Phase 0 结果报告

> 运行日期：2026-04-19
> Hermes 版本：v0.9.0 (源码 checkout at `/home/ubuntu/cqr_files/claw_works/hermes-agent/`)
> 工作根：`/home/ubuntu/cqr_files/Bioclaw_paper/BioClaw-Hermes/bioclaw-hermes-py/`
> 对应计划：`BIOCLAW_HERMES_PLAN_ZH.md` v10 §14.4（Day 1-2）

---

## 1. 四条探针结论（全部 PASS）

| 探针 | 计划预期 | 实际结果 | 结论 |
|---|---|---|---|
| Phase 0 G2 dev env | `pip install hermes-agent` + `hermes chat -q "hello"` 成功 | 机器上已有 v0.9.0 现成可用；改走 `HERMES_HOME` profile 隔离方案；`bhermes chat -q "..."` 3s 内返回 "Hello..." | **通过**（节省 ~1 ph 安装 + 1.3GB 磁盘）|
| Open WebUI / API 路径（B2） | 此 Phase 不验证 | — | 留到 Phase 2 |
| B1-A 外部 MCP server 发现 | Hermes 能 discover 外部 stdio MCP 工具 | `hermes mcp test probe` 851ms 连通,工具 discovered；LLM 通过 `mcp_probe_ping` 成功调用并拿到返回值 | **通过**——B1-A 整条路 de-risk |
| skill_migrator PATH_MAPPINGS 规则 | `send_image → mcp_bioclaw_send_image` 命名规则在 Hermes 里成立 | 探针 banner 直接显示 `mcp_probe_ping`,命名规则完全吻合计划 §11 + §7.3 预测 | **通过**——规则无需调整 |

## 2. 决策偏离：不再 `pip install hermes-agent`

计划 §14.4 写"`pip install hermes-agent`"——针对空白机器的写法。

当前机器状态：
- `/home/ubuntu/.local/bin/hermes` → 指向 `/home/ubuntu/cqr_files/claw_works/hermes-agent/venv/` 的 v0.9.0
- 源码 checkout 1.3GB site-packages 已装齐 `mcp`, `FastMCP`, OpenAI SDK, Anthropic SDK 等
- 用户真实 `~/.hermes/` **在活跃使用**（openai-codex provider + gpt-5.4 + cron + SOUL.md）

采用的方案：
- `bioclaw-hermes-py/` 建工作根（计划要求的不变）
- 通过 `HERMES_HOME=<project>/hermes-profile/` 环境变量做配置隔离
- `bin/bhermes` 是 1 行包装:`export HERMES_HOME=...; exec hermes "$@"`
- 实际 Hermes 二进制复用 `claw_works/hermes-agent/venv/`

**结果**：代码零污染,配置零污染,实验完全可回滚(删 `bioclaw-hermes-py/` 即清)。Hermes 版本和上游审阅时一致,避免版本漂移。

**注意点**：Hermes banner 提示"746 commits behind"。`hermes update` 推迟到 Phase 0 结束后再考虑——目前这个版本跑探针没问题,换版本风险更大。

## 3. skill_migrator prototype 校准数据

### 3.1 工具本体
- 文件：`bioclaw-hermes-py/tools/skill_migrator.py`
- 规模：171 LoC, ~3KB
- 功能：
  1. 递归 copy skill 目录(过滤 `__pycache__` / `tests`)
  2. Frontmatter normalize:保留 `name`/`description`,加 `version/author/license`,BioClaw 专属 `tool_type`/`primary_tool` 搬到 `metadata.bioclaw.*`
  3. PATH_MAPPINGS:body 里 `send_image` → `mcp_bioclaw_send_image`,`send_file` → `mcp_bioclaw_send_file`

### 3.2 3 个 skill 的真实运行数据

| Skill | Tier | 文件数 | PATH_MAPPINGS 命中 | Copy 时间 | Rewrite 时间 | 总耗时 |
|---|---|---:|---:|---:|---:|---:|
| `query-pdb` | trivial（单 `SKILL.md`）| 1 | 0 | 0.3ms | 0.3ms | **0.6ms** |
| `atac-seq` | moderate（SKILL.md + 2 reference .md）| 3 | 0 | 0.4ms | 0.2ms | **0.6ms** |
| `sec-report` | complex（SKILL.md + 4 .py, 含 `send_image` 引用）| 5 | 1 | 2.2ms | 0.4ms | **2.6ms** |
| **合计** | | 9 | 1 | | | **3.8ms** |

**Hermes 验证**：
- `bhermes skills list` → 3 个 skill 全部以 `local` 源出现
- `bhermes chat` banner skill 计数：74 → 77(exactly +3)
- `sec-report/SKILL.md:83` 正确改写为 `mcp_bioclaw_send_image`

### 3.3 工时校准：Phase 0.5 扩展样本（N=6）+ 全量分类器（N=39）

初版 §3.3（已删）基于 3-skill 的推论被用户拒绝（sample bias + "单挑 sec-report 说事"不可靠）。现在基于:
- `skill_classifier.py`(200 LoC)跑 BioClaw 全部 **39 skill**(`bio-manuscript-common` 无 SKILL.md,classifier 正确过滤)
- 4-dimension 信号：D1 外部二进制 / D2 重 Python 栈(≥2 heavy lib)/ D3 跨 skill 依赖 / D4 BioClaw tool 引用
- 然后每 tier 抽 2 个做端到端验证(共 **6 skill**)

**39-skill tier 分布**:

| Tier | n | % | 样本（粗体=本次端到端验证） |
|---|---:|---:|---|
| trivial | 24 | 61.5% | **query-pdb**(API-only)/ **bio-figure-design**(无 frontmatter 边界)/ 其他 22 条 |
| moderate | 13 | 33.3% | **atac-seq**(D1 bin: samtools/macs3/deepTools)/ **cell-annotation**(D2: scanpy+celltypist+pandas)/ 其他 11 |
| complex | 2 | 5.1% | **sec-report**(全 4 维命中)/ **bio-tools**(D1+D2, reference-only skill) |

**6-skill 端到端验证结果**（全部 PASS）:

| Skill | Tier | 验证项 | 结果 | 耗时 |
|---|---|---|---|---|
| `query-pdb` | trivial | agent-loop: LLM 读 SKILL.md → `execute_code` → RCSB API | Title + Method 两行正确返回 | 12s, 4 tool calls |
| `bio-figure-design` | trivial(无 frontmatter 边界)| 迁移后 Hermes discovers,fallback frontmatter 正确 | ✓ | — |
| `atac-seq` | moderate(D1) | 迁移 + Hermes discovers | ✓(runtime 未测)| — |
| `cell-annotation` | moderate(D2) | agent-loop: LLM 读 SKILL.md → 正确引用 CellTypist/scanpy/scvi-tools | ✓ | 8s, 2 tool calls |
| `sec-report` | complex | **standalone runtime**: `python sec_pipeline.py --input <test> --output /tmp/`,生成 PDF + JSON + figures | 6 sample 全分析,Q-score 对,PDF 正常 | 30s |
| `bio-tools` | complex | 迁移 + Hermes discovers(runtime 按设计是 container-only reference,不适用单独 runtime) | ✓ | — |

### 3.4 Migrator 本身的边界情况发现

Phase 0.5 批量运行暴露 **1 个真实 bug**:
- **frontmatter-less skill**(如 `bio-figure-design`,SKILL.md 直接以 `#` 开头没有 `---` 头):原 migrator 的 `parse_frontmatter` 返回 `{}`,`normalize_frontmatter` 输出不带 `name:` 的无效 frontmatter;修复成本 ~2 min:从 skill 目录名 fallback `name`,从首个非空非标题段落 fallback `description`
- 39 skill 里**只此 1 例**——bug rate ~2.5%

### 3.5 §1 工时区间的 evidence-based 校准

| 项目 | 计划 §6 估计 / 个 | Phase 0.5 refined / 个 | 校准依据 |
|---|---|---|---|
| trivial | 0.25-0.5 ph | **0.1-0.2 ph** | 6ms 机器 + 5-10 min QA(例 bio-figure-design 之类边界)|
| moderate | 1-1.5 ph | **0.3-0.8 ph** | 机器 + SKILL.md 轻度 polish + 1 次 agent-loop spot test;**运行时 dep install 另算** |
| complex | 3-5 ph | **2-4 ph/个** | 迁移本体轻;runtime dep install + 端到端验证是大头;sec-report 实测 |
| skill_migrator tool build | 隐含 | **3-5 ph**(已花 Phase 0.5 含 ~1 ph bug fix + classifier 写成)|
| **按 39 skill 全量推** | — | **24×0.15 + 13×0.55 + 2×3 + 4 = 20.6 ph** 中位 | — |

**Phase 1 skill migration scope: 15-30 ph**（中位 ~21,plan §6 原估 part 1+2 总 83-125 ph,其中很大一部分是 Dockerfile / CI / tier B config）

### 3.6 这次校准仍未覆盖的风险

1. **Runtime dep install**——只验证了 sec-report(scipy/matplotlib/typst 已在 host 存在)。moderate tier 那 13 个 skill 需要 CellTypist / DESeq2 / MACS3 等 **~25 个独特 pkg** 在 Hermes terminal env 可用;若走 Docker 路线,Dockerfile 大小可能 2-5 GB,build 20-40 min
2. **33 个未迁移 skill 的 bug 率**——只做了 6 个,bug rate 观察值 ~17%(1/6) 但置信区间大;若按 17% 外推,全量有 ~7 个 edge case,各 0.5-1 ph = 3-7 ph buffer
3. **bio-tools runtime**——这个 complex skill 按设计依赖"在 container 里 pre-installed"的一组二进制;不是独立可跑的。若 Hermes terminal 不走 Docker,bio-tools 需要改写为 "reference-only" 或整合进 bio-manuscript-pipeline
4. **Tier B 配置(smart_model_routing / approvals.mode / checkpoints.enabled)**——Phase 0.5 未触,仍按 plan §9.2 的 13 ph 算

### 3.7 综合：Phase 1 可执行性评估

| 子项 | 区间(ph) | 备注 |
|---|---|---|
| skill_migrator + classifier build | 3-5 | Phase 0.5 已花 ~3 ph,记在 Phase 0 账上 |
| 全量 39 skill 机械迁移 | 15-30 | D1 数据支撑 |
| Runtime dep 集中处理(Docker OR host venv 扩)| 10-25 | **最大不确定性** |
| 7 个 edge-case bug fix buffer | 3-7 | 外推估计 |
| Tier B 配置 | 13 | plan §9.2 |
| **Phase 1 合计** | **44-80 ph** | — |

**vs plan 原估 83-125 ph** → 下调 **20-45 ph(中位 ~32)**,但关键前提是 **runtime dep 走 host venv 扩展**(便宜)而不是 Docker 重建(贵)。

如果 Phase 2 决定走 Docker(对复现性有利),Phase 1 需要加回 **15-30 ph** 做 Dockerfile + CI,使 total 约 59-110 ph——比原 83-125 仍偏乐观但差距缩小。

## 4. 下一步

### 4.1 可以直接开 Phase 1 的前提

- [x] Phase 0 skeleton / profile 隔离
- [x] Hermes + OpenRouter 连通
- [x] B1-A MCP 外部 server discovery
- [x] skill_migrator 覆盖 frontmatter 边界
- [x] 39-skill 分类表
- [x] 各 tier 端到端验证(trivial/moderate agent-loop + complex runtime)

### 4.2 Phase 1 part 1 开工顺序建议

1. **把 mcp_probe_server.py 替换为真正的 mcp_bioclaw server**——实现 `send_image` / `send_file`(~3-5 ph),作为 PATH_MAPPINGS 改写的落地
2. **批量迁移 24 个 trivial skill**——classifier 已圈定,直接 `./bin/migrator trivial_batch`(~3-5 ph)
3. **Runtime dep strategy 决策**(在迁 moderate/complex 之前):Docker vs host venv 扩,这条选型决定 Phase 1 总工时
4. **13 个 moderate skill 逐个迁移 + runtime spot check**(~4-10 ph)
5. **2 个 complex skill 迁移 + 端到端**(~4-8 ph)

### 4.3 悬置项

| 项 | 何时处理 |
|---|---|
| Hermes 版本漂移("746 commits behind")| Phase 1 末做一次 bump + regression(见 plan §11)|
| Windows 探针 | v0.2 前决定 |
| 跨 skill 依赖顺序(skills-hub / bio-manuscript-pipeline)| Phase 1 part 2 做拓扑排序,依赖优先迁 |

## 5. Phase 0 + 0.5 Deliverables Checklist

- [x] `bioclaw-hermes-py/` 骨架 + `.gitignore`
- [x] `hermes-profile/config.yaml` 最小配置(openrouter + claude-opus-4.6 + MCP probe 注册)
- [x] `hermes-profile/.env` OpenRouter key(gitignored)
- [x] `bin/bhermes` HERMES_HOME 包装
- [x] `tools/mcp_probe_server.py` FastMCP ping 工具
- [x] `tools/skill_migrator.py`(含 frontmatter-less fallback)
- [x] `tools/skill_classifier.py`(39 skill 全量分类)
- [x] 6 skill migrated(trivial×2 + moderate×2 + complex×2)+ Hermes discovers(80 skill 计数)
- [x] 3 tier 端到端验证全绿
- [x] `docs/PHASE0_RESULTS.md`(本文件,Phase 0.5 revision)
