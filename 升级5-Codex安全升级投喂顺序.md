# 升级5 Codex 安全升级投喂顺序

> 目标：降低一次性大改导致的语义漂移与边界回退风险。  
> 核心策略：先立边界，再填实现，最后接编排与 agent。

---

## 1. 固定四步（必须按顺序）

### 第一步：只创建目录与 10 个文件

1. 只建文件，不写复杂逻辑。
2. 只允许占位注释、类型壳、最小导入。
3. 这一阶段禁止改 `/close` 业务行为。

### 第二步：只填 4 个边界文件

1. `API_CONTRACT_V2.md`
2. `conversation_state.py`
3. `ticket_workflow_state.py`
4. `session_service.py`

目标：先锁定契约与状态边界，防止 session/ticket 再次耦合。

### 第三步：只填 `ticket_api.py` 的四个动作

1. `resolve`
2. `customer_confirm`
3. `operator_close`
4. `end_session`

目标：彻底避免 `/close` 继续充当万能动作。

### 第四步：最后填 `intake_graph.py` 和 `ticket_investigation_agent.py`

1. graph 负责编排，不重写 domain 规则。
2. deep agent 负责调查与建议，不直接执行高风险动作。

---

## 2. 给 Codex 的阶段提示词模板

## 模板A（S1）

先不要改已有逻辑。只创建以下目录和10个文件，写最小占位注释与空类/空函数，不实现业务逻辑，不修改 `升级5.md`。

## 模板B（S2）

只改这4个文件：`API_CONTRACT_V2.md`、`conversation_state.py`、`ticket_workflow_state.py`、`session_service.py`。  
要求：session 和 ticket 状态必须分离；API v2 要定义 `customer_confirm/operator_close/session_end`；不要改 `ticket_api.py`。

## 模板C（S3）

只改 `ticket_api.py`，只实现 `resolve/customer_confirm/operator_close/end_session` 四个动作与必要事件字段。  
禁止把 `/close` 保留为万能语义，禁止引入自动高风险执行。

## 模板D（S4）

只改 `intake_graph.py` 和 `ticket_investigation_agent.py`，做最小可运行接入。  
保持高风险动作 HITL，不做 fully autonomous agent。

---

## 3. 每步完成后必须检查

1. 变更文件是否超出本步白名单。
2. 是否重新引入 `/close` 多语义。
3. 是否把 session/ticket 状态边界混写。
4. 关键回归是否通过（session API、ticket actions、case collab workflow）。

---

## 4. 回退原则

1. 任何一步出现语义回退，先停止后续步骤。
2. 回退到上一阶段通过点，修复后再继续。
3. 不跨阶段“顺手修”，避免边界破坏。

