# A — Telegram Real End-to-End Runbook

> 当 Telegram bot token 到位,按这个 runbook 逐步执行,~3-5 分钟跑完 BioClaw 同构闭环的**真实验证**。
>
> **前置已证**:`mcp_bioclaw_send_image` gateway-aware(`biohermes/mcp_bioclaw_server.py:41-52, 128-131`)+ Hermes `send_message` 在 gateway 上下文原生支持 Telegram `sendPhoto` / `sendDocument`(`tools/send_message_tool.py:644, 469`)+ 模拟 `TELEGRAM_HOME_CHANNEL=-1001234567890` 已让 shim 发出正确 `send_message(target='telegram:-100...', media_files=[...], text=...)` hint。
>
> **本 runbook 要证的**:从 Telegram 聊天发一条消息 → BioHermes agent 跑一个 bio skill → PDF/图 通过 Telegram 返回到同一个聊天,全程无手动干预。

---

## 0. 准备(user 侧)

1. 打开 Telegram,搜 `@BotFather`,`/newbot` 创建一个**临时 bot**(名字随意,如 `BioHermesTest_YYYYMMDD_bot`)
2. BotFather 返回一个 token,格式 `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`
3. 把 token 贴给我——或者直接 `echo "TELEGRAM_BOT_TOKEN=<token>" >> /home/ubuntu/cqr_files/Bioclaw_paper/BioHermes/.biohermes-profile/.env`(gitignored,不会泄露)

## 1. 配置 profile(~30s)

```bash
cd /home/ubuntu/cqr_files/Bioclaw_paper/BioHermes

# 追加 Telegram token 到 profile .env(如果 user 还没手动加)
cat >> .biohermes-profile/.env <<EOF
TELEGRAM_BOT_TOKEN=<paste token here>
# Optional: restrict bot to specific Telegram user IDs (防误连)
# TELEGRAM_ALLOWED_USERS=<your user id>
EOF

# 如果之前没 seed 过 profile,先 --version 触发 seed
./biohermes/bin/biohermes --version > /dev/null
```

## 2. 启动 gateway(前台,方便看日志)

```bash
./biohermes/bin/biohermes gateway run 2>&1 | tee .biohermes-profile/logs/telegram-e2e.log
```

成功启动后会看到:
```
✓ Telegram bot started — polling for updates
  Bot: @BioHermesTest_YYYYMMDD_bot
```

**留这个终端开着**,下面的步骤在另一个终端或 Telegram 客户端做。

## 3. 从 Telegram 发三条消息

### 3a. 先 pair 上 bot

在 Telegram 里找到你刚建的 bot,发:
```
/start
```

BioHermes gateway 会回一条欢迎消息。

### 3b. 告诉 gateway 这是 home channel

```
/sethome
```

这步**关键**——它让 Hermes 把当前 chat_id 写到 profile(既会持久化到 config.yaml 的 `TELEGRAM_HOME_CHANNEL`,也会 set 同名 env var),之后 `mcp_bioclaw_send_image` 才能 detect 到 GATEWAY ACTIVE 并给出正确的 `send_message(target='telegram:<chat_id>', ...)` hint。

应得到回复类似:
```
✅ Home channel set to <chat name> (ID: -1001234...).
   Cron jobs and cross-platform messages will be delivered here.
```

### 3c. 实际任务——触发 sec-report 闭环

在同一个聊天里发:
```
Run the sec-report skill on the test dataset at
/home/ubuntu/cqr_files/Bioclaw_paper/BioClaw-Hermes/container/skills/sec-report/tests/workspace/test_dataset
then send me the main PDF report via send_image.
```

## 4. 预期行为 + 观察点

Agent 应该执行以下动作序列(用另一个终端 tail log 观察):

| # | 动作 | 观察方式 |
|---|---|---|
| 1 | `skill_view` 读 sec-report SKILL.md | gateway log 出现 `📚 skill sec-report` |
| 2 | `terminal` 跑 `python sec_pipeline.py ...`(~6-10s)| log 出现 `📟 $ python3 sec_pipeline.py ...` |
| 3 | PDF 生成到输出 dir(`/tmp/...`) | `ls /tmp/sec_tg_*` |
| 4 | `mcp_bioclaw_send_image` 拷贝 PDF 到 outbox + 返回 GATEWAY ACTIVE hint | log 出现 `⚡ mcp_bioclaw_send_image`;`.biohermes-profile/outbox/` 多一个 PDF;**hint 字符串含 `target='telegram:<chat_id>'`** |
| 5 | `send_message` 调 Telegram Bot API `sendDocument`(PDF 走 document,不是 photo)| log 出现 `📨 send_message → telegram:...`;**Telegram 聊天里收到 PDF 附件** |

**最后一步是真实证据**——Telegram 里真收到 PDF = 闭环成立。

## 5. 清理(重要)

跑完验证:
```bash
# 停 gateway
# (回到 step 2 终端,Ctrl+C)

# 从 profile .env 删除 token(跑完就不用了)
sed -i '/^TELEGRAM_BOT_TOKEN=/d' .biohermes-profile/.env

# 可选:也从 BotFather 注销这个临时 bot
# /deletebot 在 @BotFather 聊天里
```

## 6. 如果出错,典型排错路径

| 症状 | 根因 | 修 |
|---|---|---|
| `biohermes gateway run` 报 `TELEGRAM_BOT_TOKEN not set` | profile .env 没 reload | 确认 `.biohermes-profile/.env` 里 token 存在且没拼写错;重启 gateway |
| `/start` 无响应,Telegram 那边永远转圈 | Telegram 长 polling 被防火墙 block,或 bot token 错 | 从 BotFather 重新确认 token;或改用 webhook mode(`TELEGRAM_WEBHOOK_URL=https://...`)|
| Agent 跑 pipeline 时卡在 `pip install` | host Python 缺 scipy/matplotlib/typst | 预装:`pip install scipy matplotlib seaborn fpdf2; apt install typst`(or 用 Docker backend) |
| `send_message` 报错 `target telegram:... not resolvable` | `/sethome` 没发,或 `TELEGRAM_HOME_CHANNEL` 没进 env | 检查 `.biohermes-profile/config.yaml` 里 `TELEGRAM_HOME_CHANNEL` 字段;或重发 `/sethome` |
| Telegram 里收到文字说 "Image saved to outbox/..." 但**没收到真 PDF** | agent 读了 mcp_bioclaw 的 hint 但**没接着调 send_message** | 检查 agent loop log;在 task prompt 强化"after saving, call send_message to deliver the PDF through Telegram" |

## 7. 结束后的 deliverable

一次成功跑通后:
- `docs/biohermes/PHASE1_PROGRESS.md` 里 "真实 gateway e2e" 从未打勾 → 已打勾
- README §3 limitation #1 "Telegram / Discord / … e2e not yet run with a real bot token" → 改成 "verified with a Telegram bot; see A_TELEGRAM_E2E_RUNBOOK.md"
- 在 `docs/biohermes/` 加一个 `A_TELEGRAM_E2E_RESULT.md`,贴出 wall-time, log 片段, Telegram 截图路径(脱敏 chat_id)
- BioHermes 至此可以公开宣称"**BioClaw 同构闭环在 Hermes-based BioHermes 上成立**"

这是本轮迭代的最后一步。
