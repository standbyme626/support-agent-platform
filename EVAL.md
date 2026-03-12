# EVAL

**版本：v0.3.0（2026-03-12）**

本文档给出当前版本的模型、检索、接入可靠性、HITL 与工作流验收口径，并记录本次实测结果。

## 1. 模型层评测

## 1.1 评测目标

1. provider 调用可用。
2. prompt registry 与 prompt version 可解析。
3. fallback 不阻断主流程。
4. llm trace metadata 可落地到 ticket/trace 接口。

## 1.2 主要验证方式

- 单元测试：
  - `tests/unit/test_llm_openai_compatible_client.py`
  - `tests/unit/test_llm_fallback_router.py`
  - `tests/unit/test_model_adapter.py`
  - `tests/unit/test_prompt_registry.py`
  - `tests/unit/test_summary_engine_llm_trace.py`
- 集成验证：
  - `tests/integration/test_ops_api_server_smoke.py`（assist 接口含 provider/prompt_version/degraded）
  - `tests/integration/test_traces_api.py`（trace detail 含 model/prompt/retry/success/error）

## 1.3 结论

- 模型调用、降级、trace 字段链路均可观测，满足升级3模型层验收要求。

## 2. 检索评测

## 2.1 评测方法

执行：

```bash
python -m llm.eval.retrieval_eval --output storage/reports/retrieval_eval_latest.json
```

## 2.2 本次结果（2026-03-12）

- `sample_count`: `12`
- `lexical_top3_hit_rate`: `0.25`
- `vector_top3_hit_rate`: `0.50`
- `hybrid_top3_hit_rate`: `0.50`
- `hybrid_top3_lift_vs_lexical_pct`: `100.0`
- `grounding_coverage`: `1.0`
- `similar_cases_availability`: `0.9167`
- Stage gate:
  - `hybrid_lift_ge_15pct`: `true`
  - `grounding_coverage_ge_95pct`: `true`
  - `similar_cases_availability_ge_90pct`: `true`

## 2.3 结论

- 检索增强达标，hybrid 相对 lexical 有显著提升。

## 3. 接入可靠性测试

## 3.1 覆盖范围

1. 渠道路由矩阵（telegram/feishu/wecom）。
2. 签名与来源校验。
3. replay 防重放。
4. outbound 重试可观测。

## 3.2 主要测试

- `tests/integration/test_channel_routing_matrix.py`
- `tests/integration/test_channels_health_api.py`
- `tests/integration/test_openclaw_gateway.py`
- `tests/regression/test_gateway_replay_guard_regression.py`

## 3.3 结论

- 接入层行为与边界符合预期；重复 webhook 不会重复建单；重试与签名事件可追踪。

## 4. HITL / 审批测试

## 4.1 覆盖范围

1. 高风险动作审批申请（pending）。
2. 批准后恢复执行（approve + resume）。
3. 拒绝/超时回退（reject/timeout）。
4. 审批事件写入 timeline 与 trace。

## 4.2 主要测试

- `tests/unit/test_approval_policy.py`
- `tests/unit/test_approval_runtime.py`
- `tests/integration/test_ticket_actions_api.py`
- `tests/integration/test_traces_api.py`

## 4.3 结论

- HITL 闭环成立：审批前不执行高风险动作，审批后可恢复，拒绝/超时可回退。

## 5. 三个工作流验收标准

## 5.1 员工请求入口工作流

- 标准：入口消息可归一化；FAQ/建单/handoff 路径可走通；trace required events 完整。
- 验证：`tests/workflow/test_support_intake_workflow.py`、`tests/integration/test_message_ingress_to_ticket.py`、acceptance 样本。

## 5.2 处理人员协同工作流

- 标准：claim/reassign/escalate/resolve/close/state 有确定性行为；高风险动作进入审批。
- 验证：`tests/workflow/test_case_collab_workflow.py`、`tests/integration/test_ticket_actions_api.py`。

## 5.3 前端工作台处理工作流

- 标准：页面可读取并操作工单、追踪链路、维护 KB、观察渠道。
- 验证：`tests/integration/test_ops_api_server_smoke.py` + `web_console/tests/*`。

## 6. 四个 Agent 验证方式

1. Intake Agent：验证分类、检索、建单、handoff 触发与证据落库。
2. Case Copilot Agent：验证 assist/similar/grounding 输出与 llm trace。
3. Operator Agent：验证 operator/queue copilot 接口返回、grounding 与风险提示。
4. Dispatch Agent：验证 dispatch copilot 与协同命令链路一致性。

## 7. Acceptance 实测结果（2026-03-12）

执行：

```bash
make acceptance
```

结果：

- 样本总数：`3`
- 通过：`3`
- 失败：`0`
- `trace_kpi.chain_complete_rate = 1.0`
- `trace_kpi.critical_missing_rate = 0.0`

样本覆盖：`faq_direct_reply`、`billing_history_case`、`complaint_handoff`。

## 8. 当前全量测试结果总结（2026-03-12）

## 8.1 后端

1. `make validate-structure`：通过
2. `make lint`：通过
3. `make typecheck`：通过（`126` source files）
4. `make test`：通过（`100 passed`）
5. `make check`：通过
   - unit：`59 passed`
   - workflow：`7 passed`
   - regression：`13 passed`
   - integration：`21 passed`
   - smoke replay：`1 passed`
6. `make acceptance`：通过（`3/3 passed`）

## 8.2 前端

执行：`npm run lint && npm run typecheck && npm run test`

- lint：通过
- typecheck：通过
- test：通过（`12 files`, `35 tests`）

## 9. 综合结论

当前版本满足“workflow-first, agent-assisted + OpenClaw边界 + HITL审批 + 可观测可回放”的收口目标，可作为 v0.3.0 交付基线。
