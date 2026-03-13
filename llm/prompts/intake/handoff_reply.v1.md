---
prompt_key: handoff_reply
prompt_version: v1
scenario: intake
expected_schema: application/json
---
你正在回复“已触发人工服务/投诉升级”的员工消息。

要求：
1. 仅输出 JSON，schema: {{"reply_text":"string"}}。
2. 回复必须说明：
   - 已转人工/升级（handoff_decision 与 handoff_reason），且必须出现“人工客服”字样
   - 当前工单状态与编号
   - 用户接下来会看到什么（例如等待人工接入、审批中、队列处理中）
3. 不要输出内部敏感策略细节。
4. 语气使用 {tone}，避免机械模板口吻。

上下文：
- user_message: {user_message}
- intent: {intent}
- ticket_id: {ticket_id}
- ticket_status: {ticket_status}
- ticket_priority: {ticket_priority}
- ticket_queue: {ticket_queue}
- ticket_assignee: {ticket_assignee}
- handoff_decision: {handoff_decision}
- handoff_reason: {handoff_reason}
- summary: {summary}
- grounding_sources: {grounding_sources}
- recommendations: {recommendations}
- latest_events: {latest_events}
