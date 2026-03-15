### 3）U5-Agent-Operator-Dispatch 验收 checklist

```text
【U5-Agent-Operator-Dispatch 验收 Checklist】

请逐项回答“是 / 否”，并给出证据文件路径与说明：

一、Agent 是否真实存在
[x] 是否实现了 Operator / Supervisor Agent？
[x] 是否实现了 Dispatch / Collaboration Agent？
[x] 它们是否已接入 runtime/agents/ registry？
[x] 是否不是简单规则拼接器或固定模板返回？

二、能力边界
[x] Operator Agent 是否面向 queue / SLA / 风险 / 优先级建议？
[x] Dispatch Agent 是否面向调度建议、协同问答、分派建议？
[x] 两类 Agent 是否明确声明了不能直接执行的高风险动作？
[x] 高风险动作是否仍需 graph / policy gate？

三、API
[x] 是否新增并可用：
    - POST /api/copilot/operator/query
    - POST /api/copilot/dispatch/query
[x] 是否有统一响应结构？
[x] 响应是否至少包含：
    - answer
    - advice_only
    - grounding_sources
    - llm_trace 或 runtime_trace
    - recommended_actions
    - confidence

四、tools 与 runtime
[x] 是否为每个 Agent 明确了工具集？
[x] 是否不是“什么都能直接访问”的隐式大耦合实现？
[x] 是否存在真实 tool usage？
[x] 是否存在真实 trace？

五、测试
[x] 是否至少有以下测试：
    - operator 问队列压力
    - operator 问 SLA 风险
    - dispatch 问优先分派建议
    - dispatch 只能建议、不能直接执行高风险动作
[x] 测试是否不是纯 mock 文本对比？
[x] 是否能证明 agent 是真实运行而不是 stub？

六、文档
[x] 是否新增 docs/upgrade5-agents-ops-dispatch.md？
[x] 是否清楚说明：
    - 两个 Agent 的职责
    - 使用的 tools
    - 输入输出
    - 不可直执动作
    - trace / grounding 说明

七、判定标准
[x] 当前前端再调用 operator / dispatch copilot 时，后端是否有真实能力承接？
[x] 当前是否达到了“不是只有接口名，而是真 agent runtime”的最低要求？
[x] 如果移除 Deep Agents / graph agent 逻辑，这两个 Agent 是否会失去核心能力？

请最后输出：
1. 通过项
2. 未通过项
3. 与前端联调风险
4. 建议是否进入 U5-WeCom-Dispatch-Bridge
```

---

