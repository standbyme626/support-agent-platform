# support-agent-platform

`support-agent-platform` 是一个以工单为核心的 `workflow-first, agent-assisted` 客服协同平台：

- `workflow-first`：建单、分派、升级、关闭、SLA、handoff 由确定性流程控制。
- `agent-assisted`：意图分类、检索、摘要、推荐动作由 Agent/LLM 增强。
- OpenClaw 只负责 `ingress/session/routing`，不承载业务规则。
- 升级2已交付 `web_console/` Ops Console，形成页面 + API 联调闭环。

## 升级现状

- 已完成 ticket 生命周期增强：`inbox`、`lifecycle_stage`、SLA 截止时间、`resolved/closed/escalated` 时间戳与 `resolution_note`。
- 已完成协同命令增强：`/claim /reassign /escalate /resolve /close`。
- OpenClaw 仍只做接入与路由，不承载业务规则。
- 参考仓统一放在 `refs/`，仅用于对照阅读，不参与运行与提交流程。

### 升级2（A1~H4）状态

- 已完成 8 个目标页面：Dashboard、Tickets、Ticket Detail、Timeline、Traces、Queues、KB、Channels/Gateway。
- 已完成升级2页面对应 `/api/*` 联调与错误语义统一（`code/message/request_id`）。
- 已完成升级2收口项（P0/P1/P2）：
  - P0：修复 Ticket 动作反馈准确性（失败不再显示成功）并补充对应测试；补齐前端最小 e2e 场景（Ticket 动作链、Trace drill-down、KB CRUD、Channels 观测）。
  - P1：补齐 Ticket List/Detail 的定制字段可见性与可筛选性；为 Ticket List、Trace、Queue、Channels 增加显式刷新入口。
  - P2：新增统一反馈组件 `ActionFeedback`，统一成功/失败提示样式与语义（已在 Ticket / KB 场景接入）。
- 前端质量闸门（`web_console`）：`lint`、`typecheck`、`vitest` 均通过；当前测试为 `33/33` 通过（含 `tests/e2e/upgrade2-minimal-flow.test.tsx`）。
- 实施与验收详见：
  - [`升级2.md`](./升级2.md)
  - [`升级2-实施要求与验收测试规范.md`](./升级2-实施要求与验收测试规范.md)
  - [`升级2-任务分解与执行清单-A1-H4.md`](./升级2-任务分解与执行清单-A1-H4.md)

## 快速启动

1. 环境要求
   - Python 3.11+
2. 安装依赖
   - `cd support-agent-platform`
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -e ".[dev]"`
3. 配置环境变量
   - `cp .env.example .env`
   - `export SUPPORT_AGENT_ENV=dev`
   - 可选：`export SUPPORT_AGENT_SQLITE_PATH=/absolute/path/tickets.db`
   - LLM（业务层）使用 OpenAI 兼容接口，可通过 `.env` 直接切换：
     - `OPENAI_BASE_URL=http://100.90.236.32:11434/v1`
     - `OPENAI_MODEL=qwen3.5:9b`
     - `OPENAI_API_KEY=ollama-local`
   - 设计边界不变：OpenClaw 只负责 ingress/session/routing，LLM 推理在项目后端执行。
4. 执行质量闸门
   - `make check`
   - `make ci`
5. 运行常用运维脚本
   - `python scripts/healthcheck.py --env dev`
   - `python scripts/gateway_status.py --env dev`
   - `python scripts/replay_gateway_event.py --env dev --channel telegram --session-id demo-001 --text "设备故障需要处理" --trace-id trace_demo_001`
   - `python scripts/trace_debug.py --env dev --trace-id trace_demo_001 --limit 20`
   - `python -m scripts.deploy_release --env dev`
   - `python -m scripts.verify_release --env dev --require-active-release`
   - `python -m scripts.rollback_release --env dev`
   - `python -m scripts.run_acceptance --env dev`
   - `python -m scripts.trace_kpi --env dev --output storage/acceptance/trace_kpi_from_log.json`
   - 企业微信桥接服务（让 OpenClaw 仅做 ingress/routing）：
     - `python -m scripts.wecom_bridge_server --env dev --host 127.0.0.1 --port 18081`
     - `openclaw --profile support-agent-wecom config set channels.wecom.bridgeUrl "http://127.0.0.1:18081/wecom/process"`
     - 重启 OpenClaw profile 后生效

## 目录结构

- `openclaw_adapter/`：OpenClaw 接入层（入口标准化、session 映射、渠道路由、回发）。
- `channel_adapters/`：`feishu/telegram/wecom` 渠道适配器。
- `workflows/`：两条业务工作流（Support Intake、Case Collaboration）。
- `core/`：业务核心引擎（intent/tool/ticket/summary/handoff/SLA/trace）。
- `tools/`：工单相关工具函数（create/assign/escalate/close/search）。
- `storage/`：SQLite 仓储、迁移脚本、日志与本地数据。
- `scripts/`：运维与调试脚本（health/status/replay/trace）。
- `tests/`：`unit/integration/workflow/regression` 四层测试。
- `seed_data/`：KB 文档与 SLA 规则样本。
- `web_console/`：升级2前端 Ops Console（页面、组件、API 客户端、前端测试）。
- `refs/`：外部参考仓（只读对照，不纳入提交）。

## 运行命令

- `make format`：格式化代码。
- `make lint`：静态检查（ruff）。
- `make typecheck`：类型检查（mypy）。
- `make test`：运行所有测试（pytest）。
- `make test-unit`：运行单元测试。
- `make test-workflow`：运行工作流测试。
- `make test-regression`：运行回归测试。
- `make test-integration`：运行集成测试。
- `make smoke-replay`：运行入口回放烟雾测试。
- `make acceptance`：运行固定样本自动验收并产出 `storage/acceptance` 报告。
- `make acceptance-gate`：独立执行 acceptance + trace-kpi（不强耦合 `make check`）。
- `make trace-kpi`：从 trace 日志计算链路 KPI 并写入文件。
- `make ci`：CI 同步质量闸门（validate + lint + typecheck + unit + workflow + regression + integration + smoke）。
- `make container-smoke`：在容器内执行 smoke replay（`docker compose run --rm smoke`）。
- `make deploy-release ENV=dev`：执行发布前检查并生成可回滚快照。
- `make verify-release ENV=dev`：执行发布后验证（健康检查 + 网关状态 + release state）。
- `make rollback-release ENV=dev`：按快照回滚最近一次发布。
- `make release-cycle ENV=dev`：一条命令执行 `deploy -> verify -> rollback`。
- `make validate-structure`：校验目录与关键文件结构。
- `make check`：完整质量闸门（validate + lint + typecheck + unit + workflow + regression + integration + smoke）。
- 若本地存在 `refs/` 参考仓，建议对本仓代码做路径限定 lint：  
  `python -m ruff check core storage workflows channel_adapters openclaw_adapter tests`

## 文档索引

- [PROJECT_SCOPE.md](./PROJECT_SCOPE.md)：项目定位、边界和禁止项。
- [ARCHITECTURE.md](./ARCHITECTURE.md)：系统边界、模块关系、关键时序。
- [RUNBOOK.md](./RUNBOOK.md)：运维脚本与故障排查。
- [EVAL.md](./EVAL.md)：验收指标、测试覆盖、演示观察点、风险边界。
- [ACCEPTANCE_CHECKLIST.md](./ACCEPTANCE_CHECKLIST.md)：MVP 验收清单（Z1）。
- [DEMO_SCRIPT.md](./DEMO_SCRIPT.md)：可复现演示脚本（Z2）。
- [ROADMAP.md](./ROADMAP.md)：后续迭代路线图（Z3）。
- [升级2.md](./升级2.md)：升级2页面与API蓝图。
- [升级2-实施要求与验收测试规范.md](./升级2-实施要求与验收测试规范.md)：升级2执行约束、验收与测试标准。
- [升级2-任务分解与执行清单-A1-H4.md](./升级2-任务分解与执行清单-A1-H4.md)：升级2文件级任务分解与完成记录。

## 常见问题

### 1) 报错 `Config file not found`

- 确认 `SUPPORT_AGENT_ENV` 为 `dev` 或 `prod`。
- 确认 `config/environments/<env>.toml` 存在。

### 2) `sqlite` 文件路径不符合预期

- 通过 `SUPPORT_AGENT_SQLITE_PATH` 覆盖默认路径。
- 用 `python scripts/healthcheck.py --env dev` 查看当前生效路径。

### 3) 为什么 OpenClaw 没有业务规则

- 这是设计约束。OpenClaw 仅做接入与路由，业务决策在 `core/` 与 `workflows/`。

### 4) 如何切换 LLM 节点或模型

- 只改 `.env`（或系统环境变量）即可，无需修改 workflow 代码：
  - `OPENAI_BASE_URL`：模型网关地址（支持本地 Ollama 与云端 OpenAI-compatible）。
  - `OPENAI_MODEL`：模型名（例如 `qwen3.5:9b`）。
  - `LLM_STREAM`：是否启用流式（当前默认 `false`）。

### 5) 企业微信为什么不再走 OpenClaw 内置 Agent

- 当 `channels.wecom.bridgeUrl` 被配置后，企业微信插件会把消息转发到本项目 bridge。
- bridge 在本仓库内执行 `SupportIntakeWorkflow`（含 LLM/RAG/工单规则）。
- OpenClaw 仍只承担渠道接入、session、routing。

### 6) 为什么没有前端后台

- 升级1阶段以前端不在范围内；升级2已新增 `web_console/` 作为 Ops Console 前端。

### 7) 为什么 `make lint` 会扫到 `refs/` 报错

- `refs/` 是第三方参考代码，不受本仓编码规范约束。
- 提交前请使用路径限定 lint，仅检查本仓业务代码目录。

## 容器与 CI

- 本地容器 smoke（干净环境）：
  - `docker compose run --rm smoke`
- CI 定义：
  - `.github/workflows/ci.yml` 包含 `quality`、`smoke-container`、`acceptance` 三个阶段。
  - `acceptance` 为独立 job，不强耦合 `check` 目标。

## 发布与回滚

- 推荐命令链（dev）：
  - `make release-cycle ENV=dev`
- 分步执行（dev）：
  - `make deploy-release ENV=dev`
  - `make verify-release ENV=dev`
  - `make rollback-release ENV=dev`
- 当发布/验证失败时，脚本会输出 `commands` 与 `diagnostics` 字段，可直接复制复现排障。
