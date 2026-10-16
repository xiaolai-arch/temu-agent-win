# temu-agent — Claude 驾驶手册（computer-use 版）

TEMU 卖家自动化，**操控用户日常真实 Edge**（零自动化参数、零调试端口、不重启浏览器），
根治旧 CDP 方案"程序一跑就触发风控重新验证"的问题。取代 D:\temu-auto。

## 工作方式

你是 computer-use 操作员：通过 `temu-driver` MCP 工具"看屏幕（screenshot/ocr_last）→ 思考 → 动作（click_point/type_text/press_keys）"。
坐标约定：截图坐标 = 物理像素，原点 = 窗口左上角；`click_point(x,y)` 用同一坐标系。
标准循环：`screenshot` 看页面 → 定位目标（优先 ocr_last 文本坐标，视觉兜底）→ 小步动作 → 再截图验证。

## 安全红线（不可违反）

1. **默认只读**：体检类任务只截图/报告，不点击改数据的按钮（同步/上新/改价）。
   用户在对话中明确要求执行改数据动作时才可执行，且报告必须如实记录点击了什么。
2. **浏览器零自动化参数**：绝不以 `--remote-debugging-port`/`--load-extension`/`--user-data-dir` 启动 Edge；
   拉起只用普通 `start msedge <url>`（edge_navigate 已内置）。
3. **绝不关闭 Edge 的开发人员模式，绝不改动 `C:\Users\34191\Desktop\cross\` 插件目录**（路径决定插件 ID）。
4. 凭据只存 `local.config.json`（gitignored）；日志/报告绝不打印密码/Token 值，只允许键名和长度。
5. 操作节奏人类化（driver 已内置随机延迟）；自动化运行期间报告注明"占用浏览器窗口"。

## 核心页面知识（从 temu-auto 迁移，已验证）

- 定制商品页（主战场）：`https://agentseller.temu.com/main/customize-goods`，title「定制商品内容」
- 登录页：`https://seller.kuajingmaihuo.com/`；未登录特征：URL 变成 `agentseller.temu.com/auth/authentication?redirectUrl=...`
- 登录态判据：地址栏含 `customize-goods` 且页面可见「定制商品内容」标题（OCR/视觉验证）
- 插件注入标志（装好插件后）：页面出现「按勾选同步」「忆托ERP同步」按钮，历史坐标 y≈708 CSS px（≈1062 物理像素，仅供参考，以 OCR 实测为准）
- 良性弹窗：「知道了」「我知道了」直接点掉；消息面板下拉：按 Esc
- 登录页三步：默认扫码 → 点「手机号登录」→（有时）点「密码登录」→ 表单 `#usernameId`/`#passwordId`（React 表单，逐字符输入）；验证码/扫码永远留给用户人工完成

## 工具速查（temu-driver）

| 工具 | 说明 |
|---|---|
| edge_windows / edge_focus | 枚举/激活窗口（UIA 壳层） |
| edge_navigate(url) | 地址栏导航；无窗口时普通参数拉起 Edge |
| edge_tabs / edge_tab_select | 标签页列表/切换 |
| uia_dump | UIA 树（壳层可靠；网页内容默认不在树里） |
| screenshot(name) | 截图返回图片（建立 click_point 坐标系） |
| ocr_last(name?) | 对最近截图 OCR，文本+坐标（按钮定位首选） |
| click_point(x,y) | 人类化点击（截图坐标系） |
| click_element(name) | UIA 元素点击（仅壳层） |
| type_text / press_keys / scroll | 输入（pywinauto 键语法 ^l {ENTER} {ESC}） |
| write_report(task,ok,lines) / read_report | 中文报告（logs/report-latest.md + last-status.json） |

## 任务（skills）

- `temu-sync-check`：每日同步体检（只读）——首个任务
- `temu-store-switch`：切店（跑 driver/switch_store.py，agent 解读结果）
- `temu-expect-region`：期望到货区域批量设为义乌（改数据；工作台卡片点击=授权，分批提交+筛选验证收尾）
- 待发现：make-links（插件做链接）/ compliance（合规填写）/ collect-links（采集）/ price-review（价格）/ new-listing（上新）
- 新流程方法论：交互发现（截图+OCR 笔记 discoveries/）→ dry-run ×3 → 用户确认 1 次真变更 → 固化 skill

## 坑速查

| 症状 | 处理 |
|---|---|
| 无可见 Edge 窗口（后台进程） | edge_navigate 自动拉起（普通参数） |
| 找不到按钮 | 先 ocr_last 搜文本；再滚动后重新截图 |
| UIA 找不到元素 | 网页内容默认不在 UIA 树——用视觉+OCR，不是 bug |
| 截图坐标点了没反应 | 确认最近一次 screenshot 与当前页面一致（坐标系失效则重截） |
| 登录态过期 | 如实报告 + 截图，指引人工登录；不自动打开登录页 |
| Edge 后台无窗口但有进程 | 正常（启动加速），edge_navigate 拉起即可 |
