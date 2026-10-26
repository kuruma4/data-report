"""Тесты расчётов: без Excel-файлов и картинок."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from report import kpis, load  # noqa: E402

CSV = """date;category;product;qty;price
01.01.2026;Кофе;Эспрессо;10;150
02.01.2026;Кофе;Капучино;5;220
15.01.2026;Десерты;Чизкейк;2;350
01.02.2026;Кофе;Эспрессо;4;150
"""


class ReportTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            file.write(CSV)

    def tearDown(self):
        os.unlink(self.path)

    def test_load_builds_revenue(self):
        frame = load(self.path)
        self.assertEqual(len(frame), 4)
        self.assertEqual(frame["revenue"].sum(), 1500 + 1100 + 700 + 600)
        self.assertEqual(set(frame["month"]), {"2026-01", "2026-02"})

    def test_kpis(self):
        data = kpis(load(self.path))
        self.assertEqual(data["Выручка"], 3900)
        self.assertEqual(data["Заказов"], 4)
        self.assertEqual(data["Продано штук"], 21)
        self.assertEqual(data["Средний чек"], 975)
        self.assertEqual(data["Выручка в месяц"], 1950)

    def test_missing_column_message(self):
        bad = Path(self.path).with_suffix(".bad.csv")
        bad.write_text("date,product\n2026-01-01,X\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as context:
            load(bad)
        self.assertIn("category", str(context.exception))
        bad.unlink()

    def test_bad_dates_dropped(self):
        frame = pd.DataFrame({"date": ["2026-01-01", "не дата"]})
        self.assertEqual(pd.to_datetime(frame["date"], errors="coerce").notna().sum(), 1)


if __name__ == "__main__":
    unittest.main()
