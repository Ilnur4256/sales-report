from datetime import date

import httpx
import pandas as pd
import pytest
from openpyxl import load_workbook

import report.__main__ as cli
from report import delivery, metrics
from report.demo_data import generate


def sales(rows):
    cols = ["date", "order_id", "product", "category", "region", "quantity", "price"]
    return metrics.prepare(pd.DataFrame(rows, columns=cols))


@pytest.fixture
def df():
    return sales(
        [
            ("2026-10-01", 1, "Phone", "Смартфоны", "Бишкек", 1, 30000),
            ("2026-10-01", 1, "Чехол", "Аксессуары", "Бишкек", 2, 500),
            ("2026-10-02", 2, "Laptop", "Ноутбуки", "Ош", 1, 70000),
            ("2026-10-02", 3, "Чехол", "Аксессуары", "Каракол", 3, 500),
        ]
    )


def test_prepare_drops_bad_rows_and_counts_revenue():
    df = sales(
        [
            ("2026-10-01", 1, "A", "X", "R", 2, 100),
            ("not a date", 2, "A", "X", "R", 1, 100),
            ("2026-10-01", 3, "A", "X", "R", "abc", 100),
            ("2026-10-01", 4, "A", "X", "R", 0, 100),
        ]
    )
    assert len(df) == 1 and df["revenue"].iloc[0] == 200


def test_missing_columns():
    with pytest.raises(metrics.DataError, match="price"):
        metrics.prepare(pd.DataFrame({"date": [], "order_id": []}))


def test_kpi(df):
    k = metrics.kpi(df)
    assert k.revenue == 102500
    assert k.orders == 3
    assert k.items == 7
    assert k.avg_check == round(102500 / 3, 2)
    assert k.revenue_change is None


def test_period_comparison(df):
    current = metrics.filter_period(df, date(2026, 10, 2), date(2026, 10, 2))
    previous = metrics.previous_period(df, current)
    assert list(previous["order_id"].unique()) == [1]
    k = metrics.kpi(current, previous)
    assert k.revenue == 71500
    assert k.revenue_change == round((71500 - 31000) / 31000 * 100, 1)


def test_groupings(df):
    cats = metrics.by_column(df, "category")
    assert cats["category"].tolist() == ["Ноутбуки", "Смартфоны", "Аксессуары"]
    assert cats["share"].sum() == pytest.approx(1, abs=0.001)
    acc = cats.set_index("category").loc["Аксессуары"]
    assert (acc["revenue"], acc["orders"], acc["items"]) == (2500, 2, 5)
    daily = metrics.daily(df)
    assert daily["revenue"].tolist() == [31000, 71500]
    assert metrics.top_products(df, n=1)["product"].tolist() == ["Laptop"]


def test_cli_builds_workbook(tmp_path, capsys):
    src = tmp_path / "sales.csv"
    generate(date(2026, 9, 1), 20).to_csv(src, index=False)
    out = tmp_path / "r.xlsx"
    assert cli.main(["--input", str(src), "--from", "2026-09-11", "--out", str(out)]) == 0
    wb = load_workbook(out)
    assert wb.sheetnames == ["Сводка", "По дням", "Категории", "Регионы", "Топ товаров", "Данные"]
    summary = wb["Сводка"]
    assert summary["A4"].value == "Выручка" and summary["B4"].value > 0
    assert len(summary._charts) == 3
    assert wb["По дням"].max_row == 11  # заголовок + 10 дней
    assert wb["Данные"].auto_filter.ref.startswith("A1:")
    assert "к прошлому периоду" in capsys.readouterr().out


def test_cli_errors(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    assert cli.main(["--input", str(bad)]) == 2
    assert cli.main(["--input", str(tmp_path / "missing.csv")]) == 2


def test_email_has_attachment(tmp_path):
    f = tmp_path / "r.xlsx"
    f.write_bytes(b"data")
    msg = delivery.build_email(
        sender="a@x.kg",
        recipients=["b@x.kg", "c@x.kg"],
        subject="Отчёт",
        body="текст",
        attachment=f,
    )
    assert msg["To"] == "b@x.kg, c@x.kg"
    att = list(msg.iter_attachments())
    assert att[0].get_filename() == "r.xlsx" and att[0].get_content() == b"data"


def test_telegram_send_document(tmp_path):
    f = tmp_path / "r.xlsx"
    f.write_bytes(b"data")
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = request.read()
        return httpx.Response(200, json={"ok": True})

    delivery.send_telegram(
        "T", "42", f, "Отчёт", httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert seen["url"].endswith("/botT/sendDocument")
    assert b'filename="r.xlsx"' in seen["body"] and b"data" in seen["body"]
