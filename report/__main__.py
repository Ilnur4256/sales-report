"""python -m report --input data/sales.csv --from 2026-10-01 --to 2026-10-31"""

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from report import delivery, metrics
from report.excel import build_workbook

log = logging.getLogger("report")


def money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ") + " сом"


def caption(title: str, period, k: metrics.Kpi) -> str:
    change = f" ({k.revenue_change:+}% к прошлому периоду)" if k.revenue_change is not None else ""
    return (
        f"{title}\n{period[0]:%d.%m.%Y} — {period[1]:%d.%m.%Y}\n"
        f"Выручка: {money(k.revenue)}{change}\n"
        f"Заказов: {k.orders}, средний чек: {money(k.avg_check)}"
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="report", description="Excel-отчёт по продажам из CSV")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--from", dest="start", type=date.fromisoformat)
    p.add_argument("--to", dest="end", type=date.fromisoformat)
    p.add_argument("--out", type=Path, default=Path("reports/sales_report.xlsx"))
    p.add_argument("--title", default="Отчёт по продажам")
    p.add_argument("--email", nargs="*", help="Получатели (SMTP_* из окружения)")
    p.add_argument(
        "--telegram", action="store_true", help="Отправить в Telegram (TG_* из окружения)"
    )
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        full = metrics.load_sales(args.input)
    except (metrics.DataError, FileNotFoundError) as e:
        print(f"Ошибка данных: {e}", file=sys.stderr)
        return 2
    df = metrics.filter_period(full, args.start, args.end)
    if df.empty:
        print("За выбранный период продаж нет", file=sys.stderr)
        return 2

    period = (df["date"].min().date(), df["date"].max().date())
    k = metrics.kpi(df, metrics.previous_period(full, df))
    path = build_workbook(
        args.out,
        title=args.title,
        period=period,
        kpi=k,
        daily=metrics.daily(df),
        categories=metrics.by_column(df, "category"),
        regions=metrics.by_column(df, "region"),
        products=metrics.top_products(df),
        raw=df.drop(columns=["revenue"]),
    )
    text = caption(args.title, period, k)
    print(text)
    log.info("Сохранено: %s", path)

    if args.email:
        msg = delivery.build_email(
            sender=os.environ["SMTP_USER"],
            recipients=args.email,
            subject=f"{args.title}: {period[0]:%d.%m} — {period[1]:%d.%m}",
            body=text,
            attachment=path,
        )
        delivery.send_email(
            msg,
            os.environ.get("SMTP_HOST", "smtp.gmail.com"),
            int(os.environ.get("SMTP_PORT", 465)),
            os.environ["SMTP_USER"],
            os.environ["SMTP_PASSWORD"],
        )
        log.info("Отправлено на почту: %s", ", ".join(args.email))
    if args.telegram:
        delivery.send_telegram(os.environ["TG_BOT_TOKEN"], os.environ["TG_CHAT_ID"], path, text)
        log.info("Отправлено в Telegram")
    return 0


if __name__ == "__main__":
    sys.exit(main())
