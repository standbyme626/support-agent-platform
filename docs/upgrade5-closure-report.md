# Upgrade 5 一页收口报告（2026-03-17）

## 1. 项目现状（一句话）

这是一个面向工单协同与客服自动化的支持平台，当前主架构已经切到 `app/graph_runtime + app/application + app/domain + app/transport`，并保留旧路径兼容壳。

## 2. 升级5已经完成什么

- Workflow1 主线并轨完成：
- 默认运行路径：`app/graph_runtime/intake_graph.py`
- `runtime/graph/intake_graph.py`：compat/frozen 兼容转发壳
- API 契约补齐完成：
- `/api/v2/intake/run` 已补 `runtime_graph`、`runtime_current_node`、`runtime_path`、`runtime_state`
- README 口径对齐完成：
- `WECOM_DISPATCH_AUTO_ENABLED` 默认行为已与代码一致
- 升级文档口径对齐完成：
- `upgrade5-workflow1.md`
- `upgrade5-runtime.md`
- `upgrade5-migration-note.md`
- `upgrade5-closure-tracker.md`
- 核心回归验证通过：
- `tests/workflow/test_support_intake_workflow.py`：24 passed
- `tests/integration/test_u5_runtime_scaffold.py tests/integration/test_copilot_api.py tests/integration/test_wecom_dispatch_bridge.py tests/integration/test_ticket_actions_api.py`：16 passed

## 3. 还没完成什么

- P1-1 `ops_api_server.py` 薄壳化还未完成：
- 现状是已下沉一部分路由到 `app/transport/http/handlers.py`，并新增
- `app/application/intake_runtime_service.py`（intake/investigation）
- `app/application/session_runtime_service.py`（session_new_issue/session_end_v2）
- 但 `scripts/ops_api_server.py` 仍承担较多编排与流程控制逻辑，仍需继续下沉

## 4. 风险点

- 薄壳化过程中，如果 API 兼容字段漏传，可能导致前端 trace 展示偏差。
- 旧兼容壳长期保留会形成“双路径心智成本”，团队容易把新逻辑误写到旧层。
- 运行链路越来越长后，需要持续靠集成测试兜底，否则回归风险会上升。

## 5. 退役计划（建议）

- 2026-03-20 前：
- 完成 `ops_api_server.py` 下一轮下沉，新增逻辑禁止进入 compat 壳
- 2026-03-24 前：
- 冻结 `runtime/graph/*` 业务改动权限，仅允许修复兼容性问题
- 2026-03-31 前：
- 输出旧路径退役评审结论（是否可移除、是否保留只读兼容窗口）

## 6. 结论

Upgrade 5 的 P0 已收口完成，主线已统一、口径已一致；当前剩余核心工作是 P1-1 薄壳化，把“看起来乱”的主要来源进一步压缩掉。
