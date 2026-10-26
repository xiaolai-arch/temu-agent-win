> 📌 2026-10-26 模块化重组：文中 driver/xxx.py 已迁至 core|store|collect|pricing|delist|export 对应模块，research/store-data 已按业务拆入各模块 data/，research/reports 的 HANDOFF 已移至 docs/。路径以根 README 模块地图为准。

# 交接：store-c（lecoddebujbrjq / 152店铺）调价+钢印下架（2026-10-24 ego 浏览器首日）

> 新会话从此文档接手。浏览器：**ego lite**（不再用 temu-driver/pywinauto）。
> 引擎：`driver/ego/grind_lib.mjs`；运行器：`C:/Users/34191/ego/store-c-20261024-1015/run-batch.mjs`。
> ego 交互层知识（登录/授权门/弹窗/填值）见 `discoveries/2026-10-24-ego浏览器操控temu.md`。

## 一、今日成果（有验证）

| 事项 | 验证 |
|---|---|
| SKC 39724504682（餐巾 x3.31）调价提交：100pcs 54.8→50、50件 112.57→34 | ✅ 导出复核：两行已生效 |
| SKC 25421989595（腕带 x2.77，32行）调价提交（20行填 34/52.5） | ✅ 弹窗现价=目标价复核 |
| 2026-10-24 深夜：餐巾批量调价 | 🔄 夜班运行中（约 1 分钟/SKC），done 文件断点续跑 |
| 钢印（压花机）成本建模：25元/个，保本=25q+9)/0.8 | ✅ 用户确认 |
| 钢印亏损失清单：61 SKC / 3904 SKU（卖36.54 < 保本42.5，亏~6/单） | ✅ `research/store-data/delist-todo-store-c-stamp.json` |
| 钢印下架 ×2（今日额度）：95977981119、13299564425 | ✅ 机器人回复「该商品已下架」（导出复核待做） |

## 〇、用户情报（2026-10-24 晚）：「商品信息待确认」筛选

- 上新生命周期管理页的待办 tab（商品信息待确认/待激活/待修改/待寄样/审版待调整/价格待确认…）
  **是筛选条件**。「商品信息待确认」= 有商品调价完成待确认 或 审核通过可上架。
- 它被勾选时，**查询其他商品一律返回 0**——今晚大量 no-tj/suspect 的根因之一。
- 引擎已在 querySkc 开头自动取消勾选该筛选（grind_lib.mjs，20:08 版）。
- 待办出现「商品信息待确认①」本身是好消息：说明调价已被平台受理。

## 二、⚠️【已推翻】所谓「平台锁价」= 窗口最小化假象（2026-10-24 深夜修正）

**结论：不存在平台锁价。** 19:00 后「填值被抹、勾选点不动」的真实原因：

1. **ego 窗口被最小化** → `innerWidth/innerHeight = 0`
   → 布局瘫痪、React 渲染停摆、坐标全变负数 → 所有写入被回滚。
   判定方法：`page.evaluate(() => innerWidth)`，0 就是它。
2. **ego 进程退出后窗口标题会变**（如「首页 - ego」），
   win.ps1 原先按 `*temu*` 匹配 → 恢复不了 → 看起来像「平台锁」。
   已改为匹配 `*ego*`，且 `ensureWindowVisible()` 已内置到 querySkc。
3. 另有三个真 bug（均已修，见 §四）：
   `rowBbox` 缺 `return box`（取消勾选 100% 失败）；
   `page.evaluate` 模板字符串里正则转义须双写 `\d`；
   填值改用 data 标记 + `page.fill`。

### 历史时间线（保留以防复发）


- 18:38 前正常；19:00 后写入全失效；20:08 复测仍失效；**23:00 恢复窗口可见后一切正常**。
- 判定：短时间几十次 发起调价弹窗+提交 触发平台风控冷却（Edge 时代 3-6 分钟/SKC
  的节奏可能正是为避这个）。**恢复方法未知，预计数小时~次日**。
- 引擎已内置防线（勿删）：
  - 连续 3 行填不上 → `locked` 状态整单跳过（不误标 done）
  - 有失败动作 → `suspect` 状态（不计 done）
  - `done` 只记 ok / nothing-to-do（0 失败动作）

## 三、明日恢复步骤

```
# 1) 窗口+环境（ego 不在 PATH）
export PATH="$HOME/.local/share/ego/active_version_dir:$PATH"
# 2) 试探锁是否解除（跑 1 个）：
#    C:/Users/34191/ego/store-c-20261024-1015/batch.json = {"from":0,"count":3,"cat":"派对餐巾"}
ego-browser nodejs -e "await import('file:///C:/Users/34191/ego/store-c-20261024-1015/run-batch.mjs')"
# 3) 解锁后开夜班（分离进程，120轮×≤25min，餐巾420个，3分钟节流）：
powershell Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','C:\Users\34191\ego\store-c-20261024-1015\night-grind.ps1' -WindowStyle Minimized
#    监控：research/store-data/adjust-run-store-c-2026-10-24.log + adjust-done-store-c-2026-10-24.txt
# 4) 收尾导出复核：goods/list 下载查询结果（round-60 的流程）→ 调价列已生效核对
```

- batch.json 参数：`from/count`（对 420 行 CSV）、`cat` 过滤、`spacingSec` 节流、`maxMin` 单轮上限。
- done 断点续跑；**误标 done 先清洗**（只留确认过的）再重跑。
- 钢印剩余 59 SKC 下架：每天额度 ~2 笔，流程见 §五；机器人回复不可信，须导出核对
  「已下架/已终止」状态。

## 四、ego 引擎要点（grind_lib.mjs，已全配齐）

- **每 SKC 全新页面**（recreatePage）：旧弹窗会毒化页面查询。
- **只信 vis=true 的行**：虚拟列表渲染窗外的行是死节点，写了会被抹。
- **fillRow 用 ego page.fill（真实键盘级输入）**：native-setter 合成事件会被 React 受控组件回滚。
- **验证 = val + 绿「降价」标签**（React 真值）；勾选 = page.click 可见 CBX_square（nth 索引）。
- **查询验证**：`全部 N 未发布` 计数==1 且卡片含 SKC 文本，否则重试/重建页面
  （查询被吞时会残留上一个商品的卡片——点开就是别家弹窗，SKC 守卫会拦）。
- **弹窗清扫 closePopups**：MDL 公告弹窗点 X；new-bell 消息面板点 header 最右图标
  （**Esc 无效**）；调价弹窗本体（含 确认调价）绝不动。
- **窗口最小化 = 全部交互假失败**（布局瘫痪+渲染暂停）：win.ps1 每 SKC 自动检查恢复；
  ego 进程退出后窗口常被最小化，凌晨批跑前务必确认。
- 弹窗表格是**虚拟长表**（首屏 17 行，实际可 32+ 行）：pass 循环滚动扫描+稳定行键
  （qty|cur|同名序号）+ 连续两轮干净才算完；提交前全表 sweep 补填。
- 提交失败报错文本会抓到日志（「请填写调整后申报价格」= 有勾选行空值 → sweep 补填）。

## 五、钢印下架 ego 流程（已验证，2笔/日）

客服图标(顶部导航) → 联系官方客服 → 自助工具 → 商品下架 → 发商品 →
表单：商品ID 类型默认 SKC ID，输入 `input[placeholder="请输入完整SKC ID"]`（native-setter 即可）→
下架原因下拉（点 select 框，选项「亏损下架」在 (921,348)，红字残留提示不影响）→
申请下架 → 确认弹窗（按钮文本「确认(3s)」倒计时后变「确认」，蓝色 button.text=确认）→
机器人回复「该商品已下架」。round-80~95 可复用。

## 六、store-c 数据现状（2026-10-24 早导出）

- 全店 3174 SKC：在售 684（早）/676（晚），未发布 2264，已下架 226→234
- 调价工单 420 SKC（餐巾+腕带，倍数降序）：`adjust-todo-store-c-2026-10-24.csv`
  - 完成 2；腕带 top 段疑被「长期提效」自动调价接管（Temu 弹窗称已选 69 条）
  - 剩余 ~59 钢印 SKC 待下架（额度 2/日）
- 其他类目（旗帜/压花机半数达标/名片等）成本模型未确认，未入工单
