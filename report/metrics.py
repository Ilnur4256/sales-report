"""Расчёт метрик на pandas. Чистые функции: DataFrame на входе — DataFrame/словарь на выходе."""

from dataclasses import dataclass
from datetime import date

import pandas as pd

REQUIRED_COLUMNS = {"date", "order_id", "product", "category", "region", "quantity", "price"}


class DataError(ValueError):
    pass


def load_sales(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return prepare(df)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise DataError(f"В файле нет колонок: {', '.join(sorted(missing))}")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    bad = df[["date", "quantity", "price"]].isna().any(axis=1)
    df = df[~bad & (df["quantity"] > 0) & (df["price"] >= 0)]
    if df.empty:
        raise DataError("После очистки не осталось строк с корректными данными")
    df["revenue"] = df["quantity"] * df["price"]
    return df.reset_index(drop=True)


def filter_period(df: pd.DataFrame, start: date | None, end: date | None) -> pd.DataFrame:
    if start:
        df = df[df["date"] >= pd.Timestamp(start)]
    if end:
        df = df[df["date"] <= pd.Timestamp(end)]
    return df


@dataclass
class Kpi:
    revenue: float
    orders: int
    items: int
    avg_check: float
    revenue_change: float | None  # % к предыдущему периоду такой же длины


def kpi(df: pd.DataFrame, previous: pd.DataFrame | None = None) -> Kpi:
    revenue = float(df["revenue"].sum())
    orders = int(df["order_id"].nunique())
    change = None
    if previous is not None and not previous.empty:
        prev = float(previous["revenue"].sum())
        change = round((revenue - prev) / prev * 100, 1) if prev else None
    return Kpi(
        revenue=revenue,
        orders=orders,
        items=int(df["quantity"].sum()),
        avg_check=round(revenue / orders, 2) if orders else 0.0,
        revenue_change=change,
    )


def previous_period(full: pd.DataFrame, current: pd.DataFrame) -> pd.DataFrame:
    start, end = current["date"].min(), current["date"].max()
    length = end - start + pd.Timedelta(days=1)
    return filter_period(full, (start - length).date(), (start - pd.Timedelta(days=1)).date())


def daily(df: pd.DataFrame) -> pd.DataFrame:
    out = df.groupby(df["date"].dt.date).agg(
        revenue=("revenue", "sum"), orders=("order_id", "nunique")
    )
    out.index.name = "date"
    return out.reset_index()


def by_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    out = (
        df.groupby(column)
        .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"), items=("quantity", "sum"))
        .sort_values("revenue", ascending=False)
        .reset_index()
    )
    out["share"] = (out["revenue"] / out["revenue"].sum()).round(4)
    return out


def top_products(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return by_column(df, "product").head(n)
