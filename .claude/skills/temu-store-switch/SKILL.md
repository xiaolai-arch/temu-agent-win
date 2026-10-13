---
name: temu-store-switch
description: TEMU 店铺切换（账号切换式多店铺）。核心是运行确定性脚本 driver/switch_store.py，agent 负责解读结果与兜底。用户要求"切店/切到某店/去店铺B"或某店体检前使用。
---

# temu-store-switch — 店铺切换

## 首选：直接跑脚本（快而稳，~115-145 秒/店）

```
python D:\temu-agent\driver\switch_store.py <store-id>    # main / store-b / store-c
python D:\temu-agent\driver\switch_store.py --check       # 只看当前在哪店
```

脚本内含完整流程（详见 discoveries/store-switch.md）：
登录（Tab 密码法 + 同意并登录 + 关闭 Edge 保存密码气泡）
→ Agent Center 联动（seller 主页 → 商品管理 → 定制商品内容 → 勾协议 → 确认授权并前往
   → 确认切换弹窗蓝色按钮像素定位）→ 店名 + 双按钮验证 → 中文报告。
三店均已打通（main=hpoiZee / store-b=boliooZ / store-c=lecoddebujbrjq），
首登店名自动学习写进 local.config.json。

退出码：0 成功 / 1 页面异常 / 2 验证码或账密错 / 3 验证失败（重跑一次通常恢复）。

## 结果处理

- **exit 0**：完成，直接引用报告（logs/report-latest.md）
- **exit 2**：出现滑块验证码或密码错 → 告知用户（验证码绝不由 agent 处理；密码核对 local.config.json）
- **exit 3**：验证失败 → 先看截图（screenshots/sw-target*.png）核对页面状态，**重跑一次**通常恢复
- **exit 1**：看脚本最后截图诊断，常见 OCR 漏读 → 重跑一次
- 连续 2 次失败 → 停手报告用户，勿反复重试（防触发风控）

## 原理速查（脚本的依据）

- seller 与 Agent Center 会话独立；授权链路走用户正常路径：主页 → 商品管理 → 定制商品内容
- 密码框只能"点手机号框→Tab"进入（坐标点击全部无效）
- 「同意并登录」确认层出现在点登录后；登录成功后 Edge「保存密码？」气泡要点「以后再说」
- 「确认切换」弹窗的蓝色按钮白字 OCR 读不出 → 像素级蓝色块检测（点「不切换」左侧）
- 账号名比对先归一化（№→li、I/1→l、0→o）；未知店读到别家店名必须走联动（防跑错店）
- 全程不点「按勾选同步」「忆托ERP同步」，不碰任何验证码
