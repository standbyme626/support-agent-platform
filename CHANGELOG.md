# CHANGELOG

All notable changes to this project are documented in this file.

## [v0.3.0] - 2026-03-12

### 本次收口版（最终工程化交付）

- 统一重写说明文档体系：`README`、`ARCHITECTURE`、`RUNBOOK`、`EVAL`、`UPGRADE3_FINAL`。
- 新增发布文档：`CHANGELOG`、`RELEASE_NOTES`。
- 补齐 Mermaid 图：系统总架构、三个工作流、四个 Agent 分布、状态机、升级3分阶段图。
- 文档口径统一为“代码事实优先”，纠正了历史文档中与实现不一致的描述（如 API 层实现方式、前端范围、升级项落地状态）。
- 版本同步到 `v0.3.0`：`pyproject.toml` 与 `web_console/package.json`。

### 升级3（A/B/C/D）落地摘要

- A 模型层：
  - OpenAI-compatible provider + fallback router。
  - Prompt registry / prompt version。
  - LLM trace metadata（provider/model/prompt/version/latency/retry/token_usage/error）。
- B 检索层：
  - lexical/vector/hybrid 检索。
  - rerank 与 source attribution。
  - retrieval eval 脚本与 gap report 输出。
- C 接入层：
  - signature/source validation。
  - replay guard + idempotency。
  - outbound retry classification + observability。
- D 审批层：
  - approval policy/runtime。
  - pending approvals + approve/reject/timeout。
  - handoff context 保存与恢复执行。

## [v0.2.x] - 升级2里程碑（历史）

### 升级2主要内容

- 交付 `web_console/` Ops Console（Dashboard/Tickets/Traces/Queues/KB/Channels）。
- 打通前后端 `/api/*` 联调链路。
- 形成 Ticket 动作链闭环（claim/reassign/escalate/resolve/close）。
- 增加最小 e2e 流程与前端质量门（lint/typecheck/vitest）。

> 说明：升级2具体任务分解与验收记录见 `升级2*.md` 文档集合。

## [v0.1.x] - 基线版本（历史）

- 建立 workflow-first support ticket 平台基础骨架。
- 完成 OpenClaw ingress/session/routing 适配与 ticket core 基线。
- 建立 unit/workflow/integration/regression 四层测试框架。
