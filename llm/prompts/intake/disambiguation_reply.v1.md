---
prompt_key: disambiguation_reply
prompt_version: v1
scenario: intake
expected_schema: application/json
---
你正在处理“同会话多工单澄清”场景，请生成一条简洁、可执行的澄清回复。

要求：
1. 仅输出 JSON，schema: {{"reply_text":"string"}}。
2. 明确给出三种可执行选项：
   - 继续当前问题
   - 新问题
   - 指定工单号
3. 语言清晰，不做额外承诺，不输出内部术语。
4. 语气使用 {tone}，长度控制在两句话以内。

上下文：
- user_message: {user_message}
- ticket_id: {ticket_id}
- session_mode: {session_mode}
- disambiguation_decision: {disambiguation_decision}
- disambiguation_reason: {disambiguation_reason}
- summary: {summary}
- latest_events: {latest_events}
