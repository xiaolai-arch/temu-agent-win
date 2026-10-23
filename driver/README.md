# driver/ — Windows 浏览器自动化层

**整个目录是 Windows 专属**（pywinauto / UIA / ctypes.windll / PowerShell OCR / `start msedge`），
操控用户日常真实 Edge（零自动化参数）。Mac 移植见 `docs/MIGRATION-MAC.md`。

## 模块分层

### 核心层（基础设施，被所有任务脚本依赖）

| 文件 | 职责 |
|---|---|
| `server.py` | temu-driver MCP server（stdio）：UIA 壳层 + 视觉/OCR 内容层 + 报告，15 工具。入口见 `.mcp.json` |
| `winutil.py` | Win32 公共层：DPI 感知、Edge 窗口枚举（只读） |
| `uia_shell.py` | UIA 壳层操作：地址栏导航、标签切换、树 dump、元素点击坐标解析 |
| `input.py` | 人类化输入：鼠标分步移动（随机速度/抖动）、键盘复用 pywinauto SendInput。所有坐标 = 屏幕物理像素 |
| `shot.py` | DPI-aware 窗口截图 + OCR（调 `ocr.ps1`，Windows Media.Ocr 中文优先）；维护最近截图坐标系（`.last-shot.json`） |
| `ocr.ps1` | PowerShell OCR 引擎（被 shot.py 调用，输出 JSON） |
| `report.py` | 中文报告落盘 `../logs/report-latest.md` + `last-status.json` |
| `ctl.py` | 调试小控制台（Bash 里一步一动作：shot/click/keys/ocr/dialog） |

### 店铺运营任务（Temu 卖家后台）

| 文件 | 职责 |
|---|---|
| `switch_store.py` | **切店主力**（账号切换式多店铺）：登录→选店→验证双按钮；`--check/--doctor/--verify-all`。凭据读 `../local.config.json`，文件锁 `.switch-lock` |
| `export_goods.py` | 商品列表导出（只读）→ `../research/store-data/<store>-goods-<date>.xlsx` |
| `grind_batch.py` | **批量调价调度**：读工单 CSV，逐 SKC 子进程跑 grind_one，断点续跑（done 文件在 research/store-data） |
| `grind_one.py` | 单 SKC 调价全流程（现行主力，弹窗 SKC-ID 匹配 + 渲染门控 + 逐行重定位验证） |
| `price_one.py` | 单 SKC 调价早期版本（数量→建议价映射；调价逻辑已被 grind_one 大修取代） |
| `csx_delist.py` | 客服自助工具批量下架（`python csx_delist.py SKU|SKC <id>...`） |
| `restore_extensions.py` | Edge 大版本更新后一键恢复 cross\ 三插件 + 开发人员模式（2026-10-14 事故产物） |

### 采集任务（速卖通选品素材）

| 文件 | 职责 |
|---|---|
| `collect_run.py` | 无人值守长跑采集：自动搜词→定位网格→逐格采集→触底换词 |
| `collect_batch.py` | Temu 搜索页批量采集（进详情→采集→关标签） |
| `collect_screen.py` / `collect_one_chrome.py` | Chrome 搜索页逐商品采集（一屏 10 个）/ 单卡片采集 |
| `ali_collect.py` / `ali_screen.py` / `ali_similar.py` | 速卖通列表页 / 搜索结果页 / 相似商品网格采集 |
| `miaoshou_login.py` | 妙手 ERP 登录自动化（会话失效时用，含图形验证码 OCR 重试） |

### 验证码求解（Temu 风控，物体无关解法）

`temu_captcha_drag.py`（拖拽入框）、`temu_captcha_rotate.py`（旋转对齐）、
`temu_captcha_slide.py` / `temu_captcha_slider.py`（滑块拼图，一条龙版）

### 历史自检（Phase 0 遗留，留作参考）

`smoke.py`（地基冒烟）、`phase0_ext_check.py`（插件状态截图）、
`check_ext_page.py`（最新截图 OCR 过滤）、`test_server.py`（MCP server 端到端自测）

## 约定

- **调用方式**：任务脚本可直接 `python <脚本>.py` 运行——路径已全部改为 `__file__` 相对推导，不依赖硬编码盘符；跨脚本 import 靠 `sys.path.insert(0, <本目录>)`。
- **坐标约定**：截图与点击坐标都是物理像素，原点 = 窗口左上角。
- **产出位置**：截图 `../screenshots/`、报告 `../logs/`、运营数据 `../research/store-data/`。
- **依赖关系**：任务脚本 → 核心四件套（winutil/uia_shell/input/shot）+ report；`grind_one` 复用 `switch_store._clear_input` 和 `export_goods.blue_button`；`grind_batch` 以子进程跑 `grind_one`。
- **凭据**：只读 `../local.config.json`（gitignored），绝不打印。
