import unittest

import numpy as np
import pandas as pd

from src.prediction import (
    HISTORICAL_RATE_FEATURES,
    HistoricalRateEncoder,
    LEAKAGE_PRONE_FEATURES,
    build_pipeline,
    prepare_data,
    summarize_probability_quality,
    summarize_fail_thresholds,
)


def _rows_for_year(year: int, count: int = 6) -> list[dict]:
    rows = []
    for i in range(count):
        rows.append(
            {
                "YV_AASTA": year,
                "YV_KUU": (i % 12) + 1,
                "PUNKTI_KOOD": "HA" if i % 2 else "MM",
                "LABIS_ESIMESEL": i % 2,
                "VANUS": 5 + i,
                "VANUS_RUUT": (5 + i) ** 2,
                "ON_VANA": int(5 + i > 10),
                "KUU_SIN": 0.0,
                "KUU_COS": 1.0,
                "MARK_SAGEDUS": 100,
                "MUDEL_SAGEDUS": 50,
                "KERETYYP_KOOD": 1,
                "EELMISED_YV": i,
                "MARK": "TESTMARK",
                "MUDEL": f"MODEL-{i % 2}",
                "KATEGOORIA": "M1",
                "KERETYYP": "SEDAAN",
                "MARK_LABIMISE_MAAR": 0.9,
                "MUDEL_LABIMISE_MAAR": 0.8,
                "PUNKTI_RANGUS": 20.0,
            }
        )
    return rows


class PredictionPreparationTest(unittest.TestCase):
    def test_uses_latest_year_as_temporal_holdout(self):
        df = pd.DataFrame(_rows_for_year(2023) + _rows_for_year(2024) + _rows_for_year(2025))

        X_train, X_test, y_train, y_test, features, split_info = prepare_data(df)

        self.assertEqual(split_info["type"], "temporal")
        self.assertEqual(split_info["train_years"], [2023, 2024])
        self.assertEqual(split_info["test_years"], [2025])
        self.assertEqual(len(X_train), 12)
        self.assertEqual(len(X_test), 6)
        self.assertEqual(len(y_train), 12)
        self.assertEqual(len(y_test), 6)
        self.assertFalse(set(LEAKAGE_PRONE_FEATURES) & set(features))

    def test_falls_back_to_random_split_for_single_year_data(self):
        df = pd.DataFrame(_rows_for_year(2025, count=20))

        *_unused, split_info = prepare_data(df)

        self.assertEqual(split_info["type"], "stratified_random")
        self.assertEqual(split_info["train_rows"], 16)
        self.assertEqual(split_info["test_rows"], 4)

    def test_summarizes_fail_thresholds(self):
        y_test = np.array([0, 0, 1, 1])
        y_prob = np.array([0.1, 0.4, 0.8, 0.9])

        rows = summarize_fail_thresholds(y_test, y_prob, target_recalls=(1.0,))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["min_fail_recall"], 1.0)
        self.assertGreaterEqual(rows[0]["fail_recall"], 1.0)
        self.assertGreater(rows[0]["fail_precision"], 0)

    def test_summarizes_probability_quality(self):
        y_test = np.array([0, 0, 1, 1])
        y_prob = np.array([0.1, 0.2, 0.8, 0.9])

        quality = summarize_probability_quality(y_test, y_prob, n_bins=2)

        self.assertIn("brier_score", quality)
        self.assertIn("log_loss", quality)
        self.assertIn("expected_calibration_error", quality)
        self.assertEqual(len(quality["calibration_bins"]), 2)
        self.assertLess(quality["brier_score"], 0.1)

    def test_historical_rate_encoder_uses_training_target_only(self):
        X_train = pd.DataFrame(
            {
                "MARK": ["A", "A", "B", "B"],
                "MUDEL": ["X", "X", "Y", "Y"],
                "KATEGOORIA": ["M1", "M1", "N1", "N1"],
                "KERETYYP": ["SEDAAN", "SEDAAN", "KAUBIK", "KAUBIK"],
                "PUNKTI_KOOD": ["P1", "P1", "P2", "P2"],
            }
        )
        y_train = pd.Series([1, 1, 0, 0])

        encoder = HistoricalRateEncoder(smoothing=0.0)
        encoder.fit(X_train, y_train)

        transformed = encoder.transform(
            pd.DataFrame(
                {
                    "MARK": ["A", "B", "C"],
                    "MUDEL": ["X", "Y", "Z"],
                    "KATEGOORIA": ["M1", "N1", "M1"],
                    "KERETYYP": ["SEDAAN", "KAUBIK", "SEDAAN"],
                    "PUNKTI_KOOD": ["P1", "P2", "P3"],
                }
            )
        )

        self.assertEqual(transformed.loc[0, "HIST_MARK_FAIL_RATE"], 0.0)
        self.assertEqual(transformed.loc[1, "HIST_MARK_FAIL_RATE"], 1.0)
        self.assertEqual(transformed.loc[2, "HIST_MARK_FAIL_RATE"], 0.5)

    def test_pipeline_adds_historical_rate_features_after_fit(self):
        df = pd.DataFrame(_rows_for_year(2023) + _rows_for_year(2024) + _rows_for_year(2025))
        X_train, _X_test, y_train, _y_test, features, _split_info = prepare_data(df)

        model = build_pipeline()
        model.fit(X_train, y_train)
        transformed = model.named_steps["historical_rates"].transform(X_train.head(2))

        self.assertTrue(set(HISTORICAL_RATE_FEATURES).issubset(transformed.columns))
        self.assertIn("MUDEL", features)


if __name__ == "__main__":
    unittest.main()
