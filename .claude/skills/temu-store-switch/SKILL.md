---
name: temu-store-switch
description: TEMU 店铺切换（账号切换式多店铺）：登录目标店手机号 → 验证定制商品页双同步按钮 → 报告。用户要求"切店/切换到某店/去店铺B看看"或跑某店的同步体检前置步骤时使用。
---

# temu-store-switch — 店铺切换

## 店铺账号

- main=主店(hpoiZee)、store-b=店铺B(boliooZ)、store-c=店铺C；凭据 `local.config.json` 的 `accounts.<id>`（手机号+密码，绝不打印）
- 当前在线店铺判别：定制商品页右上角账号名（OCR 可见）

## 流程（详见 discoveries/store-switch.md，2026-10-12 实测）

1. `edge_navigate("https://seller.kuajingmaihuo.com/login")`（**干净 URL，不带 redirectUrl**；已登录也直接出登录页）
2. OCR 定位点「手机号登录」tab；确认密码模式（有「忘记密码」链接=密码模式；否则 OCR 找「密码登录」子模式链接）
3. 点手机号输入框 → `^a` → 重打目标店手机号（**autofill 是上次账号，不可信**）
4. **点手机号框 → 按 Tab（焦点进密码框）→ `^a` → 输密码**（密码框不能靠坐标点击，Tab 法实测 100% 有效）
5. OCR 定位「登录」按钮（≈(1876,859)）→ 点击 → 等 3 秒
6. **TEMU 会弹「同意并登录 / 不同意」确认层**（布局左移）→ OCR 定位并点「**同意并登录**」（≈(1294,854)）→ 等 8 秒
7. 若出现验证码/滑块 → 截图+提示用户人工完成，轮询等待（10 分钟超时）
8. 验证 seller 侧：settle/site-main 页 SellerCentral 卡片显示目标账号名
9. **双系统会话独立**：Agent Center（agentseller.temu.com）需单独确认——导航定制商品页看右上角账号名；若仍是旧店，向用户说明并协助完成 Agent Center 侧切换（redirectUrl 法待研究，当前可能需人工）
10. `write_report("store-switch", ok, [目标店, seller账号名, AgentCenter账号名, 双按钮状态, 截图])`

## 已知坑（勿重复踩）

- 协议小勾选框不要直接点（20 次实战全部失败）——走「同意并登录」弹层战术
- DevTools 开着会压缩视口、坐标全漂——自动化前确认已关闭
- redirectUrl 版 /login 行为异常，用干净 /login

## 红线

- 不碰验证码（滑块/短信一律用户完成）；密码只从 local.config 读、type_text 输入，绝不进日志/报告
- 切店后任务结束停在目标店（下次切回主店同样流程）
