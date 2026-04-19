# BioClaw-on-Hermes 完整方案（中文 · v10）

> 受众：BioClaw 维护者
> 版本：**v10，2026-04-19**——v9 收口（agent-facing tool 名 `memory` vs 实现函数 `memory_tool` 区分 + `skills.creation_nudge_interval` 默认值口径修正）
> 工作目录：`/home/ubuntu/cqr_files/Bioclaw_paper/BioClaw-Hermes/`
> 上游参考：`qwibitai/nanoclaw` + `qwibitai/hermes-agent`
> 所有 file:line 引用已对照源码核实

---

## 0. 修订历史

### v9 → v10（v9 收口：2 项精度修正,不影响架构）

| # | v9 问题 | 证据 | v10 修正 |
|---|---|---|---|
| 1 | §9.5 多处把 agent 调用写成 `memory_tool(action=...)`——但上游对 agent 暴露的**公开工具名是 `memory`**（schema `"name": "memory"`）；`memory_tool` 只是 Python 实现函数。会直接误导后续 prompt / wrapper / 示例代码 | `tools/memory_tool.py:485` `"name": "memory"`；`website/docs/reference/tools-reference.md:84-88` 列 `memory` toolset → `memory` tool；`website/docs/user-guide/features/memory.md:20` "the agent manages its own memory via the `memory` tool" | **§9.5 全部**凡是 agent 调用 / prompt 里都改成 `memory(action=..., target=..., content=...)`；只有在引用**源码文件或实现函数**时保留 `memory_tool`（例如 `tools/memory_tool.py:434`）|
| 2 | §9.5 写"每 15 轮 skill-creation nudge"——15 只是 `cli-config.yaml.example:449` 示例值,**真实运行时代码在配置缺失时 fallback 到 10** | `run_agent.py:1236` `self._skill_nudge_interval = int(skills_config.get("creation_nudge_interval", 10))` | 统一写成"示例配置 `skills.creation_nudge_interval: 15`（运行时缺省 fallback=10）"；§9.5.1、§9.5.3、§14.2 三处都改 |

### v8 → v9（v8 收口：3 项精度修正）

| # | v8 问题 | 证据 | v9 修正 |
|---|---|---|---|
| 1 | §9.2 Tier B 三个关键配置键没对上游真实 API：(a) smart routing 写作 `provider_routing.enabled` 错——`provider_routing:` 专指 OpenRouter 的 provider 排序/白名单，跟"cheap vs strong 模型路由"是两个 section；(b) approval tool 写作 `permission_mode=ask` 不是真实键；(c) checkpoint 写作 `checkpoint_enabled=true` 不是真实键 | `cli-config.yaml.example:96-109` 有独立 `smart_model_routing:` 段（`enabled`、`cheap_model.{provider, model}`、`max_simple_chars`、`max_simple_words`）；`tools/approval.py:489-518` 读 `approvals.mode`（取值 `"manual"` / `"smart"` / `"off"`，默认 manual）和 `approvals.timeout`；`cli.py:1723-1727` 读 `checkpoints.enabled` + `checkpoints.max_snapshots` | **§9.2 表**三条配置键全部改成上游真实名：`smart_model_routing.enabled` + `smart_model_routing.cheap_model.{provider, model}`；`approvals.mode: smart`（smart 会调 auxiliary LLM 自动放行低风险命令，failback 到 manual）；`checkpoints.enabled: true` + `checkpoints.max_snapshots: 50` |
| 2 | §14.2 仍保留 v7 原文"诚实承认 Hermes 本身没有真正的自我改进,给出 BioClaw 自建的 4 层渐进方案"——跟 v7→v8 已把 §9.5 reframe 为"Hermes 有基础闭环 + BioClaw 加 research-specific 演化层"相矛盾 | §0 v7→v8 表第 1 行 与 §14.2 第 2 条；§9.5.1 已列出 Hermes 的 memory_tool + MEMORY.md/USER.md 自注入 + 10 轮 nudge + plugin 闭环 | **§14.2 第 2 条** 改成"Hermes 已有基础学习闭环（memory_tool + MEMORY.md/USER.md 自注入 + 10 轮 nudge）,BioClaw 在其上加 3 层 research-specific 演化（会话末反思 / Skill 日志 / SOUL.md 更新提案）"——跟 §9.5 同口径；同步去掉 §0 v6→v7 表里"自我改进（Hermes 本身没有）"一行的误导 |
| 3 | §9.5 memory 路径写错 + 忽略 Hermes 已有的 skill-创建 nudge：(a) 写成 "MEMORY.md / USER.md"（隐含在 `~/.hermes/` 下）实际在 `~/.hermes/memories/` 子目录；(b) §9.5.2 列出"Agent 自动写新 skill"作为 Hermes 做不到——其实 `skills.creation_nudge_interval: 15` 已会在每 15 轮 tool call 后提示 agent 自己写 skill | `tools/memory_tool.py:119-155` 取 `get_hermes_home() / "memories"` 下的 `MEMORY.md` + `USER.md`；`cli-config.yaml.example:skills.creation_nudge_interval: 15` | **§9.5** 所有 MEMORY.md/USER.md 路径补全为 `~/.hermes/memories/MEMORY.md` 和 `~/.hermes/memories/USER.md`；**§9.5.2** 把"Agent 自动写新 skill"改成"**没有 BioClaw skill 格式感知的** meta-learning（Hermes 已有通用 `skills.creation_nudge_interval=15` 的 nudge，但 nudge 出来的 skill 是 Hermes 通用格式,不符合 BioClaw 的 skill tree 结构）"，更精确 |

### v7 → v8（v7 收口：3 项小修）

| # | v7 问题 | 证据 | v8 修正 |
|---|---|---|---|
| 1 | §9.5 把 Hermes 定性为"没有自我改进"——实际 Hermes 有基础闭环 | `tools/memory_tool.py:434` 有 `memory_tool` 可供 agent `add`/`replace`/`remove` 主动更新记忆；`~/.hermes/memories/MEMORY.md` + `~/.hermes/memories/USER.md` 自动注入系统提示词；memory provider plugin 还有 Hindsight 的 periodic nudges + RetainDB 的 dialectic synthesis 等 | **§9.5 reframe**：Hermes 已有 basic learning loop（memory tool + 自动 sync），BioClaw 补的是 **research-specific 演化层**（skill 使用模式 + SOUL.md 更新提案）——而非"从零建" |
| 2 | Tier B 里配置键和 backend 描述不对上游真实 API：(a) "RetainDB 零配置本地 SQLite" 错——RetainDB 要 `RETAINDB_API_KEY` 云 key；(b) smart model routing 配置路径写作 `auxiliary.smart_routing` 不准（v8 初版改成 `provider_routing.*` 也不对，v9 修正为 `smart_model_routing.*`——详见 v8→v9 表）| `plugins/memory/retaindb/__init__.py` 文档头："`RETAINDB_API_KEY`（required）" | **§9.2 表**：移除误导的"RetainDB 零 key"条目；零-API-key 路径改成"**内置 MEMORY.md + USER.md + memory tool**"（Layer A 本就包含）|
| 3 | 尾部 v5 残留标签："v5 重算"/"v5 算术自洽"/"v5 微调"/"附录 A v5 修正版"/"——v5 结束——" | 文档历史遗留 | **清掉**；revision history 里 v4→v5 / v5→v6 仍作 archive 引用，标题和小节名不再带 v5 |

### v6 → v7（能力扩展，非错误修正）

v6 只涵盖了 Hermes 最核心的少数能力（压缩、多 provider、错误分类、代理、成本、FTS5、subagent、20 channel、cron），**漏了一大批 Hermes 自己很突出但需要显式启用的能力**。v7 做了一次全面审计，把能继承的都显式列入 roadmap。

| v6 漏掉的 Hermes 能力类别 | 数量 | v7 处理 |
|---|---|---|
| MEMORY.md + USER.md 内置记忆（档次 A）| 1 | 明确写入 Phase 1（默认开即可）|
| opt-in memory plugin（RetainDB 零配置、Hindsight 高级）| 7 个可选 backend | RetainDB 入 Phase 1，Hindsight 入 Phase 2 |
| `agent/smart_model_routing.py`（cheap vs strong 自动路由）| 1 | Phase 1 config |
| `agent/insights.py`（会话分析 + 使用洞察）| 1 | Phase 2，封装为 slash 命令 |
| `agent/credential_pool.py`（多 key 轮换）| 1 | Phase 1 config |
| `agent/title_generator.py`（对话自动命名）| 1 | Phase 1 enable |
| `agent/prompt_caching.py`（Anthropic prompt 缓存）| 1 | Phase 1 enable（省钱）|
| `agent/rate_limit_tracker.py`（自动节流）| 1 | Phase 1 默认 |
| `agent/subdirectory_hints.py`（工作目录感知提示）| 1 | Phase 1 config |
| `agent/manual_compression_feedback.py`（用户纠正压缩）| 1 | Phase 2 接 UI |
| `agent/context_references.py`（外部文件注入上下文）| 1 | Phase 2 接 UI |
| `tools/mixture_of_agents_tool.py`（MoA 多模型集成）| 1 | Phase 2（复杂 bio 分析）|
| `tools/image_generation_tool.py`（图像生成）| 1 | Phase 2 config |
| `tools/checkpoint_manager.py`（shadow git 快照）| 1 | Phase 1（危险操作保护）|
| `tools/approval.py` + `tools/clarify_tool.py`（agent 主动审批 / 澄清）| 2 | Phase 1 config |
| `voice_mode.py` + `tts_tool.py`（语音 + TTS）| 2 | Phase 3 可选 |
| `tools/environments/`（SSH / Modal / Daytona / Singularity）| 5+ | Phase 3 或按需 |
| Browser tool + Camofox | 2 | Phase 2（bio 文献爬取）|
| MCP 外部 server（filesystem / github / fetch / ...）| 若干 | Phase 1 config |
| Skin engine（branding）| 1 | Phase 0（v6 已覆盖但 v7 强化说明）|
| **research-specific 自我改进演化层**（Hermes 已有 `memory` 工具 + MEMORY.md/USER.md + 10 轮 nudge 的基础闭环,但没有针对 skill 参数 / 成功率 / SOUL.md 更新提案）| — | **v7 §9.5 新增最小设计**（v8/v9 reframe 为"基础闭环 + 演化层"两层结构）|

v7 新增两个大节：
- **§9. Hermes 全能力继承矩阵**：58 个能力按 Tier A/B/C/D/E 分类，每项标明启用方式和归属 Phase
- **§9.5. 自我改进最小设计**：4 层渐进方案（Hermes 没有就 BioClaw 自己建）

工时影响：v1.0 从 v6 的 157-250 ph 扩到 **v7 的 225-344 ph**（+70-95 ph）；staged release calendar 从 7.5-10 周扩到 **9.5-12 周**。

### v5 → v6（2 项修正）

| # | v5 问题 | 证据 | v6 修正 |
|---|---|---|---|
| 1 | §7.3 B1-A 代码用 `from mcp.server import Server` + `@server.tool(...)` + `asyncio.run(stdio_server(server))` — **当前 mcp 包的 `Server` 没有 `.tool`**，`stdio_server()` 是低阶 context manager，照写 AttributeError | 本地 `python3 -c "from mcp.server import Server; s=Server('t'); print(hasattr(s,'tool'))"` → `False`；`mcp.server.fastmcp.FastMCP` → `True`；Hermes 自家 `mcp_serve.py:49` + `optional-skills/mcp/fastmcp/templates/file_processor.py:6` 都用 FastMCP | **§7.3 代码改用 FastMCP**：`from mcp.server.fastmcp import FastMCP` + `@mcp.tool` + `mcp.run()` |
| 2 | 总表和 Bottom Line 说 v1.0 = 4-7 calendar weeks（纯工时换算），§10 roadmap 却说 W7.5-W10（含 dogfood 和反馈 loop）——两套口径混用没标注 | v5 §1.4 "4-7 calendar weeks" 和 §10 "W7.5/W10" | **§1.1 明示两套口径并列存在**："engineering-only" 跟 "staged release calendar" 是两码事；§1/§10/§14 打对应 label，不再模糊 |

### v4 → v5（归档）

| # | v4 问题 | 修正 |
|---|---|---|
| 1 | B1-A 用不存在的 `hermes_cli.mcp` 模块 | 改为外部 stdio MCP server + `~/.hermes/config.yaml` `mcp_servers` |
| 2 | 工时口径混乱（22-37 天 vs 6-10 周推不出来）| 改为 person-hours 统一单位 |

v1-v3 的修订历史见附录 D。

---

## 1. 工作量诚实表

### 1.1 两套时间口径约定（v6 明示）

本文档**同时用两套时间口径**，不要混用：

#### A. Engineering-only budget（纯工时换算）
- **person-hour (ph)**：绝对工作量单位
- **work day = 8 ph**
- **engineering week = 5 work days = 40 ph**（1 FTE 连续工作，不含任何非编码时间）
- 本节 §1.2 / §1.3 / §1.4 **全部是这个口径**——回答"做完这些活要敲多少小时键盘"

#### B. Staged release calendar（发版日历）
- 包含 dogfood、用户反馈轮次、bug 修复、稳定化时间
- 比 engineering-only 多 **约 40-50%** 的日历时间
- §10 的 W1-W10 roadmap **是这个口径**——回答"到版本标签 vX.Y 用户能拿到要多少真实日历天数"

**不要直接拿 A 的数字去算发版日期**，也不要把 B 的"某周"当成纯工时预算。两个口径在 §14 Bottom Line 会**并排列**清楚。

### 1.2 Phase 1 分项（v4 方案，数字不变）

| 任务 | 低估 | 高估 |
|---|---|---|
| skill_migrator.py 实现 + 单元测试 | 6 | 8 |
| 38 skill **path migration only**（含 trivial/easy/moderate/complex 四 tier）| 43 | 76 |
| Bio Dockerfile | 6 | 8 |
| 角色提示词 + skin + 配置 | 3 | 3 |
| e2e 测试：3 complex skill 真实跑一遍 | 10 | 15 |
| **Phase 1 总** | **68** | **110** |

### 1.3 各 Phase 工时（v7 含 Tier B/C/E 扩展）

| Phase | 低估（ph） | 高估（ph） | v7 新增内容 |
|---|---|---|---|
| Phase 0 - Ground Zero | 16 | 24 | 不变 |
| Phase 1 - Foundation + Skills + **Tier B 配置**（v7 +15） | **83** | **125** | 原 68-110 + §9.2 Tier B 的 15 ph |
| Phase 2a - Open WebUI 文本 MVP | 8 | 16 | 不变 |
| Phase 2b (B1-B) - Per-skill 行为重写 | 13 | 22 | 不变 |
| Phase 3 - Notebook Export | 20 | 30 | 不变 |
| **v0.1-alpha 总（Tier B 含进来）** | **140** | **217** | v6 是 125-202，v7 多 15 ph |

换算（**engineering-only 口径**，不含 dogfood）：
| 指标 | 低估 | 高估 |
|---|---|---|
| person-hours | 140 | 217 |
| work days (÷8) | 18 | 27 |
| **engineering weeks** (÷40) | **3.5** | **5.5** |

⚠️ 这 3.5-5.5 周是纯工时换算的 engineering weeks，**不是**到 v0.1-alpha 发布的日历周——后者见 §10。

### 1.4 到 v1.0 的升级路径（**engineering-only 口径，v7 含 Tier C + E**）

| 步骤 | 增量（ph） | 累计 ph | 累计 work days | 累计 engineering weeks |
|---|---|---|---|---|
| 到 v0.1-alpha（B1-B + Tier B）| 140-217 | 140-217 | 18-27 | 3.5-5.5 |
| **增量 B1-B → B1-A**（§7.3）| +12-18 | 152-235 | 19-29 | 4-6 |
| **增量 Tier C 核心 4 条**（§9.3：Hindsight + Insights + MoA + Browser）| +20-32 | 172-267 | 22-33 | 4.5-7 |
| **增量自我改进 Layer 2+3**（§9.5）| +18-27 | 190-294 | 24-37 | 5-7.5 |
| **增量 B1-A → B2**（§7.4）| +20-30 | 210-324 | 26-40 | 5.5-8 |
| **增量自我改进 Layer 4**（§9.5，Phase 3）| +15-20 | **225-344** | **28-43** | **5.5-8.5** |

**v1.0 的 engineering-only 总工时：225-344 ph / 28-43 work days / 5.5-8.5 engineering weeks**。

（v6 是 157-250 ph / 4-7 weeks，v7 扩展后 +70-95 ph ≈ +1.5-2 engineering weeks，因为加了 Tier C + 自我改进。）

⚠️ 这**不是**实际到 v1.0 发布的日历周。包含 dogfood / beta 反馈 / 修复 loop 的 staged release calendar 见 §10，实际是 **9-12 calendar weeks**。

### 1.5 各 B-路径独立成本（方便选路）

| 路径 | **独立**实现成本（从零）| 在 B1-B 之上增量 | 在 B1-A 之上增量 |
|---|---|---|---|
| B1-B（per-skill rewrite）| 13-22 ph | — | — |
| B1-A（外部 MCP shim server）| 18-26 ph | **+12-18 ph** | — |
| B2（BioClaw 1.x local-web 作前端）| 30-50 ph | +25-40 ph | **+20-30 ph** |
| B3（改 Hermes API 加附件+PR）| 40-60 ph + 不确定风险 | 不建议 | 不建议 |

增量数字解释：升级时 inbox/outbox 约定、用户文档、skill 迁移、测试基础设施部分可复用，所以 delta 小于独立实现。

---

## 2. NanoClaw → BioClaw fork pattern（不变）

Layer 1 必改 / Layer 2 领域基础设施 / Layer 3 可选增强。

---

## 3. Phase 0：Ground Zero（v2/v3 方案保留）

选项 G2：新建 `bioclaw-hermes-py/`，原 `BioClaw-Hermes/` 改名为 reference。**16-24 ph**。

---

## 4. Hermes 真实入口（v3/v4 保留）

CLI：`hermes chat` / `hermes chat -q` / `hermes dashboard` / `hermes gateway`
文件路径：`~/.hermes/skills/` / `~/.hermes/SOUL.md` / `~/.hermes/skins/*.yaml` / `~/.hermes/state.db` / `~/.hermes/.env` / **`~/.hermes/config.yaml`（B1-A 用，见 §7.3）**

---

## 5. Skill Migration（v3/v4 保留）

### 5.1 整棵 tree compat rewrite
```python
REWRITABLE_EXT = {'.md', '.py', '.txt', '.yaml', '.yml', '.json', '.typ', '.sh', '.toml'}
PATH_MAPPINGS = [
    ('/home/node/.claude/skills', str(HERMES_SKILLS_ROOT)),
    ('/workspace/group',          str(HERMES_WORKSPACE_ROOT)),
    # 'mcp__bioclaw__' 的 rename：Hermes 自动注册为 mcp_<server>_<tool>，见 §7.3
]
```

### 5.2 Tier 工时（§1.2 里汇总了）

Trivial 12 × 0.1-0.25h / Easy 18 × 0.5-1h / Moderate 5 × 3-5h / Complex 3 × 6-10h。

Path migration 总 **43-76 ph** + 3 complex e2e **10-15 ph**。

---

## 6. Phase 2a：Open WebUI 文本 MVP（v3/v4 保留，含 `--add-host`）

```bash
docker run -d -p 3000:8080 \
  -e OPENAI_API_BASE_URL=http://host.docker.internal:8642/v1 \
  -e OPENAI_API_KEY=<key> \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --name open-webui --restart always \
  ghcr.io/open-webui/open-webui:main
```

8-16 ph。只解决文本，不解决文件 I/O。

---

## 7. Phase 2b：文件 I/O 方案

### 7.1 问题约束（不变）

1. Hermes API response 只有 `content: string`
2. Request content 被归一化成字符串，非文本 part 静默丢弃
3. BioClaw `send_image` MCP 工具在 Hermes 生态不存在
4. file-heavy skill（sec-report 等 5-7 个）要解决三件事：输入扫描、输出写入、文件回传

### 7.2 方案 B1-B：Per-Skill Behavioral Rewrite（v0.1-alpha MVP）

方案不变，v4 §7.2 的 sec-report diff 示例保留。

**工时：13-22 ph**。

**利/弊**：不动 Hermes 代码；UX 弱（用户要开文件管理器 + 浏览器双窗口）；适合 internal dogfood，不适合 public v1.0。

### 7.3 方案 B1-A：External stdio MCP Shim Server

**v4 错误**：写成 `from hermes_cli.mcp import register_tool` 进程内 decorator。**上游没这个模块**。

**真实做法**：自建一个独立 stdio MCP server，在 `~/.hermes/config.yaml` 里配上，Hermes 会自动发现并把工具注册为 `mcp_bioclaw_<tool>` 命名空间。

#### 实现（v6 用 FastMCP，跟 Hermes 自家 mcp_serve.py 对齐）

```python
# bioclaw_hermes/mcp_server/__main__.py
"""
BioClaw MCP shim server — provides a send_image-like tool that moves
files to the outbox and returns a text notification for the agent's reply.

Runs as a stdio subprocess spawned by Hermes via ~/.hermes/config.yaml.
Uses FastMCP (same API Hermes itself uses — see
hermes-agent/mcp_serve.py:49 and optional-skills/mcp/fastmcp/templates/).

Install:  pip install "mcp[cli]"   (brings in mcp.server.fastmcp)
"""
from pathlib import Path
import shutil, os
from mcp.server.fastmcp import FastMCP

OUTBOX = Path(os.environ.get(
    "BIOCLAW_OUTBOX",
    Path.home() / ".hermes" / "workspace" / "outbox",
))
OUTBOX.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("bioclaw")

@mcp.tool
def send_image(file_path: str, caption: str = "") -> str:
    """Copy produced file to outbox/ and return a notification string
    the agent can include in its reply to the user."""
    src = Path(file_path)
    if not src.exists():
        return f"❌ File not found: {file_path}"
    dst = OUTBOX / src.name
    shutil.copy2(src, dst)
    suffix = f" — {caption}" if caption else ""
    return f"📎 File saved: outbox/{src.name}{suffix}"

@mcp.tool
def send_message(text: str) -> str:
    """BioClaw's send_message MCP equivalent — echoes into agent reply."""
    return text

if __name__ == "__main__":
    # FastMCP defaults to stdio transport, which is what Hermes spawns.
    mcp.run()
```

**为什么用 FastMCP 不用低阶 Server API**：
- 本地实测 `from mcp.server import Server` 的 `Server` 类**没有 `.tool`** 属性（用低阶 API 加 `@server.tool(...)` 会 AttributeError）
- FastMCP 才是 Hermes 自家 `mcp_serve.py:49` + `optional-skills/mcp/fastmcp/templates/file_processor.py:6` 都用的 API

配置（用户的 `~/.hermes/config.yaml`）：
```yaml
mcp_servers:
  bioclaw:
    command: "python"
    args: ["-m", "bioclaw_hermes.mcp_server"]
    env:
      BIOCLAW_OUTBOX: "/path/to/workspace/outbox"
```

Hermes 启动时会 spawn 这个 subprocess，把 `send_image` 发现为 **`mcp_bioclaw_send_image`**，把 `send_message` 发现为 **`mcp_bioclaw_send_message`**。

#### Skill 里怎么引用

BioClaw 原 skill 里写的是纯 `send_image`（BioClaw 自家 MCP 工具的本名）。在 Hermes 里要把名字改成 Hermes 注册后的 namespace：

```diff
-**Step 4 — Send the PDF report via `send_image` MCP tool**:
+**Step 4 — Send the PDF report via `mcp_bioclaw_send_image` tool**:
 file_path: $HERMES_WORKSPACE_ROOT/outbox/sec_analysis/SEC_Analysis_Report.pdf
 caption: "SEC Analysis Report"
```

`skill_migrator.py` 的 `PATH_MAPPINGS` 加一条：
```python
('send_image',   'mcp_bioclaw_send_image'),    # BioClaw MCP → Hermes external MCP
('send_message', 'mcp_bioclaw_send_message'),
```

（注意这条可能误伤——如果 skill body 里 `send_image` 出现在非工具调用上下文，会被替换。实践中只有 Step 4 的 "via `send_image`" 模式命中，误伤风险低；高风险时用更精确的正则）

#### 工时

| 任务 | 时间 |
|---|---|
| 用官方 `mcp` Python SDK 写 shim server（§7.3 示例代码基础上加 error handling + test）| 6-8 ph |
| 测试 standalone（Hermes 识别、工具 discover、调用 response 正确）| 2-3 ph |
| `~/.hermes/config.yaml` 模板 + 文档 | 1 ph |
| 改 5-7 个 file-heavy skill 里的 `send_image` → `mcp_bioclaw_send_image` 引用 | 3-5 ph |
| e2e 测试（sec-report、report-template 等真实跑通，文件进 outbox）| 4-6 ph |
| 文档 | 2-3 ph |
| **B1-A 独立总** | **18-26 ph** |

**增量 B1-B → B1-A**：
- inbox/outbox 约定 **已经在 B1-B 建立** ✓
- 用户文档框架 **部分复用** ✓
- skill 已经按 outbox 结构重写 ✓
- 新工作：MCP server 实现 + 配置 + skill 里 `send_image` 名字改回（从"不用"改成"用 mcp_bioclaw_send_image"）+ 测试
- **增量 = 12-18 ph ≈ 2-3 work days**

#### 跟上游的耦合面（Finding 1 修正后变小）

- ✅ 依赖项：**官方 MCP Python SDK**（`pip install mcp`）+ Hermes 的 `mcp_servers` 配置接入（文档化公开）
- ❌ **不再依赖** `hermes_cli.mcp`（不存在的模块）
- ❌ 不再 fork / patch Hermes 任何代码
- Regression 面：Hermes 升级时如果改 `mcp_servers` 配置格式或 MCP 工具 namespace 规则，要测；但这是 Hermes 对全部 MCP 接入方都要保持稳定的公开契约，破坏性变更概率低

#### 利/弊

**利**：
- Skill 行为跟 BioClaw 1.x 接近（仍能"发文件给用户"——只是落 outbox 而非 chat inline）
- 不 fork Hermes
- 依赖 Hermes 正经公开的 MCP 扩展点，长期稳定

**弊**：
- 需要用户配置 `~/.hermes/config.yaml`（但 BioClaw 安装器可以自动做）
- UX 仍弱于 inline chat 预览

### 7.4 方案 B2：BioClaw 1.x local-web 作前端（v0.2 → v1.0）

v3 §6.2.2 保留。**独立 30-50 ph，B1-A → B2 增量 20-30 ph**。

### 7.5 方案 B3：R&D Spike（v4 方案保留）

4 层不确定性、不进 roadmap。

### 7.6 选型总结

```
v0.1-alpha (internal dogfood, 3-5 weeks)  →  B1-B (13-22 ph)
    ↓  +12-18 ph / 2-3 work days
v0.2-beta (small user group)              →  B1-A (external MCP shim)
    ↓  +20-30 ph / 3-4 work days
v1.0 (public release)                     →  B2 (BioClaw 1.x web UI)
    [4-7 engineering weeks / 7.5-10 calendar weeks]
    ↓
R&D Spike (optional, no roadmap slot)     →  B3
```

---

## 8. Phase 3：Notebook Export（v2 方案保留）

20-30 ph。

---

## 9. Hermes 全能力继承矩阵（**v7 重写，系统扩展**）

对 Hermes 源码做了系统审计。下表把所有值得继承的能力按**启用成本 + bio 相关性**分成 5 个 Tier：

### 9.1 Tier A — 默认启用（0 工时，v0.1-alpha 自动获得）

| 能力 | 源码 | bio 用途 |
|---|---|---|
| Context compression | `agent/context_compressor.py` | 长 BLAST / scRNA 任务不撞 token |
| Multi-provider routing | `agent/auxiliary_client.py`（10+ provider）| Anthropic + OpenRouter 无缝切 |
| Error classifier + 自动重试 | `agent/error_classifier.py`（13 类）| API 暂挂自动恢复 |
| Proxy resolution | `gateway/platforms/base.py` | 中国 GFW 原生解决 |
| Cost tracking | `hermes_state.py` + `usage_pricing.py` | grant 预算可追踪 |
| FTS5 全文搜索 | `hermes_state.py` | "上次哪个分析用了 1LMT" |
| MEMORY.md + USER.md（档次 A 记忆）| `agent/memory_manager.py` + `BuiltinMemoryProvider` | 跨 session 粗粒度记忆 |
| Model metadata registry（~50 模型）| `agent/model_metadata.py` | context length + pricing 自动知 |
| Prompt caching（Anthropic）| `agent/prompt_caching.py` | 重复 system prompt 大幅降价 |
| Rate limit tracker | `agent/rate_limit_tracker.py` | 免 429 重试风暴 |
| Reasoning preservation | messages.reasoning 列 | Anthropic thinking + Codex reasoning 可复现 |
| 20 channel adapter | `gateway/platforms/` | Slack / 飞书 / 微信 / QQ / Email 等 |
| Cron scheduling | `cron/jobs.py` + `scheduler.py` | 定时跑 pipeline |
| Multi-distribution | pip / brew / Docker / Nix | 用户装起来无门槛 |
| Iteration budget + grace call | `run_agent.py` | 预算失控兜底 |
| Trajectory format | `agent/trajectory.py` | 结构化执行记录可回放 |
| Auxiliary client（cheap LLM）| `agent/auxiliary_client.py` | 压缩 / title / insights 用便宜模型 |
| Subagent delegation | `tools/delegate_tool.py` | 并行跑 N 个 BLAST |

**18 条能力全部 0 工时继承。v0.1-alpha 装上 Hermes 就有。**

### 9.2 Tier B — Opt-in config（每项 1-2 ph，Phase 1 统一开）

| 能力 | 配置方式 | bio 用途 | ph |
|---|---|---|---|
| Smart model routing（简单问题走便宜模型、复杂/debug 保持强模型）| `~/.hermes/config.yaml` 里独立 `smart_model_routing:` 段：`enabled: true` + `cheap_model: {provider, model}`（可选 `max_simple_chars` / `max_simple_words`）。⚠️ 不要跟 OpenRouter 的 `provider_routing:`（控制 provider 排序/白名单）混淆——是两个 section | 简单问题自动走便宜模型、复杂/debug 保持强模型 | 1 |
| Fast mode（Anthropic Priority）| `service_tier=priority` | 紧急分析低延迟 | 0.5 |
| MEMORY.md sync nudge 频率 | `memory.nudge_interval`（默认 10）| 长对话里更频繁提示 agent 沉淀 | 0.5 |
| ~~RetainDB memory plugin（零 key）~~——**v8 移除**：RetainDB 实际需要 `RETAINDB_API_KEY`（云 API），不是零配置。零配置的跨 session 记忆已经由 Tier A 的内置 `memory` 工具 + MEMORY.md/USER.md 提供 | — | — | — |
| Approval tool（危险命令前 agent 主动问/智能放行）| `approvals.mode: smart`（`"manual"` / `"smart"` / `"off"`，默认 manual）+ `approvals.timeout: 60`。smart 模式调 auxiliary LLM 自动放行低风险命令,uncertain/deny 回退到 manual——参考 OpenAI Codex Smart Approvals | 危险命令前 agent 主动问 | 1 |
| Clarify tool | 启用 tool | 不懂就问，减少瞎做 | 1 |
| Credential pool | `~/.hermes/auth.json` 多 key | grant 有 5 个 OpenRouter key 可轮换 | 2 |
| Title generator | 启用开关 | 对话自动命名 "SEC analysis 1LMT" | 1 |
| Subdirectory hints | `config.yaml` | 工作在 `proteomics/` 里自动提示相关 skill | 1 |
| Checkpoint manager（rm/sed 前自动 shadow git 快照）| `checkpoints.enabled: true`（或 CLI `--checkpoints`）+ `checkpoints.max_snapshots: 50`（默认），快照存在 `~/.hermes/checkpoints/{sha256(abs_dir)[:16]}/` | rm/sed 前自动 shadow git 快照 | 2 |
| MCP 外部 server：filesystem | `mcp_servers.filesystem` | 让 agent 访问特定目录 | 1 |
| MCP 外部 server：github | `mcp_servers.github` | PR / issue 操作 | 1 |
| MCP 外部 server：fetch | `mcp_servers.fetch` | HTTP 爬取（替代自家 tool）| 1 |

**12 条能力合计 ~13 ph（约 2 work days），全部 Phase 1 统一开**（v8 移除 RetainDB"零配置"误导条目，合计 -2 ph；v9 校准三个关键配置键到上游真实名:`smart_model_routing.*`、`approvals.mode`、`checkpoints.enabled`，工时不变）。

### 9.3 Tier C — 要 BioClaw 集成工作（Phase 2，每项 5-15 ph）

| 能力 | 工时 | 集成内容 | bio 用途 |
|---|---|---|---|
| Hindsight memory plugin（档次 B+ 知识图谱）| 6-8 ph | 接入 + 用户文档 | 精细记忆："这用户的 SEC 1 柱子 pH 7.4" |
| Insights engine | 5-8 ph | slash 命令 `/insights` + 报表模板 | 月度看：跑了多少任务、花了多少钱、哪些 skill 常用 |
| Mixture of Agents（MoA）tool | 6-10 ph | 为 bio 场景配 reference models | 复杂蛋白结构推理用多模型 voting |
| Image generation tool | 4-6 ph | config provider + 示例 prompt | 生成 schema / cartoon 图 |
| Browser tool + Camofox（可选 stealth）| 5-8 ph | config + 示例脚本 | 爬 PDB / UniProt 深页 |
| Manual compression feedback | 4-6 ph | 接入 Open WebUI 侧边 hook | 用户纠正"别压缩这段，是关键结论" |
| Context references（外部文件注入）| 4-6 ph | 接入 UI 文件选择器 | 把 protocol.md 注入 system prompt |
| MCP OAuth（高级 MCP 鉴权）| 3-5 ph | 文档 | 企业环境的 MCP server 接入 |

**8 条合计 ~35-60 ph，Phase 2 按需选**。BioClaw-Hermes v0.2/v1.0 推荐启用 Hindsight、Insights、MoA、Browser 这 4 条；其他按需。

### 9.4 Tier D — 跳过或按需（Phase 3+ / 用户显式要求）

| 能力 | 为什么跳 / 延后 |
|---|---|
| Voice mode + TTS | bio 研究场景非核心；可选 Phase 3 或 v1.1 |
| Multi-environment（Modal / Daytona / SSH / Singularity 沙盒）| 用户在自己集群跑更常见；按需文档化接入 |
| Home Assistant tool | bio 不涉及 |
| ACP adapter（嵌 Zed / VS Code）| BioClaw 桌面用户，不用 |
| 某些窄 channel（Signal、Matrix、Bluebubbles、DingTalk、Mattermost）| BioClaw 用户主要用 Slack / Feishu / WeChat，其他按需 |

### 9.5 Tier E — Hermes 有基础学习闭环，BioClaw 补 research-specific 演化层

详见独立小节 **§9.5（下方）**。

### 9.6 总工时对比

| Tier | 条数 | 工时 (ph) | 归属 Phase |
|---|---|---|---|
| A（免费）| 18 | 0 | v0.1-alpha 自动 |
| B（opt-in config）| 13 | ~15 | **Phase 1 新增** |
| C（集成工作）| 8 | ~35-60 | **Phase 2 新增**（按选 4-8 条）|
| D（跳过）| 5+ | — | — |
| E（自建，§9.6）| 4 层 | ~30-40 | **Phase 2-3 新增** |

v7 新增 ~80-115 ph。**Phase 1 增量：+15 ph（Tier B）；Phase 2 增量：+35-60 ph（Tier C）+15-20 ph（Tier E 前两层）；Phase 3 增量：+15-25 ph（Tier E 后两层）**。

---

## 9.5 自我改进：Hermes 的基础闭环 + BioClaw 的 research-specific 演化层

### 9.5.1 Hermes 其实已有基础学习闭环

v7 一度把 Hermes 定性为"没有自我改进"，过于简单。再核实后修正：

**Hermes 已有的基础学习闭环**（在 v0.1-alpha 全部默认启用）：

| 机制 | 源码 | 做什么 |
|---|---|---|
| **`memory` 工具**（agent-facing 名字；实现在 `tools/memory_tool.py`）| schema `"name": "memory"` 在 `tools/memory_tool.py:485`；dispatcher `memory_tool(...)` 在 `tools/memory_tool.py:434` | Agent 在任何 turn 里可以调用 `memory(action="add", target="memory", content=...)` 或 `replace` / `remove`（target 取值 `"memory"` 或 `"user"`）——**主动更新** `~/.hermes/memories/MEMORY.md` 或 `~/.hermes/memories/USER.md`，不只是"被动 nudge" |
| MEMORY.md + USER.md 自注入 | `agent/memory_manager.py:build_system_prompt()` | 每次 session 启动,把 `~/.hermes/memories/MEMORY.md` + `~/.hermes/memories/USER.md` 内容塞进系统提示词；`user` target 专门存**用户画像**（偏好、沟通风格、领域） |
| 每 10 轮 memory nudge | `run_agent.py:1136` `_memory_nudge_interval=10`（config `memory.nudge_interval`，默认 10）| 提示 agent 回顾最近对话决定是否调用 `memory` 工具 |
| Skill-creation nudge（每 N 轮 tool call 后提示 agent 考虑保存 skill）| `run_agent.py:1236` `self._skill_nudge_interval = int(skills_config.get("creation_nudge_interval", 10))`——**运行时缺省 fallback=10**；`cli-config.yaml.example:449` 示例写 15 | 复杂任务后提示 agent 考虑**保存 skill**（Hermes 通用 skill 格式）|
| Memory flush on session end | `memory.flush_min_turns: 6`（默认）| 压缩/exit/`/new`/`/reset` 前给 agent 一轮机会沉淀记忆 |
| Memory provider 插件的高级闭环 | `plugins/memory/hindsight/` / `retaindb/` 等 | Hindsight 后台跑 periodic nudges 生成建议；RetainDB 用"dialectic synthesis"持续更新用户模型；每轮自动 prefetch 相关记忆 |

这意味着：**agent 真的会在每次交互里"记东西"并在下次用**。v0.1-alpha 默认就有这个能力。

### 9.5.2 Hermes 基础闭环**做不到**什么

但 Hermes 的内置闭环是**通用 agent 思路**，不针对 research workflow：

- ❌ **Skill 级参数记忆**：Hermes 的 MEMORY.md 是自由文本，没有"哪个 skill 什么参数好用"的结构化记录
- ❌ **成功率统计**：不知道 sec-report 跑 12 次成功 10 次失败 2 次；也没基于这个调整后续行为
- ❌ **SOUL.md 周期化演进**：SOUL.md 一次写死，不会根据用户持续观察生成更新提案
- ❌ **BioClaw skill 格式感知的 meta-learning**：Hermes 的 `skills.creation_nudge_interval=15` 会提示 agent 写新 skill,但写出来的是 Hermes 通用 skill 格式——不符合 BioClaw skill tree 的嵌套目录 / manifest / PATH_MAPPINGS 约束。Hermes 侧"能写"，BioClaw 侧"写出来也不能直接用"

BioClaw 要做的不是"从零建自我改进"，而是**在 Hermes 基础闭环之上加 research-specific 演化层**——强化这 4 个做不到的点。

### 9.5.3 BioClaw-Hermes 4 层演化栈（衔接 Hermes 已有）

**Layer 0（Hermes 已有，0 ph 继承）**：
- `memory(action=add/replace/remove, target=memory|user)` —— agent-facing 工具名 `memory`（Python 实现函数 `memory_tool`）,主动写 `~/.hermes/memories/MEMORY.md` 或 `~/.hermes/memories/USER.md`
- `memory.nudge_interval` 每 10 轮提示 agent 沉淀 + `memory.flush_min_turns` 在 session 结束前最后一刷
- `skills.creation_nudge_interval`（运行时 fallback=10,示例配置常写 15）每 N 轮 tool call 后提示 agent 考虑写新 skill（Hermes 通用格式）
- （可选）memory provider 插件跑 periodic nudges（Hindsight）、dialectic synthesis（RetainDB）

**Layer 1：会话末显式反思**（Phase 2，10-15 ph）
- 每次 session 结束（或长任务结束）时自动触发一个 auxiliary LLM 调用
- Prompt：`"Session 跑了 X 个 turn，用了 Y skill。总结 3-5 行关键学习，格式 '[SKILL] → Insight'，**用 memory(action="add", target="memory", content=...) 写入 ~/.hermes/memories/MEMORY.md**。"`
- 用 cheap model（Haiku），单次 <$0.001
- 实现：挂在 Hermes `memory.flush_min_turns` 已有 flush 机制上,或 `run_agent` 的 session-end hook——**复用现成基础设施,不建新 API**
- **复用 Hermes 已有 `memory` 工具**，不建新 API

**Layer 2：Skill 使用日志 + 参数记忆**（Phase 2，8-12 ph）
- 新文件：`~/.bioclaw-hermes/skill-logs/{skill-name}.jsonl`
- 每次 skill 被调用时自动追加一行：
  ```json
  {"ts":"2026-04-19T10:00:00","skill":"sec-report","args":{"input":"data.zip","col":"A"},"success":true,"duration_s":180,"cost_usd":0.23}
  ```
- skill_migrator 在 Phase 1 注入这个记录 hook（通过 skill body 里加一段 "execution logging" 模板）
- 用途：
  - Agent 可以读 `skill-logs/sec-report.jsonl` 看"上次这个用户跑 sec-report 用了什么参数、成功吗"——算一种局部记忆
  - 用户跑 `/insights` 时看到"你跑了 sec-report 12 次，10 次成功"

**Layer 3：SOUL.md 周期更新提案**（Phase 3，15-20 ph）
- 每 N 个 session（默认 N=20）触发 auxiliary LLM 做一次元分析：
  - 读 MEMORY.md + 近期 skill-logs
  - 识别模式：哪些 skill 反复失败？用户常问什么？哪些 workflow 重复出现？
  - 生成 SOUL.md 更新 **proposal**（diff 格式）：
    ```
    SUGGESTED SOUL.md CHANGE:
    + When user uploads SEC data with column "A", default to "--pH 7.4" 
    + The user prefers summary tables over full paragraphs for bio results
    ```
  - **必须用户手动审批**才生效（一键 accept/reject）
- 这是 Hermes 没有但在 research assistant 场景**特别有价值**的——agent 真的在演化，但演化路径透明可审计

### 9.5.4 诚实边界（Hermes Layer 0 + BioClaw Layer 1-3 合起来）

**整个演化栈能做到**：
- ✅ 跨 session 的用户偏好记住（Layer 0 的 `~/.hermes/memories/USER.md` 已经覆盖；Layer 1 强化反思频率）
- ✅ Skill 的"上次怎么用"可查（Layer 2 结构化 skill-logs）
- ✅ Agent 系统提示词按观察演化（Layer 3 SOUL.md 更新提案）

**做不到**：
- ❌ Agent 自动写出**符合 BioClaw skill tree 规格**的新 skill（Hermes 有通用 skill nudge,但 BioClaw skill 有嵌套目录 / manifest / PATH_MAPPINGS 约束,通用 nudge 写不出来——真正的 bioclaw-skill-creator 算 Future Work）
- ❌ 从坏结果自动学习模型参数（需要 fine-tuning 基础设施）
- ❌ 跨用户学习（隐私 + 多租户复杂度）

### 9.5.5 总工时（v8 按 0-3 重新编号）

| Layer | 工时 | Phase |
|---|---|---|
| 0. Hermes `memory` 工具 + `~/.hermes/memories/MEMORY.md` + `~/.hermes/memories/USER.md` 主动闭环 + skill-creation nudge | 0 | Phase 1 自动（已有）|
| 1. 会话末显式反思 | 10-15 ph | Phase 2 新增 |
| 2. Skill 使用日志 + 参数记忆 | 8-12 ph | Phase 2 新增 |
| 3. SOUL.md 周期更新提案 | 15-20 ph | Phase 3 新增 |
| **BioClaw 新增合计**（Layer 1-3）| **33-47 ph** | Phase 2-3 |

---

## 10. Phased Roadmap

### Phase 总览（v7 含 Tier B/C/E）
| Phase | 工时 (ph) | Work days | 累计 engineering weeks |
|---|---|---|---|
| 0 — Ground Zero | 16-24 | 2-3 | 0.5 |
| 1 — Foundation + Skills + **Tier B**（v7）| 83-125 | 10-16 | 2.5-3.5 |
| 2a — Open WebUI 文本 | 8-16 | 1-2 | 3-4 |
| 2b (B1-B) — Per-skill rewrite | 13-22 | 2-3 | 3.5-5 |
| 3 — Notebook Export | 20-30 | 3-4 | **3.5-5.5**（v0.1-alpha 里程碑）|
| — v0.1-alpha 发布 —| | | |
| delta B1-A | 12-18 | 2-3 | 4-6 |
| **Tier C 核心 4 条**（v7）| 20-32 | 3-4 | 4.5-7 |
| **自我改进 L2+L3**（v7 §9.5）| 18-27 | 2-3 | 5-7.5 |
| delta B2 | 20-30 | 3-4 | 5.5-8 |
| **自我改进 L4**（v7）| 15-20 | 2-3 | **5.5-8.5**（v1.0 里程碑）|

### Staged Release Calendar（**含 dogfood/beta/feedback**，跟 §1 engineering-only 是不同口径，v7 含 Tier B/C/E）

| 日历周 | 内容 | 标签 |
|---|---|---|
| W1 | Windows 探针 + Phase 0 + Phase 1 part 1（skill_migrator + trivial+easy skills）| — |
| W2 | Phase 1 part 2（moderate + complex skills + Dockerfile）| — |
| W3 | Phase 1 + **Tier B 配置**（v7 新增 15 ph）| — |
| W3.5 | Phase 1 e2e + Phase 2a + 开始 Phase 2b | — |
| W4 | Phase 3 Notebook Export | — |
| W4.5 | **v0.1-alpha 内部发布** + dogfood | 🏷️ v0.1-alpha |
| W5-5.5 | dogfood 反馈修复 + Phase 2b 升级 B1-A | buffer |
| W6 | **Tier C 核心**（Hindsight + Insights，v7 新增） | — |
| W6.5 | **v0.2-beta 小范围用户** | 🏷️ v0.2-beta |
| W7 | **自我改进 L2+L3**（会话末反思 + skill 日志，v7 新增）| — |
| W7.5 | **Tier C 进阶**（MoA + Browser，v7 新增）| — |
| W8 | 反馈收集 + Phase 2b 升级 B2 | buffer |
| W8.5 | **自我改进 L4**（SOUL.md 更新提案，v7 新增）| — |
| W9 | 集成测试 + 文档 | — |
| W9.5 | **v1.0 公开发布** | 🏷️ v1.0 |

**乐观（顺利场景）**：
- v0.1-alpha 发布 = W4.5（**~4.5 calendar weeks**）
- v1.0 发布 = W9.5（**~9.5 calendar weeks**）

**保守（每个 buffer 各拖 1 周）**：
- v0.1-alpha 发布 = W5.5（**~5.5 calendar weeks**）
- v1.0 发布 = W12（**~12 calendar weeks**）

**因此 staged release calendar 区间**：
- v0.1-alpha：**4.5-5.5 calendar weeks**
- v1.0：**9.5-12 calendar weeks**

⚠️ 这组数字**比 §1.4 的 engineering-only 区间（3-5 / 4-7 weeks）多 40-50%**——因为包含：
- dogfood / beta 两轮反馈 loop（各约 0.5-1 周 buffer）
- 文档 / 测试 / 打磨时间

§1.4 回答"敲多少小时键盘"；本节回答"用户能拿到版本标签的真实日历周数"。**两者都对，不要搞混**。

---

## 11. 维护现实化

Regression checklist（每次 `pip install --upgrade hermes-agent` 后）：

1. Skill 加载机制兼容
2. Message schema 兼容
3. API server 兼容（Phase 2a）
4. Slash 命令兼容
5. Skill 中 tool 引用兼容
6. Docker 容器兼容
7. skill_migrator PATH_MAPPINGS 重跑
8. **MCP server 注册协议兼容** — `mcp_servers` config 格式、工具 namespace `mcp_<server>_<tool>` 规则、stdio 协议版本（B1-A 之后）

每次 30-60 分钟。

---

## 12. 风险与决策点

### 12.1 Windows 原生支持（不变）
强烈建议 Day 1 探针。

### 12.2 MCP shim server 的稳定性
- ✅ 官方 MCP Python SDK 是公开 API（PyPI `mcp` 包），稳定
- ✅ Hermes `mcp_servers` config 格式文档化（`mcp.md`）
- ⚠️ 注意：Hermes 升级可能改 MCP 工具 namespace 规则——但作为对所有外部 MCP 接入方的公开契约，破坏性变更概率低
- **`hermes_cli.mcp` 不存在**（v4 曾假设、v6 修正），改走外部 MCP server 即绕开

### 12.3 v0.1-alpha vs public release 的预期管理（不变）
README 和 CHANGELOG 写明 v0.1.x 是 alpha，文件 I/O 走 inbox/outbox 是已知限制。

---

## 13. 八个开放问题

1. Phase 0 G1 vs G2？→ G2
2. Phase 2b MVP B1-A vs B1-B？→ **B1-B**（更快、更少依赖）
3. v1.0 选 B1-A vs B2？→ **B2**（UX 更好；B1-A 是过渡）
4. Skill migrator PATH_MAPPINGS 是否包括 send_image→mcp_bioclaw_send_image？→ **是**（§7.3）
5. Windows 探针先做吗？→ **强烈推荐**
6. Notebook export 多媒体？→ v0.1 只文本+代码，图像 v0.2
7. Memory 插件？→ 不开，按需
8. BioClaw 1.x 数据迁移？→ 用户量决定

---

## 14. Bottom Line

### 14.1 三方案最终对比（v7-v10 含 Tier B/C/E 扩展）

| 方案 | Engineering-only 工时（v0.1-alpha / v1.0）| Staged release calendar（v0.1-alpha / v1.0）| 性质 |
|---|---|---|---|
| Migration | — / 37-41 work days | — / ~8-10 calendar weeks | 渐进 |
| Foundation | — / 29-48 work days | — / ~6-10 calendar weeks | 夹层 |
| **BioClaw-on-Hermes v10** | **18-27 / 28-43 work days**（3.5-5.5 / 5.5-8.5 engineering weeks）| **4.5-5.5 / 9.5-12 calendar weeks** | 下游发行版 + 深度能力继承 |

v6 → v7 的工时增加（+70-95 ph）对应**Hermes 全能力继承**+**研究场景演化层**。v8/v9/v10 为零工时的精度修正（config 键 / 路径 / 工具名 / 默认值 / 口径对齐）。

两套数字都参考：
- 拿 engineering-only 跟"我/团队手头有多少人天"对照
- 拿 staged release calendar 跟"用户何时能拿到 v0.1-alpha / v1.0"对照

### 14.2 v7-v10 累积核心变化 vs v6

1. **§9 Hermes 能力全矩阵**（v7 新增）——审计后列出 58 个可继承能力按 Tier A/B/C/D/E 分类，每条标明启用方式和归属 Phase
2. **§9.5 自我改进两层结构**（v7 初版 → v8/v9/v10 reframe）——Hermes 已有**基础学习闭环**（agent-facing `memory` 工具 + `~/.hermes/memories/MEMORY.md` + `~/.hermes/memories/USER.md` 自注入 + 10 轮 `memory.nudge_interval` + `skills.creation_nudge_interval`（运行时 fallback=10,示例配 15）+ 可选 memory-provider 插件）,BioClaw 在其上加 **3 层 research-specific 演化层**（会话末反思 / Skill 参数日志 / SOUL.md 更新提案）
3. **§9.2 Tier B 配置键**（v9 校准）——三个关键配置键全部对齐上游真实名:`smart_model_routing.*`（不是 `provider_routing.*`——后者专指 OpenRouter）、`approvals.mode: smart/manual/off`、`checkpoints.enabled`
4. **v1.0 工时 +70-95 ph**（Tier B +13 / Tier C +35-60 / 演化层 Layer 1-3 +33-47）——从 v6 的 157-250 扩到 **225-344 ph**
5. **Staged release calendar** 从 v6 的 7.5-10 周扩到 **9.5-12 周**（深度能力接入需要 dogfood 反馈 loop）

### 14.3 v6 核心变化 vs v5（归档）

1. §7.3 B1-A 代码改 FastMCP
2. 两套时间口径明示区分

### 14.4 Day 1-2 动作

| Day | 动作 | 输出 |
|---|---|---|
| 1 | Windows 探针 | go/no-go |
| 2 | Phase 0 G2：建 `bioclaw-hermes-py/` + `pip install hermes-agent` + `hermes chat -q "hello"` | dev env |
| 2 | skill_migrator prototype 在 3 个 skill 上 | tier 工时校验 |
| 2 | `pip install mcp`，写一个最小 stdio MCP server（不含业务逻辑，只注册一个 `ping` 工具），配到 `~/.hermes/config.yaml`，用 `hermes chat -q "use mcp_test_ping"` 看 Hermes 能不能发现 | **B1-A 可行性的真实验证（替代 v4 里的"hermes_cli.mcp 是否稳定"）**|

第 4 项是**关键探针**：如果 Hermes 能 discover 外部 MCP 工具，B1-A 整条路就清晰了；如果 discover 有问题（`hermes_cli/mcp_config.py` 有 bug、协议版本不匹配等），提前 2 周发现。

---

## 附录 A：Hermes 真实入口

### A.1 已验证 CLI
`hermes chat` / `hermes chat -q "..."` / `hermes dashboard` / `hermes gateway`

### A.2 已验证文件路径
`~/.hermes/skills/` / `~/.hermes/SOUL.md` / `~/.hermes/skins/*.yaml` / `~/.hermes/state.db` / `~/.hermes/.env` / `~/.hermes/config.yaml`

### A.3 MCP 集成
**用法**：在 `~/.hermes/config.yaml` 的 `mcp_servers` 下声明外部 MCP server，Hermes 自动发现并把工具注册为 `mcp_<server_name>_<tool_name>`。

**不走 hermes_cli.mcp**（不存在），**不 import Hermes internal class**。

### A.4 Python embedding（继续标"待验证"）
`run_agent.py:526` 的 `AIAgent` 是 internal。**原则**：只通过 CLI + API server + 外部 MCP server 三个入口跟 Hermes 交互。

---

## 附录 B：v1 → v6 决策轨迹

| 决策点 | v1 | v2 | v3 | v4 | v5 | v6 |
|---|---|---|---|---|---|---|
| Phase 0 | 漏 | 加 G1/G2 | 保留 | 保留 | 保留 | 保留 |
| Skill 迁移成本 | 1-2h | 16-32h | 32-60h | 43-76h + 10-15h e2e | 不变 | 不变 |
| Chat UX | 自建 80-110h | Open WebUI 8-16h | 2a+2b 分拆 | 2a + 2b-B1-B MVP | 不变 | 不变 |
| B1-A 实现 | — | — | — | `hermes_cli.mcp` 进程内（**错**）| 外部 stdio MCP server（low-level `Server` API，**本地跑不通**）| **FastMCP API**（跟 Hermes `mcp_serve.py:49` 一致）|
| 文件 I/O B3 | — | — | 并列选项 | R&D spike | 保留 | 保留 |
| Phase 1 工时 | — | 40-60h | 48-72h（错）| 68-110h | 不变 | 不变 |
| v0.1 定位 | 公开 | 公开 | 混乱 | alpha 内部 | 不变 | 不变 |
| v1.0 时间表述 | — | — | — | 22-37 天 / 6-10 周（打架）| 4-7 calendar weeks（单口径）| **4-7 engineering weeks + 7.5-10 calendar weeks**（双口径并列）|
| MCP 稳定性风险 | — | — | — | 不确定 | 公开契约，低 | 不变 |

---

## 附录 C：三方案战略差异（保留）

- Migration：BioClaw 是维护对象
- Foundation：BioClaw 是壳
- **BioClaw-on-Hermes**：BioClaw 是 Hermes 生态的**下游发行版**

---

## 附录 D：v1 → v4 修订历史

- v1→v2：基线描述错、skill 成本低估、Hermes 入口写错、维护承诺过乐、notebook export 平移假设
- v2→v3：Open WebUI 不是 local-web 等价物（阻塞级）、skill rewrite 范围、Python embedding API 猜的、docker 命令缺 `--add-host`
- v3→v4：B1 不闭环（阻塞级）、工时不自洽、B3 当 roadmap、v0.1 定位矛盾

详情见 v2/v3/v4 对应章节（已归档）。

——v10 结束——
