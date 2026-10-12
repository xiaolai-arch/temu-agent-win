---
name: temu-store-switch
description: TEMU 店铺切换（账号切换式多店铺）。核心是运行确定性脚本 driver/switch_store.py，agent 负责解读结果与兜底。用户要求"切店/切到某店/去店铺B"或某店体检前使用。
---

# temu-store-switch — 店铺切换

## 首选：直接跑脚本（快而稳，~60-90 秒）

```
python D:\temu-agent\driver\switch_store.py <store-id>    # main / store-b / store-c
python D:\temu-agent\driver\switch_store.py --check       # 只看当前在哪店
```

脚本内含完整流程（详见 discoveries/store-switch.md）：登录（Tab 密码法+同意并登录）
→ Agent Center 联动（自动/重授权+键盘选分区）→ 双按钮验证 → 中文报告。
退出码：0 成功 / 1 页面异常 / 2 验证码或账密错 / 3 卡 auth 授权页。

## 结果处理

- **exit 0**：完成，直接引用报告（logs/report-latest.md）
- **exit 2**：出现验证码或密码错 → 告知用户（验证码绝不由 agent 处理；密码核对 local.config.json）
- **exit 3**：卡 Agent Center 授权页（该页对自动操作免疫）→ 明确告诉用户：
  "浏览器当前页面用鼠标点一下「商家中心」卡片（10 秒），完成后说一声，我重跑验证"
- **exit 1**：看脚本最后截图（screenshots/sw-*.png）诊断，常见为 OCR 漏读 → 重跑一次

## 原理速查（脚本的依据）

- seller 与 Agent Center 会话独立；授权良好时登录后自动联动
- 密码框只能"点手机号框→Tab"进入（坐标点击全部无效）
- 「同意并登录」确认层出现在点登录后（左侧按钮）
- 选分区页鼠标免疫但键盘 Tab×4+Enter 可过；auth 地区页对一切合成输入免疫（人工 10 秒）
