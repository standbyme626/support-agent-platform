# RUNBOOK

## 1. 适用范围

本手册覆盖 MVP 阶段四个运维脚本：

- `scripts/healthcheck.py`
- `scripts/gateway_status.py`
- `scripts/replay_gateway_event.py`
- `scripts/trace_debug.py`
- `scripts/run_acceptance.py`
- `scripts/trace_kpi.py`
- `scripts/deploy_release.py`
- `scripts/verify_release.py`
- `scripts/rollback_release.py`
- `scripts/wecom_bridge_server.py`

## 2. 运行前检查

1. 进入目录：`cd support-agent-platform`
2. 激活环境：`source .venv/bin/activate`
3. 配置环境：
   - `export SUPPORT_AGENT_ENV=dev`
   - 可选：`export SUPPORT_AGENT_SQLITE_PATH=/absolute/path/tickets.db`
   - 可选：配置业务层 LLM（OpenAI-compatible）
     - `export OPENAI_BASE_URL=http://100.90.236.32:11434/v1`
     - `export OPENAI_MODEL=qwen3.5:9b`
     - `export OPENAI_API_KEY=ollama-local`
     - `export LLM_ENABLED=true`
4. 若使用容器 smoke：
   - 安装 Docker 与 Docker Compose
   - 执行 `docker compose build`

## 3. 脚本使用说明

### 3.1 healthcheck

命令：

```bash
python scripts/healthcheck.py --env dev
```

关注字段：

- `status`: `ok` 或 `degraded`
- `checks.config`
- `checks.storage`（含 `sqlite_path`、`applied_migrations`）
- `checks.session_mapper.bindings`

### 3.2 gateway status

命令：

```bash
python scripts/gateway_status.py --env dev
```

关注字段：

- `gateway`
- `sqlite_path`
- `session_bindings`
- `log_path`
- `recent_events`（最近 5 条 trace）

### 3.3 replay gateway event

命令：

```bash
python scripts/replay_gateway_event.py \
  --env dev \
  --channel telegram \
  --session-id demo-001 \
  --text "设备故障需要工程师处理" \
  --trace-id trace_demo_001
```

关注字段：

- `status` 应为 `ok`
- `trace_id` 与传入一致
- `inbound.metadata.thread_id` 非空
- `outbound.body` 包含 `[gateway-ack]`

### 3.4 trace debug

命令：

```bash
python scripts/trace_debug.py --env dev --trace-id trace_demo_001 --limit 20
```

可替换参数：

- `--ticket-id <id>`
- `--session-id <id>`

预期：返回 JSON 数组，含 `event_type`、`trace_id`、`ticket_id`、`session_id`。

### 3.5 acceptance（固定样本自动验收）

命令：

```bash
python -m scripts.run_acceptance --env dev
```

输出文件：

- `storage/acceptance/acceptance_summary.json`
- `storage/acceptance/acceptance_summary.md`
- `storage/acceptance/trace_kpi.json`

验收摘要必须包含：

- 通过/失败样本统计
- 失败样本可复现命令（`replay_command`）
- trace KPI（`chain_complete_rate`、`critical_missing_rate`）

### 3.6 trace KPI（独立计算）

命令：

```bash
python -m scripts.trace_kpi --env dev --output storage/acceptance/trace_kpi_from_log.json
```

可选参数：

- `--trace-ids trace_a,trace_b`
- `--required-events ingress_normalized,egress_rendered,route_decision,sla_evaluated,recommended_actions,handoff_decision`

### 3.7 container smoke（干净环境链路）

命令：

```bash
docker compose run --rm smoke
```

预期：

- 命令退出码为 0
- 输出包含 `1 passed`（`tests/integration/test_openclaw_gateway.py`）

### 3.8 CI 阶段

- `quality`：`make ci`
- `smoke-container`：`docker compose run --rm smoke`
- `acceptance`：`make acceptance-gate`（独立 job，不强耦合 `check`）

### 3.9 deploy（发布前检查 + 快照）

命令：

```bash
python -m scripts.deploy_release --env dev
```

预期：

- `status` 为 `ok`
- 输出 `release_id`、`snapshot_dir`
- 输出可复现命令：`commands.verify`、`commands.rollback`

### 3.10 verify（发布后验证）

命令：

```bash
python -m scripts.verify_release --env dev --require-active-release
```

预期：

- `status` 为 `ok`
- `diagnostics.healthcheck.status` 非 `error`
- `diagnostics.gateway_status.recent_events` 可读

### 3.11 rollback（失败回滚）

命令：

```bash
python -m scripts.rollback_release --env dev
```

预期：

- `status` 为 `ok`
- 返回 `rolled_back_release_id` 与 `restored_paths`

### 3.12 一条命令链（deploy -> verify -> rollback）

```bash
make release-cycle ENV=dev
```

该命令可复现完整发布链路，适合作为 staging/dev 演练入口。

### 3.13 企业微信 bridge（OpenClaw 仅 ingress/session/routing）

1. 启动 bridge 服务：

```bash
python -m scripts.wecom_bridge_server --env dev --host 127.0.0.1 --port 18081
```

2. 配置 OpenClaw 企业微信插件转发到 bridge：

```bash
openclaw --profile support-agent-wecom config set channels.wecom.bridgeUrl "http://127.0.0.1:18081/wecom/process"
```

3. 重启 OpenClaw profile 对应 gateway 进程。
4. 健康检查：
   - `curl http://127.0.0.1:18081/healthz`
   - 企业微信发消息后，bridge 返回 `handled=true`，业务回复来自本仓库 workflow。

## 4. 故障排查步骤

### 4.1 healthcheck 返回 `error` 或 `degraded`

1. 检查 `SUPPORT_AGENT_ENV` 和配置文件路径。
2. 检查 `checks.storage.error` 是否为 SQLite 路径或迁移失败。
3. 清理损坏数据库后重建：
   - 备份旧库；
   - 删除损坏库；
   - 重新执行 `python scripts/healthcheck.py --env dev` 触发迁移。

### 4.2 replay 报 `Unsupported channel`

1. 确认 `--channel` 仅使用 `telegram|feishu|wecom`。
2. 若需新渠道，先实现对应 `channel_adapter` 并注册到 `ChannelRouter`。

### 4.3 trace_debug 没有事件

1. 先执行 replay 命令制造事件。
2. 用 `python scripts/gateway_status.py --env dev` 确认 `log_path`。
3. 检查查询条件是否错用 trace/ticket/session。

### 4.4 协同命令执行失败

1. 检查命令格式：
   - `/reassign` 需要目标 assignee。
   - `/close` 需要 resolution note。
2. 通过 trace/event 日志确认最后一次状态变更事件。

### 4.5 deploy 脚本失败

1. 查看返回 JSON 的 `reason` 与 `diagnostics.healthcheck`。
2. 先执行 `commands.precheck` 修复环境问题。
3. 修复后重新执行 `python -m scripts.deploy_release --env <env>`。

### 4.6 verify 脚本失败

1. 查看 `errors` 是否包含 `active_release_missing` 或 `healthcheck_failed`。
2. 先执行 `commands.healthcheck`、`commands.gateway_status` 收集诊断信息。
3. 若发布异常，执行 `commands.rollback` 回滚。

### 4.7 rollback 脚本失败

1. 查看 `reason` 是否为 `snapshot_missing`。
2. 使用 `diagnostics.missing_snapshots` 定位缺失快照。
3. 执行 `commands.redeploy` 重新发布，随后 `commands.verify` 复核。

### 4.8 企业微信仍走 OpenClaw 内置 Agent

1. 检查 OpenClaw 配置是否存在 `channels.wecom.bridgeUrl`。
2. 确认 bridge 服务存活：`curl http://127.0.0.1:18081/healthz`。
3. 重启 OpenClaw profile 网关进程，避免旧配置残留。
4. 若 bridge 不可达，插件会返回兜底错误文案，不应再触发内置 Agent 推理。

## 5. 标准恢复流程

1. 运行 `healthcheck` 确认配置和存储。
2. 运行 `replay_gateway_event` 发送最小样例。
3. 运行 `gateway_status` 检查会话绑定和 recent events。
4. 运行 `trace_debug` 对齐 trace 链路。
5. 必要时执行 `make check`，确认代码与测试基线未破坏。

## 6. 架构边界提醒

- OpenClaw 仅做接入/会话/路由（ingress/session/routing）。
- 工单业务与 LLM 推理在 `core/`、`workflows/`、`llm/` 内完成，不放入 OpenClaw。
