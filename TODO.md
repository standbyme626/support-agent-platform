support-agent-platform
TODO 执行清单（依据《工单系统计划书》）

版本：v1.0
语言：中文
定位：Workflow-First, Agent-Assisted
更新时间：2026-03-11

1. 执行规则（必须遵守）
- [ ] 不实现通用聊天机器人；所有对话必须落到 ticket/case 或其协同动作。
- [ ] 不把 OpenClaw 当业务引擎；它只负责 channel ingress、session、routing。
- [ ] MVP 不优先做前端后台；先完成消息入口 + Ticket 后端 + 管理 API。
- [ ] 不只做 FAQ 问答；必须覆盖 create/update/assign/reassign/escalate/summary/handoff。
- [ ] 必须保留 human handoff，且保留上下文、证据与推荐动作。
- [ ] 必须同步建设单元/集成/workflow/回归测试。
- [ ] 坚持 workflow-first、agent-assisted，不走 autonomy-first。

2. A–Z 分阶段执行清单
2.1 A. 项目边界与非目标
任务包说明：
- [x] A1 输出 `PROJECT_SCOPE.md`
- [x] A2 明确 workflow-first
- [x] A3 列出禁止项
验收标准：
- [x] 能清晰回答“系统是什么/不是什么”。

2.2 B. 工程骨架与仓库规范
任务包说明：
- [x] B1 初始化 monorepo
- [x] B2 建立目录结构
- [x] B3 配置 lint/format/typecheck
验收标准：
- [x] 仓库可运行，目录与计划书一致。

2.3 C. 配置管理与环境变量
任务包说明：
- [x] C1 编写 `.env.example`
- [x] C2 建立 dev/prod 配置
- [x] C3 实现 secrets 读取
验收标准：
- [x] 无硬编码密钥，配置可切换。

2.4 D. OpenClaw 接入层
任务包说明：
- [x] D1 安装/接入 Gateway
- [x] D2 编写 bindings
- [x] D3 补齐状态与日志脚本
验收标准：
- [x] 能验证消息进入并回发。

2.5 E. 企业微信/飞书/Telegram Adapter
任务包说明：
- [x] E1 实现 Feishu Adapter
- [x] E2 实现 Telegram Adapter
- [x] E3 搭建 WeCom Adapter 接口骨架
验收标准：
- [x] 渠道代码与业务逻辑解耦。

2.6 F. Session 与 Identity Mapping
任务包说明：
- [x] F1 `session_id -> thread_id`
- [x] F2 `session_id -> ticket_id`
- [x] F3 实现元数据透传
验收标准：
- [x] 消息上下文可稳定落盘。

2.7 G. Ticket 数据模型
任务包说明：
- [x] G1 建立 `tickets` 表
- [x] G2 建立 `ticket_events` 表
- [x] G3 完成 migration
验收标准：
- [x] 数据库可创建、可迁移、可回滚。

2.8 H. 基础 Ticket API
任务包说明：
- [x] H1 create/update/get/list
- [x] H2 assign/reassign
- [x] H3 close/escalate
验收标准：
- [x] Ticket API 覆盖核心状态流转。

2.9 I. 知识库与种子数据
任务包说明：
- [x] I1 FAQ 数据
- [x] I2 SOP 数据
- [x] I3 历史工单样本
验收标准：
- [x] 可离线运行最小 KB。

2.10 J. RAG 检索层
任务包说明：
- [x] J1 FAQ 检索
- [x] J2 SOP 检索
- [x] J3 相似工单检索
验收标准：
- [x] 返回结果可用于 agent grounding。

2.11 K. LLM / Model Adapter
任务包说明：
- [x] K1 模型配置
- [x] K2 prompt 版本化
- [x] K3 fallback 策略
验收标准：
- [x] 可替换模型且不改 workflow。

2.12 L. Intent Router
任务包说明：
- [x] L1 完成 FAQ/报修/投诉/费用/其他分类
- [x] L2 设定置信度阈值
- [x] L3 低置信度降级
验收标准：
- [x] 分类结果可测试。

2.13 M. Tool Router
任务包说明：
- [x] M1 `search_kb`
- [x] M2 `create_ticket`
- [x] M3 `update_ticket`
- [x] M4 `escalate_case`
验收标准：
- [x] 工具边界清晰，入参可校验。

2.14 N. Summary Engine
任务包说明：
- [x] N1 intake summary
- [x] N2 case summary
- [x] N3 wrap-up summary
验收标准：
- [x] 摘要可供人工接手阅读。

2.15 O. Recommended Actions Engine
任务包说明：
- [x] O1 下一步动作推荐
- [x] O2 相似案例引用
- [x] O3 风险提示
验收标准：
- [x] 推荐动作具备来源与规则约束。

2.16 P. Human Handoff 模块
任务包说明：
- [x] P1 handoff 触发规则
- [x] P2 handoff payload
- [x] P3 人工接回状态
验收标准：
- [x] 复杂 case 可平滑转人工。

2.17 Q. SLA / Escalation 模块
任务包说明：
- [x] Q1 SLA 规则
- [x] Q2 首响/解决时限
- [x] Q3 自动催办与升级
验收标准：
- [x] 超时可触发事件与通知。

2.18 R. Workflow A：Support Intake
任务包说明：
- [x] R1 intake entry
- [x] R2 FAQ 回复
- [x] R3 自动建单
- [x] R4 handoff
验收标准：
- [x] 项目一最小闭环可演示。

2.19 S. Workflow B：Case Collaboration
任务包说明：
- [x] S1 新单推送
- [x] S2 `/claim`
- [x] S3 `/reassign`
- [x] S4 `/escalate`
- [x] S5 `/close`
验收标准：
- [x] 项目二最小闭环可演示。

2.20 T. Observability / Trace
任务包说明：
- [x] T1 `trace_id`
- [x] T2 tool 调用日志
- [x] T3 route/handoff/SLA 事件
验收标准：
- [x] 能回溯单个 case 全链路。

2.21 U. 管理 API / 运维脚本
任务包说明：
- [x] U1 healthcheck
- [x] U2 gateway status
- [x] U3 replay/debug helpers
验收标准：
- [x] 支持演示、调试和运维。

2.22 V. 单元测试
任务包说明：
- [x] V1 router tests
- [x] V2 tool tests
- [x] V3 summary/handoff tests
验收标准：
- [x] 核心模块覆盖率达标。

2.23 W. 集成测试
任务包说明：
- [x] W1 消息入口到 ticket 创建
- [x] W2 ticket 到协同更新
- [x] W3 渠道路由
验收标准：
- [x] 至少跑通三条关键链路。

2.24 X. 回归测试
任务包说明：
- [x] X1 FAQ 回答回归
- [x] X2 handoff 回归
- [x] X3 SLA 触发回归
验收标准：
- [x] 改动后主路径稳定。

2.25 Y. 文档与演示材料
任务包说明：
- [x] Y1 README
- [x] Y2 ARCHITECTURE
- [x] Y3 RUNBOOK
- [x] Y4 EVAL
验收标准：
- [x] 外部可读，Codex 可执行。

2.26 Z. 验收与发布
任务包说明：
- [x] Z1 MVP 验收清单
- [x] Z2 演示脚本
- [x] Z3 后续 roadmap
验收标准：
- [x] 形成可投递/可演示成果。

3. 测试与质量闸门（与计划书第 14 章一致）
- [x] 单元测试覆盖 Intent Router / Tools / Summary / Handoff 的核心边界与异常处理。
- [x] 集成测试覆盖“消息入口 -> Ticket -> 协同”三条关键链路。
- [x] Workflow 测试覆盖 R/S 两条工作流的状态机转移。
- [x] 回归测试覆盖 FAQ、建单、summary、handoff、SLA 触发稳定性。
- [x] 建立固定种子数据与测试样本，避免结果随机漂移。
- [x] 重点加固 `handoff`、`SLA`、`session_id -> ticket_id` 映射回归测试。

4. 分阶段目标验收（与计划书第 15 章一致）
- [x] 第 1 阶段（基础打通）：Gateway 就绪，至少一个渠道可接入并回发。
- [x] 第 2 阶段（项目一可演示）：Support Intake 全链路可演示。
- [x] 第 3 阶段（项目二可演示）：Case Collaboration + SLA 可运行。
- [x] 第 4 阶段（可投递/可迭代）：测试、文档、回归、演示材料齐备。

5. 每次任务完成后的固定输出
- [ ] 变更文件列表
- [ ] 实现说明
- [ ] 未完成项
- [ ] 测试结果
- [ ] 下一步建议
