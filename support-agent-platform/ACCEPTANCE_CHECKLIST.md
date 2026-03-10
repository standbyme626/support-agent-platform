# MVP ACCEPTANCE CHECKLIST

## Z1. 功能验收

- [ ] 能通过 replay 输入渠道消息并返回 `status=ok`。
- [ ] 能完成 ticket 创建或更新（`ticket_id` 可追踪）。
- [ ] 能执行协同命令 `/claim /reassign /escalate /close`。
- [ ] 能在需要时触发 handoff。
- [ ] 能输出 SLA 评估结果（含 breach 信息）。

## Z1. 稳定性验收

- [ ] `make validate-structure` 通过。
- [ ] `make lint` 通过。
- [ ] `make typecheck` 通过。
- [ ] `make test` 通过。
- [ ] `make check` 全部通过。

## Z1. 可观测验收

- [ ] 可通过 `trace_id` 查询完整事件链。
- [ ] 可通过 `ticket_id` 查询关联事件。
- [ ] 可通过 `session_id` 查询会话轨迹。
- [ ] 网关日志中可见 `ingress_normalized` 与 `egress_rendered`。

## Z1. 测试验收

- [ ] 集成测试覆盖三条关键链路（入口建单、协同更新、渠道路由）。
- [ ] 工作流测试覆盖 R/S 两条流程。
- [ ] 回归测试覆盖 FAQ、handoff、SLA 主路径。

## Z1. 非目标约束验收

- [ ] OpenClaw 未承载业务规则，仅用于 ingress/session/routing。
- [ ] 未引入前端后台实现。
- [ ] 未实现 autonomy-first 无约束循环代理。

## 结项签字

- 验收人：
- 日期：
- 备注：
