"""Excel-отчёт через openpyxl: форматирование, автофильтры и «родные» диаграммы Excel
(их можно редактировать в Excel, в отличие от вставленных картинок)."""

from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from report.metrics import Kpi

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")
THIN = Side(style="thin", color="D0D7E2")
MONEY = '#,##0 "сом"'
PERCENT = "0.0%"

HEADERS = {
    "date": "Дата",
    "revenue": "Выручка",
    "orders": "Заказы",
    "items": "Товары, шт",
    "share": "Доля",
    "category": "Категория",
    "region": "Регион",
    "product": "Товар",
    "order_id": "№ заказа",
    "quantity": "Кол-во",
    "price": "Цена",
}
FORMATS = {"revenue": MONEY, "price": MONEY, "share": PERCENT, "date": "DD.MM.YYYY"}


def write_table(ws, df: pd.DataFrame, start_row: int = 1) -> None:
    for c, name in enumerate(df.columns, start=1):
        cell = ws.cell(row=start_row, column=c, value=HEADERS.get(name, name))
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
    for r, row in enumerate(df.itertuples(index=False), start=start_row + 1):
        for c, (name, value) in enumerate(zip(df.columns, row, strict=True), start=1):
            if isinstance(value, pd.Timestamp):
                value = value.date()
            cell = ws.cell(row=r, column=c, value=value)
            cell.border = Border(bottom=THIN)
            if name in FORMATS:
                cell.number_format = FORMATS[name]
    last_col = get_column_letter(len(df.columns))
    ws.auto_filter.ref = f"A{start_row}:{last_col}{start_row + len(df)}"
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    for c, name in enumerate(df.columns, start=1):
        width = max(len(HEADERS.get(name, name)), *(len(str(v)) for v in df[name].head(200)))
        ws.column_dimensions[get_column_letter(c)].width = min(max(width + 3, 10), 40)


def build_workbook(
    path: Path,
    *,
    title: str,
    period: tuple[date, date],
    kpi: Kpi,
    daily: pd.DataFrame,
    categories: pd.DataFrame,
    regions: pd.DataFrame,
    products: pd.DataFrame,
    raw: pd.DataFrame,
) -> Path:
    wb = Workbook()

    # --- Сводка ---
    ws = wb.active
    ws.title = "Сводка"
    ws["A1"] = title
    ws["A1"].font = Font(bold=True, size=16, color="1F4E78")
    ws["A2"] = f"Период: {period[0]:%d.%m.%Y} — {period[1]:%d.%m.%Y}"
    rows = [
        ("Выручка", kpi.revenue, MONEY),
        ("Заказов", kpi.orders, "#,##0"),
        ("Продано товаров, шт", kpi.items, "#,##0"),
        ("Средний чек", kpi.avg_check, MONEY),
        (
            "Выручка к прошлому периоду",
            kpi.revenue_change / 100 if kpi.revenue_change is not None else "нет данных",
            "+0.0%;-0.0%",
        ),
    ]
    for i, (label, value, fmt) in enumerate(rows, start=4):
        ws.cell(row=i, column=1, value=label).font = Font(bold=True)
        cell = ws.cell(row=i, column=2, value=value)
        cell.number_format = fmt
        cell.font = Font(size=12)
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 20

    # --- Динамика по дням + линейный график ---
    ws_daily = wb.create_sheet("По дням")
    write_table(ws_daily, daily)
    line = LineChart()
    line.title, line.y_axis.title, line.height, line.width = "Выручка по дням", "сом", 8, 22
    line.add_data(
        Reference(ws_daily, min_col=2, min_row=1, max_row=len(daily) + 1), titles_from_data=True
    )
    line.set_categories(Reference(ws_daily, min_col=1, min_row=2, max_row=len(daily) + 1))
    line.series[0].smooth = False
    ws.add_chart(line, "D3")

    # --- Категории + круговая диаграмма ---
    ws_cat = wb.create_sheet("Категории")
    write_table(ws_cat, categories)
    pie = PieChart()
    pie.title, pie.height, pie.width = "Доля категорий в выручке", 8, 11
    pie.add_data(
        Reference(ws_cat, min_col=2, min_row=1, max_row=len(categories) + 1), titles_from_data=True
    )
    pie.set_categories(Reference(ws_cat, min_col=1, min_row=2, max_row=len(categories) + 1))
    ws.add_chart(pie, "D20")

    # --- Регионы + столбчатая ---
    ws_reg = wb.create_sheet("Регионы")
    write_table(ws_reg, regions)
    bar = BarChart()
    bar.type, bar.title, bar.height, bar.width = "bar", "Выручка по регионам", 8, 11
    bar.add_data(
        Reference(ws_reg, min_col=2, min_row=1, max_row=len(regions) + 1), titles_from_data=True
    )
    bar.set_categories(Reference(ws_reg, min_col=1, min_row=2, max_row=len(regions) + 1))
    bar.legend = None
    ws.add_chart(bar, "K20")

    write_table(wb.create_sheet("Топ товаров"), products)
    write_table(wb.create_sheet("Данные"), raw)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path
