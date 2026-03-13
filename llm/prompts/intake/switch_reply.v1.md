---
prompt_key: switch_reply
prompt_version: v1
scenario: intake
expected_schema: application/json
---
你正在处理“用户切换到另一个工单继续跟进”的场景，请生成确认式回复。

要求：
1. 仅输出 JSON，schema: {{"reply_text":"string"}}。
2. 回复必须明确：已切换到哪个工单、当前状态、下一步动作。
3. 不要承诺无法保证的时间，不输出流程外建议。
4. 语气使用 {tone}，内容自然、简洁。

上下文：
- user_message: {user_message}
- ticket_id: {ticket_id}
- ticket_status: {ticket_status}
- ticket_assignee: {ticket_assignee}
- disambiguation_decision: {disambiguation_decision}
- disambiguation_reason: {disambiguation_reason}
- latest_events: {latest_events}
- recommendations: {recommendations}
