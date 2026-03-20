# 全项目评审与重构路线图

**版本：v0.1（2026-03-18）**

## 1. 文档目的

本文档沉淀当前 `support-agent-platform` 的一次全项目评审结果，覆盖：

1. 当前前端界面与交互结构是否合理。
2. 当前后端架构、API 边界、状态流与迁移方向是否清晰。
3. 接下来应如何分阶段推进前后端收口，而不是做高风险重写。

本文档的目标不是重新定义产品方向，而是为后续迭代提供一份可执行的改造路线图。

---

## 2. 结论摘要

### 2.1 总体判断

项目的总体方向是成立的：

- 核心思路明确：`workflow-first + agent-assisted + HITL`
- 入口层和业务规则层有明确边界
- 工单、审批、trace、知识检索已经形成一条统一主线
- 前端页面已经覆盖 Dashboard、Tickets、Ticket Detail、Traces、Queues、KB、Channels

但当前项目存在明显的“中间态”特征：

1. 前端已经能用，但页面密度偏高，角色分层不够明确。
2. 后端业务规则已经可跑，但 HTTP 入口过胖，迁移中的 `app/*` 结构还没有完全接管主链路。
3. 前端数据层目前是“每页一个手写 hook”，模式统一但重复明显。
4. 项目最应该做的是“收口与分层”，不是“大重写”。

### 2.2 最高优先级建议

本轮评审后，优先级最高的三个改造方向是：

1. **Ticket Detail 收口**
   目标：从“工程信息大面板”收敛为“summary-first + detail-on-demand”。

2. **web_console 数据层统一**
   目标：把重复的 loading/error/refetch/query 逻辑收敛成统一模式。

3. **Ops API 继续瘦身**
   目标：让 `scripts/ops_api_server.py` 逐步退化为启动与兼容入口，把路由和应用逻辑迁到 `app/transport + app/application`。

---

## 3. 当前项目结构判断

## 3.1 已经稳定的主链路

当前真正承载主流程的核心仍然是：

- `scripts/ops_api_server.py`
- `core/ticket_api.py`
- `core/workflow_engine.py`
- `workflows/support_intake_workflow.py`
- `workflows/case_collab_workflow.py`
- `web_console/*`

这些模块构成了当前“可跑、可联调、可观测”的主干。

## 3.2 正在形成中的新结构

项目内已经出现更清晰的分层结构：

- `app/transport/http/*`
- `app/application/*`
- `app/domain/*`
- `app/graph_runtime/*`
- `app/bootstrap/runtime.py`

这说明项目并不是没有演进方向，而是已经开始从“脚本式单体”向“分层应用”过渡。

### 3.3 当前最重要的架构判断

当前最合理的演进策略不是推翻 legacy，而是：

1. 先让 `app/transport` 接管 HTTP 路由表达。
2. 再让 `app/application` 接管应用层编排。
3. 最后逐步让 `app/domain` 吃掉 legacy `core/*` 中的规则中心。

换句话说，应该做“壳层迁移”，而不是直接对 `core/*` 做大爆炸替换。

---

## 4. 前端评审

## 4.1 当前前端的优点

当前前端有几个优点值得保留：

1. 页面覆盖面已经完整，基本形成了一个可操作的 Ops Console。
2. 视觉系统虽然简单，但整体风格统一，没有明显的页面割裂。
3. 页面组件化已经开始形成，至少按 `tickets / traces / queues / kb / channels / shared` 做了分组。
4. 页面级测试和组件级测试已经有一定基础。

## 4.2 当前前端的核心问题

### 问题一：信息架构偏“全展开”，不够“任务优先”

很多页面不是按用户任务排序，而是按系统能力平铺。

最明显的是 Ticket Detail：

- 时间线、核心字段、Runtime 视角、Grounding、推荐动作、Copilot、调查、会话结束、Reply Workspace、审批恢复同时出现。
- 这对平台排障和开发联调有帮助，但对客服/主管的一线操作不够高效。

### 问题二：角色分层不够

当前导航和页面层级更像“一个统一控制台”，而不是面向不同角色的工作区。

当前实际上混合了三类工作：

1. 客服处理工作
2. 运营监控工作
3. 平台观测与调试工作

这三类工作在导航中基本同级，导致界面心智负担偏大。

### 问题三：数据层模式统一，但重复度很高

`useTickets`、`useTraceList`、`useKB`、`useGatewayHealth`、`useTicketDetail` 都在重复：

- `loading / error / refetch`
- 本地状态定义
- 首次加载
- 分页和筛选
- action success / action error

这不是单页 bug，而是数据层缺少统一抽象。

### 问题四：核心页面文件过胖

目前几个核心文件体量已经说明问题：

- `scripts/ops_api_server.py`：1863 行
- `web_console/app/(dashboard)/tickets/[ticketId]/page.tsx`：691 行
- `web_console/lib/hooks/useTicketDetail.ts`：388 行

这说明当前改造重点应该是“拆边界”，不是继续往里加条件分支。

## 4.3 按页面的建议

### Dashboard

当前定位：运营总览页。

当前问题：

- 指标较多，但主次关系不够清晰。
- 指标、审批、风险块都在首屏争夺注意力。

建议：

1. 第一层只保留 `SLA 风险 / 待审批 / 待接管 / 处理中` 四类核心指标。
2. 第二层保留队列压力与异常入口。
3. 第三层保留 trace/channel 观测块。

### Tickets

当前定位：工单收件箱。

当前问题：

- 左筛选 + 右表格结构合理，但筛选项已开始过多。
- URL 状态、localStorage 状态、表格状态都在页面级 hook 手工维护。

建议：

1. 把筛选拆成“常用筛选”和“高级筛选”。
2. 统一筛选状态来源与序列化策略。
3. 后续将筛选 schema 抽成共享配置，而不是散在 hook 和组件内部。

### Ticket Detail

当前定位：复合型工作台。

当前问题：

- 技术信息过多，默认就对用户展开。
- 一线处理和平台排障混在同一屏。
- 页面与 hook 都过胖。

建议：

1. 改成 `summary-first + detail-on-demand`。
2. 默认只展示：
   - 客户原话/上下文
   - AI 摘要
   - 推荐动作
   - 回复工作区
   - 审批状态
3. 将下列内容降级为二级内容：
   - Timeline
   - Runtime 视角
   - Trace / Graph / Reply Events
   - 技术细节字段
4. 将 `useTicketDetail` 拆为：
   - `useTicketCore`
   - `useTicketAI`
   - `useTicketReply`
   - `useTicketApprovals`

### Traces

当前定位：系统观测工作台。

当前问题：

- 结构合理，但偏平台工程视角。
- 和 Tickets 的视觉层级差异不足。

建议：

1. 保持列表 + 详情结构不变。
2. 强化“这是调试页，不是客服主工作区”的视觉和导航分层。
3. 将 Trace Detail 中的 Graph Drilldown 继续收口到可折叠区域，避免页面过度技术化。

### Queues

当前定位：运营与主管看板。

当前问题：

- 页面结构清晰，但指标表达还偏“静态卡片页”。

建议：

1. 强化“按队列处理”的任务入口。
2. 让卡片更多承担 drill-down 作用，而不是纯展示。
3. 增加和 Tickets 的联动心智，例如“从队列卡直接进入已筛选工单视图”。

### KB

当前定位：后台内容管理。

当前问题：

- 目前是标准 CRUD 管理台，但还缺少知识质量信号。

建议：

1. 补充命中量、更新时间、是否参与 grounding、最近引用记录。
2. 增加 FAQ / SOP / 历史案例的差异化信息，而不只是换个 `source_type`。

### Channels

当前定位：入口层和网关层观测页。

当前问题：

- 内容完整，但“平台运维页”的身份还不够强。

建议：

1. 在导航和版式上与 Tickets/Dashboard 拉开距离。
2. 保持工程化字段，但减少其对主业务工作流的干扰。

---

## 5. 后端评审

## 5.1 当前后端的优点

1. 工单状态机和生命周期规则是集中表达的。
2. 审批、事件、trace、检索、agent 增强都围绕同一条 ticket 主线。
3. OpenClaw 边界清晰，没有把 ticket 业务规则塞回入口层。

## 5.2 当前后端的核心问题

### 问题一：主 HTTP 入口过胖

`scripts/ops_api_server.py` 同时承担了：

- runtime bootstrap
- agent/build 初始化
- HTTP handler 适配
- route dispatch
- payload 组装
- 兼容逻辑
- 查询聚合

这会导致：

1. 接口越多，文件越难维护。
2. 前端联调时很难快速定位某个接口属于哪一层职责。
3. 后续迁移 `app/*` 时容易双写和回退逻辑交错。

### 问题二：Legacy 与 V2 结构并存

目前 runtime 中同时持有：

- `LegacyTicketAPI`
- `TicketAPIV2`

这本身不是坏事，但如果没有明确迁移顺序，就会长期停留在“双结构共存”状态。

### 问题三：应用服务和领域规则尚未完全分离

虽然 `app/application/*`、`app/domain/*` 已经出现，但很多业务真实规则仍主要落在：

- `core/ticket_api.py`
- `core/workflow_engine.py`
- `workflows/support_intake_workflow.py`
- `workflows/case_collab_workflow.py`

这意味着当前更适合继续“收口分层”，而不是贸然切换到纯新结构。

## 5.3 后端建议

### 建议一：先瘦 `ops_api_server.py`

原则：

- 不在 `ops_api_server.py` 继续新增复杂业务逻辑。
- 新接口优先落到 `app/transport/http/handlers.py + app/application/*`。

### 建议二：明确迁移顺序

建议顺序：

1. HTTP route pattern 与 handler 下沉到 `app/transport/http/*`
2. 应用编排下沉到 `app/application/*`
3. 领域状态规则再逐步收拢到 `app/domain/*`

### 建议三：以“接口组”为迁移单位

不建议按“文件整体重写”迁移，建议按接口组迁移：

1. Ticket Read
2. Ticket Actions
3. Reply Runtime
4. Copilot / Investigation
5. Approval / Session Control
6. Trace / Channels / Dashboard

这样便于保留行为一致性和测试边界。

---

## 6. 改造原则

后续所有前后端改造都建议遵循以下原则：

1. **先收口，再美化**
   先解决页面层级、边界和数据流问题，再做视觉提升。

2. **先拆接口边界，再拆领域内部**
   先让 API / page / hook / handler 各回各位，再考虑底层模型升级。

3. **禁止大爆炸重写**
   当前项目已经有较多流程、测试和联调资产，不应推倒重来。

4. **保持 workflow-first 主线**
   不能因为引入更多 agent/runtime 能力而弱化规则控制和审批闸门。

5. **让一线处理与平台调试分层**
   Tickets/Ticket Detail 以处理效率优先；
   Traces/Channels 以观测与排障优先。

---

## 7. 分阶段计划

## Phase 0：信息架构与边界冻结

目标：

- 冻结页面角色分层
- 冻结 Ticket Detail 新结构
- 冻结后端迁移边界

交付：

1. 页面级 IA 文档更新
2. Ticket Detail 模块拆分方案
3. 后端 route group 切分表

## Phase 1：前端页面收口

目标：

- 优先解决页面可用性和信息层级问题

改造项：

1. 重构 Ticket Detail 为 `summary-first`
2. 调整 Dashboard 为“异常优先”
3. 收口导航分组
4. 明确角色权限可见性

验收：

1. Ticket Detail 页面的主路径不再依赖技术字段理解
2. 一线客服能在首屏完成“看懂 -> 回复 -> 流转”

## Phase 2：前端数据层统一

目标：

- 统一 web_console 的数据获取和 mutation 模式

改造项：

1. 提炼共享 query/mutation 抽象
2. 统一 `loading/error/refetch`
3. 收敛 filter state / URL state / localStorage state
4. 拆分超大 hook

验收：

1. 页面 hook 明显变薄
2. 新页面不再重复手写相同模式

## Phase 3：后端入口层收口

目标：

- 让 `ops_api_server.py` 从巨石入口逐步退化为启动和兼容壳层

改造项：

1. 把路由判定迁到 `app/transport/http/routes.py`
2. 把 handler 聚合继续迁到 `app/transport/http/handlers.py`
3. 把应用层逻辑迁到 `app/application/*`

验收：

1. `ops_api_server.py` 体量明显下降
2. 新接口不再直接堆进 legacy 入口文件

## Phase 4：领域层渐进迁移

目标：

- 逐步让 `app/domain/*` 接管更多规则中心能力

改造项：

1. 先迁 Ticket Action 语义
2. 再迁 Session / Conversation 语义
3. 最后收口 runtime graph 与 legacy workflow 的边界

验收：

1. Legacy 与 V2 的职责边界清晰
2. 不再出现同一规则在三层重复定义

---

## 8. 执行版任务清单

本节将分阶段计划进一步细化为可执行任务。

使用原则：

1. 每次只推进一个主阶段，不交叉开大面。
2. 每个阶段先做结构收口，再做行为补齐。
3. 每个阶段结束都要有明确的测试与验收证据。

## 8.1 Phase 0 执行清单：信息架构与边界冻结

### In Scope

- Ticket Detail 新页面层级草案
- 顶部导航与角色分组草案
- Ops API 路由分组草案

### Out of Scope

- 不改业务逻辑
- 不做 UI 重构
- 不迁移后端领域实现

### 任务拆分

1. 梳理前端页面角色分层，形成三类工作区：
   - 客服处理
   - 运营监控
   - 系统观测

2. 产出 Ticket Detail 模块草图，明确首屏与折叠区边界：
   - 首屏保留：客户上下文、AI 摘要、推荐动作、Reply Workspace、审批状态
   - 二级区域保留：Timeline、Runtime、Trace、Reply Events、定制字段

3. 梳理后端 route group，对当前接口按职责归类：
   - dashboard
   - ticket read
   - ticket actions
   - reply runtime
   - copilot
   - approvals
   - traces
   - channels
   - sessions

### 重点文件

- `web_console/app/(dashboard)/layout.tsx`
- `web_console/app/(dashboard)/page.tsx`
- `web_console/app/(dashboard)/tickets/[ticketId]/page.tsx`
- `scripts/ops_api_server.py`
- `app/transport/http/routes.py`

### 验证

1. 文档内已有新的页面层级说明。
2. 能给每个前端页面明确归属到某一类工作区。
3. 能给现有 `/api/*` 接口明确分到某个 route group。

## 8.2 Phase 1 执行清单：前端页面收口

### In Scope

- Ticket Detail
- Dashboard
- 顶部导航与页面分组
- 角色权限可见性

### Out of Scope

- 不统一底层 query 框架
- 不重做视觉风格系统

### 任务拆分

1. 重构 Ticket Detail 页面信息层级。
   - 将 [page.tsx](/home/kkk/Project/support-agent-platform/web_console/app/(dashboard)/tickets/[ticketId]/page.tsx) 拆成更小的页面段落组件。
   - 将技术调试信息移入折叠区或 tab。
   - 落地 `support-agent-platform-qnsk`。

2. 收口 Ticket Detail 组件职责。
   - `ticket-summary-card.tsx` 聚焦摘要和风险。
   - `reply-workspace.tsx` 聚焦“草稿 -> 编辑 -> 发送”。
   - `ticket-actions-panel.tsx` 聚焦状态流转。
   - `ticket-timeline.tsx` 聚焦详情回溯，不承担主流程入口。

3. 重排 Dashboard 优先级。
   - 首屏只保留关键风险指标与待处理入口。
   - 将 trace/channel 观测块降级。

4. 调整导航。
   - 将 Tickets / Dashboard 放在主处理入口。
   - 将 Traces / Channels 显式标记为观测或调试工作区。

5. 落地角色权限可见性。
   - 将页面按钮可见性与权限模型对齐。
   - 优先处理 observer / operator / supervisor 这三类角色。
   - 对应 `support-agent-platform-olep`。

### 重点文件

- `web_console/app/(dashboard)/layout.tsx`
- `web_console/app/(dashboard)/page.tsx`
- `web_console/app/(dashboard)/tickets/[ticketId]/page.tsx`
- `web_console/components/tickets/ticket-summary-card.tsx`
- `web_console/components/tickets/reply-workspace.tsx`
- `web_console/components/tickets/ticket-actions-panel.tsx`
- `web_console/components/tickets/ticket-timeline.tsx`
- `web_console/app/globals.css`

### 验证

前端质量门：

```bash
cd web_console
npm run lint
npm run typecheck
npm run test -- tickets
```

验收标准：

1. 一线客服能在首屏完成“理解问题 -> 编辑回复 -> 执行动作”。
2. 首屏不再要求理解 `runtime_trace/current_graph_node/dispatch_status` 之类字段。
3. observer 角色看不到或不能触发高风险操作。

## 8.3 Phase 2 执行清单：前端数据层统一

### In Scope

- hooks 模式统一
- mutation 模式统一
- filter/query state 收口
- 超大 hook 拆分

### Out of Scope

- 不在本阶段重改页面信息架构
- 不引入与现有团队习惯明显冲突的重型前端框架

### 任务拆分

1. 提炼共享 API 查询抽象。
   - 为 `loading/error/refetch` 提供统一封装。
   - 统一错误对象到 `ApiError` 或一致的页面错误模型。

2. 拆分 Ticket Detail hook。
   - 从 [useTicketDetail.ts](/home/kkk/Project/support-agent-platform/web_console/lib/hooks/useTicketDetail.ts) 拆出：
     - `useTicketCore`
     - `useTicketAI`
     - `useTicketReply`
     - `useTicketApprovals`

3. 统一列表页 hook 模式。
   - `useTickets`
   - `useTraceList`
   - `useKB`
   - `useGatewayHealth`
   - `useQueues`

4. 收口筛选状态。
   - 明确 URL 优先还是 localStorage 优先。
   - 将筛选 schema 从 hook 内部抽离。

5. 落地 `support-agent-platform-b3nq`。

### 重点文件

- `web_console/lib/api/client.ts`
- `web_console/lib/api/tickets.ts`
- `web_console/lib/hooks/useTicketDetail.ts`
- `web_console/lib/hooks/useTickets.ts`
- `web_console/lib/hooks/useTraceList.ts`
- `web_console/lib/hooks/useKB.ts`
- `web_console/lib/hooks/useGatewayHealth.ts`
- `web_console/lib/hooks/useQueues.ts`

### 验证

```bash
cd web_console
npm run lint
npm run typecheck
npm run test
```

验收标准：

1. 新页面新增查询时，不再需要重复手写一套完整状态机。
2. Ticket Detail 页面逻辑显著从单一 hook 中分离。
3. 列表页的筛选状态来源与持久化策略一致。

## 8.4 Phase 3 执行清单：后端入口层收口

### In Scope

- route 分组迁移
- handler 下沉
- application 层编排迁移

### Out of Scope

- 不在本阶段大规模修改 Ticket 领域规则
- 不一次性替换 legacy `core/*`

### 任务拆分

1. 继续按 route group 清空 `ops_api_server.py` 中的分发细节。
   - 保留启动、runtime bootstrap、兼容入口。
   - 将分发逻辑下沉到 `app/transport/http/handlers.py`。

2. 把新增接口统一走 `app/transport/http/routes.py` 正则声明。

3. 将下列应用层能力继续迁到 `app/application/*`：
   - ticket runtime action
   - reply runtime
   - session runtime
   - intake runtime

4. 将 payload 组装与 response 序列化从入口文件中抽离。

5. 落地 `support-agent-platform-o13q`。

### 重点文件

- `scripts/ops_api_server.py`
- `app/transport/http/routes.py`
- `app/transport/http/handlers.py`
- `app/application/ticket_runtime_service.py`
- `app/application/reply_runtime_service.py`
- `app/application/session_runtime_service.py`
- `app/application/intake_runtime_service.py`

### 验证

```bash
pytest tests/integration -q
pytest tests/unit -q
ruff check .
mypy .
```

验收标准：

1. `ops_api_server.py` 只保留少量启动和兼容装配职责。
2. 新接口不再直接在 legacy 入口文件里长分支追加。
3. 现有前端 API 行为保持兼容。

## 8.5 Phase 4 执行清单：领域层渐进迁移

### In Scope

- Ticket action 语义迁移
- Session / Conversation 状态迁移
- graph runtime 与 legacy workflow 边界收口

### Out of Scope

- 不追求一次性完成所有 domain 重写
- 不在没有测试托底时替换生产路径

### 任务拆分

1. 明确 legacy TicketAPI 与 TicketAPIV2 的职责边界。
2. 选定一个最小动作集合做迁移试点：
   - `claim`
   - `resolve`
   - `customer-confirm`
   - `operator-close`

3. 将 session/conversation 状态表达逐步从 session mapper metadata 过渡到更明确的 domain state 抽象。

4. 收口 `graph runtime` 和 legacy workflow 的运行边界，避免重复表达同一状态。

### 重点文件

- `core/ticket_api.py`
- `core/workflow_engine.py`
- `workflows/support_intake_workflow.py`
- `workflows/case_collab_workflow.py`
- `app/domain/ticket/ticket_api.py`
- `app/domain/ticket/ticket_workflow_state.py`
- `app/domain/conversation/conversation_state.py`
- `app/graph_runtime/intake_graph.py`

### 验证

```bash
pytest tests/workflow -q
pytest tests/integration -q
pytest tests/unit -q
```

验收标准：

1. 关键动作只在一套清晰的领域语义中定义。
2. legacy 与 v2 之间不再存在长期不明双写。
3. graph runtime 与 workflow 输出状态语义一致。

## 8.6 推荐执行顺序

如果只按收益/风险比排序，建议按以下顺序推进：

1. `support-agent-platform-qnsk`
2. `support-agent-platform-olep`
3. `support-agent-platform-b3nq`
4. `support-agent-platform-o13q`
5. 领域层渐进迁移试点

原因：

1. Ticket Detail 是当前用户感知最强、收益最高的问题点。
2. 角色权限是安全和流程约束的前置条件。
3. 数据层统一能降低后续所有页面改造成本。
4. 后端入口层收口应在前端主要调用面稳定后推进。

---

## 9. 当前建议对应的跟踪项

本轮评审已补充以下 `bd` 跟踪项：

- `support-agent-platform-qnsk`
  工单详情页改为 `summary-first + detail-on-demand`

- `support-agent-platform-b3nq`
  前端重构：统一 `web_console` 数据查询层与页面状态模型

- `support-agent-platform-o13q`
  后端收口：逐步将 Ops API 从 `scripts/ops_api_server.py` 迁移到 `app/transport + app/application`

---

## 10. 不建议做的事

以下做法当前阶段都不建议：

1. 不建议重写整个前端 UI 框架。
2. 不建议把所有 `core/*` 一次性迁到 `app/domain/*`。
3. 不建议继续把复杂业务逻辑直接堆进 `Ticket Detail` 页面和 `ops_api_server.py`。
4. 不建议为了“更 AI”而弱化审批、审计和状态流控制。

---

## 11. 下一步推荐动作

如果下一轮要开始执行，推荐顺序如下：

1. 先出 Ticket Detail 新信息架构草图与模块拆分清单。
2. 然后同步设计 `web_console` 的统一 query/mutation 模式。
3. 接着整理 Ops API 的 route group 迁移表。
4. 最后按“页面收口 -> 数据层收口 -> 入口层收口 -> 领域迁移”推进。

这会比“先动后端底层”更稳，也更容易拿到连续可验证的结果。
