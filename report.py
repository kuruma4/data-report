#!/usr/bin/env python3
"""Отчёт по продажам из CSV: графики PNG, сводка в Markdown и Excel.

    python report.py data/sample_sales.csv --out out
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # без графического окна — работает на сервере
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

REQUIRED = {"date", "category", "product", "qty", "price"}
MONTHS_RU = {
    1: "янв", 2: "фев", 3: "мар", 4: "апр", 5: "май", 6: "июн",
    7: "июл", 8: "авг", 9: "сен", 10: "окт", 11: "ноя", 12: "дек",
}


def load(path: str | Path) -> pd.DataFrame:
    """Читает CSV и приводит типы. Падает понятно, если колонок не хватает."""
    # sep=None: разделитель определяется сам (запятая, точка с запятой, таб)
    frame = pd.read_csv(path, sep=None, engine="python")
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise SystemExit(f"В файле нет колонок: {', '.join(sorted(missing))}")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", dayfirst=True)
    frame = frame.dropna(subset=["date"])
    frame["qty"] = pd.to_numeric(frame["qty"], errors="coerce").fillna(0).astype(int)
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce").fillna(0.0)
    frame["revenue"] = frame["qty"] * frame["price"]
    frame["month"] = frame["date"].dt.to_period("M").astype(str)
    frame["product"] = frame["product"].astype(str).str.strip()
    frame["category"] = frame["category"].astype(str).str.strip()
    return frame


def kpis(frame: pd.DataFrame) -> dict:
    """Ключевые показатели отчёта."""
    months = frame["month"].nunique() or 1
    return {
        "Выручка": frame["revenue"].sum(),
        "Заказов": len(frame),
        "Средний чек": frame["revenue"].sum() / len(frame),
        "Продано штук": int(frame["qty"].sum()),
        "Выручка в месяц": frame["revenue"].sum() / months,
        "Позиций": frame["product"].nunique(),
    }


def chart_monthly(frame: pd.DataFrame, path: Path) -> None:
    series = frame.groupby("month")["revenue"].sum()
    figure, axes = plt.subplots(figsize=(8, 4.2), dpi=140)
    axes.plot(series.index, series.values, marker="o", color="#2f6fed", linewidth=2)
    axes.fill_between(series.index, series.values, alpha=0.12, color="#2f6fed")
    axes.set_title("Выручка по месяцам, ₽", fontsize=12, loc="left")
    axes.grid(axis="y", alpha=0.25, linestyle="--")
    axes.spines[["top", "right"]].set_visible(False)
    axes.tick_params(axis="x", rotation=45, labelsize=8)
    axes.yaxis.set_major_formatter(lambda value, _: f"{value / 1000:.0f}к")
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)


def chart_categories(frame: pd.DataFrame, path: Path) -> None:
    series = frame.groupby("category")["revenue"].sum().sort_values()
    figure, axes = plt.subplots(figsize=(8, 4.2), dpi=140)
    bars = axes.barh(series.index, series.values, color="#2f6fed", height=0.6)
    axes.bar_label(bars, labels=[f"{value / 1000:.0f}к ₽" for value in series.values], padding=4, fontsize=8)
    axes.set_title("Выручка по категориям", fontsize=12, loc="left")
    axes.grid(axis="x", alpha=0.25, linestyle="--")
    axes.spines[["top", "right"]].set_visible(False)
    axes.set_xlim(0, series.max() * 1.2)
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)


def chart_top_products(frame: pd.DataFrame, path: Path, limit: int = 10) -> None:
    series = frame.groupby("product")["revenue"].sum().nlargest(limit).sort_values()
    figure, axes = plt.subplots(figsize=(8, 4.6), dpi=140)
    axes.barh(series.index, series.values, color="#16a34a", height=0.6)
    axes.set_title(f"Топ-{limit} товаров по выручке", fontsize=12, loc="left")
    axes.grid(axis="x", alpha=0.25, linestyle="--")
    axes.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)


def summary_markdown(frame: pd.DataFrame, figures: dict[str, Path]) -> str:
    data = kpis(frame)
    lines = ["# Отчёт по продажам", "", f"Период: {frame['date'].min():%d.%m.%Y} — {frame['date'].max():%d.%m.%Y}", "", "## Показатели", "", "| Показатель | Значение |", "|---|---|"]
    for name, value in data.items():
        if name in ("Выручка", "Средний чек", "Выручка в месяц"):
            lines.append(f"| {name} | {value:,.0f} ₽ |".replace(",", " "))
        else:
            lines.append(f"| {name} | {value:,} |".replace(",", " "))
    lines += ["", "## Топ-5 товаров", "", "| Товар | Выручка | Штук |", "|---|---|---|"]
    top = frame.groupby("product").agg(revenue=("revenue", "sum"), qty=("qty", "sum")).nlargest(5, "revenue")
    for product, row in top.iterrows():
        lines.append(f"| {product} | {row['revenue']:,.0f} ₽ | {int(row['qty'])} |".replace(",", " "))
    lines.append("")
    categories = frame.groupby("category")["revenue"].sum().sort_values(ascending=False)
    total = categories.sum()
    lines += ["## Категории", "", "| Категория | Доля |", "|---|---|"]
    for category, revenue in categories.items():
        lines.append(f"| {category} | {revenue / total:.0%} |")
    lines.append("")
    for title, path in figures.items():
        lines.append(f"![{title}]({path.name})")
        lines.append("")
    return "\n".join(lines)


def save_excel(frame: pd.DataFrame, path: Path) -> None:
    products = frame.groupby(["category", "product"]).agg(
        выручка=("revenue", "sum"), штук=("qty", "sum")
    ).reset_index().sort_values("выручка", ascending=False)
    monthly = frame.groupby("month").agg(выручка=("revenue", "sum"), заказов=("revenue", "size")).reset_index()
    with pd.ExcelWriter(path) as writer:
        products.to_excel(writer, sheet_name="Товары", index=False)
        monthly.to_excel(writer, sheet_name="По месяцам", index=False)
        frame.to_excel(writer, sheet_name="Сырые данные", index=False)


def build(source: str | Path, out_dir: str | Path) -> dict:
    """Полный проход: данные -> графики -> отчёты. Возвращает сводку."""
    out = Path(out_dir)
    (out / "charts").mkdir(parents=True, exist_ok=True)
    frame = load(source)
    figures = {
        "Выручка по месяцам": out / "charts" / "monthly.png",
        "Категории": out / "charts" / "categories.png",
        "Топ товаров": out / "charts" / "top_products.png",
    }
    chart_monthly(frame, figures["Выручка по месяцам"])
    chart_categories(frame, figures["Категории"])
    chart_top_products(frame, figures["Топ товаров"])
    (out / "summary.md").write_text(summary_markdown(frame, figures), encoding="utf-8")
    save_excel(frame, out / "report.xlsx")
    return kpis(frame)


def main() -> int:
    parser = argparse.ArgumentParser(description="Отчёт по продажам из CSV")
    parser.add_argument("source", help="CSV: date,category,product,qty,price")
    parser.add_argument("--out", default="out", help="папка для графиков и отчётов")
    args = parser.parse_args()
    data = build(args.source, args.out)
    print("Готово. Показатели:")
    for name, value in data.items():
        print(f"  {name}: {value:,.0f}".replace(",", " "))
    print(f"Файлы: {args.out}/summary.md, {args.out}/report.xlsx, {args.out}/charts/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
