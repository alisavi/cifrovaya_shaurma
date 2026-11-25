"""Bootstrap confidence intervals for standardised coefficients and ORs.

Method (deliberately different from ML-A's `out/factors.csv`, which resampled
the whole analysis sample):

* the preprocessor is fitted on **train only**;
* the encoded train matrix is resampled with replacement;
* logistic regression is refitted on each bootstrap sample;
* OR = exp(coef) because numeric columns are standardised and one-hot levels
  are compared with the reference level.

Test rows never enter this module.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression

from ml_a.pipeline import build_preprocessor, raw_of_encoded

from .config import CI_PERCENTILES


def encode_train(
    train: pd.DataFrame,
    features: Sequence[str],
    numeric: Sequence[str],
    categorical: Sequence[str],
    seed: int,
):
    """Fit preprocessing on train and return (encoder, dense matrix, names)."""
    pre = build_preprocessor(numeric, categorical)
    matrix = pre.fit_transform(train[list(features)])
    if sparse.issparse(matrix):
        matrix = matrix.toarray()
    return pre, np.asarray(matrix, dtype=float), list(pre.get_feature_names_out())


def fit_logit(matrix: np.ndarray, target: np.ndarray, seed: int) -> LogisticRegression:
    return LogisticRegression(max_iter=2000, random_state=seed).fit(matrix, target)


def bootstrap_coefficients(
    matrix: np.ndarray,
    target: np.ndarray,
    n_boot: int,
    seed: int,
) -> np.ndarray:
    """Refit logit on `n_boot` row resamples of the encoded train matrix."""
    rng = np.random.default_rng(seed)
    n_rows = len(target)
    coefs = np.empty((n_boot, matrix.shape[1]), dtype=float)
    for draw in range(n_boot):
        index = rng.integers(0, n_rows, n_rows)
        model = LogisticRegression(max_iter=2000, random_state=seed).fit(
            matrix[index], target[index]
        )
        coefs[draw] = model.coef_[0]
    return coefs


def direction_from_ci(low: float, high: float) -> str:
    if low > 1.0:
        return "positive"
    if high < 1.0:
        return "negative"
    return "unclear"


def strength_from_coef(coef: float) -> str:
    absolute = abs(float(coef))
    if absolute < 0.2:
        return "weak"
    if absolute <= 0.5:
        return "moderate"
    return "strong"


def encoded_level(encoded_name: str) -> tuple[str, str]:
    """`cat__SLQ050_1.0` -> ('SLQ050', '1.0'); numeric -> (name, '')."""
    raw = raw_of_encoded(encoded_name)
    if encoded_name.startswith("cat__"):
        body = encoded_name.split("__", 1)[1]
        return raw, body[len(raw) + 1 :]
    return raw, ""


def build_factor_table(
    names: Sequence[str],
    coef: np.ndarray,
    boot: np.ndarray,
    feature_to_block: dict[str, str],
    n_train: int,
) -> pd.DataFrame:
    """One row per encoded column with point OR, bootstrap CI and diagnostics."""
    low_p, high_p = CI_PERCENTILES
    low = np.percentile(boot, low_p, axis=0)
    high = np.percentile(boot, high_p, axis=0)
    boot_se = boot.std(axis=0, ddof=1)

    rows = []
    for index, name in enumerate(names):
        raw, level = encoded_level(name)
        or_value = float(np.exp(coef[index]))
        ci_low = float(np.exp(low[index]))
        ci_high = float(np.exp(high[index]))
        direction = direction_from_ci(ci_low, ci_high)
        se = float(boot_se[index])
        p_value = (
            float(2 * norm.sf(abs(float(coef[index])) / se)) if se > 0 else float("nan")
        )
        same_sign = np.mean(np.sign(boot[:, index]) == np.sign(coef[index]))
        conclusion = {
            "positive": "CI > 1: положительная связь",
            "negative": "CI < 1: отрицательная связь",
            "unclear": "CI включает 1: направление не определено",
        }[direction]
        rows.append(
            {
                "encoded_feature": name,
                "factor": raw if not level else f"{raw}={level}",
                "feature": raw,
                "level": level,
                "block": feature_to_block.get(raw, ""),
                "n_train": int(n_train),
                "coef_std": float(coef[index]),
                "or_per_sd": or_value,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "direction": direction,
                "strength": strength_from_coef(coef[index]),
                "boot_se": se,
                "p_value": p_value,
                "sign_stability": float(same_sign),
                "n_boot": int(boot.shape[0]),
                "conclusion": conclusion,
            }
        )
    return pd.DataFrame(rows)
