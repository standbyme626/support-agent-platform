# RUNBOOK

## 1. 适用范围

本手册覆盖 MVP 阶段四个运维脚本：

- `scripts/healthcheck.py`
- `scripts/gateway_status.py`
- `scripts/replay_gateway_event.py`
- `scripts/trace_debug.py`

## 2. 运行前检查

1. 进入目录：`cd support-agent-platform`
2. 激活环境：`source .venv/bin/activate`
3. 配置环境：
   - `export SUPPORT_AGENT_ENV=dev`
   - 可选：`export SUPPORT_AGENT_SQLITE_PATH=/absolute/path/tickets.db`

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

## 5. 标准恢复流程

1. 运行 `healthcheck` 确认配置和存储。
2. 运行 `replay_gateway_event` 发送最小样例。
3. 运行 `gateway_status` 检查会话绑定和 recent events。
4. 运行 `trace_debug` 对齐 trace 链路。
5. 必要时执行 `make check`，确认代码与测试基线未破坏。
