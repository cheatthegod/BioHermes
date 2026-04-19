# A — Gateway Real End-to-End Runbook

> 本 runbook 要证的:**从聊天发一条消息 → BioHermes agent 跑一个 bio skill → PDF/图通过同一条聊天通道返回**,全程无手动干预 —— 这是 "BioHermes 和 BioClaw 一样能把产出发回聊天" 的真实验证(不是 simulated）。
>
> 两条平行路径,按**你手边哪个最快**选一个:
>
> - **Path A1 — Feishu(推荐)**:你 `~/.hermes/.env` 已经配了 7 个 `FEISHU_*` 凭证 + 有可用 bot。credentials 复用到 BioHermes profile 一步到位,不用去 BotFather 另建 bot。~2 分钟。
> - **Path A2 — Telegram**:如果飞书不方便(比如生产 bot 不想借用),去 [@BotFather](https://t.me/BotFather) `/newbot` 开一个临时 bot,token 贴进 profile。~3-5 分钟。
>
> 两条路径的 agent 逻辑、验证点完全一致,只有 §0-§1 不同。
>
> **前置已证**(2026-04-19):
> - `biohermes/mcp_bioclaw_server.py:41-55` — shim 认识 TELEGRAM / DISCORD / SLACK / WHATSAPP / SIGNAL / MATRIX / WEIXIN / **FEISHU** / DINGTALK / QQBOT / MATTERMOST / BLUEBUBBLES / WECOM / EMAIL 共 14 个 `*_HOME_CHANNEL` env var。
> - 模拟测试两次通过:`TELEGRAM_HOME_CHANNEL=-1001234567890` → shim 发出 `send_message(target='telegram:-100...', ...)`;`FEISHU_HOME_CHANNEL=oc_sample_chat_id_12345` → `send_message(target='feishu:oc_sample_chat_id_12345', ...)`。
> - Hermes 原生 `send_message` 工具在所有列出平台上都支持 media_files 附件派发(`tools/send_message_tool.py:205-215, 308-344`;Feishu 媒体入口见 `gateway/platforms/feishu.py:1244+`)。

---

## Path A1 — Feishu(凭证复用,最快)

### A1.0 前置检查(user 侧,~30s)

1. **停用 user 自己的 Hermes gateway**(如果在跑)——Feishu 长连接 / webhook 一次只能一个进程监听:
   ```bash
   hermes gateway status           # 看看有没有 running
   hermes gateway stop             # 如果 running,停掉
   ```

2. **确认你打算用的 Feishu bot 当前不绑 critical 的 production 聊天**——测试过程会向 home channel 发文件;选一个私聊或测试群更安全。

### A1.1 复制 Feishu 凭证到 BioHermes profile(user 侧,~10s)

```bash
cd /home/ubuntu/cqr_files/Bioclaw_paper/BioHermes

# 触发首次 profile seed(如果还没做过)
./biohermes/bin/biohermes --version > /dev/null 2>&1

# 从 user 个人 ~/.hermes/.env 抽出 FEISHU_* 变量,追加到 BioHermes profile
grep -E "^FEISHU_" ~/.hermes/.env >> .biohermes-profile/.env

# 确认
grep -cE "^FEISHU_" .biohermes-profile/.env   # 应为 7(或 user 自己 env 里有多少 FEISHU_ 就多少)
```

### A1.2 启动 BioHermes gateway(前台 + log tail)

```bash
./biohermes/bin/biohermes gateway run 2>&1 | tee .biohermes-profile/logs/feishu-e2e.log
```

成功后终端里应出现类似:
```
✓ Feishu platform ready
  App: <your FEISHU_APP_ID>
  Bot: <your FEISHU_BOT_NAME>
  Long polling active
```

**保持这个终端开着**——下面的步骤在 Feishu 客户端做。

### A1.3 从 Feishu 发三条消息

打开 Feishu,找到你那个 bot(DM 它,或把它拉进一个测试群)。

1. **`/start`** — BioHermes gateway 应回欢迎消息
2. **`/sethome`** — 关键步骤。这让 gateway 把当前 chat_id 写到 profile(同时 set `FEISHU_HOME_CHANNEL` env var,这样 mcp_bioclaw_send_image 后续调用能认出 GATEWAY ACTIVE + 给出正确 `send_message(target='feishu:<chat_id>', ...)` 提示)
3. **实际任务**:
   ```
   Run the sec-report skill on the test dataset at
   /home/ubuntu/cqr_files/Bioclaw_paper/BioClaw-Hermes/container/skills/sec-report/tests/workspace/test_dataset
   then send me the main PDF report via send_image.
   ```

### A1.4 预期 agent 动作 + 观察

用另一个终端 `tail -f .biohermes-profile/logs/feishu-e2e.log`,观察:

| # | 动作 | log / 文件系统证据 |
|---|---|---|
| 1 | `skill_view` 读 sec-report SKILL.md | `📚 skill sec-report` |
| 2 | `terminal` 跑 `sec_pipeline.py`(~6-10s)| `📟 $ python3 sec_pipeline.py ...` |
| 3 | PDF 生成到 `/tmp/.../SEC_Analysis_Report.pdf` | `ls /tmp/sec_*` |
| 4 | `mcp_bioclaw_send_image` 拷贝到 outbox + 返回 GATEWAY ACTIVE hint | `.biohermes-profile/outbox/` 多一个 PDF;hint 字符串含 `target='feishu:<chat_id>'` |
| 5 | **`send_message` 调 Feishu API 发 document 附件** | log `📨 send_message → feishu:...`;**Feishu 聊天里收到 PDF 附件** |

**第 5 步是真实 end-to-end 证据**——飞书里真收到 PDF = 闭环成立。

### A1.5 清理

```bash
# 停 gateway(在 A1.2 的终端 Ctrl+C)

# 撤回 FEISHU_ 凭证(避免 BioHermes profile 长期携带)
sed -i '/^FEISHU_/d' .biohermes-profile/.env

# 恢复 user 个人 Hermes gateway(如果之前 stop 了)
hermes gateway start     # 或 `hermes gateway run` 根据之前怎么跑的
```

---

## Path A2 — Telegram(新 bot,中立验证)

### A2.0 去 BotFather 开临时 bot

1. Telegram 搜 `@BotFather`,`/newbot` 创建 BioHermes 临时 bot(名字如 `BioHermesTest_YYYYMMDD_bot`)
2. 拿到 token(形如 `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### A2.1 写入 profile

```bash
cd /home/ubuntu/cqr_files/Bioclaw_paper/BioHermes
./biohermes/bin/biohermes --version > /dev/null 2>&1   # first-seed

cat >> .biohermes-profile/.env <<EOF
TELEGRAM_BOT_TOKEN=<paste your token here>
# 可选:限制只有指定 Telegram 用户能触发
# TELEGRAM_ALLOWED_USERS=<your user id>
EOF
```

### A2.2-A2.4 启动 / 三条消息 / 观察

步骤和 A1.2-A1.4 完全相同,只是:
- log 会显示 `✓ Telegram bot started`
- `/sethome` 发到 Telegram bot
- 第 5 步 log 是 `📨 send_message → telegram:...`,Telegram 聊天里收到 PDF(若 PDF <50MB 走 `sendDocument`,否则 `sendPhoto` 降级为预览图)

### A2.5 清理

```bash
sed -i '/^TELEGRAM_BOT_TOKEN=/d' .biohermes-profile/.env
# 可选:@BotFather `/deletebot` 销毁这个临时 bot
```

---

## 通用 — 常见故障

| 症状 | 根因 | 修 |
|---|---|---|
| `biohermes gateway run` 找不到 Feishu/Telegram 凭证 | `.biohermes-profile/.env` 没有对应变量 | 重新做 A1.1 / A2.1;确认 profile .env 不是 user ~/.hermes/.env |
| 两个 gateway 都想连 Feishu,其中一个连不上 | User's personal Hermes gateway 还在跑 | `hermes gateway stop`(A1.0 第 1 点漏了)|
| `/sethome` 无响应 | 消息没到 gateway(网络 / webhook / bot 权限)| 查 log;Feishu 要确认 bot 在群里、机器人权限开启 |
| Agent 跑 pipeline 卡在 `pip install scipy/matplotlib/typst` | host Python 缺包 | 预装:`pip install scipy matplotlib seaborn fpdf2`;typst 单独装(`cargo install typst-cli` 或 `apt install typst`)|
| `send_message` 报 `target feishu:... not resolvable` | `/sethome` 没发,或 `FEISHU_HOME_CHANNEL` 没进 env | 重发 `/sethome`,或手动 `export FEISHU_HOME_CHANNEL=<chat_id>` 再 run gateway |
| 聊天里收到文字 "Image saved to outbox/..." 但**没收到 PDF 附件** | Agent 读了 hint 但**没接着调 send_message** | 强化 task prompt 末尾:"after the tool returns, immediately call send_message to deliver the PDF to the chat" |

## 结束后的 deliverable

成功跑通后更新:
- `docs/biohermes/PHASE1_PROGRESS.md` — 勾上"真实 gateway e2e"
- `README.md §3 limitation #1` → "verified with [Feishu|Telegram] bot on YYYY-MM-DD; see A_GATEWAY_E2E_RUNBOOK.md"
- 新建 `docs/biohermes/A_GATEWAY_E2E_RESULT.md` 贴:wall-time / log 关键片段(脱敏 chat_id 和 token)/ Feishu-or-Telegram 截图路径

至此 BioHermes 可公开宣称 **"BioClaw 同构闭环在 Hermes-based BioHermes 上成立,跨平台 7+ 消息通道"**。

这是本轮迭代的最后一步。
