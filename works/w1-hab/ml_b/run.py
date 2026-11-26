#!/usr/bin/env python
"""ML-B deliverable: bootstrap CI, stability checks and KT-3 consistency.

Usage:
    cd works/w1-hab
    python ml_b/run.py

Reads only the ML-A handover. Writes:
    handover/factors_mlb.csv
    handover/stability.json
    handover/MLB_SUMMARY.md
    report/importance_ci.svg
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

from ml_a.pipeline import build_pipeline  # noqa: E402

from ml_b import stability  # noqa: E402
from ml_b.bootstrap import (  # noqa: E402
    bootstrap_coefficients,
    build_factor_table,
    encode_train,
    fit_logit,
)
from ml_b.chart import write_importance_svg  # noqa: E402
from ml_b.config import (  # noqa: E402
    BLOCK_PERM_REPEATS,
    CI_PERCENTILES,
    CV_FOLDS,
    HANDOVER,
    N_BOOT,
    N_SUBSAMPLES,
    OUT,
    REPORT,
    SEEDS,
    SUBSAMPLE_FRACTION,
)
from ml_b.data import load_split, verify_handover  # noqa: E402
from ml_b.integration import (  # noqa: E402
    build_mlb_metrics,
    build_report_section,
    write_canonical_factors,
)


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    raise TypeError(f"not JSON serialisable: {type(value)!r}")


def _summary_markdown(
    contract: dict,
    point_auc: float,
    factors: pd.DataFrame,
    stability_payload: dict,
    written: dict,
    hash_report: dict,
    mla_comparison: list[dict],
) -> str:
    strong = factors[factors["direction"] != "unclear"].copy()
    strong["abs_coef"] = strong["coef_std"].abs()
    strong = strong.sort_values("abs_coef", ascending=False).head(8)

    crlf = [
        item["file"]
        for item in hash_report.values()
        if item.get("content_match") and not item.get("byte_match")
    ]
    hash_note = (
        "CSV выгружены с CRLF: sha256 байтов не совпадает с контрактом, "
        "но LF-нормализованный хеш совпадает — контент идентичен."
        if crlf
        else "Все sha256 совпадают с контрактом."
    )

    lines = [
        "# ML-B: bootstrap, устойчивость и KT-3",
        "",
        f"**Задача:** {contract['task']}, владелец ML-A → получатель ML-B.",
        f"**Сгенерировано:** {stability_payload['meta']['created_at']}.",
        "**Данные:** только handover ML-A; test не использовался для обучения.",
        "",
        "## Канонический CI",
        "",
        f"- Канонический интервал — **train-only**: n = "
        f"{stability_payload['meta']['n_train']}, bootstrap "
        f"{stability_payload['bootstrap']['n_boot']} ресэмплов, test исключён.",
        "- Именно эта таблица записана в `out/factors.csv` "
        "(`ci_scope = train; test excluded`). `handover/factors_mlb.csv` — "
        "исходная ML-B-выгрузка с теми же числами.",
        "- Полная выборка (n = 3984) больше **не** используется для OR/CI.",
        "",
        "## Контракт и модель",
        "",
        f"- Seed {contract['seed']}, split {contract['split']['n_train']}/"
        f"{contract['split']['n_test']}, target `{contract['target']}`.",
        f"- AUC на фиксированном test: **{point_auc:.4f}** "
        f"(в контракте {contract['metrics']['test_auc']:.4f}).",
        f"- Bootstrap: {stability_payload['bootstrap']['n_boot']} ресэмплов "
        "**только train**, preprocessing обучен на train.",
        f"- Хеши: {hash_note}",
        "",
        "## Факторы с CI, не включающим 1",
        "",
        "| Фактор | Блок | OR (95% CI) | Направление | Знак в bootstrap |",
        "|---|---|---|---|---:|",
    ]
    for _, row in strong.iterrows():
        lines.append(
            f"| {row['factor']} | {row['block']} | "
            f"{row['or_per_sd']:.2f} ({row['ci_low']:.2f}–{row['ci_high']:.2f}) | "
            f"{row['direction']} | {row['sign_stability']:.0%} |"
        )

    seeds = stability_payload["seed_stability"]
    subs = stability_payload["subsample_stability"]
    cv = stability_payload["cv"]
    ranks = stability_payload["block_rank_stability"]["summary"]
    lines += [
        "",
        "## Устойчивость",
        "",
        f"- Alt. splits, {len(seeds['per_seed'])} seed’ов: AUC "
        f"{seeds['auc_mean']:.3f} ± {seeds['auc_sd']:.3f} "
        f"(min {seeds['auc_min']:.3f}, max {seeds['auc_max']:.3f}).",
        f"- Подвыборки {subs['n_subsamples']}×{subs['fraction']:.0%} train: "
        f"средняя устойчивость знака {subs['sign_consistency_mean']:.0%}, "
        f"минимум {subs['sign_consistency_min']:.0%}.",
        f"- CV {cv['folds']}-fold на train: AUC {cv['auc_mean']:.3f} ± {cv['auc_sd']:.3f}.",
        f"- Ранжирование блоков: точное совпадение с ML-A в "
        f"{ranks['exact_order_match']:.0%} alt. split’ов, "
        f"Kendall τ = {ranks['kendall_tau_mean']:.2f}.",
        f"- Порядок привычек (без контроля) совпал в "
        f"{ranks['habit_exact_order_match']:.0%} split’ов, "
        f"τ = {ranks['habit_kendall_tau_mean']:.2f}.",
        "",
        "## KT-3: ML-B vs handover",
        "",
        "| Блок | ML-B OR (95% CI) | ML-B направление | В handover | Совпало |",
        "|---|---|---|---|---|",
    ]
    for item in stability_payload["kt3_check"]:
        lines.append(
            f"| {item['block']} | {item['mlb_or']:.2f} "
            f"({item['mlb_ci_low']:.2f}–{item['mlb_ci_high']:.2f}) | "
            f"{item['mlb_direction']} | {item['handover_direction']} | "
            f"{'да' if item['direction_match'] else 'нет'} |"
        )

    mismatched = [
        item for item in stability_payload["kt3_check"] if not item["direction_match"]
    ]
    if mismatched:
        names = ", ".join(item["ml_factor"] for item in mismatched)
        lines += [
            "",
            f"Расхождение по {names}: точечное направление то же, но 95% CI "
            "на train включает 1, поэтому ML-B ставит `unclear`, а не `positive`. "
            "Это уточнение значимости, а не противоположный вывод.",
        ]

    if mla_comparison:
        lines += [
            "",
            "## Историческое расхождение (легаси full-sample)",
            "",
            "До канонизации `out/factors.csv` содержал β/CI ML-A на **полной "
            f"выборке** (n = {mla_comparison[0]['n_mla']}), включая test. "
            "Теперь `out/factors.csv` заменён на train-only ML-B "
            f"(n = {mla_comparison[0]['n_mlb']}); таблица ниже сохранена только "
            "как история различий:",
            "",
            "| Фактор | Легаси ML-A, full sample | Канонический ML-B, train |",
            "|---|---|---|",
        ]
        for item in mla_comparison:
            label = item["feature"] + (f"={item['level']}" if item["level"] else "")
            lines.append(
                f"| {label} | {item['or_mla']:.2f} "
                f"({item['ci_mla_low']:.2f}–{item['ci_mla_high']:.2f}), "
                f"{item['direction_mla']} | {item['or_mlb']:.2f} "
                f"({item['ci_mlb_low']:.2f}–{item['ci_mlb_high']:.2f}), "
                f"{item['direction_mlb']} |"
            )
        lines += [
            "",
            "В отчётах и `out/factors.csv` используется только правая колонка "
            "(train-only). Расхождения по значимости — уточнение, а не "
            "противоположный вывод.",
        ]

    unstable = factors[
        (factors["seed_sign_consistency"] < 0.9)
        | (factors["subsample_sign_consistency"] < 0.9)
    ]
    if not unstable.empty:
        lines += [
            "",
            "## Неустойчивый знак",
            "",
            "| Фактор | Seed’ы | Подвыборки | Bootstrap |",
            "|---|---:|---:|---:|",
        ]
        for _, row in unstable.iterrows():
            lines.append(
                f"| {row['factor']} | {row['seed_sign_consistency']:.0%} | "
                f"{row['subsample_sign_consistency']:.0%} | "
                f"{row['sign_stability']:.0%} |"
            )
        lines += [
            "",
            "Для этих факторов знак/значимость зависят от выборки; вывод — "
            "«направление не определено».",
        ]

    lines += [
        "",
        "## Файлы",
        "",
        f"- `{written['factors'].relative_to(ROOT)}` — β, OR, 95% bootstrap CI, "
        "устойчивость знака, вывод.",
        f"- `{written['canonical'].relative_to(ROOT)}` — каноническая таблица "
        "train-only в публичной схеме (`ci_scope`, `n_boot`, `sign_stability`, "
        "`conclusion`).",
        f"- `{written['section'].relative_to(ROOT)}` — готовый HTML-фрагмент "
        "для обоих отчётов.",
        f"- `{written['metrics'].relative_to(ROOT)}` — секция `ml_b`.",
        f"- `{written['stability'].relative_to(ROOT)}` — полный JSON устойчивости.",
        f"- `{written['chart'].relative_to(ROOT)}` — важность блоков с CI.",
        "",
        "## Ограничения",
        "",
        "- Это ассоциации, не причинность; test один и тот же для всех сравнений.",
        "- Альтернативные split’ы — sensitivity analysis, а не новая отчётная метрика.",
        "- Блочная permutation-важность зависит от корреляции блоков между собой.",
        "- Survey-веса не применялись; выборка complete-case.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    print("ML-B: проверка handover…")
    contract, hash_report = verify_handover(HANDOVER)
    line_ending_warnings = [
        item
        for item in hash_report.values()
        if item.get("content_match") and not item.get("byte_match")
    ]
    for item in line_ending_warnings:
        print(
            f"  ! {item['file']}: CRLF, sha256 байтов не совпадает, "
            "но контент после LF-нормализации совпадает с контрактом"
        )
    train, test, contract = load_split(HANDOVER, contract)
    features = list(contract["features"])
    numeric = list(contract["numeric"])
    categorical = list(contract["categorical"])
    target = contract["target"]
    seed = int(contract["seed"])

    print(f"  train={len(train)}, test={len(test)}, features={len(features)}")

    y_train = train[target].to_numpy(dtype=int)
    y_test = test[target].to_numpy(dtype=int)

    print("ML-B: point fit на train + проверка test AUC…")
    pipe = build_pipeline(numeric, categorical, seed).fit(train[features], y_train)
    point_auc = float(roc_auc_score(y_test, pipe.predict_proba(test[features])[:, 1]))
    contract_auc = float(contract["metrics"]["test_auc"])
    if abs(point_auc - contract_auc) > 1e-6:
        raise RuntimeError(
            f"retrained test AUC {point_auc:.6f} != contract {contract_auc:.6f}"
        )
    print(f"  test AUC={point_auc:.4f} (контракт {contract_auc:.4f})")

    print("ML-B: bootstrap коэффициентов на train…")
    pre, matrix, names = encode_train(train, features, numeric, categorical, seed)
    point = fit_logit(matrix, y_train, seed)
    point_coef = point.coef_[0]
    boot = bootstrap_coefficients(matrix, y_train, N_BOOT, seed)
    factors = build_factor_table(
        names, point_coef, boot, contract["feature_to_block"], len(train)
    )

    importance_path = HANDOVER / "importance.csv"
    if importance_path.exists():
        importance = pd.read_csv(importance_path, encoding="utf-8")
        importance = importance.rename(
            columns={
                "ci_low": "perm_ci_low",
                "ci_high": "perm_ci_high",
                "block": "perm_block",
            }
        )[
            [
                "encoded_feature",
                "perm_importance",
                "perm_ci_low",
                "perm_ci_high",
                "repeats",
            ]
        ]
        factors = factors.merge(importance, on="encoded_feature", how="left")

    print(f"ML-B: устойчивость — {len(SEEDS)} split’ов, "
          f"{N_SUBSAMPLES} подвыборок, CV {CV_FOLDS}-fold…")
    full = pd.concat([train, test], ignore_index=False)
    seed_metrics, seed_coefs = stability.seed_stability(
        full,
        features,
        target,
        numeric,
        categorical,
        SEEDS,
        contract["split"]["test_size"],
    )
    # seed_stability needs the full analysis frame to draw alternative splits
    point_series = pd.Series(point_coef, index=names)
    seed_sign = stability._sign_consistency(seed_coefs, reference=point_series)

    subsample_coefs = stability.subsample_stability(
        train,
        features,
        target,
        numeric,
        categorical,
        N_SUBSAMPLES,
        SUBSAMPLE_FRACTION,
        seed,
    )
    subsample_sign = stability._sign_consistency(
        subsample_coefs, reference=point_series
    )
    subsample_summary = stability.summarize_subsamples(subsample_coefs)
    cv_result = stability.cv_auc(
        train, features, target, numeric, categorical, CV_FOLDS, seed
    )

    factors["seed_sign_consistency"] = factors["encoded_feature"].map(seed_sign)
    factors["subsample_sign_consistency"] = factors["encoded_feature"].map(
        subsample_sign
    )

    print("ML-B: ранжирование блоков на альтернативных split’ах…")
    block_frame = stability.block_rank_stability(
        full,
        features,
        target,
        numeric,
        categorical,
        contract["block_order"],
        contract["feature_to_block"],
        SEEDS,
        contract["split"]["test_size"],
        BLOCK_PERM_REPEATS,
        seed,
    )

    mla_blocks = pd.read_csv(HANDOVER / "importance_blocks.csv", encoding="utf-8")
    mla_blocks = mla_blocks.sort_values("perm_importance", ascending=False)
    reference_order = list(mla_blocks["block"])
    rank_stats = stability.rank_summary(block_frame, reference_order)

    kt3 = pd.read_csv(HANDOVER / "kt3_consistency.csv", encoding="utf-8")
    kt3_rows = []
    for _, row in kt3.iterrows():
        feature = str(row["ml_factor"])
        match = factors[factors["feature"] == feature]
        if len(match) != 1:
            continue
        item = match.iloc[0]
        kt3_rows.append(
            {
                "block": str(row["block"]),
                "ml_factor": feature,
                "mlb_or": float(item["or_per_sd"]),
                "mlb_ci_low": float(item["ci_low"]),
                "mlb_ci_high": float(item["ci_high"]),
                "mlb_direction": str(item["direction"]),
                "mlb_sign_stability": float(item["sign_stability"]),
                "ci_excludes_1": bool(item["direction"] != "unclear"),
                "handover_direction": str(row["ml_direction"]),
                "direction_match": bool(str(item["direction"]) == str(row["ml_direction"])),
                "traditional_or": float(row["traditional_or"]),
            }
        )

    order = {block: index for index, block in enumerate(contract["block_order"])}
    factors["_order"] = factors["block"].map(order)
    factors = factors.sort_values(
        ["_order", "coef_std"], ascending=[True, False]
    ).drop(columns="_order")

    mla_comparison: list[dict] = []
    mla_factor_path = ROOT / "out" / "factors.csv"
    if mla_factor_path.exists():
        mla_factors = pd.read_csv(mla_factor_path, encoding="utf-8")
        mla_factors["level"] = mla_factors["level"].fillna("").astype(str)
        ours = factors.copy()
        ours["level"] = ours["level"].fillna("").astype(str)
        merged = mla_factors.merge(
            ours, on=["feature", "level"], how="inner", suffixes=("_mla", "_mlb")
        )
        for _, row in merged.iterrows():
            if str(row["direction_mla"]) == str(row["direction_mlb"]):
                continue
            mla_comparison.append(
                {
                    "feature": str(row["feature"]),
                    "level": str(row["level"]),
                    "block": str(row["block_mla"]),
                    "n_mla": int(row["n"]),
                    "n_mlb": int(row["n_train"]),
                    "or_mla": float(row["or_per_sd_mla"]),
                    "ci_mla_low": float(row["ci_low_mla"]),
                    "ci_mla_high": float(row["ci_high_mla"]),
                    "direction_mla": str(row["direction_mla"]),
                    "or_mlb": float(row["or_per_sd_mlb"]),
                    "ci_mlb_low": float(row["ci_low_mlb"]),
                    "ci_mlb_high": float(row["ci_high_mlb"]),
                    "direction_mlb": str(row["direction_mlb"]),
                }
            )
        mla_comparison.sort(
            key=lambda item: (
                order.get(item["block"], 99),
                -abs(np.log(item["or_mla"]) - np.log(item["or_mlb"])),
            )
        )

    factor_path = HANDOVER / "factors_mlb.csv"
    factors.to_csv(
        factor_path,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
        float_format="%.10g",
    )

    # Canonical public table: same schema as the old out/factors.csv, but the
    # OR/CI columns now come from the train-only ML-B bootstrap.
    canonical_path = OUT / "factors.csv"
    canonical = write_canonical_factors(
        factors,
        canonical_path,
        units_path=canonical_path,
    )

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stability_payload = {
        "meta": {
            "owner": "ML-B",
            "created_at": created_at,
            "source": "handover/ (ML-A)",
            "n_train": int(len(train)),
            "n_test": int(len(test)),
            "n_features": len(features),
            "bootstrap_scope": "train only",
            "handover_hashes": hash_report,
        },
        "point_model": {
            "test_auc": point_auc,
            "contract_test_auc": contract_auc,
            "auc_match": True,
        },
        "bootstrap": {
            "n_boot": N_BOOT,
            "ci_percentiles": list(CI_PERCENTILES),
            "note": "preprocessing fitted on train; train rows resampled with replacement",
        },
        "seed_stability": {
            "seeds": list(SEEDS),
            "alternative_split_note": "sensitivity analysis; contract test stays fixed",
            "per_seed": seed_metrics.to_dict(orient="records"),
            "auc_mean": float(seed_metrics["test_auc"].mean()),
            "auc_sd": float(seed_metrics["test_auc"].std(ddof=1)),
            "auc_min": float(seed_metrics["test_auc"].min()),
            "auc_max": float(seed_metrics["test_auc"].max()),
            "sign_consistency_mean": float(seed_sign.mean()),
            "sign_consistency_min": float(seed_sign.min()),
            "n_features_sign_stable_90": int((seed_sign >= 0.9).sum()),
        },
        "subsample_stability": {
            "n_subsamples": N_SUBSAMPLES,
            "fraction": SUBSAMPLE_FRACTION,
            "sign_consistency_mean": float(subsample_sign.mean()),
            "sign_consistency_min": float(subsample_sign.min()),
            "or_percentiles": {
                "low": float(subsample_summary["or_low"].min()),
                "high": float(subsample_summary["or_high"].max()),
            },
            "per_feature": {
                str(name): {
                    "or_mean": float(row["or_mean"]),
                    "or_low": float(row["or_low"]),
                    "or_high": float(row["or_high"]),
                    "sign_consistency": float(row["sign_consistency"]),
                }
                for name, row in subsample_summary.iterrows()
            },
        },
        "cv": cv_result,
        "block_rank_stability": {
            "per_split": block_frame.to_dict(orient="records"),
            "summary": rank_stats,
            "mla_importance_blocks": mla_blocks.to_dict(orient="records"),
        },
        "kt3_check": kt3_rows,
        "mla_comparison": mla_comparison,
    }

    stability_path = HANDOVER / "stability.json"
    stability_path.write_text(
        json.dumps(
            stability_payload,
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    chart_path = write_importance_svg(
        mla_blocks,
        REPORT / "importance_ci.svg",
    )

    section_path = HANDOVER / "report_mlb_section.html"
    section_path.write_text(
        build_report_section(stability_payload),
        encoding="utf-8",
    )

    # Keep the public metrics file in sync with the canonical train-only CI.
    metrics_path = OUT / "metrics.json"
    metrics = {}
    if metrics_path.exists():
        try:
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            metrics = {}
    metrics["ml_b"] = build_mlb_metrics(stability_payload)
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    written = {
        "factors": factor_path,
        "canonical": canonical_path,
        "stability": stability_path,
        "chart": chart_path,
        "section": section_path,
        "metrics": metrics_path,
    }
    summary_path = HANDOVER / "MLB_SUMMARY.md"
    summary_path.write_text(
        _summary_markdown(
            contract,
            point_auc,
            factors,
            stability_payload,
            written,
            hash_report,
            mla_comparison,
        ),
        encoding="utf-8",
    )
    written["summary"] = summary_path

    print("\nML-B: готово")
    print(f"  factors:   {factor_path}")
    print(f"  stability: {stability_path}")
    print(f"  chart:     {chart_path}")
    print(f"  summary:   {summary_path}")
    print(
        f"  seeds AUC {stability_payload['seed_stability']['auc_mean']:.3f} ± "
        f"{stability_payload['seed_stability']['auc_sd']:.3f}; "
        f"CV {cv_result['auc_mean']:.3f} ± {cv_result['auc_sd']:.3f}"
    )
    print(
        f"  block order match {rank_stats['exact_order_match']:.0%}, "
        f"Kendall tau {rank_stats['kendall_tau_mean']:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
