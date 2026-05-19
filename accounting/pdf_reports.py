"""Server-side PDF builders for accounting reports.

This module intentionally keeps the PDF layout independent from the React UI.
The monthly expense report uses the same aggregated API payload but renders a
print-friendly document with stable charts, summary cards, and ranked tables.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, Iterable, Optional

from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PAGE_WIDTH, PAGE_HEIGHT = A4

NAVY = colors.HexColor("#0f172a")
SLATE = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748b")
TEAL = colors.HexColor("#14b8a6")
BLUE = colors.HexColor("#2563eb")
ORANGE = colors.HexColor("#f97316")
RED = colors.HexColor("#ef4444")
GREEN = colors.HexColor("#16a34a")
GRAY = colors.HexColor("#94a3b8")
SOFT_BG = colors.HexColor("#f8fafc")
SOFT_BORDER = colors.HexColor("#e2e8f0")


CHART_PALETTE = [BLUE, TEAL, ORANGE, RED, GREEN, GRAY, colors.HexColor("#8b5cf6"), colors.HexColor("#f59e0b")]


def _money(value: Any) -> str:
    numeric = float(value or 0)
    sign = "-" if numeric < 0 else ""
    return f"{sign}${abs(numeric):,.0f}"


def _signed_money(value: Any) -> str:
    numeric = float(value or 0)
    sign = "+" if numeric > 0 else "-" if numeric < 0 else ""
    return f"{sign}${abs(numeric):,.0f}"


def _percent(value: Any) -> str:
    numeric = float(value or 0)
    sign = "+" if numeric > 0 else "-" if numeric < 0 else ""
    return f"{sign}{abs(numeric):.1f}%"


def _paragraph_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=NAVY,
        alignment=TA_LEFT,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=12,
        textColor=MUTED,
        alignment=TA_LEFT,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=NAVY,
        spaceBefore=12,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="SectionNote",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=MUTED,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="CardLabel",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=MUTED,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="CardValue",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=NAVY,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="TableText",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.25,
        leading=10,
        textColor=SLATE,
    ))
    styles.add(ParagraphStyle(
        name="TableTextSmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=SLATE,
    ))
    return styles


def _metric_card(label: str, value: str, avg_value: str, accent: colors.Color) -> Table:
    card = Table(
        [
            [Paragraph(label, _STYLES["CardLabel"])], 
            [Paragraph(value, _STYLES["CardValue"])],
            [Paragraph(f"Avg: {avg_value}", _STYLES["TableTextSmall"])]
        ],
        colWidths=[38 * mm],
        rowHeights=[7 * mm, 11 * mm, 6 * mm],
    )
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.7, accent),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (0, 2), (-1, 2), "CENTER"),
    ]))
    return card


def _metric_cards(metrics: list[tuple[str, str, str, colors.Color]]) -> Table:
    cards = [[_metric_card(label, value, avg_value, accent) for label, value, avg_value, accent in metrics]]
    table = Table(cards, colWidths=[43 * mm, 43 * mm, 43 * mm, 43 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def _table_title(title: str, note: Optional[str] = None) -> list[Any]:
    flowables: list[Any] = [Paragraph(title, _STYLES["SectionHeading"])]
    if note:
        flowables.append(Paragraph(note, _STYLES["SectionNote"]))
    return flowables


def _chart_box(drawing: Drawing, caption: Optional[str] = None) -> list[Any]:
    items: list[Any] = [drawing]
    if caption:
        items.append(Spacer(1, 2 * mm))
        items.append(Paragraph(caption, _STYLES["SectionNote"]))
    return items


def _cash_flow_chart(summary_series: list[dict[str, Any]]) -> Drawing:
    data = summary_series
    labels = [item["month"] for item in data]
    revenue = [float(item.get("revenue", 0) or 0) for item in data]
    expenses = [float(item.get("expenses", 0) or 0) for item in data]
    savings = [float(item.get("savings", 0) or 0) for item in data]
    max_value = max([0, *revenue, *expenses, *savings])

    drawing = Drawing(520, 220)
    chart = VerticalBarChart()
    chart.x = 45
    chart.y = 28
    chart.width = 440
    chart.height = 150
    chart.data = [revenue, expenses, savings]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.angle = 30
    chart.categoryAxis.labels.dy = -8
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max_value * 1.15 if max_value else 100
    chart.valueAxis.valueStep = max(1, int((max_value * 1.15) / 5)) if max_value else 20
    chart.bars[0].fillColor = TEAL
    chart.bars[1].fillColor = ORANGE
    chart.bars[2].fillColor = BLUE
    chart.barSpacing = 1
    chart.groupSpacing = 4
    chart.barWidth = 9
    if len(data) > 24:
        chart.barWidth = 5
        chart.groupSpacing = 2
    chart.strokeColor = colors.transparent
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = SOFT_BORDER
    chart.valueAxis.gridStrokeDashArray = (1, 2)
    drawing.add(chart)
    return drawing


def _wealth_builder_chart(summary_series: list[dict[str, Any]]) -> Drawing:
    cumulative = 0
    raw_points = []
    for item in summary_series:
        cumulative += float(item.get("savings", 0) or 0)
        raw_points.append((item["month"], cumulative))

    # Convert to step points: (x1, y1), (x2, y1), (x2, y2), ...
    months = []
    values = []
    for i in range(len(raw_points)):
        p_curr = raw_points[i]
        if i > 0:
            months.append("")  # Intermediate step
            values.append(raw_points[i-1][1])
        months.append(p_curr[0])
        values.append(p_curr[1])

    max_value = max(values) if values else 100
    min_value = min(values) if values else 0

    drawing = Drawing(520, 200)
    chart = HorizontalLineChart()
    chart.x = 45
    chart.y = 28
    chart.width = 440
    chart.height = 150
    chart.data = [values]
    chart.categoryAxis.categoryNames = months
    chart.categoryAxis.labels.angle = 30
    chart.categoryAxis.labels.dy = -8
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = min_value if min_value < 0 else 0
    chart.valueAxis.valueMax = max_value * 1.15
    chart.lines[0].strokeColor = colors.HexColor("#8b5cf6")
    chart.lines[0].strokeWidth = 3
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = SOFT_BORDER
    drawing.add(chart)
    return drawing


def _stacked_category_chart(categories: list[dict[str, Any]]) -> Drawing:
    if not categories or not categories[0].get("series"):
        return Drawing(520, 200)

    months = [p["month"] for p in categories[0]["series"]]
    data = []
    category_names = []
    for cat in categories:
        category_names.append(cat["category_name"])
        data.append([float(p.get("amount", 0) or 0) for p in cat["series"]])

    # Calculate max stacked height
    max_sum = 0
    for i in range(len(months)):
        month_sum = sum(series[i] for series in data)
        if month_sum > max_sum:
            max_sum = month_sum

    # Higher drawing to accommodate legend
    drawing = Drawing(520, 300)
    chart = VerticalBarChart()
    chart.x = 45
    chart.y = 110 # Raised to leave room for legend at bottom
    chart.width = 440
    chart.height = 150
    chart.data = data
    chart.categoryAxis.categoryNames = months
    chart.categoryAxis.style = "stacked"
    chart.categoryAxis.labels.angle = 30
    chart.categoryAxis.labels.dy = -8
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max_sum * 1.15 if max_sum else 100
    
    color_series = []
    for i in range(len(data)):
        color = CHART_PALETTE[i % len(CHART_PALETTE)]
        chart.bars[i].fillColor = color
        color_series.append((color, category_names[i]))

    chart.barWidth = 10
    if len(months) > 24:
        chart.barWidth = 6

    chart.strokeColor = colors.transparent
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = SOFT_BORDER
    drawing.add(chart)

    # Add legend at the bottom
    legend = Legend()
    legend.x = 45
    legend.y = 80 # Below the chart X-axis labels
    legend.fontSize = 8
    legend.fontName = "Helvetica"
    legend.alignment = "right"
    legend.columnMaximum = 4 # 4 items per row max
    legend.colorNamePairs = color_series
    legend.deltax = 110 # Horizontal spacing between columns
    legend.deltay = 12  # Vertical spacing between rows
    legend.dxTextSpace = 5
    legend.dx = 8
    legend.dy = 8
    drawing.add(legend)
    
    return drawing


def _comparison_chart(categories: list[dict[str, Any]]) -> Drawing:
    names = [item["category_name"] for item in categories]
    current = [float(item.get("current_month_amount", 0) or 0) for item in categories]
    averages = [float(item.get("all_time_average", 0) or 0) for item in categories]
    max_value = max([0, *current, *averages])

    drawing = Drawing(520, 185)
    chart = HorizontalBarChart()
    chart.x = 95
    chart.y = 20
    chart.width = 395
    chart.height = 135
    chart.data = [current, averages]
    chart.categoryAxis.categoryNames = names
    chart.categoryAxis.labels.fontSize = 7.5
    chart.categoryAxis.labels.leftPadding = 3
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max_value * 1.15 if max_value else 100
    chart.valueAxis.valueStep = max(1, int((max_value * 1.15) / 5)) if max_value else 20
    chart.bars[0].fillColor = BLUE
    chart.bars[1].fillColor = GRAY
    chart.barSpacing = 3
    chart.groupSpacing = 7
    chart.barWidth = 7
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = SOFT_BORDER
    drawing.add(chart)
    return drawing


def _category_line_chart(category: dict[str, Any]) -> Drawing:
    series = category.get("series", [])
    if len(series) > 18:
        series = series[-18:]
    months = [item["month"] for item in series]
    values = [float(item.get("amount", 0) or 0) for item in series]
    average = [float(category.get("all_time_average", 0) or 0) for _ in series]
    max_value = max([0, *values, *average])

    drawing = Drawing(520, 220)
    chart = HorizontalLineChart()
    chart.x = 45
    chart.y = 28
    chart.width = 440
    chart.height = 150
    chart.data = [values, average]
    chart.categoryAxis.categoryNames = months
    chart.categoryAxis.labels.angle = 30
    chart.categoryAxis.labels.dy = -8
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max_value * 1.15 if max_value else 100
    chart.valueAxis.valueStep = max(1, int((max_value * 1.15) / 5)) if max_value else 20
    chart.lines[0].strokeColor = TEAL
    chart.lines[0].strokeWidth = 2.5
    chart.lines[0].symbol = None
    chart.lines[1].strokeColor = RED
    chart.lines[1].strokeWidth = 1.5
    chart.lines[1].strokeDashArray = [4, 3]
    chart.lines[1].symbol = None
    chart.valueAxis.visibleGrid = True
    chart.valueAxis.gridStrokeColor = SOFT_BORDER
    drawing.add(chart)
    return drawing


def _build_table(headers: list[str], rows: list[list[Any]], col_widths: list[float]) -> Table:
    data = [[Paragraph(header, _STYLES["TableText"] ) for header in headers]]
    data.extend(rows)
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT_BG]),
        ("GRID", (0, 0), (-1, -1), 0.4, SOFT_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _draw_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, PAGE_HEIGHT - 24 * mm, PAGE_WIDTH, 24 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(doc.leftMargin, PAGE_HEIGHT - 13.5 * mm, "Monthly Expense Report")
    canvas.setFont("Helvetica", 8.5)
    canvas.drawRightString(PAGE_WIDTH - doc.rightMargin, PAGE_HEIGHT - 13.5 * mm, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(PAGE_WIDTH - doc.rightMargin, 10 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def build_monthly_expense_report_pdf(report_data: dict[str, Any], selected_month: Optional[str] = None) -> bytes:
    global _STYLES
    _STYLES = _paragraph_styles()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=30 * mm,
        bottomMargin=16 * mm,
    )

    report_month = selected_month or report_data.get("latest_month") or "All available months"
    summary_series = list(report_data.get("summary_series", []))
    categories = list(report_data.get("categories", []))
    transactions = list(report_data.get("top_transactions", []))
    
    top_categories_for_table = categories[:5]
    top_transactions = transactions[:5]

    metrics = [
        ("Revenue", _money(report_data.get("latest_revenue", 0)), _money(report_data.get("avg_revenue", 0)), BLUE),
        ("Expenses", _money(report_data.get("latest_expenses", 0)), _money(report_data.get("avg_expenses", 0)), ORANGE),
        ("Savings", _money(report_data.get("latest_savings", 0)), _money(report_data.get("avg_savings", 0)), GREEN),
        ("Savings Rate", f"{(report_data.get('latest_savings', 0) / report_data.get('latest_revenue', 1) * 100):.1f}%" if report_data.get("latest_revenue", 0) else "0.0%", "N/A", TEAL),
    ]

    story: list[Any] = []
    
    # --- PAGE 1: MONTHLY ANALYSIS ---
    story.append(Paragraph(f"Monthly Financial Analysis: {report_month}", _STYLES["ReportTitle"]))
    story.append(Paragraph(
        "A snapshot of your household performance for the selected month, comparing key metrics and highlighting top expenditures.",
        _STYLES["ReportSubtitle"],
    ))
    story.append(_metric_cards(metrics))
    story.append(Spacer(1, 10 * mm))

    story.extend(_table_title("Top 5 Expense Categories", "Categories with the highest spend this month."))
    if top_categories_for_table:
        rows = []
        for index, category in enumerate(top_categories_for_table, start=1):
            rows.append([
                Paragraph(str(index), _STYLES["TableText"]),
                Paragraph(category.get("category_name", "—"), _STYLES["TableText"]),
                Paragraph(_money(category.get("current_month_amount", 0)), _STYLES["TableText"]),
                Paragraph(_money(category.get("all_time_average", 0)), _STYLES["TableText"]),
                Paragraph(_signed_money(category.get("delta_vs_average", 0)), _STYLES["TableText"]),
                Paragraph(_percent(category.get("delta_vs_average_pct") or 0), _STYLES["TableText"]),
            ])
        story.append(_build_table(["#", "Category", "Current", "Average", "Delta", "Delta %"], rows, [12 * mm, 62 * mm, 27 * mm, 27 * mm, 27 * mm, 18 * mm]))
    else:
        story.append(Paragraph("No category data available.", _STYLES["TableText"]))

    story.append(Spacer(1, 10 * mm))
    story.extend(_table_title("Top 5 Transactions", "Largest individual expense items recorded."))
    if top_transactions:
        rows = []
        for index, transaction in enumerate(top_transactions, start=1):
            merchant_label = transaction.get("merchant_name") or transaction.get("description", "—")
            description = transaction.get("description", "—")
            rows.append([
                Paragraph(str(index), _STYLES["TableText"]),
                Paragraph(str(transaction.get("date", "")), _STYLES["TableText"]),
                Paragraph(merchant_label, _STYLES["TableText"]),
                Paragraph(description, _STYLES["TableTextSmall"]),
                Paragraph(transaction.get("category_name", "—"), _STYLES["TableText"]),
                Paragraph(_money(transaction.get("amount", 0)), _STYLES["TableText"]),
            ])
        story.append(_build_table(["#", "Date", "Merchant", "Description", "Category", "Amount"], rows, [10 * mm, 20 * mm, 48 * mm, 65 * mm, 32 * mm, 22 * mm]))
    else:
        story.append(Paragraph("No transaction data available.", _STYLES["TableText"]))

    story.append(PageBreak())

    # --- PAGE 2: EVOLUTION ---
    story.extend(_table_title("Cash Flow Evolution", "Monthly revenue, expense, and savings trends across history."))
    story.extend(_chart_box(_cash_flow_chart(summary_series), "Blue=Revenue, Orange=Expenses, Teal=Savings."))
    story.append(Spacer(1, 15 * mm))

    story.extend(_table_title("Wealth Builder", "Cumulative step-line of monthly savings over time."))
    story.extend(_chart_box(_wealth_builder_chart(summary_series), "This chart represents total financial growth from savings."))
    
    story.append(PageBreak())

    # --- PAGE 3: BREAKDOWN ---
    story.extend(_table_title("Category Comparison", "Current month vs Historical Average for all categories."))
    comp_drawing = _comparison_chart(categories)
    # Scale height if many categories
    if len(categories) > 10:
        comp_drawing.height = 15 * len(categories)
        comp_drawing.contents[0].height = comp_drawing.height - 40
    story.extend(_chart_box(comp_drawing, "Blue=Current, Grey=Average."))
    story.append(Spacer(1, 15 * mm))

    story.extend(_table_title("Spend Composition", "Stacked view of category contributions over time."))
    story.extend(_chart_box(_stacked_category_chart(categories), "Each color represents a top-level category."))

    story.append(PageBreak())

    # --- PAGE 4: TOP EXPENSE CATEGORIES (FULL TABLE) ---
    story.extend(_table_title("All Expense Categories", "Ranked comparison for the current month."))
    if categories:
        rows = []
        for index, category in enumerate(categories, start=1):
            rows.append([
                Paragraph(str(index), _STYLES["TableText"]),
                Paragraph(category.get("category_name", "—"), _STYLES["TableText"]),
                Paragraph(_money(category.get("current_month_amount", 0)), _STYLES["TableText"]),
                Paragraph(_money(category.get("all_time_average", 0)), _STYLES["TableText"]),
                Paragraph(_signed_money(category.get("delta_vs_average", 0)), _STYLES["TableText"]),
                Paragraph(_percent(category.get("delta_vs_average_pct") or 0), _STYLES["TableText"]),
            ])
        story.append(_build_table(["#", "Category", "Current", "Average", "Delta", "Delta %"], rows, [12 * mm, 62 * mm, 27 * mm, 27 * mm, 27 * mm, 18 * mm]))
    
    story.append(PageBreak())

    # --- PAGE 5+: INDIVIDUAL TRENDS (2 PER PAGE) ---
    for i in range(0, len(categories), 2):
        chunk = categories[i:i+2]
        for category in chunk:
            story.extend(_table_title(category.get('category_name', 'Category'), f"Current: {_money(category.get('current_month_amount', 0))} | Avg: {_money(category.get('all_time_average', 0))}"))
            story.extend(_chart_box(_category_line_chart(category)))
            story.append(Spacer(1, 10 * mm))
        
        if i + 2 < len(categories):
            story.append(PageBreak())

    # Appendix
    if summary_series:
        story.append(PageBreak())
        story.extend(_table_title("Appendix: Historical Snapshot"))
        rows = []
        for row in summary_series:
            rows.append([
                Paragraph(str(row.get("month", "")), _STYLES["TableText"]),
                Paragraph(_money(row.get("revenue", 0)), _STYLES["TableText"]),
                Paragraph(_money(row.get("expenses", 0)), _STYLES["TableText"]),
                Paragraph(_money(row.get("savings", 0)), _STYLES["TableText"]),
            ])
        story.append(_build_table(["Month", "Revenue", "Expenses", "Savings"], rows, [32 * mm, 36 * mm, 36 * mm, 36 * mm]))

    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return buffer.getvalue()
