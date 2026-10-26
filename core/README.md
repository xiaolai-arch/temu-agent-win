# core/ — 自动化基础设施（Windows 专属）

被所有业务模块（store/collect/select/pricing/delist/export）依赖的底层。
pywinauto / UIA / ctypes.windll / PowerShell OCR，操控日常真实浏览器
（ego 默认，`TEMU_BROWSER=edge` 可切回 Edge，2026-10-26 起）。Mac 移植见 `docs/MIGRATION-MAC.md`。

## 文件

| 文件 | 职责 |
|---|---|
| `server.py` | temu-driver MCP server（stdio）：UIA 壳层 + 视觉/OCR 内容层 + 报告，15 工具。入口见 `.mcp.json` |
| `test_server.py` | MCP server 端到端自测（改完底层跑这个） |
| `winutil.py` | Win32 公共层：DPI 感知、浏览器窗口枚举/拉起（ego/Edge/Chrome 三套） |
| `uia_shell.py` | UIA 壳层操作：地址栏导航、标签切换、树 dump、元素点击 |
| `input.py` | 人类化输入：鼠标分步移动（随机速度/抖动）、键盘 SendInput。坐标 = 屏幕物理像素 |
| `shot.py` | DPI-aware 窗口截图 + OCR（调 `ocr.ps1`）；维护最近截图坐标系（`.last-shot.json`，gitignored） |
| `ocr.ps1` | PowerShell OCR 引擎（Windows Media.Ocr 中文优先，输出 JSON） |
| `report.py` | 中文报告落盘 `../logs/report-latest.md` + `last-status.json` |
| `ctl.py` | 调试小控制台（Bash 里一步一动作：shot/click/keys/ocr/dialog） |
| `temu_captcha_slide.py` | 滑块拼图求解（纯几何，被 collect_run / scan_keywords 复用） |
| `temu_captcha_rotate.py` | 旋转类验证码（模板匹配+闭环点击；网格坐标需按屏微调，未接入自动链路） |

## 约定

- **被业务脚本引用的方式**：各模块脚本 `sys.path.insert(0, <本模块>/../core)` 后裸 import。
- **坐标约定**：截图与点击坐标都是物理像素，原点 = 窗口左上角。
- **产出位置**：截图 `../screenshots/`、报告 `../logs/`（目录名被 core 脚本相对引用，勿改名）。
- **凭据**：只读 `../local.config.json`（gitignored），绝不打印。
