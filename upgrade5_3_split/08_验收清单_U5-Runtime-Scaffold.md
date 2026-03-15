## 二、每个任务完成后的“验收 checklist 原文”

下面是 5 份，一份对应一个任务。你可以在 Codex 完成后直接贴给它，要求它逐项自检；也可以自己拿来验收。

---

### 1）U5-Runtime-Scaffold 验收 checklist

```text
【U5-Runtime-Scaffold 验收 Checklist】

请逐项回答“是 / 否”，并给出证据文件路径与说明：

一、依赖与目录
[x] 是否已引入 LangGraph 相关运行时依赖？
[x] 是否已引入 LangChain 相关依赖？
[x] 是否已引入 Deep Agents 相关依赖？
[x] 是否新增了清晰的 runtime 目录结构？
[x] 是否存在 runtime/graph/？
[x] 是否存在 runtime/agents/？
[x] 是否存在 runtime/state/？
[x] 是否存在 runtime/tools/？
[x] 是否存在 runtime/checkpoints/？

二、统一运行时骨架
[x] 是否定义了统一 state schema？
[x] state schema 是否至少包含：
    - ticket
    - session
    - handoff
    - approval
    - grounding
    - trace
    - copilot_outputs
    - channel_route
[x] 是否实现了最小可运行 graph？
[x] graph 是否不是空壳，而是真的可 invoke / run？
[x] 是否支持 interrupt / resume？
[x] 是否存在 checkpoint / persistence 骨架？

三、兼容层设计
[x] 是否说明了旧 workflows 与新 runtime 的关系？
[x] 是否保留了兼容壳而不是直接砍掉旧入口？
[x] 是否明确了哪些模块仍是 compatibility shell？
[x] 是否避免了“旧 workflow 仍是主干，新 runtime 只是点缀”？

四、测试与验证
[x] 是否新增至少 1 个集成测试？
[x] 测试是否验证 graph 可以运行？
[x] 测试是否验证 graph 可以中断？
[x] 测试是否验证 graph 可以恢复？
[x] 测试是否真实执行代码而不是 mock 全流程？

五、文档
[x] 是否新增 docs/upgrade5-runtime.md？
[x] 文档是否说明：
    - runtime 结构
    - graph/state/checkpoint
    - compatibility shell
    - 后续 U5-2/U5-3/U5-4 如何接入

六、判定标准
[x] 如果删除 LangGraph / Deep Agents 相关代码，当前提交是否会失去核心能力？
[x] 当前提交是否已经表明 Upgrade 5 开始进入 runtime 迁移，而不是旧架构收尾？

请最后输出：
1. 通过项
2. 未通过项
3. 阻塞问题
4. 建议是否进入下一任务
```

---

