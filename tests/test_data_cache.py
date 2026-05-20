import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src import data_cache


class DataCacheTest(unittest.TestCase):
    def test_uses_local_cache_when_present(self):
        cache_path = Path("C:/cache/yv_2025.csv")

        with patch.object(data_cache, "has_cached_year", return_value=True), patch.object(
            data_cache, "cached_year_path", return_value=cache_path
        ):
            self.assertEqual(data_cache.source_for_year(2025), cache_path.resolve().as_posix())

    def test_falls_back_to_remote_when_cache_missing(self):
        with patch.object(data_cache, "has_cached_year", return_value=False):
            source = data_cache.source_for_year(2025)

        self.assertIn("yv_2025.csv", source)
        self.assertFalse(source.endswith("data/cache/yv_2025.csv"))

    def test_source_list_sql_quotes_sources(self):
        sql = data_cache.source_list_sql([2025], prefer_cache=False)

        self.assertTrue(sql.startswith("['"))
        self.assertTrue(sql.endswith("']"))
        self.assertIn("yv_2025.csv", sql)

    def test_defect_summary_flags_bad_entries(self):
        values = pd.Series(["VO:1;OV:2;EOV:3", "BAD:4;VO:not-number;OV:99"])

        with patch.object(data_cache, "_read_rikked_values", return_value=values):
            summary = data_cache._defect_summary("unused.csv", known_defect_ids={1, 2, 3})

        self.assertEqual(summary["parsed_defects"], 4)
        self.assertEqual(summary["unknown_severity_entries"], 1)
        self.assertEqual(summary["malformed_defect_entries"], 1)
        self.assertEqual(summary["unique_defect_ids"], 4)
        self.assertEqual(summary["defect_ids_missing_from_rike"], 1)


if __name__ == "__main__":
    unittest.main()
