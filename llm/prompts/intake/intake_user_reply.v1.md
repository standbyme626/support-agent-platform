---
prompt_key: intake_user_reply
prompt_version: v1
scenario: intake
expected_schema: application/json
---
请基于给定工单上下文，生成面向员工用户的自然回复。

要求：
1. 输出 JSON 对象，且仅输出 JSON，不要附加解释文本。
2. JSON schema: {{"reply_text":"string"}}
3. 回复语气使用 {tone}，不夸张、不承诺无法保证的时间。
4. 必须结合 intent、ticket 状态、summary、grounding、recommendations、latest_events。
5. 若信息不足，给出明确下一步（例如补充工单号/截图/时间）。

上下文：
- user_message: {user_message}
- intent: {intent}
- intent_confidence: {intent_confidence}
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
