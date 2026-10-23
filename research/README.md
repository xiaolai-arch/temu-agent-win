# research/ — 调研与运营数据

| 模块 | 内容 |
|---|---|
| `reports/` | 结论性报告（按日期命名）+ `HANDOFF-调价下架任务交接.md`（**当前进行中任务的交接文档，接手先读它**） |
| `store-data/` | 店铺运营数据：商品导出 xlsx、调价工单 CSV、建议价表（suggested-prices.csv）、下架清单、done 断点记录。HANDOFF 引用的主数据都在这 |
| `scan/` | 速卖通选品扫描工具链：`probe*.py` = requests 直拉探测（反爬验证），`scan_keywords.py`/`scan_stars.py` = 浏览器只读扫描（输出 json 同目录）；依赖 `../driver` 核心层 |
| `linkfox/` | LinkFox 技能盘点（技能全量清单 json + 盘点报告）与试跑沙盒（init_test / sandbox） |
| `analyze_stores.py` | 汇总分析 store-data 各店导出 xlsx → `store-data/summary.json`（纯 openpyxl，跨平台可直接跑） |

选品结论示例：`reports/2026-10-22-选品报告.md`（基于 scan/ 数据）；店群接管全案：`reports/2026-10-22-店群AI接管工作流设计.md`。
