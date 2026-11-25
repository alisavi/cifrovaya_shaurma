"""Reusable ML-A pipeline: preprocessing, one train fit, permutation importance.

Design rules encoded here (checked by tests):
* scaler and one-hot encoder live inside the Pipeline and are fitted on train;
* the evaluated model is fitted once on train and never on test;
* permutation importance is computed on the encoded matrix, so one-hot levels
  of the same categorical variable get separate importance values;
* random state and split are explicit and reproducible.
"""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import (
    CATEGORICAL,
    FEATURE_TO_BLOCK,
    NUMERIC,
    SEED,
    TEST_SIZE,
)


def build_preprocessor(
    num: Sequence[str] | None = None, cat: Sequence[str] | None = None
) -> ColumnTransformer:
    """Scale numeric columns and one-hot encode categoricals, all inside the model."""
    num = list(num) if num is not None else list(NUMERIC)
    cat = list(cat) if cat is not None else list(CATEGORICAL)
    return ColumnTransformer(
        [
            ("num", StandardScaler(), num),
            ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), cat),
        ],
        remainder="drop",
    )


def build_pipeline(
    num: Sequence[str] | None = None,
    cat: Sequence[str] | None = None,
    seed: int = SEED,
) -> Pipeline:
    """Preprocessing + L2 logistic regression; the fitted object is the handover model."""
    return Pipeline(
        [
            ("pre", build_preprocessor(num, cat)),
            (
                "lr",
                LogisticRegression(max_iter=2000, random_state=seed),
            ),
        ]
    )


def split_data(X, y, test_size: float = TEST_SIZE, seed: int = SEED):
    """Stratified train/test split; returns copies with original indices preserved."""
    return train_test_split(
        X,
        y,
        test_size=test_size,
        stratify=y,
        random_state=seed,
    )


def encoded_matrix(pre: ColumnTransformer, X) -> np.ndarray:
    """Dense encoded matrix used for permutation importance."""
    matrix = pre.transform(X)
    return matrix.toarray() if sparse.issparse(matrix) else np.asarray(matrix, dtype=float)


def raw_of_encoded(name: str) -> str:
    """Map `num__log_kcal` / `cat__RIAGENDR_2.0` back to the raw column name."""
    body = name.split("__", 1)[1]
    return body.split("_", 1)[0] if name.startswith("cat__") else body


def block_indices(
    encoded_names: Iterable[str], block_map: dict[str, str] | None = None
) -> dict[str, list[int]]:
    """Indices of encoded columns belonging to each block (order from the map)."""
    mapping = block_map or FEATURE_TO_BLOCK
    blocks = list(dict.fromkeys(mapping.values()))
    return {
        block: [
            i
            for i, name in enumerate(encoded_names)
            if mapping.get(raw_of_encoded(name)) == block
        ]
        for block in blocks
    }


class EncodedPermutation:
    """Permutation importance on the *encoded* test matrix.

    One instance caches the encoded test matrix and the baseline AUC, so 18
    individual features + 5 blocks do not re-transform the test set 23 times.
    """

    def __init__(self, pipe: Pipeline, X_test, y_test):
        self.pipe = pipe
        self.pre = pipe.named_steps["pre"]
        self.model = pipe.named_steps["lr"]
        self.X = encoded_matrix(self.pre, X_test)
        self.y = np.asarray(y_test).astype(int)
        self.names: list[str] = list(self.pre.get_feature_names_out())
        self.base_auc = float(roc_auc_score(self.y, self.model.predict_proba(self.X)[:, 1]))

    def drop(self, columns: Sequence[int], repeats: int, rng: np.random.Generator):
        """Mean drop in ROC AUC and percentile 95% CI for the given encoded columns."""
        values = []
        for _ in range(repeats):
            permuted = self.X.copy()
            order = rng.permutation(len(self.X))
            for column in columns:
                permuted[:, column] = self.X[order, column]
            values.append(
                self.base_auc
                - float(roc_auc_score(self.y, self.model.predict_proba(permuted)[:, 1]))
            )
        return (
            float(np.mean(values)),
            float(np.percentile(values, 2.5)),
            float(np.percentile(values, 97.5)),
        )
