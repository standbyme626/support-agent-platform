# Upgrade 5 收口执行看板

更新时间：2026-03-17  
当前主负责人：Codex（与项目 owner 对齐执行）

## 1. 目标与范围

- 目标：把 Upgrade 5 从“可运行但双轨并存”收口到“单主线、口径一致、可验收”。
- 主线决策（待代码落地）：`app/graph_runtime/*` 作为唯一演进主线；`runtime/graph/*` 进入兼容冻结并逐步退役。

## 2. 当前问题清单（按优先级）

### P0（必须先完成）

- [x] P0-1 红灯清除：`tests/workflow/test_support_intake_workflow.py` 失败用例修复并全绿
- [ ] P0-2 唯一架构主线落地：Workflow1 默认运行路径并轨到 `app/graph_runtime/*`
- [x] P0-3a 文档口径对齐（README）：`WECOM_DISPATCH_AUTO_ENABLED` 默认值已与代码对齐
- [ ] P0-3b 文档口径对齐（升级文档）：升级5相关文档与主线决策、兼容壳状态保持一致

### P1（P0 完成后推进）

- [ ] P1-1 薄壳化收口：继续收缩 `scripts/ops_api_server.py`，业务逻辑继续下沉到 `app/transport + app/application + app/domain`
- [ ] P1-2 升级5收口报告：一页版（已完成/未完成/风险点/旧路径退役计划）

## 3. 验收标准（Definition of Done）

### A. 测试验收（硬门槛）

- Workflow 核心回归通过：
  - `pytest -q tests/workflow/test_support_intake_workflow.py`
- Upgrade5 关键集成回归通过：
  - `pytest -q tests/integration/test_u5_runtime_scaffold.py tests/integration/test_copilot_api.py tests/integration/test_wecom_dispatch_bridge.py`

### B. 架构验收（主线唯一化）

- `SupportIntakeWorkflow` 默认图运行路径以 `app/graph_runtime/*` 为主（兼容开关可保留，但非默认）。
- `runtime/graph/*` 标记为 compat/frozen，不再新增业务逻辑。

### C. 文档验收（口径一致）

- README 中涉及默认行为的配置项必须与代码一致。
- 升级5相关文档明确“主线/兼容壳/退役节奏”，避免执行时歧义。

## 4. 执行进度与证据

### 已完成

- [x] 修复 Workflow 红灯并补防回归（commit: `f7c3966`）
  - 已通过：`4 passed`（定向失败用例 + 新增防回归）
  - 已通过：`24 passed`（`tests/workflow/test_support_intake_workflow.py` 全量）
  - 已通过：`12 passed`（Upgrade5 关键集成）
- [x] 命令误判收敛（已落代码）
  - 收紧会话结束与工单列表中文触发词，减少自然语句误判。
  - 显式工单号场景优先按 ticket switch 语义处理。

### 进行中

- [ ] 主线唯一化并轨设计与代码落地（P0-2）
- [ ] 文档口径对齐全量清扫（P0-3b）
- [x] Step 1 子项：`/api/v2/intake/run` 返回契约已补齐 `runtime_graph/runtime_current_node/runtime_path/runtime_state`（加字段兼容）

## 5. 迁移执行顺序（后续按此打勾）

- [x] Step 1：统一 intake 图运行契约（输入/输出/runtime_trace 字段，先完成 `/api/v2/intake/run` 输出侧）
- [ ] Step 2：将 Workflow1 默认图路径并轨到 `app/graph_runtime/intake_graph.py`
- [ ] Step 3：保留 `runtime/graph/*` 兼容回退开关并冻结新增逻辑
- [ ] Step 4：继续 `ops_api_server.py` 薄壳化下沉
- [ ] Step 5：发布一页版升级5收口报告并确认退役窗口

## 6. 风险与回滚策略

- 风险：并轨时如果 runtime trace 字段不一致，前端详情页/trace页可能出现展示偏差。
- 回滚：保留 compat 开关，一旦出现线上回归可切回旧路径并保留事件审计。
