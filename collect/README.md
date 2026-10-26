# collect/ — 采集（速卖通选品素材 → 妙手 ERP）

## collect_run.py — 无人值守长跑采集（主力）

```bash
python collect/collect_run.py
```

Chrome 打开速卖通：自动搜词 → 网格定位 → 逐格点「采集」→ 触底换词。
词池在脚本内 `KEYWORDS`（2026-10-22 换新池，依据 `select/2026-10-22-选品报告.md`）；
进度日志 `../logs/collect_run.log`；掉登录时自动跑 miaoshou_login（含图形验证码 OCR 重试）。
滑块验证码用 `core/temu_captcha_slide` 自动过。

## miaoshou_login.py — 妙手 ERP 登录

```bash
python collect/miaoshou_login.py --check          # 只检测登录态
python collect/miaoshou_login.py [--chrome]       # 未登录则自动登录
python collect/miaoshou_login.py --captcha 3210   # OCR 认不出时人工看图直填
```

凭据：`../local.config.json` 的 `miaoshou.phone/password`。

## 历史脉络

2026-10-18 横评结论（`../discoveries/2026-10-18-采集链路全面测试.md`）：7 种采集方式里
**插件采集是唯一可靠通道**，requests 直抓被反爬墙挡死（旧 probe 已删）。
旧的逐屏/单卡/相似商品采集脚本（ali_*、collect_screen 等）已被 collect_run 全自动版取代，2026-10-26 清理。
