"""Tests for the ML-B integration layer (canonical table / labels / units)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from ml_b.integration import (
    CANONICAL_COLUMNS,
    canonical_factor_table,
    read_labels,
    write_canonical_factors,
)


def raw_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "encoded_feature": "num__log_pota",
                "factor": "log_pota",
                "feature": "log_pota",
                "level": "",
                "block": "питание",
                "n_train": 2988,
                "coef_std": -0.41,
                "or_per_sd": 0.66,
                "ci_low": 0.57,
                "ci_high": 0.75,
                "direction": "negative",
                "strength": "moderate",
                "boot_se": 0.05,
                "p_value": 1e-8,
                "sign_stability": 1.0,
                "n_boot": 1000,
                "conclusion": "CI < 1: отрицательная связь",
                "perm_importance": 0.059,
                "perm_ci_low": 0.04,
                "perm_ci_high": 0.076,
                "repeats": 1000,
                "seed_sign_consistency": 1.0,
                "subsample_sign_consistency": 1.0,
            }
        ]
    )


class IntegrationTest(unittest.TestCase):
    def test_canonical_table_maps_human_label_and_unit(self) -> None:
        table = canonical_factor_table(
            raw_table(),
            units={("log_pota", ""): "лог(мг/день)"},
            labels={("log_pota", ""): "Калий (овощи/фрукты)"},
        )
        self.assertEqual(table.loc[0, "factor"], "Калий (овощи/фрукты)")
        self.assertEqual(table.loc[0, "unit"], "лог(мг/день)")
        self.assertEqual(int(table.loc[0, "n"]), 2988)
        self.assertIn("train (n=2988", table.loc[0, "ci_scope"])
        self.assertEqual(list(table.columns), CANONICAL_COLUMNS)

    def test_write_reads_labels_from_existing_mla_table(self) -> None:
        metadata = pd.DataFrame(
            [
                {
                    "factor": "Калий (овощи/фрукты)",
                    "feature": "log_pota",
                    "level": "",
                    "unit": "лог(мг/день)",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            meta_path = tmp_path / "meta.csv"
            out_path = tmp_path / "factors.csv"
            metadata.to_csv(meta_path, index=False, encoding="utf-8-sig")
            write_canonical_factors(raw_table(), out_path, units_path=meta_path)
            result = pd.read_csv(out_path, encoding="utf-8-sig", keep_default_na=False)
        self.assertEqual(result.loc[0, "factor"], "Калий (овощи/фрукты)")
        self.assertEqual(result.loc[0, "unit"], "лог(мг/день)")

    def test_read_labels_ignores_empty_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "meta.csv"
            pd.DataFrame(
                [
                    {"factor": "Калий", "feature": "log_pota", "level": "", "unit": "мг"},
                    {"factor": "", "feature": "log_fat", "level": "", "unit": "г"},
                ]
            ).to_csv(path, index=False, encoding="utf-8-sig")
            labels = read_labels(path)
        self.assertEqual(labels[("log_pota", "")], "Калий")
        self.assertNotIn(("log_fat", ""), labels)


if __name__ == "__main__":
    unittest.main()
