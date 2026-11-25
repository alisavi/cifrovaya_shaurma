"""Contract tests for the ML-A package.

Run:
    cd works/w1-hab
    python -m unittest discover -s ml_a/tests -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml_a.config import FEATURES, TARGET, TEST_SIZE, validate_contract
from ml_a.pipeline import (
    EncodedPermutation,
    block_indices,
    build_pipeline,
    raw_of_encoded,
    split_data,
)


def synthetic(n: int = 240) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    signal = rng.normal(size=n)
    frame = pd.DataFrame(
        {
            "x1": signal + rng.normal(scale=0.3, size=n),
            "x2": rng.normal(size=n),
            "cat1": rng.choice([1.0, 2.0, 3.0], size=n),
            "cat2": rng.choice([0.0, 1.0], size=n),
        }
    )
    frame["target"] = (signal + rng.normal(scale=0.5, size=n) > 0).astype(int)
    return frame


class PipelineContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.df = synthetic()
        self.num = ["x1", "x2"]
        self.cat = ["cat1", "cat2"]
        X = self.df[self.num + self.cat]
        y = self.df["target"]
        self.Xtr, self.Xte, self.ytr, self.yte = split_data(X, y)

    def test_split_is_stratified_and_deterministic(self) -> None:
        X = self.df[self.num + self.cat]
        y = self.df["target"]
        a = split_data(X, y, test_size=TEST_SIZE, seed=42)
        b = split_data(X, y, test_size=TEST_SIZE, seed=42)
        self.assertEqual(list(a[1].index), list(b[1].index))
        self.assertLess(abs(a[3].mean() - y.mean()), 0.05)
        self.assertEqual(len(a[1]), int(round(len(y) * TEST_SIZE)))

    def test_pipeline_predicts_probabilities(self) -> None:
        pipe = build_pipeline(self.num, self.cat).fit(self.Xtr, self.ytr)
        proba = pipe.predict_proba(self.Xte)[:, 1]
        self.assertEqual(proba.shape, (len(self.Xte),))
        self.assertTrue(np.all((proba >= 0) & (proba <= 1)))

    def test_encoded_importance_is_finite_and_separates_levels(self) -> None:
        pipe = build_pipeline(self.num, self.cat).fit(self.Xtr, self.ytr)
        perm = EncodedPermutation(pipe, self.Xte, self.yte)
        cat_names = [n for n in perm.names if n.startswith("cat__")]
        self.assertGreater(len(cat_names), 1)
        rng = np.random.default_rng(1)
        values = [perm.drop([i], repeats=5, rng=rng) for i in range(min(3, len(perm.names)))]
        for mean, low, high in values:
            self.assertTrue(np.isfinite(mean))
            self.assertLessEqual(low, high)

    def test_block_indices_cover_all_encoded_columns(self) -> None:
        pipe = build_pipeline(self.num, self.cat).fit(self.Xtr, self.ytr)
        names = list(pipe.named_steps["pre"].get_feature_names_out())
        block_map = {"x1": "a", "x2": "a", "cat1": "b", "cat2": "b"}
        blocks = block_indices(names, block_map)
        covered = [i for indices in blocks.values() for i in indices]
        self.assertEqual(sorted(covered), list(range(len(names))))

    def test_raw_name_mapping(self) -> None:
        self.assertEqual(raw_of_encoded("num__log_kcal"), "log_kcal")
        self.assertEqual(raw_of_encoded("cat__RIAGENDR_2.0"), "RIAGENDR")

    def test_model_roundtrip(self) -> None:
        pipe = build_pipeline(self.num, self.cat).fit(self.Xtr, self.ytr)
        expected = pipe.predict_proba(self.Xte)[:, 1]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.joblib"
            joblib.dump(pipe, path)
            loaded = joblib.load(path)
            actual = loaded.predict_proba(self.Xte)[:, 1]
        np.testing.assert_allclose(expected, actual, rtol=0, atol=0)

    def test_no_target_leakage(self) -> None:
        self.assertNotIn(TARGET, FEATURES)
        self.assertNotIn("BMXBMI", FEATURES)
        self.assertEqual(len(set(FEATURES)), len(FEATURES))

    def test_contract_matches_feature_map(self) -> None:
        validate_contract()


if __name__ == "__main__":
    unittest.main()
