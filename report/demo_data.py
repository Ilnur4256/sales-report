"""Генерирует демо-файл продаж (фиктивный магазин), чтобы проект можно было сразу запустить."""

import argparse
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

CATALOG = {
    "Смартфоны": [("Phone X", 32000), ("Phone Mini", 21000), ("Phone Max", 45000)],
    "Ноутбуки": [("Laptop Air", 68000), ("Laptop Pro", 115000)],
    "Аксессуары": [("Наушники", 3500), ("Чехол", 800), ("Зарядка", 1500), ("Кабель USB-C", 450)],
    "Планшеты": [("Tab 11", 29000), ("Tab Mini", 19000)],
}
REGIONS = ["Бишкек", "Ош", "Каракол", "Джалал-Абад", "Нарын"]
REGION_WEIGHTS = [50, 20, 12, 12, 6]


def generate(start: date, days: int, seed: int = 42) -> pd.DataFrame:
    rnd = random.Random(seed)
    rows = []
    order_id = 1000
    for d in range(days):
        day = start + timedelta(days=d)
        orders_today = rnd.randint(8, 20) + (6 if day.weekday() >= 5 else 0)
        for _ in range(orders_today):
            order_id += 1
            region = rnd.choices(REGIONS, REGION_WEIGHTS)[0]
            for _ in range(rnd.choice([1, 1, 1, 2, 3])):
                category = rnd.choice(list(CATALOG))
                product, price = rnd.choice(CATALOG[category])
                qty = rnd.choice([1, 1, 1, 2]) if price > 5000 else rnd.randint(1, 4)
                rows.append(
                    {
                        "date": day.isoformat(),
                        "order_id": order_id,
                        "product": product,
                        "category": category,
                        "region": region,
                        "quantity": qty,
                        "price": price,
                    }
                )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("data/sales.csv"))
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--start", type=date.fromisoformat, default=date(2026, 9, 1))
    args = p.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    generate(args.start, args.days).to_csv(args.out, index=False)
    print(f"Saved {args.out}")
