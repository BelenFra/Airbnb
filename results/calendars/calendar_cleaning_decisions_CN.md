# Calendar 数据清洗决策（Yu Wang）

> 适用对象：MBA706 Term Project 的 5 城市 `calendar.csv`（Hawaii / Los Angeles / Nashville / New York / San Francisco）。
> 维护人：Yu Wang。最后更新：2026-04-26。

## 1. 命名与对接口径（与 Belu / Agostino 共享）

| 维度 | 约定 |
| --- | --- |
| `city` 列取值 | `hawaii`、`los_angeles`、`nashville`、`new_york`、`san_francisco`（全小写、下划线） |
| `listing_id` | 保持 Inside Airbnb 原始 `int64`，全程不重命名 |
| 日期格式 | `YYYY-MM-DD` 字符串 |
| 缺失值 | 一律使用 `NaN`，不使用空串、`"NA"`、`"None"` |
| 文件编码 | UTF-8（读入时容忍 BOM：`utf-8-sig`） |

**目的：** listings / reviews / calendar 三方产物可以无歧义按 `(listing_id, city)` join。

## 2. 输入与产出路径

- 输入：`data/Term Project/<City Name>/calendar.csv`（5 个，原始文件）
- 中间产物：`data/processed/calendars/`
  - `<city>_calendar_cleaned.csv` × 5：行级清洗后的日历表（含 `city` 列）
  - `<city>_listing_occupancy.csv` × 5：listing 级聚合（占用率 + 价格）
  - `all_cities_calendar_cleaned.csv`：5 城市拼接（同表头）
  - `all_cities_listing_occupancy.csv`：5 城市 listing 级合并表（**核心交付物**）
- 审计 / 文档：`results/calendars/`
  - `calendars_cleaning_audit.csv`：每城市清洗审计（清洗前后行数、被剔除原因等）
  - `calendar_cleaning_decisions.md`：本文件
  - `calendar_dataset_README.md`：给团队的一页说明

## 3. 行级清洗规则（在分块流式处理中执行）

按以下顺序在每个 `chunksize=200_000` 的块内执行：

1. **列保留**：仅保留 `listing_id, date, available, price, adjusted_price, minimum_nights, maximum_nights`。
2. **去重**：按七列哈希全局去重，保留首次出现行。
3. **必填字段**：`listing_id`、`date`、`available` 任一为空 → 剔除。
4. **日期解析**：`pd.to_datetime(errors="coerce")`，解析失败 → 剔除；最终输出标准化为 `YYYY-MM-DD`。
5. **`available` 标准化**：`t/true/1 → True`，`f/false/0 → False`，其他值 → 剔除。
6. **价格清洗**：`price` 与 `adjusted_price` 去除非数字字符（`$`、`,`、空格）后转 `float`。允许 `NaN`（在不可订日期上 `NaN` 是 Inside Airbnb 的常态）。
7. **整数列**：`minimum_nights`、`maximum_nights` 转 `Int64`。
8. **离群值处理（不删行，仅 clip + 计数）**：
   - `price > 10000` → 置 `NaN`，并记录数量（极少见，多为录入异常）。
   - `minimum_nights` 限制在 `[1, 1125]`；`maximum_nights` 限制在 `[1, 1125]`（Airbnb 平台上限）。
   - 价格分位裁剪不在行级做，避免“看起来便宜=被剪”；若后续建模需要分位裁剪，由各分析脚本按需做。
9. **添加 `city` 列**：来自父目录映射。

输出列序：`listing_id, city, date, available, price, adjusted_price, minimum_nights, maximum_nights`。

## 4. Listing 级 Occupancy 聚合规则

在同一遍流式处理中累加，每个 `listing_id` 累计：

- `n_days`：该 listing 在该城市日历表里的行数。
- `n_days_available`：`available == True` 的天数。
- `n_days_unavailable`：`available == False` 的天数。
- `first_date` / `last_date`：日期最小 / 最大。
- `price_sum_when_available`、`price_count_when_available`：价格不为空且 `available == True` 时累加。
- `price_sum_when_unavailable`、`price_count_when_unavailable`：价格不为空且 `available == False` 时累加。
- `min_minimum_nights`、`max_maximum_nights`。

衍生指标（最后一次性算）：

- `availability_rate = n_days_available / n_days`
- `unavailability_rate = n_days_unavailable / n_days`
- `occupancy_rate_proxy = unavailability_rate`
  - **重要说明**：Inside Airbnb 中 `available=f` 不严格等于“被预订”，也可能是房东自己屏蔽（host blocked）。我们使用 `unavailability_rate` 作为占用率的**代理（proxy）**，并在 README 中明确标注；如团队希望切换到 review-based 估算（San Francisco model），由 reviews 团队提供 `reviews_per_year` 后再合成。
- `avg_price_when_available = price_sum_when_available / price_count_when_available`
- `avg_price_when_unavailable = price_sum_when_unavailable / price_count_when_unavailable`
- `est_annual_revenue_proxy = avg_price_when_available × occupancy_rate_proxy × 365`
  - 当 `avg_price_when_available` 缺失时退化为 `avg_price_when_unavailable`；二者皆缺失则 `NaN`。

## 5. 我**没有**做、需下游各自决定的事

- 价格的分位裁剪（建模时再按城市 P1/P99 处理）。
- 缺失价格的填充（不要全局填均值，建议按 `room_type × neighborhood` 填，且由 listings 团队主导）。
- 与 listings 表的 join（在合并表里只提供 `listing_id` + `city`，由 Belu 主导 join）。
- 与 reviews 的占用率融合（San Francisco model 由 Agostino + Yu 后续合作）。

## 6. 已知风险与提醒

- **数据量**：LA 622 MB、NYC 471 MB、HI 442 MB；必须用 `chunksize` 流式读，禁止一次性 `read_csv` 全量。
- **价格分布右偏**：Hawaii / SF 顶部价格远高于 Nashville；任何跨城市的价格均值/中位数比较都要按城市分组。
- **occupancy proxy 偏高**：因为它把“host blocked”也算成被订。论文与建模里要明确标注为 proxy。
- **日期窗口非完全 365 天**：新挂牌或下线 listing 可能 `n_days < 365`；分母用 `n_days` 而非硬编码 365。
- **路径要相对仓库根**：脚本一律基于 `PROJECT_ROOT` 解析，禁止硬编码 OneDrive 路径。
