"""Stability checks for ML-B: alternative splits, subsamples, CV, block ranks.

These are sensitivity analyses. The reported model metric stays the handover
test AUC on the fixed 996-row test set; alternative splits below are labelled
as such and never replace the contract.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score

from ml_a.pipeline import (
    EncodedPermutation,
    block_indices,
    build_pipeline,
    split_data,
)

from .config import OR_PERCENTILES


def _fit_names(
    frame: pd.DataFrame,
    features: Sequence[str],
    target: str,
    numeric: Sequence[str],
    categorical: Sequence[str],
    seed: int,
):
    pipe = build_pipeline(numeric, categorical, seed).fit(frame[list(features)], frame[target])
    names = list(pipe.named_steps["pre"].get_feature_names_out())
    coef = pipe.named_steps["lr"].coef_[0]
    return pipe, names, coef


def _sign_consistency(frame: pd.DataFrame, reference: pd.Series | None = None) -> pd.Series:
    """Share of fitted models whose coefficient has the reference sign.

    With no reference, each column uses its own majority sign. Missing encoded
    levels (a level absent from some resample) are ignored.
    """
    result = {}
    for column in frame.columns:
        values = frame[column].dropna()
        if values.empty:
            result[column] = float("nan")
            continue
        sign = np.sign(values)
        if reference is not None and column in reference.index:
            intended = np.sign(reference[column])
        else:
            intended = 1.0 if (sign >= 0).sum() >= (sign < 0).sum() else -1.0
        result[column] = float((sign == intended).mean())
    return pd.Series(result)


def seed_stability(
    df: pd.DataFrame,
    features: Sequence[str],
    target: str,
    numeric: Sequence[str],
    categorical: Sequence[str],
    seeds: Sequence[int],
    test_size: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Refit on alternative stratified splits; return per-seed metrics and coefs."""
    metrics = []
    coefs: dict[int, pd.Series] = {}
    for seed in seeds:
        Xtr, Xte, ytr, yte = split_data(df[list(features)], df[target], test_size, seed)
        pipe, names, coef = _fit_names(
            df.loc[Xtr.index], features, target, numeric, categorical, seed
        )
        auc = float(roc_auc_score(yte, pipe.predict_proba(Xte)[:, 1]))
        metrics.append(
            {
                "seed": int(seed),
                "n_train": int(len(Xtr)),
                "n_test": int(len(Xte)),
                "test_events": int(yte.sum()),
                "test_auc": auc,
            }
        )
        coefs[int(seed)] = pd.Series(coef, index=names)
    coef_frame = pd.DataFrame(coefs).T
    return pd.DataFrame(metrics), coef_frame


def subsample_stability(
    train: pd.DataFrame,
    features: Sequence[str],
    target: str,
    numeric: Sequence[str],
    categorical: Sequence[str],
    n_subsamples: int,
    fraction: float,
    seed: int,
) -> pd.DataFrame:
    """Refit on `fraction` of train without replacement; rows = subsamples."""
    rng = np.random.default_rng(seed)
    n_rows = len(train)
    size = max(2, int(round(n_rows * fraction)))
    coefs: dict[int, pd.Series] = {}
    for draw in range(n_subsamples):
        index = rng.choice(n_rows, size=size, replace=False)
        subset = train.iloc[np.sort(index)]
        _, names, coef = _fit_names(
            subset, features, target, numeric, categorical, seed
        )
        coefs[draw] = pd.Series(coef, index=names)
    return pd.DataFrame(coefs).T


def summarize_subsamples(coef_frame: pd.DataFrame) -> pd.DataFrame:
    """Per encoded feature: OR percentiles and sign consistency."""
    low_p, high_p = OR_PERCENTILES
    rows = {}
    for column in coef_frame.columns:
        values = coef_frame[column].dropna()
        sign = np.sign(values)
        majority = 1.0 if (sign >= 0).sum() >= (sign < 0).sum() else -1.0
        rows[column] = {
            "n_used": int(len(values)),
            "or_mean": float(np.exp(values).mean()),
            "or_low": float(np.exp(np.percentile(values, low_p))),
            "or_high": float(np.exp(np.percentile(values, high_p))),
            "sign_consistency": float((sign == majority).mean()),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def cv_auc(
    train: pd.DataFrame,
    features: Sequence[str],
    target: str,
    numeric: Sequence[str],
    categorical: Sequence[str],
    folds: int,
    seed: int,
) -> dict:
    pipe = build_pipeline(numeric, categorical, seed)
    folds_iter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    scores = cross_val_score(
        pipe,
        train[list(features)],
        train[target],
        cv=folds_iter,
        scoring="roc_auc",
    )
    return {
        "folds": int(folds),
        "auc_mean": float(np.mean(scores)),
        "auc_sd": float(np.std(scores, ddof=1)),
        "auc_folds": [float(value) for value in scores],
    }


def block_rank_stability(
    df: pd.DataFrame,
    features: Sequence[str],
    target: str,
    numeric: Sequence[str],
    categorical: Sequence[str],
    block_order: Sequence[str],
    feature_to_block: dict[str, str],
    seeds: Sequence[int],
    test_size: float,
    repeats: int,
    seed: int,
) -> pd.DataFrame:
    """Permutation importance of whole blocks on each alternative split."""
    rng = np.random.default_rng(seed)
    rows = []
    for split_seed in seeds:
        Xtr, Xte, ytr, yte = split_data(
            df[list(features)], df[target], test_size, split_seed
        )
        pipe = build_pipeline(numeric, categorical, split_seed).fit(Xtr, ytr)
        permutation = EncodedPermutation(pipe, Xte, yte)
        indices = block_indices(permutation.names, feature_to_block)
        importance = {
            block: float(permutation.drop(indices[block], repeats, rng)[0])
            for block in block_order
        }
        order = sorted(block_order, key=lambda block: importance[block], reverse=True)
        row = {"seed": int(split_seed), "test_auc": float(permutation.base_auc)}
        for block in block_order:
            row[f"importance_{block}"] = importance[block]
        row["order"] = " > ".join(order)
        rows.append(row)
    return pd.DataFrame(rows)


def rank_summary(order_frame: pd.DataFrame, reference_order: Sequence[str]) -> dict:
    """Mean rank, share-first and rank agreement against the ML-A ordering."""
    from scipy.stats import kendalltau

    blocks = list(reference_order)
    reference_position = {block: index for index, block in enumerate(blocks)}
    orders = [row.split(" > ") for row in order_frame["order"]]
    ranks = {block: [] for block in blocks}
    taus = []
    exact = 0
    for order in orders:
        for position, block in enumerate(order):
            ranks[block].append(position + 1)
        vector = [order.index(block) for block in blocks]
        taus.append(float(kendalltau(vector, list(range(len(blocks)))).correlation))
        exact += int(order == list(blocks))
    habits = [block for block in blocks if block != "контроль"]
    habit_orders = [[block for block in order if block in habits] for order in orders]
    habit_exact = sum(order == habits for order in habit_orders)
    habit_taus = [
        float(kendalltau([order.index(block) for block in habits], list(range(len(habits)))).correlation)
        for order in habit_orders
    ]
    return {
        "reference_order": list(blocks),
        "n_splits": len(orders),
        "mean_rank": {
            block: float(np.mean(ranks[block])) for block in blocks
        },
        "rank_sd": {
            block: float(np.std(ranks[block], ddof=1)) if len(ranks[block]) > 1 else 0.0
            for block in blocks
        },
        "share_first": {
            block: float(np.mean([order[0] == block for order in orders]))
            for block in blocks
        },
        "share_habit_block_first": float(
            np.mean([order[0] in habits for order in orders])
        )
        if orders
        else 0.0,
        "habit_reference_order": habits,
        "habit_exact_order_match": float(habit_exact / len(orders)) if orders else 0.0,
        "habit_kendall_tau_mean": float(np.mean(habit_taus)) if habit_taus else 0.0,
        "exact_order_match": float(exact / len(orders)) if orders else 0.0,
        "kendall_tau_mean": float(np.mean(taus)) if taus else 0.0,
        "kendall_tau_min": float(np.min(taus)) if taus else 0.0,
        "reference_position": reference_position,
    }
