# delist/ — 下架

## 两条通道

1. **佳同插件批量下架（首选，待首次实操）**：表格上传、不限次数。
   流程笔记 `../discoveries/2026-10-25-佳同插件批量下架.md`；上传表 = `data/delist-stamp-batch-store-c-2026-10-25.xlsx`（59 SKC 钢印亏损）。
2. **csx_delist.py（客服自助工具，兜底）**：限每日 2 笔，每 ID 间隔 50s：
   ```bash
   python delist/csx_delist.py SKU|SKC <id> [<id> ...]   # 前提：浏览器已登录目标店铺
   ```
   日志追加 `data/delist-log.txt`。

## data/ 工单

| 文件 | 状态 |
|---|---|
| `delist-stamp-batch-store-c-2026-10-25.xlsx` | store-c 59 SKC 钢印批量下架表，**待实操验证** |
| `delist-todo-store-c-stamp.json` | store-c 钢印亏损清单（上表的源头分析） |
| `delist-todo-store-b.json` | store-b 52 链接下架工单（10-23 冻结未执行） |

## ⚠ 待人工核实

2026-10-25 佳同批量下架后导出（`../export/data/store-c-goods-2026-10-25-after-delist.xlsx`）与
下架前导出 md5 完全相同——**批量下架可能未生效**，需在 TEMU 后台人工核实钢印商品状态。
