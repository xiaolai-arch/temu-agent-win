# temu-agent — TEMU 卖家自动化（computer-use 版）

操控**你日常真实 Edge**（零自动化参数、登录态与插件原生保留）完成 TEMU 卖家重复工作，
取代旧项目 D:\temu-auto（CDP 方案，已被 TEMU 风控判定环境异常）。

## 架构

```
CloudCLI 工作台（D:\claudecodecui，localhost:3001）
  └─ temu-panel 插件：任务按钮 + 实时日志
        ↓ POST /api/agent
Claude Code CLI（本地已配 API）  ← cwd = 本目录（.mcp.json）
  └─ temu-driver MCP（driver/server.py，Python）
        ↓ UIA 壳层 + 视觉/OCR 内容层 + 人类化鼠标键盘
你的日常 Edge（不带任何调试/注入参数）
```

## 环境要求

- Python 3.10+：`pip install -r requirements.txt`（阿里云镜像快）
- 本地 Claude Code CLI（cc-switch 配置供应商）
- CloudCLI（可选，工作台 UI）

## 首次配置（已完成项打勾）

- [x] Phase 0 地基验证（见 docs/phase0-findings.md）
- [x] temu-driver MCP server + 15 工具自测
- [ ] 一次性安装 3 个 ERP 插件到日常 Edge（开开发人员模式 + 加载 cross\ 三目录；之后永不关）
- [ ] CloudCLI API key + temu-panel 插件

## 日常使用

在 Claude Code（或 CloudCLI 工作台）里：
- "跑同步体检" → temu-sync-check（只读，出报告）
- 改数据操作（真实同步/上新）需要你明确说出要求并确认

## 红线

默认只读；浏览器零自动化参数；绝不关开发人员模式/不动 cross\ 插件目录；
凭据只存 local.config.json；报告如实。
