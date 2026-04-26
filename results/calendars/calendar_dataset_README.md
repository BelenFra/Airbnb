# Calendar 数据使用说明（团队对接）

> 维护人：Yu Wang（calendar 负责人）
> 最后更新：2026-04-26
> 关联文档：`results/calendars/calendar_cleaning_decisions.md`（清洗规则）

## 1. 你应该用哪份文件？

| 你的需求 | 用这个 | 行数 / 大小 |
| --- | --- | --- |
| 直接用 listing 级占用率与年化收入做投资比较 / 建模 | `data/processed/calendars/all_cities_listing_occupancy.csv` | 132,677 行 / 16 MB |
| 单个城市的占用率分析 | `data/processed/calendars/<city>_listing_occupancy.csv` | 见下表 |
| 全城日历级时间序列（季节性 / 周期性） | `data/processed/calendars/all_cities_calendar_cleaned.csv` | ~48.4M 行 / 2.3 GB |
| 单城市日历级 | `data/processed/calendars/<city>_calendar_cleaned.csv` | 见下表 |
| 清洗审计 / 决策追踪 | `results/calendars/calendars_cleaning_audit.csv` | 5 行 |

> **建议**：除非你做季节性分析，**优先用 `all_cities_listing_occupancy.csv`**。它已经把 365 天日历压缩到每 listing 一行，并 join 了 `listings.csv` 的价格。

## 2. 5 城市概览（清洗后）

| 城市 | listings | 有价格 (%) | 占用率代理 (mean) | listing_price (median) | 年化收入代理 (median) |
| --- | ---: | ---: | ---: | ---: | ---: |
| hawaii | 33,457 | 97.6% | 37.0% | $230 | $26,100 |
| los_angeles | 45,886 | 80.1% | 41.7% | $155 | $10,278 |
| nashville | 9,443 | 70.2% | 31.5% | $158 | $10,803 |
| new_york | 36,111 | 58.5% | 55.6% | $152 | $11,960 |
| san_francisco | 7,780 | 74.3% | 48.0% | $170 | $18,196 |
| **合计** | **132,677** | **77.6%** | — | — | — |

> 业务直觉提示（不是结论，是讨论起点）：
> - Hawaii 价格最高（平均 $434，中位 $230），占用率反而不算高（37%），但年化收入显著最高 → 高价低周转。
> - NYC 占用率最高（55.6%）但价格中等（$152），且 41% 的 listings 没有价格（监管/合规屏蔽）→ 数据完整性需注意。
> - SF 价格、占用率均偏高，listings 数量却最少（7,780）→ 供给紧、单位收益尚可。
> - LA 供给最大（45,886）但价格与中位收入都不突出 → 竞争最激烈。

## 3. 字段定义（`*_listing_occupancy.csv`）

| 字段 | 含义 | 备注 |
| --- | --- | --- |
| `listing_id` | Inside Airbnb listing 主键 | int64，用它和 listings/reviews join |
| `city` | 城市 | snake_case：hawaii / los_angeles / nashville / new_york / san_francisco |
| `n_days` | 该 listing 在 calendar 中的总天数 | 通常 = 365 |
| `first_date` / `last_date` | 日历窗口起止 | YYYY-MM-DD 字符串 |
| `n_days_available` / `n_days_unavailable` | 可订 / 不可订天数 | `available == True / False` 计数 |
| `availability_rate` | 可订率 | `n_days_available / n_days` |
| `unavailability_rate` | 不可订率 | `n_days_unavailable / n_days` |
| `occupancy_rate_proxy` | **占用率代理** | 等于 `unavailability_rate`，**不是真实占用率**，详见第 5 节警告 |
| `listing_price` | 来自 `listings.csv` 的挂牌价（USD/晚） | 已去 $/逗号；可能为 NaN（尤其 NYC） |
| `min_minimum_nights` | 全年最小最少夜数 | 已 clip 到 [1, 1125] |
| `max_maximum_nights` | 全年最大最多夜数 | 已 clip 到 [1, 1125] |
| `est_annual_revenue_proxy` | **年化收入代理** | `listing_price × occupancy_rate_proxy × 365`；`listing_price` 缺失则为 NaN |

## 4. 字段定义（`*_calendar_cleaned.csv`，行级）

`listing_id, city, date, available, price, adjusted_price, minimum_nights, maximum_nights`

- `date`：YYYY-MM-DD
- `available`：bool（True=可订，False=不可订）
- `price` / `adjusted_price`：**几乎全为 NaN**（Inside Airbnb 近期版本已从 calendar 移走价格列，如有需要请用 `listing_price` 或 `listings.csv`）
- `minimum_nights` / `maximum_nights`：`Int64`，已 clip 到 [1, 1125]

## 5. 重要警告（一定要看）

1. **`occupancy_rate_proxy` 不等于真实预订率。**
   Inside Airbnb 中 `available=False` 同时包含「已被预订」与「房东主动屏蔽」两种情况，无法区分。该指标**系统性高估**真实预订。
   - 如要更接近真实预订，建议接入 reviews 数据，按 San Francisco 模型估算（review_rate=50%, avg_nights=3）。这块由 reviews 团队（Agostino）+ 我后续合作。
   - 在 memo / 图表里**始终使用 “proxy / 代理” 字样**，不要直接称 “occupancy”。

2. **`listing_price` 不是实际成交价**，是房东挂牌价；旺季 / 淡季差异不会反映在它里。

3. **NYC 有 41% 的 listings 没有价格**（短租监管所致）。如果你的分析对 NYC 价格敏感（比如做城市比较），要么单独剔除这些 listing，要么用 listings 表里的 `room_type × neighborhood` 价格中位数做填充——这个填充由 listings 团队（Belu）主导更合适。

4. **calendar.csv 里的 `price` 列是空的**——别再去算它的均值（已踩过坑）。

5. **`n_days` 不一定 = 365**。新挂牌 / 下线 listing 可能短一些；分母用 `n_days`，**不要硬编码 365**。

## 6. 怎么 join

```python
import pandas as pd

occ = pd.read_csv('data/processed/calendars/all_cities_listing_occupancy.csv')
listings = pd.read_csv('data/processed/listings/all_cities_listings_cleaned.csv')  # Belu 产出
df = listings.merge(occ, on=['listing_id', 'city'], how='left')
```

> 关键约定：
> - `listing_id` 全部团队保持 `int64`，名称统一为 `listing_id`（listings 表的 `id` 应被 rename）。
> - `city` 全部使用 snake_case 五个值之一。
> - left join：以 listings 为基础，没有 calendar 数据的 listing 保留为 NaN。

## 7. 已知风险与下一步

- [ ] 与 Belu 联调：listings 清洗后 `listing_id` 命中率应 ≥ 95%（calendar 端 132,677 → 看能有多少和 listings join 上）。
- [ ] 与 Agostino 联调：reviews 端的 city 列保持一致；后续考虑用 review_rate 估占用。
- [ ] 价格缺失填充策略：建议 listings 团队按 `room_type × neighborhood` 中位数做。
- [ ] 重新运行：脚本是幂等的，删除 `data/processed/calendars/` 后重跑 `python scripts/cleaning/calendars/run_full_calendar_cleaning.py` 即可（约 22 分钟）。

## 8. 复现命令

```bash
python scripts/cleaning/calendars/run_full_calendar_cleaning.py
# 仅跑指定城市:
python scripts/cleaning/calendars/run_full_calendar_cleaning.py --cities nashville san_francisco
# 跳过 2.3GB 的合并行级文件（推荐建模时用，省磁盘）:
python scripts/cleaning/calendars/run_full_calendar_cleaning.py --no-merged-rows
```

输入：`data/Term Project/<City>/{calendar.csv, listings.csv}`
输出：`data/processed/calendars/`、`results/calendars/calendars_cleaning_audit.csv`
