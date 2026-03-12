# web_console

**版本：v0.3.0（2026-03-12）**

`web_console` 是 `support-agent-platform` 的前端工作台（Workflow 3）。

## 作用

1. 展示 Dashboard、Tickets、Traces、Queues、KB、Channels。
2. 通过 `/api/*` 与后端联调，执行 claim/reassign/escalate/resolve/close。
3. 展示 trace、grounding、审批待办等运营与协同信息。

## 技术栈

- Next.js 15
- React 19
- TypeScript
- Vitest

## 常用命令

```bash
npm install
npm run dev
npm run lint
npm run typecheck
npm run test
```

## 说明

前端页面与后端能力边界说明统一在根目录文档：

- `../README.md`
- `../ARCHITECTURE.md`
- `../RUNBOOK.md`
- `../EVAL.md`
