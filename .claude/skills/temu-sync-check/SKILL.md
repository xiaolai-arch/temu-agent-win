---
name: temu-sync-check
description: TEMU 每日同步体检（只读）：导航到定制商品页，验证登录态与「按勾选同步」「忆托ERP同步」两个插件按钮，截图取证并写中文报告。不点击任何改数据的按钮。用户要求"跑同步体检/每日体检/sync-check"时使用。
---

# temu-sync-check — 每日同步体检（只读）

## 流程

1. `edge_navigate("https://agentseller.temu.com/main/customize-goods")`，等待页面加载（sleep 后截图确认）
2. 若弹「知道了/我知道了」弹窗：用 ocr_last 定位按钮 → click_point 点掉 → 重新截图
3. 消息下拉遮挡时：press_keys("{ESC}")
4. 登录态判断（任一失败即未登录）：
   - `edge_tabs` 当前标签含「定制商品内容」
   - 截图 OCR 可见「定制商品内容」标题
   - 未登录特征：标签/地址栏变为 `auth/authentication?redirectUrl=...`
5. 插件按钮验证：`ocr_last` 搜「按勾选同步」与「忆托ERP同步」，记录两者坐标；
   搜不到时先 `scroll(-300)` 回顶再试一次（按钮为插件注入，通常在页面中下部工具栏）
6. 最终 `screenshot("sync-check-final")` 全页取证
7. `write_report("sync-check", ok, lines)`：
   - 行1：登录态（已登录/未登录+跳转URL）
   - 行2：插件按钮（两个按钮+坐标 / 缺失）
   - 行3：**"未执行任何同步点击"**（只读任务，必须如实）
   - 未登录时加指引：直接跑切店脚本恢复（见下「未登录/别店处理」），勿手动走授权流程
8. **未登录 / 停在别店**：`python driver/switch_store.py <store-id>`（全程
   自动到同步页，含登录与身份切换；切回当前在用店 = `main`）。**不要**手动点授权卡、
   也不要直航 `auth/authentication?redirectUrl=...`——那只刷新授权不切身份（2026-10-16 实测）。
   切店后回到步骤 1 重跑体检。

## 红线

- 绝不点击「按勾选同步」「忆托ERP同步」——本任务只验证存在性
- 用户明确要求执行同步时，先复述将点击的按钮并获确认，另走同步执行流程
