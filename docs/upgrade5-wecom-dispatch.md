# Upgrade 5: WeCom Dispatch Bridge

## 目标

打通 WeCom 建单后的跨群协同分发链路：

- Dispatch Agent 给出建议（advice-only）。
- Policy gate 决定是否允许自动分发。
- WeCom bridge 执行非当前 session 的二次 outbound。
- 输出可追踪的 routing / decision / delivery 状态。

## Routing Model

桥接入口：`scripts/wecom_bridge_server.py::process_wecom_message`

1. `gateway.receive("wecom", payload)` 归一化 inbound。
2. `intake_workflow.run(...)` 生成工单与回复。
3. 调用 Dispatch Agent 生成建议与 `runtime_trace`。
4. 解析目标映射（queue/inbox -> target_session_id/target_group_id）。
5. policy gate 判断是否自动分发：
   - `WECOM_DISPATCH_AUTO_ENABLED`
   - ticket_action 是否可分发
   - target 映射是否存在
   - Dispatch runtime policy 是否阻断
6. 若允许：
   - 用户会话发送回执（user_receipt）
   - 目标处理群发送协同消息（collab_dispatch）
7. 若阻断：记录阻断原因与 trace 事件。

## 协同命令识别（v5.3 收口）

- 支持标准命令：`/claim`、`/resolve`、`/operator-close`、`/customer-confirm`、`/end-session`。
- 支持空格变体：`/ claim TCK-xxx`、`/ resolve TCK-xxx 备注`。
- 支持常见中文自然语义映射：
  - `认领工单 TCK-xxx`、`我来处理 TCK-xxx` -> `claim`
  - `已解决 TCK-xxx`、`处理完成 TCK-xxx` -> `resolve`
  - `强制关闭 TCK-xxx`、`人工关闭 TCK-xxx` -> `operator-close`
- 当工单号无效时，不再吞异常；会返回可执行提示，并在 trace 中记录失败原因（`failure_reason/error_type/error_message`）。

## 命令总览（统一斜杠口径）

- 用户侧会话命令统一为：`/new`、`/end`。
- 系统保留历史兼容（如 `\new`、`\end`），但对外文档与培训口径统一使用斜杠写法。

| 命令 | 何时可用 | 典型场景 | 示例 |
| --- | --- | --- | --- |
| `/new` | 当前会话中要切换到新问题 | 同一用户连续报修多个故障 | `/new` |
| `/end` | 当前会话要结束 | 本轮咨询结束，准备下次再提问 | `/end` |
| `/claim` | 处理群内、工单已存在 | 工程师接手工单 | `/claim TCK-123456` |
| `/resolve` | 工程师已处理完成 | 进入“待用户确认恢复” | `/resolve TCK-123456 已修复并复测正常` |
| `/customer-confirm` | 用户确认恢复 | 结束工单闭环 | `/customer-confirm TCK-123456 用户确认恢复` |
| `/operator-close` | 需要人工强制关闭 | 用户失联、重复单、误报等 | `/operator-close TCK-123456 用户失联，按流程关闭` |
| `/end-session` | 协同侧主动结束会话上下文 | 工单处理结束后清理会话态 | `/end-session TCK-123456 manual_end_session` |
| `/close` | 兼容命令（建议迁移到 `/customer-confirm` 或 `/operator-close`） | 老命令平滑过渡 | `/close TCK-123456 兼容关闭` |

补充说明：

- 协同命令支持“空格变体”，如 `/ claim TCK-xxx`。
- `resolve/operator-close` 支持中文自然语义触发（如“处理完成 TCK-xxx”“人工关闭 TCK-xxx”）。
- 会话命令也支持空格写法：`/ new ...`、`/ end`。
- 显式 `/new` 仅切换会话模式，不会立即新建工单；需下一条消息补充故障描述后再建单。

## Target Mapping

环境变量：`WECOM_DISPATCH_TARGETS_JSON`

支持键优先级：

1. `queue:<queue_name>`
2. `inbox:<inbox_name>`
3. `<queue_name>`
4. `<inbox_name>`
5. `default`

值可为：

- 字符串：`target_session_id`
- 对象：`{ "target_session_id": "...", "target_group_id": "..." }`

字符串支持以下写法（均可自动解析）：

- `group:<group_id>:user:<actor_id>`（完整 session_id）
- `group:<group_id>`（自动补 `:user:u_dispatch_bot`）
- `<group_id>`（纯群 ID，自动补 `group:` 与 `:user:u_dispatch_bot`）

也支持 `target_group_id` 单独配置（会生成 group session_id）。

## 派发文案口径（v5.3 收口）

- 新工单派发：`新工单 TCK-xxxx 已创建，建议队列：...，优先级：中文分级（P级别）。 调度说明：...`
- 优先级展示口径：`紧急（P0）/高（P1）/中（P2）/普通（P3）/低（P4）`。
- 详情补充：下一行固定追加 `工单详情：...`（包含工单摘要、SLA、风险、建议命令）
  - 若 workflow 暂未提供 `collab_push.message`，会自动回退为用户原始上报内容，确保处理群始终能看到问题详情。
  - 若 `collab_push.message` 为内部结构串（如 `[new-ticket] ... summary=... commands=...`），bridge 会自动清洗为可读详情（优先提取 `latest/summary`，否则回退用户原始上报），避免群内出现调试字段。
- 私聊/群聊双通道补充：当会话已绑定工单时，用户在私聊或群聊中的补充描述会实时同步到工单处理群，文案口径为 `工单 xxx 收到补充信息：...`。
- 信息不足引导：当触发 `clarification_required` 时，用户侧会收到补充引导；同时工单处理群会收到 `工单 xxx 当前信息待补充` 的同步提示，方便工程师提前关注。
- 工单群协同同步：
  - 认领：`工单 xxx 已由 yyy 正在处理（接手处理）。`
  - 完成：`工单 xxx 已处理完成，请确认是否恢复正常。`
  - 人工关闭：`工单 xxx 已由处理工程师关闭，原因：...。`
- 群聊长回复默认走“规则快回”；详细说明私发给提报人，减少群内刷屏。
- 私发详细说明采用异步发送（默认开启）：`WECOM_GROUP_PRIVATE_DETAIL_ASYNC=1`（设为 `0` 可改为同步发送，便于排障）。
- 群内规则快回去重（默认开启）：同群 + 同工单 + 同模板文案在 `60` 秒内只发一次。
  - 开关窗口：`WECOM_GROUP_TEMPLATE_DEDUP_WINDOW_SECONDS`（默认 `60`，设为 `0` 表示关闭去重）。
  - 去重命中会记录 trace 事件：`wecom_group_template_dedup_suppressed`。
- 群快回触发私聊详情时，会先将 `dm:<userid>` 绑定到当前工单上下文，避免私聊补充信息进入“继续当前/新问题”歧义分支。

## Delivery Trace

新增 trace 事件：

- `wecom_dispatch_decision`
- `wecom_dispatch_blocked`
- `wecom_dispatch_delivery`

并复用网关已有 outbound trace：

- `egress_rendered`
- `egress_failed`
- `egress_retry_scheduled`

## WeCom 长消息分段

- 环境变量：`WECOM_BRIDGE_OUTBOUND_CHUNK_CHARS`
- 默认值：`1200`
- 说明：当 WeCom 出站消息超过阈值时，bridge 会按“段落换行 -> 句号/问号/分号 -> 逗号/空格”的优先级切分，降低中途断句；每段带 `chunked/chunk_index/chunk_total` 元数据，便于 trace 与回放定位。
- 建议：如果群消息普遍较长，可将该值下调到 `800-1200` 以提升阅读体验。

## WeCom 应用 API 真发送

- `WECOM_APP_API_ENABLED=1`：开启真实 API 投递（默认关闭，仅渲染不投递）。
- `WECOM_CORP_ID`（可回退 `WECOM_BOT_ID`）：企业 CorpID。
- `WECOM_AGENT_SECRET`（可回退 `WECOM_CORP_SECRET` / `WECOM_BOT_SECRET`）：应用 Secret。
- `WECOM_AGENT_ID`：应用 AgentId（`message/send` 必需）。
- `WECOM_API_BASE_URL`：默认 `https://qyapi.weixin.qq.com`，用于私网代理时覆盖。

发送策略：

- `outbound_type=collab_dispatch` 且存在 `target_group_id`（或 session 可解析 group）时，走 `/cgi-bin/appchat/send`。
- 其余走 `/cgi-bin/message/send`（按用户投递）。
- 失败会进入现有 `egress_failed/egress_retry_*` 重试链路；成功追加 `egress_delivered` trace。

## 真实复测建议

1. 单条真发送 smoke（非 mock）：
   - `WECOM_APP_API_ENABLED=1` 后，调用 `gateway.send_outbound(channel="wecom", ...)`。
   - 观察 trace 中是否出现 `egress_delivered`。
2. bridge 链路真发送：
   - 通过 `scripts/wecom_bridge_server.py` 的 `/wecom/process` 入口发送真实 payload。
   - 验证 `wecom_dispatch_delivery.delivery_status` 与实际企业微信收件一致。

## 推荐启动命令（当前群配置）

以下命令将 Upgrade5 的关键开关一次性带齐，并把派工目标固定到当前“工单处理群”：

```bash
cd /home/kkk/Project/support-agent-platform

PYTHONPATH=. \
WECOM_APP_API_ENABLED=1 \
WECOM_DISPATCH_AUTO_ENABLED=1 \
WECOM_CORP_ID=wwd783420586740f2d \
WECOM_AGENT_ID=1000044 \
WECOM_AGENT_SECRET="$WECOM_AGENT_SECRET" \
WECOM_DISPATCH_TARGETS_JSON='{"inbox:wecom.default":"group:wrAEX9RgAAKNkRjmFs6f3f2z_tEPiT1A:user:u_dispatch_bot"}' \
python scripts/wecom_bridge_server.py --env dev --host 0.0.0.0 --port 18081 --path /wecom/process
```

配套群信息（用于人工核对）：

- 故障维修群（上报入口）：`wrAEX9RgAAEuFUL3vLamRkD6m8MtU6bQ`
- 工单处理群（派工目标）：`wrAEX9RgAAKNkRjmFs6f3f2z_tEPiT1A`

## 返回结构

`BridgeResult.as_json()` 新增：

- `channel_route`
- `collab_target`
- `dispatch_decision`
- `delivery_status`

其中 `channel_route` 包含：

- `collab_target`
- `dispatch_decision`
- `delivery_status`

对应 Upgrade 5 要求中的 `channel_route / collab_target / dispatch_decision / delivery_status`。
