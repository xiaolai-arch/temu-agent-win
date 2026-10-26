# export/ — 商品导出 · 盘点

## 工具链

```bash
python export/export_goods.py <store-id>     # 当前店 goods/list 页只读导出 → data/<store>-goods-<date>.xlsx
                                              # （前置：store/switch_store.py 已切到目标店）
python export/analyze_stores.py              # 四店最新快照 → 结构化统计 data/summary.json（各店自动取最新）
```

- export_goods 轮询 `D:\Download` 拿导出文件后拷贝归档；tab 计数/待办 chips 一并 OCR 记录。
- analyze_stores 2026-10-26 起不再硬编码快照日期，自动取各店最新 `*-goods-YYYY-MM-DD.xlsx`。

## data/ 快照（2026-10-26 清理后各店只留最新）

| 文件 | 说明 |
|---|---|
| `main-goods-2026-10-22.xlsx` / `store-d-goods-2026-10-22.xlsx` | 唯一快照 |
| `store-b-goods-2026-10-24.xlsx` | store-b 最新（旧快照已删） |
| `store-c-goods-2026-10-25-after-delist.xlsx` | store-c 最新；⚠ 与下架前导出 md5 相同（见 delist/README 疑点） |
| `work-orders.json` | 四店工单总表（main/store-d 的下架工单只有这里有） |
| `summary.json` | analyze_stores 输出（可重生成） |

四店全量盘点结论（19,410 SKC、在售 14.9% 等）见 `../docs/2026-10-22-四店铺上架链接盘点.md`。
调价/下架工单的生成入口在 `../pricing`、`../delist`。
