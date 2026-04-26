"""Generate the Yu Wang (calendar lead) task brief as a PDF.

Output: reports/MBA706_TermProject_wangyu_calendar_tasks.pdf
"""

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "reports" / "MBA706_TermProject_wangyu_calendar_tasks.pdf"


def build_styles() -> dict[str, ParagraphStyle]:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    base_font = "STSong-Light"
    mono_font = "Courier"

    sample = getSampleStyleSheet()
    base = ParagraphStyle(
        "base",
        parent=sample["BodyText"],
        fontName=base_font,
        fontSize=10.5,
        leading=16,
        alignment=TA_LEFT,
        textColor=HexColor("#111827"),
    )
    title = ParagraphStyle(
        "title",
        parent=base,
        fontSize=20,
        leading=26,
        spaceAfter=4,
        textColor=HexColor("#0f172a"),
    )
    subtitle = ParagraphStyle(
        "subtitle",
        parent=base,
        fontSize=11,
        leading=16,
        spaceAfter=12,
        textColor=HexColor("#475569"),
    )
    h1 = ParagraphStyle(
        "h1",
        parent=base,
        fontSize=15,
        leading=22,
        spaceBefore=14,
        spaceAfter=6,
        textColor=HexColor("#0f172a"),
    )
    h2 = ParagraphStyle(
        "h2",
        parent=base,
        fontSize=12.5,
        leading=18,
        spaceBefore=10,
        spaceAfter=4,
        textColor=HexColor("#1f2937"),
    )
    body = ParagraphStyle("body", parent=base)
    quote = ParagraphStyle(
        "quote",
        parent=base,
        leftIndent=14,
        textColor=HexColor("#374151"),
        backColor=HexColor("#f1f5f9"),
        borderPadding=8,
        spaceBefore=4,
        spaceAfter=8,
    )
    code = ParagraphStyle(
        "code",
        parent=base,
        fontName=mono_font,
        fontSize=9,
        leading=12,
        textColor=HexColor("#111827"),
        backColor=HexColor("#f8fafc"),
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=8,
    )
    return {
        "base": base,
        "title": title,
        "subtitle": subtitle,
        "h1": h1,
        "h2": h2,
        "body": body,
        "quote": quote,
        "code": code,
    }


def bullet(items: list[str], style: ParagraphStyle) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(t, style), leftIndent=10) for t in items],
        bulletType="bullet",
        bulletFontName="STSong-Light",
        bulletFontSize=9,
        leftIndent=14,
        spaceBefore=2,
        spaceAfter=6,
    )


def numbered(items: list[str], style: ParagraphStyle) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(t, style), leftIndent=10) for t in items],
        bulletType="1",
        bulletFontName="STSong-Light",
        bulletFontSize=9,
        leftIndent=18,
        spaceBefore=2,
        spaceAfter=6,
    )


def build_story(styles: dict[str, ParagraphStyle]) -> list:
    s = styles
    story: list = []

    story.append(Paragraph("MBA706 Term Project — Yu Wang 任务清单", s["title"]))
    story.append(
        Paragraph(
            "角色：Calendar 数据负责人（5 城市清洗 + 占用率计算 + 合并）",
            s["subtitle"],
        )
    )

    story.append(Paragraph("一、任务一句话总结", s["h1"]))
    story.append(
        Paragraph(
            "负责把 5 个城市的 calendar.csv 清洗成统一格式，按城市落地一份 cleaned 文件，"
            "再合并出一份多城市表，并基于它<b>计算 occupancy</b>，供 listings/reviews 团队"
            "和最终模型/推荐使用。",
            s["body"],
        )
    )

    story.append(Paragraph("二、为什么你这块特别关键", s["h1"]))
    story.append(
        Paragraph(
            "课程文档（MBA706_Term_Project.docx, Section 4 Data Cleaning）原文：",
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "“Clean and merge all three files (listings, reviews, calendar) across all five "
            "cities. Parse prices, handle missing values, remove outliers, "
            "<b>compute occupancy from calendar data</b>. Document your decisions.”",
            s["quote"],
        )
    )
    story.append(
        Paragraph(
            "项目核心 Revenue Equation：<b>Annual Revenue = Price × Occupancy × 365</b>。"
            "Occupancy 这一项<b>只能从 calendar 数据里算出来</b>——也就是你这份产出。"
            "如果这块不到位，后面的投资推荐就立不住。",
            s["body"],
        )
    )

    story.append(Paragraph("三、当前数据状况（已替你核过）", s["h1"]))
    story.append(
        Paragraph("每个城市的 calendar.csv 列结构相同：", s["body"])
    )
    story.append(
        Preformatted(
            "listing_id, date, available, price, adjusted_price, "
            "minimum_nights, maximum_nights",
            s["code"],
        )
    )
    story.append(Paragraph("文件大小：", s["body"]))
    story.append(
        bullet(
            [
                "Hawaii/calendar.csv ≈ 442 MB",
                "Los Angeles/calendar.csv ≈ 622 MB",
                "Nashville/calendar.csv ≈ 128 MB",
                "New York/calendar.csv ≈ 471 MB",
                "San Francisco/calendar.csv ≈ 102 MB",
            ],
            s["body"],
        )
    )
    story.append(Paragraph("注意点：", s["body"]))
    story.append(
        bullet(
            [
                "available 是 t/f 字符串，需要转布尔。",
                "price / adjusted_price 在样本中常见 NaN，多对应不可订日期。",
                "文件大，必须用 chunksize 分块处理（LA 622MB 一次性读会爆内存）。",
                "已有模板 scripts/cleaning/calendars/run_full_calendar_cleaning.py 不能直接跑，"
                "因为它读 data/raw/calendars/calendar_&lt;city&gt;.csv，"
                "你的实际数据在 data/Term Project/&lt;City&gt;/calendar.csv，"
                "需要修路径或建立目录映射。",
            ],
            s["body"],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("四、你的详细任务清单（建议顺序）", s["h1"]))

    story.append(Paragraph("步骤 1：与队友对齐口径（半小时）", s["h2"]))
    story.append(
        bullet(
            [
                "city 列命名规范（建议小写下划线："
                "new_york / los_angeles / san_francisco / nashville / hawaii）。",
                "listing_id 在三种文件中都保持原始 int64，不被改写。",
                "统一日期格式：YYYY-MM-DD。",
                "缺失值统一用 NaN，不用空串或 \"NA\"。",
            ],
            s["body"],
        )
    )

    story.append(Paragraph("步骤 2：决定 calendar 清洗规则（写下来）", s["h2"]))
    story.append(
        bullet(
            [
                "去重：同一 (listing_id, date) 只保留一条。",
                "必填字段：listing_id、date、available 不能空。",
                "available：t→True / f→False，其他值视为非法剔除。",
                "price、adjusted_price：去 $、,，转 float；available=False 的缺失允许保留为 NaN。",
                "minimum_nights、maximum_nights：转 Int64；对极端值（如 &gt;1125）做 winsorize 或标记。",
                "价格离群值：用 IQR 或<b>分城市的 99 分位</b>裁剪（推荐分城市，"
                "因为 Hawaii/SF 与 Nashville 价位差很大）。",
                "日期合理性：只保留“今天起 365 天内”的日期。",
            ],
            s["body"],
        )
    )
    story.append(
        Paragraph(
            "把上述决策写到 results/calendars/calendar_cleaning_decisions.md，"
            "对应课程要求的 “documented decisions”。",
            s["body"],
        )
    )

    story.append(Paragraph("步骤 3：把现有清洗脚本跑通", s["h2"]))
    story.append(
        Paragraph(
            "复用并修正 scripts/cleaning/calendars/run_full_calendar_cleaning.py：",
            s["body"],
        )
    )
    story.append(
        bullet(
            [
                "改 RAW_DIR 与匹配模式，使其指向 data/Term Project/*/calendar.csv，"
                "并从父目录名提取 city；或在 data/raw/calendars/ 下做 5 份软链/拷贝，"
                "命名 calendar_&lt;city&gt;.csv。",
                "输出每城市一份：data/processed/calendars/&lt;city&gt;_calendar_cleaned.csv。",
                "输出审计：results/calendars/calendars_cleaning_audit.csv（脚本已自带）。",
            ],
            s["body"],
        )
    )

    story.append(Paragraph("步骤 4：补脚本里目前还没做的两块", s["h2"]))
    story.append(
        numbered(
            [
                "<b>离群值处理</b>：当前脚本没有 outlier 剔除。给 price、minimum_nights "
                "做分位裁剪，并在 audit 中记录被裁剪行数。",
                "<b>occupancy 计算</b>：在 cleaned 的 per-listing-per-day 之上，"
                "再聚合一份 listing 级占用率表。",
            ],
            s["body"],
        )
    )
    story.append(Paragraph("occupancy 表建议字段：", s["body"]))
    story.append(
        Preformatted(
            "listing_id, city, n_days, n_booked_days,\n"
            "occupancy_30d, occupancy_60d, occupancy_90d, occupancy_365d,\n"
            "avg_price_when_available, median_price_when_available,\n"
            "est_annual_revenue_365 = avg_price_when_available "
            "* occupancy_365d * 365",
            s["code"],
        )
    )
    story.append(
        Paragraph(
            "建议：n_booked_days = sum(available == False)（Inside Airbnb 惯例：f 视作不可订）。"
            "把口径写进 decisions 文档，避免下游算错。",
            s["body"],
        )
    )

    story.append(Paragraph("步骤 5：合并 5 城市", s["h2"]))
    story.append(
        bullet(
            [
                "data/processed/calendars/all_cities_calendar_cleaned.csv（很大，建议同时存 .parquet）。",
                "data/processed/calendars/all_cities_listing_occupancy.csv "
                "（这是交付给 Belu 和后面建模/推荐部分的核心成果）。",
            ],
            s["body"],
        )
    )

    story.append(Paragraph("步骤 6：给团队的一页“数据说明”", s["h2"]))
    story.append(
        Paragraph(
            "放在 results/calendars/calendar_dataset_README.md，写清楚：",
            s["body"],
        )
    )
    story.append(
        bullet(
            [
                "输入文件清单与每城市最早/最晚日期。",
                "你做的清洗规则。",
                "occupancy 的具体定义（避免下游算错收入）。",
                "已知风险（LA 文件大、Hawaii 价格右偏等）。",
            ],
            s["body"],
        )
    )

    story.append(Paragraph("步骤 7：与 listings/reviews 团队联调", s["h2"]))
    story.append(
        bullet(
            [
                "跟 Belu 确认 listings 清洗后 listing_id 仍是同类型；"
                "做一次 join 测试，listing 命中率应 ≥ 95%，否则排查。",
                "跟 Agostino 对齐 reviews 中 city 列命名一致。",
            ],
            s["body"],
        )
    )

    story.append(PageBreak())
    story.append(Paragraph("五、交付物清单", s["h1"]))
    story.append(Paragraph("代码：", s["h2"]))
    story.append(
        bullet(
            [
                "scripts/cleaning/calendars/run_full_calendar_cleaning.py "
                "（修过、能跑通、含 occupancy）",
            ],
            s["body"],
        )
    )
    story.append(Paragraph("中间数据：", s["h2"]))
    story.append(
        bullet(
            [
                "data/processed/calendars/&lt;city&gt;_calendar_cleaned.csv（5 份）",
                "data/processed/calendars/&lt;city&gt;_listing_occupancy.csv（5 份）",
                "data/processed/calendars/all_cities_calendar_cleaned.csv（或 .parquet）",
                "data/processed/calendars/all_cities_listing_occupancy.csv",
            ],
            s["body"],
        )
    )
    story.append(Paragraph("审计与文档：", s["h2"]))
    story.append(
        bullet(
            [
                "results/calendars/calendars_cleaning_audit.csv",
                "results/calendars/calendar_cleaning_decisions.md",
                "results/calendars/calendar_dataset_README.md",
            ],
            s["body"],
        )
    )

    story.append(Paragraph("六、避免踩坑（提醒）", s["h1"]))
    story.append(
        bullet(
            [
                "不要 read_csv 一次性读 LA 那个 622MB 文件，沿用 chunksize=200_000。",
                "price 缺失不等于价格为 0：available=False 时缺失正常；"
                "available=True 时还缺失才需要警告。",
                "occupancy 只在“看得到的窗口”里算，不要默认乘 365；"
                "在 README 中说明窗口长度。",
                "团队约定 RANDOM_STATE=42，不要乱设其他随机种子。",
                "路径写相对 PROJECT_ROOT，不要写 OneDrive 绝对路径。",
            ],
            s["body"],
        )
    )

    return story


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    styles = build_styles()

    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm,
        title="MBA706 Term Project - Yu Wang Calendar Tasks",
        author="MBA706 Group",
    )
    story = build_story(styles)
    doc.build(story)
    print(f"PDF written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
