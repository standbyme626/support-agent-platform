### 2）U5-Workflow1-Graphize 验收 checklist

```text
【U5-Workflow1-Graphize 验收 Checklist】

请逐项回答“是 / 否”，并给出证据文件路径与说明：

一、Workflow 1 是否真正 graph 化
[x] 员工请求入口是否已进入 LangGraph 主路径？
[x] SupportIntakeWorkflow 是否已改为 compatibility shell？
[x] 是否不是“旧流程照跑，只包一层 facade”？
[x] 是否定义了清晰的 graph nodes？

二、节点与边
[x] 是否至少存在以下节点或等价节点：
    - ingest_message
    - classify_intent
    - retrieve_context
    - faq_answer_or_ticket_open
    - session_control_detect
    - customer_confirm_detect
    - emit_user_reply
    - emit_collab_push
[x] 是否有清晰 edge 定义？
[x] 是否能在 trace 中看到节点流转？

三、语义边界
[x] session_end 是否与 ticket close 严格分离？
[x] customer_confirm 是否只代表客户确认关闭？
[x] operator_close 是否仍保留独立终态语义？
[x] session_end 是否不会错误关闭 ticket？
[x] customer 自然语言确认关闭是否已在 graph 中显式建模？

四、功能覆盖
[x] FAQ 直答是否仍可用？
[x] 建单是否仍可用？
[x] 会话结束是否仍可用？
[x] 新问题模式是否仍可用？
[x] resolved 后客户自然语言确认关闭是否仍可用？
[x] 是否保留了与旧 response shape 的兼容？

五、测试
[x] 是否新增或更新测试覆盖：
    - FAQ 直答
    - 建单
    - resolved 后客户自然语言确认关闭
    - /end 或自然语言结束当前对话
    - 新问题模式
[x] 测试是否经过真实 graph 路径？

六、trace / grounding
[x] 输出是否带 trace 元数据？
[x] 输出是否带 grounding 或 state snapshot？
[x] 是否能定位每次入口处理经过哪些节点？

七、文档
[x] 是否新增 docs/upgrade5-workflow1.md？
[x] 是否描述了 graph 节点、边、state 与兼容关系？

八、判定标准
[x] 当前 Workflow 1 的主干是否已从旧 workflow 迁到 graph？
[x] 如果把 graph 去掉，Workflow 1 是否会退回旧实现？
[x] 当前是否已达到“按 Upgrade 5 系列完成入口 graph 化”的最低要求？

请最后输出：
1. 通过项
2. 未通过项
3. 回退风险
4. 建议是否进入 U5-Agent-Operator-Dispatch
```

---

