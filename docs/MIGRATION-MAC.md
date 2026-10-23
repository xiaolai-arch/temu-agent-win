# 迁移指南：Windows → Mac

项目已在 2026-10-24 按模块整理（见根 README 目录地图）。本文说明哪些能直接带走、
哪些带不走、哪些要手动搬。

## 第一步：把所有东西纳入 git（Windows 上做）

大量调研报告、store-data 数据和新驱动脚本目前**未跟踪**（`git status` 里的 `??`）。
不 commit 的话 push/clone 都不会带过去。在 Windows 上：

```bash
git add -A                      # local.config.json / logs/ / screenshots/ 已被 .gitignore 挡住，不会被提交
git commit -m "模块化整理 + 全量入库（Mac 迁移准备）"
git push
```

## 第二步：Mac 上恢复

```bash
git clone <仓库地址> ~/temu-agent
python3 -m pip install pillow openpyxl requests   # 见下方依赖说明
```

## 直接可用（跨平台）

| 模块 | 说明 |
|---|---|
| `research/` 全部 | 报告、数据、选品结论。`analyze_stores.py` 纯 openpyxl 可直接跑；`scan/`、`probe*` 脚本逻辑可参考但依赖 driver（见下） |
| `plugin/temu-panel` | Node 服务，跨平台。启动前 `export TEMU_DIR=~/temu-agent`（不设则默认 Windows 路径）。注意它 spawn 的是 `claude` CLI + cmd.exe，Mac 上需小改 `server.mjs` 的 spawn 段 |
| `.claude/skills/` | 三个技能文档可读，但流程里引用的 driver 脚本在 Mac 上跑不了 |
| `docs/` `discoveries/` | 全部是 markdown 知识，直接带走 |
| LinkFox API 技能 | 技能本体在 `~/.zcode/skills/linkfox-*`（用户目录，**不在本仓库**），Mac 上重新安装/同步；API 本身与平台无关 |

## Windows 专属（Mac 上不可用，留作参考）

- **`driver/` 整个目录**：pywinauto、UIA、ctypes.windll、PowerShell OCR（Media.Ocr）、`start msedge`、
  `D:\Download` 轮询、`C:\Users\...\Desktop\cross` 插件目录——全部 Windows API。
- `bin/*.cmd`：计划任务启动器（Windows 任务计划 TEMU-Agent-DailySyncCheck 也在 Mac 上不存在，需用 launchd/cron 重做）。
- `scripts/*.ps1`：PowerShell 对话框/截图辅助。
- `.mcp.json`：指向 `D:\temu-agent\driver\server.py`，Mac 上该 server 本身跑不起来，迁移后应删除或注释掉该 MCP 配置。
- `requirements.txt` 里的 `pywinauto`、`comtypes` 在 Mac 上装不上也用不到。

## 必须手动搬运（不在 git 里）

| 东西 | 位置 | 方式 |
|---|---|---|
| `local.config.json` | 项目根（gitignored） | 手动拷贝。含各店账号凭据 + 妙手凭据，**敏感，别走网盘明文** |
| `LINKFOXAGENT_API_KEY` | 环境变量 | Mac 上重新配置 |
| Temu 各店 access_token | LinkFox 技能体系内 | 按技能文档在 Mac 重新授权（应用名须为「酷鸟卖家助手」） |
| Edge 三插件 `cross\` | `C:\Users\34191\Desktop\cross` | Mac Edge 需重新解压加载；**注意插件 ID 由路径决定，ID 变了插件登录态/配置可能重置** |
| Windows 上的 Edge 登录态 | 浏览器 profile | 无法迁移，Mac 上各店重新登录（switch_store 流程会引导） |

## 如果要在 Mac 上继续浏览器自动化（移植路线）

核心层的**接口约定**（见 `driver/README.md`：物理像素坐标、screenshot→ocr→click 循环、
人类化输入、报告落盘）可以照搬，实现全部重写：

| Windows 实现 | Mac 对应 |
|---|---|
| `winutil.py`（窗口枚举/DPI） | AppleScript / CGWindowList（pyobjc） |
| `uia_shell.py`（地址栏/标签） | AppleScript `tell application "Microsoft Edge"`（activate / open location / tab 操作） |
| `shot.py` + `ocr.ps1` | `screencapture -l <windowid>` + Vision 框架 OCR（pyobjc，或 `shortcuts` CLI） |
| `input.py`（人类化鼠标键盘） | pyautogui（本身跨平台，移动曲线逻辑可平移） |
| 风控要点不变 | 依旧零自动化启动参数、操控日常浏览器、人类化节奏 |

工作量集中在 winutil/uia_shell/shot 三个文件；任务脚本（switch_store 的流程逻辑、
grind_one 的弹窗匹配策略）主要是坐标与文案断言，可按新 OCR 输出逐个验证迁移。

## 迁移后 Mac 日常

- 选品分析（research/）与 LinkFox API 写操作（发品/改价/订单，需用户确认的红线不变）可立即恢复；
- 浏览器自动化（切店/体检/采集）在移植完成前不可用，优先走 API 技能。
