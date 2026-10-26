# select/ — 选品

## 扫描脚本（只读）

```bash
python select/scan_keywords.py [起始索引]   # 速卖通搜索页逐词扫描：截图+OCR 解析 销量/价格，断点续跑
python select/scan_stars.py                 # 头部词按订单排序提爆款卡
```

输出 `data/scan_results.json`、`data/stars.json`；依赖 `../core`（winutil/uia_shell/shot）。

## 报告与数据

- `2026-10-22-选品报告.md` — 26 个候选词实测（销量/价格/定制契合度）→ 定出 18 词新词池，
  结论已写入 `collect/collect_run.py` 的 KEYWORDS。
- 流程：本模块扫描出词池 → `collect/` 采集素材 → 妙手做链接 → 同步上架（见 `docs/2026-10-22-店群AI接管工作流设计.md`）。
