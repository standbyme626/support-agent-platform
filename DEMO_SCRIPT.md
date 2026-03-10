# DEMO SCRIPT

## Z2. 目标

在 10-15 分钟内复现 MVP 主流程：消息入口 -> 工单处理 -> 可观测回溯 -> 关键测试验证。

## 0. 预备

```bash
cd support-agent-platform
source .venv/bin/activate
export SUPPORT_AGENT_ENV=dev
```

可选重置：

```bash
rm -f storage/tickets.db storage/gateway-dev.log
```

## 1. 环境健康检查

命令：

```bash
python scripts/healthcheck.py --env dev
```

输入样例：无。

预期输出：

- `status` 为 `ok` 或 `degraded`。
- `checks.storage.sqlite_path` 存在。
- `checks.session_mapper` 返回 `ok=true`。

## 2. 回放一条入口消息

命令：

```bash
python scripts/replay_gateway_event.py \
  --env dev \
  --channel telegram \
  --session-id demo-001 \
  --text "设备故障需要工程师处理" \
  --trace-id trace_demo_001
```

输入样例：

- channel: `telegram`
- session-id: `demo-001`
- text: `设备故障需要工程师处理`
- trace-id: `trace_demo_001`

预期输出：

- `status = "ok"`
- `trace_id = "trace_demo_001"`
- `inbound.metadata.thread_id` 非空
- `outbound.body` 含 `[gateway-ack]`

## 3. 查看网关状态

命令：

```bash
python scripts/gateway_status.py --env dev
```

预期输出：

- `session_bindings >= 1`
- `recent_events` 含最近 trace 事件
- `log_path` 指向可读日志文件

## 4. 按 trace 回溯链路

命令：

```bash
python scripts/trace_debug.py --env dev --trace-id trace_demo_001 --limit 20
```

预期输出：

- 返回 JSON 数组。
- 至少可见 `ingress_normalized` 或其它同 trace 事件。

## 5. 跑关键工作流测试（演示可重复性）

命令：

```bash
python -m pytest tests/workflow/test_workflow_r_s_chain.py -q
```

预期输出：

- 测试通过（`1 passed`）。
- 覆盖 Intake 到 Case Collaboration 串链。

## 6. 结束口径

满足以下条件可宣布演示通过：

1. 步骤 1-5 全部成功。
2. 输出满足预期字段。
3. 无违反非目标约束的实现（OpenClaw 仅接入层，无前端后台）。
