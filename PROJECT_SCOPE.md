# PROJECT_SCOPE

## 1. 项目定义（What It Is）

`support-agent-platform` 是一个 **Ticket-Centric Workflow System with Agent Capabilities**，即：

- 以 `ticket/case` 为核心业务对象的客服工单系统。
- 以 **workflow-first** 为主干：建单、状态流转、SLA、升级、关闭均为可审计流程。
- 以 **agent-assisted** 为增强：在分类、检索、摘要、推荐动作、转人工节点引入 LLM/Agent 能力。
- 以消息入口驱动：企业微信/飞书/Telegram 等作为交互入口，OpenClaw 负责接入层能力。

## 2. 非目标定义（What It Is Not）

本项目 **不是**：

- 通用聊天机器人项目。
- 通用自主代理平台（autonomy-first / 无限自循环）。
- 以 OpenClaw 承载业务规则的“渠道即业务”系统。
- 只做 FAQ 问答而不具备工单生命周期管理的系统。
- 重型 ITSM 平台复刻项目。

## 3. A2：Workflow-First 原则

以下能力必须固定在工作流与业务规则层，不由模型自由决策：

- 是否建单、何时建单。
- ticket 状态流转与关闭条件。
- SLA 时限、催办与升级触发条件。
- 人工接管（handoff）触发与接回机制。

模型能力只用于增强节点质量，不替代业务主干：

- 意图分类、FAQ/SOP/历史工单检索。
- 回复草稿、intake/case/wrap-up 摘要。
- recommended actions 与相似案例建议。

## 4. A3：禁止项清单

以下事项为明确禁止：

1. 禁止实现“通用聊天机器人”而不落地到 `ticket/case` 对象。
2. 禁止把 OpenClaw 当业务引擎（仅可用于 channel ingress、session、routing）。
3. 禁止 MVP 阶段优先建设前端后台（先打通消息入口 + Ticket 后端 + 管理 API）。
4. 禁止仅实现 FAQ 问答，必须覆盖 `create/update/assign/reassign/escalate/summary/handoff`。
5. 禁止移除 human handoff，复杂 case 必须可转人工并保留上下文证据。
6. 禁止无测试交付（单元、接口/集成、workflow、回归测试缺一不可）。
7. 禁止采用 autonomy-first（无限循环、多轮自发拆任务、无约束工具探索）。
8. 禁止照搬参考仓实现（参考资料用于边界校准，不用于拼贴式复制）。
9. 禁止把系统做成重型 ITSM 复刻，偏离当前客服工单场景目标。

## 5. 验收口径（A 组）

满足以下条件即视为 A1~A3 完成：

- 能清晰回答“系统是什么 / 不是什么”。
- 文档明确 workflow-first、agent-assisted 的边界。
- 禁止项具备可执行与可检查性，能用于后续任务评审。
