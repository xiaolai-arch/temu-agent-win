# pricing/ — 调价

## 定价模型（grind_one / make_adjust_todo 一致）

保本价=(成本×数量+9)/0.8，建议价=(成本×数量+9)/0.5（COST 表在 make_adjust_todo.py，
压花机/钢印 25 元/个）；工单只收 在售中+已生效+数量可解析 且 倍数=现价/建议价>1.05 的 SKC。

## 工具链

```bash
python pricing/make_adjust_todo.py <store>     # 从最新商品导出(../export/data)生成调价工单 CSV
python pricing/grind_batch.py <工单.csv> [--limit N]   # 批量调度：逐 SKC 子进程跑 grind_one，断点续跑
python pricing/grind_one.py <SKC> <关键词>     # 单 SKC 调价（OCR/像素版，Edge 时代主力）
```

- **ego DOM 版引擎**（现行更稳）：`ego/grind_lib.mjs`，由 ego 会话 runner 调用
  （上个批次：`C:/Users/34191/ego/store-c-20261024-1015/run-batch.mjs`，路径已同步本模块）。
  交互知识见 `../discoveries/2026-10-24-ego浏览器操控temu.md`。
- `grind_one.py` 复用 `../store` 的 `_clear_input` 和 `../export` 的 `blue_button`。

## data/ 当前状态（2026-10-26）

| 文件 | 状态 |
|---|---|
| `adjust-todo-store-c-2026-10-24.csv` | ✅ 已完成：420/420 SKC 全部 done（`adjust-done-store-c-2026-10-24.txt` 恰 420 行，10-25 15:58 夜批跑完） |
| `adjust-todo-store-b-2026-10-24.csv` | ⏸ 未跑：533 SKC，10-23 冻结待续（旧 HANDOFF 见 `../docs/HANDOFF-调价下架任务交接.md`） |
| `suggested-prices.csv` | 10,793 SKU 全量建议价表（定价参考，仍在用） |
| `adjust-done-2026-10-24.txt` | store-b 10-24 凌晨 3 笔 done 记录 |

任务交接细节（夜批恢复、平台锁价翻案、弹窗坑）见 `../docs/HANDOFF-store-c-ego调价下架-2026-10-24.md`。
