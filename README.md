# temu-agent — TEMU 卖家自动化（computer-use 版）

操控**你日常真实 Edge**（零自动化参数、登录态与插件原生保留）完成 TEMU 卖家重复工作，
取代旧项目 D:\temu-auto（CDP 方案，已被 TEMU 风控判定环境异常）。

**换 Mac 工作：先读 `docs/MIGRATION-MAC.md`**（哪些模块跨平台、哪些 Windows 专属、凭据怎么搬）。

## 目录地图

```
temu-agent/
├── driver/        Windows 浏览器自动化层（MCP server + 核心输入/截图/OCR + 切店/调价/采集任务）
│                  分层与约定见 driver/README.md —— 整目录 Windows 专属
├── research/      调研与运营数据：reports/（报告+任务交接）、store-data/（导出与工单）、
│                  scan/（速卖通选品扫描）、linkfox/（技能盘点）；见 research/README.md
├── plugin/temu-panel/  CloudCLI 工作台面板（Node，跨平台；项目目录可用 TEMU_DIR 环境变量覆盖）
├── .claude/skills/ 3 个 agent 技能：temu-sync-check / temu-store-switch / temu-expect-region
├── discoveries/   交互发现笔记（新流程方法论：截图+OCR 实测 → 固化 skill）
├── docs/          phase0 地基验证 + Mac 迁移指南
├── scripts/       Windows 辅助脚本（PowerShell 对话框/截图）
├── bin/           Windows 启动器（计划任务体检、工作台一键启动）
├── local.config.json  凭据（gitignored，绝不提交）
└── CLAUDE.md      agent 驾驶手册（安全红线 + 页面知识 + 工具速查）
```

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
- 改数据操作（真实同步/上新/调价）需要你明确说出要求并确认

## 红线

默认只读；浏览器零自动化参数；绝不关开发人员模式/不动 cross\ 插件目录；
凭据只存 local.config.json；报告如实。
