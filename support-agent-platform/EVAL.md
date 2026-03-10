# EVAL

## 1. 验收指标（Y4）

## 1.1 功能指标

- 能完成消息接入、自动建单/更新、协同命令处理、闭环关闭。
- 能在复杂场景触发 handoff，并保留上下文。
- 能依据 SLA 规则输出超时评估结果。

## 1.2 稳定性指标

- `make check` 全绿：`validate-structure + ruff + mypy + pytest`。
- 基线测试应全部通过（当前基线：`27 passed`）。

## 1.3 可观测指标

- 每条链路至少可按一种维度检索：`trace_id`、`ticket_id`、`session_id`。
- 关键事件可见：`ingress_normalized`、`route_decision`、`sla_evaluated`、`handoff_decision`。

## 1.4 约束符合性指标

- OpenClaw 仅限 ingress/session/routing。
- 不交付前端后台。
- 业务规则由 workflow/core 承载，不由模型自由决策。

## 2. 测试覆盖说明

按测试分层说明如下：

- 单元测试（`tests/unit`）
  - 覆盖 adapter、intent、tool、summary/handoff/SLA、repository、ticket API、trace/logger、ops scripts。
- 集成测试（`tests/integration`）
  - 覆盖 `消息入口 -> ticket 创建`、`ticket -> 协同更新`、`渠道路由矩阵`、`OpenClaw gateway`、`G-Q 引擎链路`。
- 工作流测试（`tests/workflow`）
  - 覆盖 Support Intake、Case Collaboration、R->S 串链。
- 回归测试（`tests/regression`）
  - 覆盖 FAQ 回答、handoff、SLA 触发三条主路径。

## 3. 演示观察点

演示时建议重点观察：

1. replay 后是否生成可追踪的 `trace_id`。
2. `gateway_status` 是否出现 `session_bindings` 与 `recent_events`。
3. `trace_debug` 能否串起 ingress 与业务事件。
4. workflow 链路是否完成创建、协同命令、关闭或 handoff。

详见 [DEMO_SCRIPT.md](./DEMO_SCRIPT.md)。

## 4. 风险边界

当前版本的明确边界：

- 渠道接入以 mock/replay 与适配器骨架为主，未覆盖生产网络不稳定与重试策略。
- 存储为 SQLite，未覆盖多实例并发写入场景。
- Agent 策略为流程增强，不提供自治任务规划。
- 无前端操作台与权限体系。

## 5. 结论口径

若满足以下条件，可判定 MVP 达成：

1. `make check` 全部通过。
2. 演示脚本可复现关键链路且输出与预期一致。
3. 非目标约束未被破坏。
