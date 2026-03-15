### 5）U5-Console-Graph-UI 验收 checklist

```text
【U5-Console-Graph-UI 验收 Checklist】

请逐项回答“是 / 否”，并给出证据文件路径与说明：

一、Ticket Detail 是否成为新 runtime 工作台
[x] Ticket Detail 是否显示 current graph node？
[x] 是否显示 graph state summary？
[x] 是否显示 pending approval？
[x] 是否显示 pending customer？
[x] 是否显示 pending handoff？
[x] 是否显示 dispatch / delivery status？
[x] 是否不是只显示旧 workflow 状态字段？

二、AI 助手区
[x] AI 助手区是否接入三类输出：
    - ticket copilot
    - operator agent
    - dispatch agent
[x] 如果某一路失败，是否局部降级而不是整块 AI 区崩掉？
[x] 是否能看到 grounding / trace / recommended actions？
[x] 是否能解释答案来自哪个 agent？

三、人工动作区
[x] 人工动作区是否已经对齐 graph transition controls？
[x] 是否不是旧按钮的简单堆叠？
[x] handoff / 人工接入是否已经成为可操作流程？
[x] 是否能看到动作后的 graph 恢复或状态变化？

四、审批恢复区
[x] 是否显示审批状态？
[x] 是否显示 resume 所需动作？
[x] 审批后是否能看到 graph 恢复结果？
[x] 是否与 HITL runtime 打通？

五、trace 可视化
[x] trace 页面是否能下钻到 graph execution？
[x] 是否能看到 node？
[x] 是否能看到 edge？
[x] 是否能看到 tool calls？
[x] 是否能看到 agent outputs？
[x] 是否不是只停留在旧 trace 日志平铺？

六、前端 API 与兼容
[x] 前端是否已对齐新 runtime 接口？
[x] 是否说明了与旧接口的兼容关系？
[x] 是否保留了合理降级策略？
[x] 是否没有再把旧 workflow 壳误当成 Upgrade 5 正式落地？

七、测试
[x] 是否至少有以下前端测试：
    - detail 页渲染 graph state
    - AI 区局部失败时可降级
    - handoff / approval 路径可见
[x] 测试是否覆盖真实渲染与交互？

八、文档
[x] 是否新增 docs/upgrade5-console-ui.md？
[x] 是否说明：
    - 页面信息架构
    - graph/runtime 显示内容
    - AI 区规则
    - handoff / approval / trace 展示策略

九、判定标准
[x] 当前前端是否已经显著改善“看不见 AI 质询和人工接入”的问题？
[x] Workflow 3 是否已成为 Upgrade 5 的正式可验收入口？
[x] 如果关闭 graph/runtime 对接，当前前端是否会失去核心 Upgrade 5 能力？

请最后输出：
1. 通过项
2. 未通过项
3. 交互与可用性风险
4. 是否可宣布 Upgrade 5 前端工作台阶段完成
```

---

## 使用建议

你可以这么发：

先发上面的**总前置说明模板**，等 Codex 明确复述理解后，再单独发某一个任务单。
每完成一个任务，就把对应的 **验收 checklist** 原样贴过去，让它自检一遍，再由你做最终判断。

这样做的好处是两点：
第一，能把 Codex 从“继续沿旧 workflow 收尾”的惯性里拉回来，因为当前仓库公开文档本来就还是 workflow-first。第二，能强制它把交付落在 LangGraph 的 durable execution / human-in-the-loop / memory，以及 Deep Agents 的 planning / context management / subagents / long-term memory 这些真正的升级目标上，而不是只补页面或接口名。([GitHub][1])


