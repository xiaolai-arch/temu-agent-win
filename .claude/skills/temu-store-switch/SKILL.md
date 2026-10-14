---
name: temu-store-switch
description: TEMU 店铺切换（账号切换式多店铺）。核心是运行确定性脚本 driver/switch_store.py，agent 负责解读结果与兜底。用户要求"切店/切到某店/去店铺B"或某店体检前使用。
---

# temu-store-switch — 店铺切换

## 首选：直接跑脚本（快而稳，~115-145 秒/店）

```
python D:\temu-agent\driver\switch_store.py <store-id>    # main / store-b / store-c / …（配置里的都行）
python D:\temu-agent\driver\switch_store.py --check       # 只看当前在哪店
python D:\temu-agent\driver\switch_store.py --doctor      # 环境自检（OCR/窗口/凭据/同步插件，不登录）
python D:\temu-agent\driver\switch_store.py --verify-all  # 全店轮回实测（加新店后必跑）
```

脚本内含完整流程（详见 discoveries/store-switch.md）：
登录（Tab 密码法 + 同意并登录 + 关闭 Edge 保存密码气泡）
→ Agent Center 联动（seller 主页 → 商品管理 → 定制商品内容 → 勾协议 → 确认授权并前往
   → 确认切换弹窗——含后台新标签里的，蓝色按钮像素定位；失败自动重试一次）
→ 店名 + 双按钮验证 → 中文报告。
同一时刻只允许一个切店进程（文件锁 driver/.switch-lock，15 分钟过期）。

退出码：0 成功 / 1 页面异常 / 2 验证码或账密错 / 3 验证失败（重跑一次通常恢复）。

## 环境出问题时（双按钮全消失 / 全部 failpage）

先 `--doctor`：OCR 管线、各店凭据、**同步插件在位**（Edge 大版本更新会把解压插件
整批卸掉——2026-10-14 事故）都查。缺插件跑 `python driver/restore_extensions.py` 恢复。

## 加新店铺（免改代码）

1. `local.config.json` → `accounts` 加 `"store-d": {"phone": "...", "password": "..."}`（name 留空自动学）
2. `--doctor` 全绿 → 3. 首切 `store-d` → 4. `--verify-all` 全店矩阵全 ✅ 即接入完成
（工作台店铺卡从配置动态生成，重启工作台即出现新店按钮；详见 discoveries/store-switch.md「新店接入 SOP」）

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
