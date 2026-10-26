# temu-agent — TEMU 店群自动化（computer-use 版）

操控**日常真实浏览器**（ego 默认 / Edge 可切，零自动化参数、登录态与插件原生保留）完成
TEMU 卖家重复工作，取代旧项目 D:\temu-auto（CDP 方案，已被 TEMU 风控判定环境异常）。

**换 Mac 工作：先读 `docs/MIGRATION-MAC.md`**（哪些模块跨平台、哪些 Windows 专属、凭据怎么搬）。

## 业务模块地图（2026-10-26 重组：代码+数据+文档随模块走）

| 模块 | 目录 | 内容 | 当前状态 |
|---|---|---|---|
| 基础设施 | `core/` | 窗口/UIA/输入/截图/OCR/报告 + MCP server + 验证码求解 | 稳定 |
| 切店·同步 | `store/` | switch_store（切店/`--check`同步体检/`--doctor`自检）+ 插件恢复 | 每日在用 |
| 采集 | `collect/` | 速卖通→妙手 ERP 无人值守采集 + ERP 登录 | 稳定 |
| 选品 | `select/` | 速卖通词池扫描 + 选品报告 | 稳定 |
| 调价 | `pricing/` | 工单生成 make_adjust_todo / 批量 grind_batch / ego DOM 引擎 + `data/` 工单 | store-c ✅ 420/420；store-b ⏸ 533 待续 |
| 下架 | `delist/` | 佳同插件批量下架（待实操）+ csx_delist 兜底 + `data/` 工单 | store-c 59 SKC 待实操；store-b 52 链接冻结 |
| 导出·盘点 | `export/` | 商品列表导出 + 四店统计 + `data/` 各店最新快照 | 稳定 |
| 文档 | `docs/` | 架构方案 / HANDOFF 交接 / 盘点与 linkfox 技能报告 / Mac 迁移 | — |
| 交互笔记 | `discoveries/` | 新流程方法论（截图+OCR 实测 → 固化 skill/脚本） | 持续沉淀 |
| 工作台 | `plugin/temu-panel/` | CloudCLI 面板（Node，`TEMU_DIR` 可覆盖项目目录） | 可选 |
| 辅助 | `scripts/` `bin/` | 截图定位小工具 / 计划任务与工作台启动器 | — |
| 运行产物 | `logs/` `screenshots/` | 报告与截图（gitignored，定期清理旧件） | — |

## 架构

```
CloudCLI 工作台（可选，localhost:3001）
  └─ temu-panel 插件：任务按钮 + 实时日志
        ↓ POST /api/agent
Claude Code CLI / ZCode（本地已配 API）  ← cwd = 本目录（.mcp.json → core/server.py）
  └─ temu-driver MCP（core/server.py，Python）
        ↓ UIA 壳层 + 视觉/OCR 内容层 + 人类化鼠标键盘
日常浏览器（ego / Edge，不带任何调试/注入参数）
```

写操作（发品/改价/上下架）优先走 LinkFox Temu API 技能（`linkfox-temu-*`，见 CLAUDE.md），
浏览器点击只作 API 失败的兜底和采集用。

## 环境要求

- Python 3.10+：`pip install -r requirements.txt`（阿里云镜像快）
- 本地 Claude Code CLI / ZCode（cc-switch 配置供应商）
- CloudCLI（可选，工作台 UI）

## 日常使用

- "跑同步体检" → temu-sync-check skill（只读，出报告）
- 改数据操作（真实同步/上新/调价/下架）需要明确说出要求并确认
- 各模块入口命令见对应目录 README

## 红线

默认只读；浏览器零自动化参数；绝不关开发人员模式/不动 cross\ 插件目录；
凭据只存 local.config.json；报告如实。
