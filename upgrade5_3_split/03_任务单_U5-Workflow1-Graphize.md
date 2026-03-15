### 任务单 2：U5-Workflow1-Graphize

这个任务单直接把 **Workflow 1 员工请求入口** 从旧的 `SupportIntakeWorkflow` 迁到 graph 思路上。之所以先迁 Workflow 1，是因为 README 已经把它定义成入口理解、FAQ/建单分流、必要时 handoff 与协同推送，这条线最适合优先 graph 化。v2 合约也已经明确把 `resolve / customer-confirm / operator-close / session_end` 拆开了，所以迁移时要把 ticket 终态与 session 结束严格分离。([GitHub][1])

```text
你现在要做的是 Upgrade 5 第二阶段：把 Workflow 1（员工请求入口）迁移到 LangGraph 运行时。

背景要求：
- 现有仓库里有 Support Intake 语义，但 Upgrade 5 目标不是继续堆旧 workflow，而是把入口流 graph 化。
- 必须保留 LangGraph / Deep Agents 目标。
- 不允许把任务简化成“保持旧逻辑不动，只包一层 facade”。

任务目标：
A. 把员工请求入口流拆成显式 graph nodes，至少包括：
   - ingest_message
   - classify_intent
   - retrieve_context
   - faq_answer_or_ticket_open
   - session_control_detect
   - customer_confirm_detect
   - emit_user_reply
   - emit_collab_push
B. 将原有 SupportIntakeWorkflow 改造成 compatibility shell：
   - 接收旧入口
   - 转发到新的 graph runtime
   - 输出与旧系统兼容的 response shape
C. 把 session_end / new_issue 与 ticket close 严格分开：
   - session_end 只结束会话上下文
   - customer_confirm / operator_close 才能触发 ticket close 语义
D. customer 自然语言确认关闭必须在 graph 中显式建模，不允许散落在 if/else 中。
E. FAQ 直答、建单、会话结束、新问题模式都要在 graph trace 中可见。
F. 输出节点必须带 trace / grounding / state snapshot 元数据。

必须交付：
1. Workflow 1 的 graph 实现代码。
2. SupportIntakeWorkflow compatibility shell 改造。
3. 新增测试覆盖：
   - FAQ 直答
   - 建单
   - resolved 后客户自然语言确认关闭
   - /end 或自然语言结束当前对话
   - 新问题模式
4. 一份 docs/upgrade5-workflow1.md，附 graph 节点与边说明。
5. 最少一个 trace 示例输出，能展示 graph state 流转。

完成定义（DoD）：
- Workflow 1 主路径进入 LangGraph，而不是继续由旧 workflow 主导。
- session_end 与 ticket close 不混淆。
- 测试通过，trace 可见。
- 旧接口仍能工作，但内部已走新 graph。

禁止事项：
- 不允许删除原有功能点来“完成迁移”。
- 不允许把 graph 只做成空壳。
- 不允许绕过 session_end / customer_confirm / operator_close 的边界定义。
```

---

