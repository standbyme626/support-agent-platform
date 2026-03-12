# RUNBOOK

**版本：v0.3.0（2026-03-12）**

本文档用于本地开发、联调、验收与故障排查。

## 1. 开发环境启动

### 1.1 后端准备

```bash
cd support-agent-platform
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
export SUPPORT_AGENT_ENV=dev
```

### 1.2 启动 Ops API（后端）

```bash
python -m scripts.ops_api_server --env dev --host 127.0.0.1 --port 18082
```

健康检查：

```bash
curl http://127.0.0.1:18082/healthz
```

### 1.3 启动 Gateway（两种方式）

#### 方式A：嵌入式网关（推荐本地联调）

Ops API、acceptance、wecom bridge 都会在进程内实例化 `OpenClawGateway`，无需额外守护进程。

#### 方式B：外部 OpenClaw profile（企业微信联调）

```bash
openclaw --profile support-agent-wecom config set channels.wecom.bridgeUrl "http://127.0.0.1:18081/wecom/process"
```

然后按你本地 OpenClaw 安装方式重启对应 profile。

### 1.4 启动企业微信 bridge（可选）

```bash
python -m scripts.wecom_bridge_server --env dev --host 127.0.0.1 --port 18081
curl http://127.0.0.1:18081/healthz
```

### 1.5 启动前端

```bash
cd web_console
npm install
npm run dev
```

## 2. 检查命令（质量门）

按顺序执行：

```bash
make validate-structure
make lint
make typecheck
make test
make check
make acceptance
```

前端：

```bash
cd web_console
npm run lint
npm run typecheck
npm run test
```

## 3. 日常运维与调试命令

### 3.1 配置和状态

```bash
python scripts/healthcheck.py --env dev
python scripts/gateway_status.py --env dev
```

### 3.2 入口回放（replay）

```bash
python scripts/replay_gateway_event.py \
  --env dev \
  --channel wecom \
  --session-id demo-001 \
  --text "停车场抬杆故障" \
  --trace-id trace_demo_001
```

### 3.3 trace/debug

```bash
python scripts/trace_debug.py --env dev --trace-id trace_demo_001 --limit 50
python scripts/trace_debug.py --env dev --ticket-id TCK-00001 --limit 50 --include-reliability
python scripts/trace_kpi.py --env dev --output storage/acceptance/trace_kpi_from_log.json
```

### 3.4 acceptance

```bash
python -m scripts.run_acceptance --env dev
```

产物：

- `storage/acceptance/acceptance_summary.json`
- `storage/acceptance/acceptance_summary.md`
- `storage/acceptance/trace_kpi.json`

## 4. 链路验证手册

## 4.1 验证企业微信/渠道链路

1. 启动 `wecom_bridge_server` 与 Ops API。
2. 执行 replay 或真实发消息。
3. 查看：
   - `GET /api/channels/health`
   - `GET /api/channels/events`
   - `GET /api/channels/signature-status`
   - `GET /api/openclaw/replays`
   - `GET /api/openclaw/retries`

预期：

- `ingress_normalized` 与 `egress_rendered` 可见。
- 重放消息命中 `duplicate_ignored`（有 idempotency key 时）。
- 签名问题能在 `signature_rejected` 观测到。

## 4.2 验证审批 / handoff / 进度查询链路

1. 创建工单：`replay_gateway_event.py`。
2. 升级动作触发审批：

```bash
curl -X POST http://127.0.0.1:18082/api/tickets/<ticket_id>/escalate \
  -H 'Content-Type: application/json' \
  -d '{"actor_id":"u_ops_01","note":"需要主管审批"}'
```

3. 查看待审批：

```bash
curl http://127.0.0.1:18082/api/approvals/pending
```

4. 批准/拒绝：

```bash
curl -X POST http://127.0.0.1:18082/api/approvals/<approval_id>/approve \
  -H 'Content-Type: application/json' \
  -d '{"actor_id":"u_supervisor_01","note":"同意"}'
```

5. 验证状态流与事件：

- `GET /api/tickets/<ticket_id>`
- `GET /api/tickets/<ticket_id>/events`
- `GET /api/tickets/<ticket_id>/pending-actions`

6. 进度查询：

- 运营侧：通过 `GET /api/tickets/<ticket_id>` 获取实时状态。
- 员工侧：继续在同会话发送消息，系统会在当前工单上下文下回复处理进展回执（当前无独立 progress API）。

## 5. 常见故障排查

### 5.1 `Config file not found`

- 检查 `SUPPORT_AGENT_ENV`。
- 检查 `config/environments/<env>.toml` 是否存在。

### 5.2 API 启动后无数据

- 先跑一条 replay。
- 检查 SQLite 路径：`python scripts/healthcheck.py --env dev`。

### 5.3 `duplicate_ignored` 频繁出现

- 说明同 `session_id + idempotency_key` 重复。
- 换 `MsgId/message_id` 或 `session_id` 后重试。

### 5.4 升级动作一直 pending

- 确认是否命中审批策略。
- 到 `/api/approvals/pending` 处理审批。

### 5.5 前端页面空白或 500

- 检查 `NEXT_PUBLIC_OPS_API_BASE_URL`。
- 确认 Ops API 可访问 `http://127.0.0.1:18082/healthz`。

### 5.6 trace 不完整

- 用 `scripts/trace_kpi.py` 检查 required events。
- 确认链路是否走完整：ingress -> workflow -> egress。

## 6. 发布/回滚演练

```bash
python -m scripts.deploy_release --env dev
python -m scripts.verify_release --env dev --require-active-release
python -m scripts.rollback_release --env dev
```

一条命令：

```bash
make release-cycle ENV=dev
```
