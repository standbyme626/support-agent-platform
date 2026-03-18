# Upgrade5 前端人工接管私聊闭环完整版实施方案

版本：v1.0（2026-03-18）  
状态：核心链路已落地（2026-03-18），真实企微会话联调待环境验证
适用范围：`web_console` + `app/transport` + `app/application` + WeCom Bridge 发送链路

---

## 0. 实施进度（2026-03-18）

已完成（P0）：

1. 后端新增 `POST /api/v2/tickets/:ticketId/reply-send`，落地权限、幂等、防重复、失败重试可观测。
2. 后端新增 `POST /api/v2/tickets/:ticketId/reply-draft`。
3. reply 事件写入与查询打通：`reply_draft_generated / reply_send_*` 可在 `reply-events + trace` 可见。
4. 前端新增 `ReplyWorkspace`，实现 `AI草稿 -> 人工编辑 -> 人工确认发送`。
5. 观察者发送拦截（前端禁用 + 后端 403 双保险）。

待完成（环境相关）：

1. 真实企业微信应用会话“用户收到消息”的生产/联调环境验收证据。
2. 灰度发布与回滚演练记录。

---

## 1. 背景与问题（基于现有文档与代码）

### 1.1 文档已明确的目标

1. 人工接管应是 `summary-first + detail-on-demand + AI草稿可编辑发送`。  
   见：`升级4.md`（2.2、E1/E2/E3）。
2. 需要“人工回复发送 API”（支持草稿编辑后发送）。  
   见：`升级4.md:303`。
3. 前端详情页要展示来源渠道消息，对齐用户原话。  
   见：`升级5-2.md:71`。
4. 私聊详情通过企业微信应用消息链路发送，且已存在异步发送与 trace 约束。  
   见：`docs/upgrade5-wecom-dispatch.md`（私聊详情说明）。

### 1.2 当前实现现状（代码事实）

1. 前端已有“来源消息 / 上下文”展示。  
2. 前端已有 AI 建议带入人工动作表单（用于工单动作，不是用户回复发送）。  
3. 后端已有 `GET /api/sessions/:sessionId/reply-events` 与 `GET /api/tickets/:ticketId/reply-events`。  
4. 但前端无“人工回复工作区 + 编辑后发送”能力；后端也无对应发送接口。

### 1.3 核心差距

“看得到上下文和建议”已经有；“在前端完成人工回复并真实发到用户私聊”还没有闭环。

---

## 2. 要达成的目标（完整版）

1. 在工单详情页新增“人工回复工作区”：
   - AI 草稿生成
   - 人工编辑
   - 人工确认发送
   - 发送结果回显（成功/失败/重试）
2. 发送目标为当前工单绑定用户私聊（企业微信应用消息链路）。
3. 发送全过程可审计、可追踪、可回放（reply events + trace）。
4. 严格保持 `advice_only` 与“人工确认后才可发送”。
5. 角色权限落地：观察者不可发送，高风险/敏感内容需要二次确认。

---

## 3. 非目标（本阶段不做）

1. 不做通用聊天机器人界面。
2. 不绕过工单语义直接做“自由对话”。
3. 不把 Deep Agent 变成自动外呼执行器。

---

## 4. 目标链路（To-Be）

```mermaid
flowchart LR
  A[用户在企微发消息] --> B[工单/会话上下文]
  B --> C[前端 Ticket Detail 人工回复工作区]
  C --> D[AI 生成回复草稿]
  D --> E[人工编辑]
  E --> F[人工确认发送]
  F --> G[Ops API reply-send]
  G --> H[WeCom Bridge /cgi-bin/message/send]
  H --> I[delivery ack/fail]
  I --> J[reply-events + trace]
  J --> K[前端时间线与发送状态回显]
```

---

## 5. 接口设计（完整版）

## 5.1 保留并接入现有查询接口

1. `GET /api/sessions/:sessionId/reply-events`
2. `GET /api/tickets/:ticketId/reply-events`

前端用于展示：
- 历史草稿
- 历史发送记录
- 成功/失败与重试信息

## 5.2 新增发送接口（必须）

1. `POST /api/v2/tickets/:ticketId/reply-send`

请求体建议：
- `actor_id`：发送人
- `session_id`：绑定会话（可选，后端兜底从 ticket 推导）
- `to_user_id`：接收用户（可选，后端按 ticket/session 解析）
- `content`：发送正文（人工编辑后的最终文本）
- `draft_source`：`ai_draft` / `manual` / `mixed`
- `idempotency_key`：防重必填
- `trace_id`：可选，缺省由后端生成

响应体建议：
- `reply_id`
- `delivery_status`：`queued|sent|failed`
- `channel`：`wecom`
- `target`：脱敏后的接收信息
- `trace_id`

## 5.3 新增草稿接口（建议）

1. `POST /api/v2/tickets/:ticketId/reply-draft`

请求体建议：
- `actor_id`
- `style`（安抚/说明/催补充/结案确认）
- `max_length`

响应体建议：
- `draft_text`
- `risk_flags`
- `grounding`
- `advice_only=true`

---

## 6. 前端改造清单（web_console）

1. 在 `tickets/[ticketId]` 新增 `ReplyWorkspace` 区块（放在 AI 助手区下方或人工动作区上方）。
2. 支持“一键带入草稿 -> 编辑 -> 发送确认”。
3. 新增发送状态 UI：
   - `sending`
   - `sent`
   - `failed`（支持重试）
4. 接入 `reply-events` 列表与筛选（按 `draft/send/retry`）。
5. 角色控制：
   - 观察者只读
   - 客服可发送
   - 主管可发送与重试
6. 错误处理：
   - 幂等冲突提示
   - 目标用户无法解析提示
   - 渠道发送失败提示

---

## 7. 后端改造清单（分层）

1. `app/transport/http/routes.py`
   - 增加 `REPLY_SEND_V2`、`REPLY_DRAFT_V2` 路由正则。
2. `app/transport/http/handlers.py`
   - 接线 `POST /api/v2/tickets/:ticketId/reply-send`
   - 接线 `POST /api/v2/tickets/:ticketId/reply-draft`（可选）
3. `app/application/*`
   - 新增 `reply_runtime_service.py`
   - 统一处理：参数校验、权限校验、幂等校验、发送编排、落审计
4. `app/domain/*`（或现有 ticket/reply 领域模块）
   - 统一 reply 事件模型与状态机（draft/send/retry）
5. WeCom Bridge
   - 复用现有真实发送链路与 `WECOM_GROUP_PRIVATE_DETAIL_ASYNC` 策略
   - 对 reply-send 增加专属 trace 事件

---

## 8. 审计与观测（必须）

新增/复用事件：
1. `reply_draft_generated`
2. `reply_send_requested`
3. `reply_send_delivered`
4. `reply_send_failed`
5. `reply_send_retry_scheduled`

建议指标：
1. `reply_send_total{status}`
2. `reply_send_latency_ms`
3. `reply_send_retry_total`
4. `reply_send_dedup_hit_total`

---

## 9. 验收标准（Definition of Done）

## 9.1 功能验收

1. 客服可在前端看到 AI 草稿并编辑。
2. 点击发送后，用户在企微应用会话可收到消息。
3. 发送结果回写 reply-events，前端可见。
4. 失败可重试，且不会重复发送（幂等生效）。

## 9.2 安全与权限验收

1. 观察者账号不可发送。
2. 所有发送动作有 `actor_id + trace_id + ticket_id + session_id` 审计。
3. 未确认不发送（无自动外发）。

## 9.3 测试验收

1. 后端单元/集成测试新增：
   - `reply-send` 成功、失败、重试、幂等
2. 前端测试新增：
   - `ReplyWorkspace` 交互测试
   - 发送成功/失败态测试
3. 真实链路测试：
   - 企微真实可见：至少 1 条完整“草稿->编辑->发送->回执”链路

---

## 10. 实施顺序（建议 7 天）

1. `D1`：接口与事件模型定稿（含幂等与权限）。
2. `D2-D3`：后端 `reply-send/reply-draft` 落地 + 集成测试。
3. `D4-D5`：前端 `ReplyWorkspace` 落地 + 前端测试。
4. `D6`：企微真实链路联调（应用会话可见性校验）。
5. `D7`：灰度上线 + 回滚预案演练 + 文档收口。

---

## 11. 风险与回滚

1. 风险：重复发送/误发
   - 方案：`idempotency_key` + 发送前确认弹窗 + 角色控制
2. 风险：企微通道波动
   - 方案：重试队列 + 失败可重放
3. 风险：前后端口径不一致
   - 方案：先定 API contract，再并行开发

回滚策略：
1. 前端开关关闭 `ReplyWorkspace`（保留只读）。
2. 后端关闭 `reply-send` 路由写入，仅保留查询接口。
3. 保留审计与 trace，不丢历史记录。

---

## 12. 与现有 bd 任务映射

1. `support-agent-platform-2iri`：主任务（人工接管回复工作区闭环）
2. `support-agent-platform-olep`：角色权限控制
3. `support-agent-platform-rrn1`：文档口径对齐
4. `support-agent-platform-dvi0`：真实链路 E2E/回放
5. `support-agent-platform-ss43`：Trace Drilldown 补齐（来源会话/操作者/结果）

---

## 13. 结论

当前项目离“前端可完成人工接管私聊闭环”只差最后一段主链路：  
`ReplyWorkspace + reply-send API + 可审计发送回执`。  

这段做完，才能真正实现：  
“前端直接借助智能机器人与用户私聊，AI 提炼+人工把关后完成对话闭环”。
