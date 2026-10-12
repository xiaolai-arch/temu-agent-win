# store-switch（账号切换式多店铺）— 发现会话（2026-10-12 实测打通）

## 模式定案

多店铺 = **同一浏览器内切换登录账号**（每店一个手机号+密码），不是多 Edge profile。
账号名即店铺标识：主店=hpoiZee(15194470169)，店铺B=boliooZ(13419966639)，店铺C=凭据见 local.config。

## ⚠️ 双系统会话独立（重要）

- `seller.kuajingmaihuo.com`（卖家门户）和 `agentseller.temu.com`（Agent Center/定制商品页所在）**各自持有独立会话**
- 登录只切 seller 侧；Agent Center 旧会话不自动失效（实测 2 分钟+仍存活），定制商品页仍显示旧店
- **完整切店 = seller 登录 + Agent Center 也切换**：redirectUrl 登录法（`/login?redirectUrl=https%3A%2F%2Fagentseller.temu.com%2Fmain%2Fcustomize-goods`）理论可行但该页面行为异常（本轮未跑通，待下轮研究）；当前实操：seller 登录后，到 Agent Center 用其 auth 流程再登一次，或人工完成
- 登出路由探测：`agentseller.temu.com/auth/logout`、`/logout` 均无效（404）

## 实测有效流程（干净 /login，seller 侧）

1. **导航 `https://seller.kuajingmaihuo.com/login`**（不带参数；带 redirectUrl 的版本行为异常）——已登录也直接出登录页，无需先退出
2. OCR 点「手机号登录」tab（(1824,537) 附近，坐标会漂移，实时定位）
3. 密码模式：浏览器通常记住上次模式（特征：「忘记密码」链接）；若在验证码模式，OCR 找「密码登录」子模式链接
4. **手机号**：autofill 是上次账号（不可信）→ 点手机号框 → `^a` → 重打目标手机号
5. **密码**：**点手机号框 → 按 Tab（焦点进密码框）→ `^a` → 输密码**（密码框坐标点击从未命中，Tab 法 100% 有效）
6. 点「登录」（约 (1876,859)，OCR 定位）
7. **关键：点登录后弹出「同意并登录/不同意」确认层**——点「同意并登录」（弹层出现时布局左移，按钮约 (1294,854)，OCR 实时定位）→ 登录完成
8. 验证：settle/site-main 的 SellerCentral 卡片显示目标账号名

## 坑速查（今晚 20+ 次实战教训）

| 坑 | 真相/解法 |
|---|---|
| 协议小勾选框点不中（9 组坐标+键盘流全败） | **别找勾选框**：直接点登录 → TEMU 弹「同意并登录/不同意」→ 点「同意并登录」一步到位 |
| 「是否阅读并同意」提示常驻 (1049,778) | 它是确认弹层的文字，不是错误 toast；点登录弹层会出现 |
| 密码框 (1877,700) 点击无效 | 密码框坐标从未命中；**点手机号框→Tab** 才是正解 |
| DevTools 开着 | 压缩视口、所有坐标漂移（y 从 631→406）；**自动化前确认 DevTools 已关** |
| redirectUrl 版 /login | 行为与干净版不同（本轮卡死）；用干净 /login |
| autofill 手机号 | 是上次登录账号，必须 ^a 重打 |
| 登录成功但定制商品页还是旧店 | 双系统会话独立（见上），Agent Center 需单独切 |

## 待下轮研究

1. redirectUrl 登录法跑通（一次登两个系统）——正确的参数格式/时机
2. Agent Center 独立登出/切换入口（右上角无账号菜单，auth 页机制待探）
3. 切店固化到 skill 后实测：temu-store-switch 全自动（含「同意并登录」战术）

