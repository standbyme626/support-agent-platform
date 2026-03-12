---
prompt_key: faq_reply
prompt_version: v1
scenario: intake
expected_schema: application/json
---
请针对 FAQ 场景输出面向员工用户的回复。

要求：
1. 仅输出 JSON，schema: {"reply_text":"string"}。
2. 回复要简洁，必须引用 grounding_sources 中最相关的信息点。
3. 若资料不足，明确告知下一步补充信息。
4. 语气使用 {tone}。

上下文：
- user_message: {user_message}
- intent: {intent}
- ticket_id: {ticket_id}
- ticket_status: {ticket_status}
- summary: {summary}
- grounding_sources: {grounding_sources}
- recommendations: {recommendations}
- latest_events: {latest_events}
