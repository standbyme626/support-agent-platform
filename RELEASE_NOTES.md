# RELEASE NOTES

## Release v0.3.0

- 发布日期：2026-03-12
- 发布类型：升级3收口版（可展示、可阅读、可维护、可交付）

## 主要能力

1. 三个工作流共享同一套 ticket/case core。
2. 四个 Agent 能力接口齐备（Intake / Case Copilot / Operator / Dispatch）。
3. OpenClaw 接入可靠性增强（签名、防重放、重试观测、渠道健康）。
4. HITL 审批链路闭环（pending -> approve/reject/timeout -> resume）。
5. 前端 Ops Console 与后端 API 一体化联调。

## 主要改进

1. 模型层：provider fallback、prompt version、llm trace 全链路可见。
2. 检索层：hybrid/vector/rerank/source attribution 已接入。
3. 运行层：acceptance + trace KPI + release/verify/rollback 脚本齐备。
4. 文档层：架构、运行、评测、升级总结与发布文档统一。

## 已知限制

1. API 层当前使用 `http.server`，并非 FastAPI。
2. SQLite 为单实例形态，不覆盖多实例并发写入场景。
3. Operator/Queue/Dispatch Copilot 当前以规则化回答 + grounding 为主，尚未全部切到真实 LLM 生成。
4. 员工“进度查询”当前以工单详情接口与会话回执组合实现，暂无独立进度意图 API。
5. 未引入多租户/RBAC 权限体系。

## 建议下一步（克制范围）

1. 将 Operator/Dispatch Copilot 从规则化回答逐步切到真实模型调用，并保持现有 trace 字段兼容。
2. 把员工进度查询补成独立意图路径（保留 workflow-first 约束）。
3. 在不改变业务边界前提下，引入更强的存储与并发方案（如 Postgres）。
