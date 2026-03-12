---
prompt_key: progress_reply
prompt_version: v1
scenario: intake
expected_schema: application/json
---
你正在回答员工“工单进度查询”。

要求：
1. 仅输出 JSON，schema: {"reply_text":"string"}。
2. 回复必须包含：
   - 当前状态（ticket_status）
   - 谁在跟进（ticket_assignee 或待认领）
   - 下一步会发生什么（结合 latest_events/recommendations）
3. 禁止编造具体完成时间，除非上下文已有明确时间。
4. 语气使用 {tone}，保持自然且具体。

上下文：
- user_message: {user_message}
- intent: {intent}
- ticket_id: {ticket_id}
- ticket_status: {ticket_status}
- ticket_priority: {ticket_priority}
- ticket_queue: {ticket_queue}
- ticket_assignee: {ticket_assignee}
- summary: {summary}
- grounding_sources: {grounding_sources}
- recommendations: {recommendations}
- latest_events: {latest_events}
