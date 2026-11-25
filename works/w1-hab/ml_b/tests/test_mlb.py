"""Tests for the ML-B package.

Run:
    cd works/w1-hab
    python -m unittest discover -s ml_b/tests -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from ml_b.bootstrap import (
    bootstrap_coefficients,
    build_factor_table,
    direction_from_ci,
    encode_train,
    encoded_level,
    strength_from_coef,
)
from ml_b.chart import write_importance_svg
from ml_b.data import load_split, verify_handover
from ml_b.stability import rank_summary, summarize_subsamples


def synthetic(n: int = 90, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    signal = rng.normal(size=n)
    frame = pd.DataFrame(
        {
            "x1": signal + rng.normal(scale=0.4, size=n),
            "x2": rng.normal(size=n),
            "cat1": rng.choice([1.0, 2.0, 3.0], size=n),
        }
    )
    frame["target"] = (signal + rng.normal(scale=0.6, size=n) > 0).astype(int)
    return frame


class HandoverTest(unittest.TestCase):
    def test_contract_and_split(self) -> None:
        contract, hash_report = verify_handover()
        self.assertTrue(all(item["content_match"] for item in hash_report.values()))
        train, test, _ = load_split(contract=contract)
        self.assertEqual(len(train), contract["split"]["n_train"])
        self.assertEqual(len(test), contract["split"]["n_test"])
        self.assertEqual(int(test[contract["target"]].sum()), contract["split"]["test_events"])
        self.assertFalse(set(train["SEQN"]) & set(test["SEQN"]))

    def test_no_target_in_features(self) -> None:
        contract, _ = verify_handover()
        self.assertNotIn(contract["target"], contract["features"])
        self.assertEqual(len(set(contract["features"])), len(contract["features"]))


class BootstrapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = synthetic()
        self.features = ["x1", "x2", "cat1"]
        self.numeric = ["x1", "x2"]
        self.categorical = ["cat1"]

    def test_encode_and_bootstrap_shapes(self) -> None:
        _, matrix, names = encode_train(
            self.frame, self.features, self.numeric, self.categorical, 42
        )
        self.assertEqual(matrix.shape[1], len(names))
        boot = bootstrap_coefficients(matrix, self.frame["target"].to_numpy(), 25, 42)
        self.assertEqual(boot.shape, (25, len(names)))
        self.assertTrue(np.all(np.isfinite(boot)))

    def test_factor_table_has_ci_and_sign_stability(self) -> None:
        _, matrix, names = encode_train(
            self.frame, self.features, self.numeric, self.categorical, 42
        )
        y = self.frame["target"].to_numpy()
        from ml_b.bootstrap import fit_logit

        coef = fit_logit(matrix, y, 42).coef_[0]
        boot = bootstrap_coefficients(matrix, y, 40, 42)
        table = build_factor_table(
            names,
            coef,
            boot,
            {"x1": "a", "x2": "a", "cat1": "b"},
            len(self.frame),
        )
        self.assertEqual(len(table), len(names))
        self.assertTrue((table["ci_low"] <= table["ci_high"]).all())
        self.assertTrue(table["sign_stability"].between(0, 1).all())
        self.assertTrue(set(table["direction"]).issubset({"positive", "negative", "unclear"}))
        self.assertTrue(set(table["strength"]).issubset({"weak", "moderate", "strong"}))
        self.assertIn("encoded_feature", table.columns)

    def test_ci_rules(self) -> None:
        self.assertEqual(direction_from_ci(1.2, 2.0), "positive")
        self.assertEqual(direction_from_ci(0.5, 0.9), "negative")
        self.assertEqual(direction_from_ci(0.8, 1.3), "unclear")
        self.assertEqual(strength_from_coef(0.1), "weak")
        self.assertEqual(strength_from_coef(0.3), "moderate")
        self.assertEqual(strength_from_coef(-0.8), "strong")

    def test_encoded_level_parsing(self) -> None:
        self.assertEqual(encoded_level("num__log_kcal"), ("log_kcal", ""))
        self.assertEqual(encoded_level("cat__SLQ050_1.0"), ("SLQ050", "1.0"))


class StabilityTest(unittest.TestCase):
    def test_rank_summary_matches_reference(self) -> None:
        reference = ["контроль", "питание", "сон", "активность", "стресс"]
        frame = pd.DataFrame(
            {
                "seed": [1, 2],
                "order": [" > ".join(reference), " > ".join(reference)],
            }
        )
        summary = rank_summary(frame, reference)
        self.assertEqual(summary["exact_order_match"], 1.0)
        self.assertAlmostEqual(summary["kendall_tau_mean"], 1.0)
        self.assertEqual(summary["habit_exact_order_match"], 1.0)
        self.assertEqual(summary["mean_rank"]["контроль"], 1.0)

    def test_subsample_summary_percentiles(self) -> None:
        coefs = pd.DataFrame(
            {
                "num__x1": [0.1, 0.2, 0.15, 0.12],
                "num__x2": [-0.1, -0.2, -0.15, -0.12],
            }
        )
        summary = summarize_subsamples(coefs)
        self.assertEqual(set(summary.index), {"num__x1", "num__x2"})
        self.assertTrue((summary["or_low"] <= summary["or_high"]).all())
        self.assertTrue(summary["sign_consistency"].between(0, 1).all())


class ChartTest(unittest.TestCase):
    def test_svg_is_written(self) -> None:
        frame = pd.DataFrame(
            {
                "block": ["питание", "сон", "стресс", "активность", "контроль"],
                "perm_importance": [0.041, 0.020, 0.001, 0.016, 0.061],
                "ci_low": [0.023, 0.006, -0.003, 0.005, 0.039],
                "ci_high": [0.061, 0.033, 0.006, 0.028, 0.085],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = write_importance_svg(frame, Path(tmp) / "chart.svg")
            text = path.read_text(encoding="utf-8")
        self.assertIn("<svg", text)
        self.assertIn("питание", text)
        self.assertIn("</svg>", text)


if __name__ == "__main__":
    unittest.main()
