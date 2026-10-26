# store/ — 切店 · 登录 · 同步验证 · 环境自检

`switch_store.py` 是本模块核心，也是**每日同步体检**的底座（一个文件多种模式）：

```bash
python store/switch_store.py <store-id>    # 切店：登录→侧边栏UIA联动→授权→店名+双按钮验证
python store/switch_store.py --check       # 同步体检（只读）：当前在哪店 + 「按勾选同步」「忆托ERP同步」双按钮在位
python store/switch_store.py --doctor      # 环境自检：OCR管线/窗口/各店凭据/三同步插件在位（读 Secure Preferences）
python store/switch_store.py --verify-all  # 全店轮回实测（加新店后必跑）
```

- 凭据：`../local.config.json` 的 `accounts.<id>`（手机号+密码）。
- 文件锁 `store/.switch-lock`（15 分钟过期）防并发抢浏览器窗口。
- 验证码/扫码永远留给人工（退出码 2）；退出码 3 = 切换后验证失败。
- 对应技能：`.claude/skills/temu-store-switch`（切店）、`.claude/skills/temu-sync-check`（每日体检，
  计划任务入口 `bin/daily-sync-check.cmd`）。

## restore_extensions.py — 插件恢复

Edge/ego 大版本更新会关开发人员模式并卸载解压插件（2026-10-14/19 两次事故）。
`python store/restore_extensions.py` 一键恢复 cross\ 三插件；doctor 第 4 项会检测在位状态。

## 同步说明

「同步」业务 = ERP 插件把采集/链接数据同步到 TEMU 后台，agent 侧只做**只读体检**
（双按钮在位即插件正常）；点同步按钮属改数据操作，需用户明确授权。
