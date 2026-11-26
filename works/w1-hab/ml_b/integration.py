"""Shared helpers that make the ML-B train-only CI canonical.

ML-A writes a full-sample factor table; ML-B rebuilds coefficients with
preprocessing fitted on train and resampling train rows only.  This module
turns the ML-B table into the same schema as `out/factors.csv`, builds the
`ml_b` section for `out/metrics.json`, and renders the HTML section used by
both reports.
"""

from __future__ import annotations

from typing import Mapping

import pandas as pd

CANONICAL_COLUMNS = [
    "factor",
    "block",
    "feature",
    "level",
    "unit",
    "n",
    "coef_std",
    "or_per_sd",
    "ci_low",
    "ci_high",
    "direction",
    "strength",
    "perm_importance",
    "perm_ci_low",
    "perm_ci_high",
    "p_value",
    "ci_scope",
    "n_boot",
    "sign_stability",
    "conclusion",
]

CONCLUSION = "Питание точечно первое, но ранг не доказан"


def read_units(path) -> dict[tuple[str, str], str]:
    """Read feature/level -> unit from an existing factor table (if present)."""
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return {}
    if not {"feature", "level", "unit"}.issubset(frame.columns):
        return {}
    return {
        (str(row["feature"]), str(row["level"])): str(row["unit"])
        for _, row in frame.iterrows()
    }


def canonical_factor_table(
    factors: pd.DataFrame,
    units: Mapping[tuple[str, str], str] | None = None,
) -> pd.DataFrame:
    """Map the ML-B table to the public `out/factors.csv` schema."""
    frame = factors.copy()
    frame["level"] = frame["level"].fillna("").astype(str)
    frame["unit"] = [
        (units or {}).get((str(feature), str(level)), "")
        for feature, level in zip(frame["feature"], frame["level"])
    ]
    frame["n"] = frame["n_train"].astype(int)
    n_train = int(frame["n"].max())
    frame["ci_scope"] = f"train (n={n_train}; test excluded)"
    frame["n_boot"] = frame["n_boot"].astype(int)
    frame["sign_stability"] = frame["sign_stability"].astype(float)
    frame["conclusion"] = frame["conclusion"].astype(str)
    for column in CANONICAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    return frame[CANONICAL_COLUMNS].reset_index(drop=True)


def write_canonical_factors(factors: pd.DataFrame, out_path, units_path=None) -> pd.DataFrame:
    """Write the train-only table to `out/factors.csv`; return the frame."""
    units = read_units(units_path) if units_path is not None else {}
    table = canonical_factor_table(factors, units)
    table.to_csv(
        out_path,
        index=False,
        encoding="utf-8-sig",
        lineterminator="\n",
        float_format="%.10g",
    )
    return table


def build_mlb_metrics(stability: dict) -> dict:
    """Compact ML-B block for `out/metrics.json`."""
    seeds = stability["seed_stability"]
    subs = stability["subsample_stability"]
    cv = stability["cv"]
    ranks = stability["block_rank_stability"]["summary"]
    return {
        "ci_scope": "train only",
        "n_boot": int(stability["bootstrap"]["n_boot"]),
        "n_train": int(stability["meta"]["n_train"]),
        "n_test": int(stability["meta"]["n_test"]),
        "canonical_factors": "out/factors.csv",
        "conclusion": CONCLUSION,
        "seed_stability": {
            "seeds": list(seeds["seeds"]),
            "auc_mean": float(seeds["auc_mean"]),
            "auc_sd": float(seeds["auc_sd"]),
            "auc_min": float(seeds["auc_min"]),
            "auc_max": float(seeds["auc_max"]),
            "sign_consistency_mean": float(seeds["sign_consistency_mean"]),
            "sign_consistency_min": float(seeds["sign_consistency_min"]),
        },
        "subsample_stability": {
            "n_subsamples": int(subs["n_subsamples"]),
            "fraction": float(subs["fraction"]),
            "sign_consistency_mean": float(subs["sign_consistency_mean"]),
            "sign_consistency_min": float(subs["sign_consistency_min"]),
        },
        "cv": {
            "folds": int(cv["folds"]),
            "auc_mean": float(cv["auc_mean"]),
            "auc_sd": float(cv["auc_sd"]),
            "auc_folds": [float(value) for value in cv["auc_folds"]],
        },
        "ranking": {
            "reference_order": list(ranks["reference_order"]),
            "control_first_share": float(ranks["share_first"].get("контроль", 0.0)),
            "exact_order_match": float(ranks["exact_order_match"]),
            "kendall_tau_mean": float(ranks["kendall_tau_mean"]),
            "kendall_tau_min": float(ranks["kendall_tau_min"]),
            "habit_exact_order_match": float(ranks["habit_exact_order_match"]),
            "habit_kendall_tau_mean": float(ranks["habit_kendall_tau_mean"]),
            "mean_rank": {
                str(block): float(value)
                for block, value in ranks["mean_rank"].items()
            },
        },
    }


def build_report_section(stability: dict, chart_href: str = "importance_ci.svg") -> str:
    """HTML fragment shared by report.html and report_engineer.html."""
    metrics = build_mlb_metrics(stability)
    seeds = metrics["seed_stability"]
    subs = metrics["subsample_stability"]
    cv = metrics["cv"]
    ranking = metrics["ranking"]
    return f"""<h2>ML-B: bootstrap CI (train) и устойчивость</h2>
<p><b>Канонический CI — train-only (n = {metrics['n_train']})</b>: коэффициенты
пересчитаны на train, test в bootstrap не входит. Таблица с этими OR/CI —
<code>out/factors.csv</code>; исходная ML-B-выгрузка — <code>handover/factors_mlb.csv</code>.</p>
<ul>
  <li><b>{len(seeds['seeds'])} seed’ов</b> (альтернативные стратифицированные split’ы):
      AUC <b>{seeds['auc_mean']:.3f} ± {seeds['auc_sd']:.3f}</b>
      (min {seeds['auc_min']:.3f}, max {seeds['auc_max']:.3f}).</li>
  <li><b>{subs['n_subsamples']} подвыборок</b> по {subs['fraction']:.0%} train:
      знак устойчив в среднем <b>{subs['sign_consistency_mean']:.0%}</b>,
      минимум <b>{subs['sign_consistency_min']:.0%}</b>.</li>
  <li><b>CV {cv['folds']}-fold на train</b>: AUC <b>{cv['auc_mean']:.3f} ± {cv['auc_sd']:.3f}</b>.</li>
  <li><b>Ранжирование блоков</b>: контроль первый в
      {ranking['control_first_share']:.0%} split’ов; порядок привычек совпал с ML-A
      в {ranking['habit_exact_order_match']:.0%} случаев; Kendall τ =
      <b>{ranking['kendall_tau_mean']:.2f}</b> (для привычек τ =
      {ranking['habit_kendall_tau_mean']:.2f}).</li>
  <li><b>Вывод:</b> питание точечно первое среди привычек, но ранг не доказан:
      интервалы пересекаются, а порядок воспроизводится не полностью.</li>
</ul>
<p><a href="{chart_href}">{chart_href}</a> — важность блоков с 95% CI.</p>
<img src="{chart_href}" alt="Важность блоков с 95% CI (ML-A permutation importance)">
"""
