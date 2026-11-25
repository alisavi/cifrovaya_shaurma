"""ML-A → ML-B handover.

Writes a small, self-contained package:

* `model.joblib`          fitted sklearn Pipeline (train only)
* `model_dataset.csv`     full analysis sample with train/test split flag
* `test_set.csv`          held-out test rows (for permutation importance)
* `contract.json`         seed, metric, target, features, blocks, hashes
* `metrics.json`          model card numbers
* `CARD.md`               human-readable handover card
* `kt3_consistency.md`    ML vs "traditional way" direction check
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from .config import (
    BLOCK_ORDER,
    BLOCKS,
    CATEGORICAL,
    FEATURE_TO_BLOCK,
    FEATURES,
    HANDOVER,
    METRIC,
    NUMERIC,
    SEED,
    TARGET,
    TEST_SIZE,
    validate_contract,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def _kt3_table(primary, trad) -> list[dict]:
    factors = primary["factors"]
    rows = []
    specs = [
        (
            "Питание: клетчатка",
            "log_fiber",
            "низкая клетчатка → выше ожирение (традиционный)",
            "высокая клетчатка → ниже ожирение (ML, OR < 1)",
            "protective",
        ),
        (
            "Сон",
            "SLD012",
            "короткий сон → выше ожирение (традиционный)",
            "длиннее сон → ниже ожирение (ML, OR < 1)",
            "protective",
        ),
        (
            "Стресс",
            "phq_mean",
            "высокий стресс → выше ожирение (традиционный)",
            "выше стресс → выше ожирение (ML, OR > 1)",
            "risk",
        ),
        (
            "Активность",
            "sed",
            "низкая активность → выше ожирение (традиционный)",
            "больше сидячего времени → выше ожирение (ML, OR > 1)",
            "risk",
        ),
    ]
    trad_by_factor = {row["factor"]: row for row in trad["rows"]}
    for trad_name, feature, trad_meaning, ml_meaning, direction in specs:
        trow = trad_by_factor[trad_name]
        ml = factors[factors["feature"] == feature].iloc[0]
        t_or, m_or = float(trow["or"]), float(ml["or_per_sd"])
        agree = (t_or > 1) == (m_or > 1) if direction == "risk" else (t_or > 1) == (m_or < 1)
        defined = ml["direction"] != "unclear"
        if not defined:
            verdict = (
                "направление согласуется, но ML CI включает 1"
                if agree
                else "направление противоречит, но ML CI включает 1"
            )
        elif agree:
            verdict = "согласуется по направлению"
        else:
            verdict = "противоречит по направлению"
        rows.append(
            {
                "block": trad_name,
                "traditional_comparison": trow["comparison"],
                "traditional_or": round(t_or, 3),
                "traditional_ci": f"{trow['ci_low']:.2f}–{trow['ci_high']:.2f}",
                "ml_factor": feature,
                "ml_or": round(m_or, 3),
                "ml_ci": f"{ml['ci_low']:.2f}–{ml['ci_high']:.2f}",
                "ml_direction": ml["direction"],
                "ml_strength": ml["strength"],
                "verdict": verdict,
                "comment": f"{trad_meaning}; {ml_meaning}. "
                f"Традиционный OR без поправок, ML — с контролем.",
            }
        )
    return rows


def _kt3_markdown(rows: list[dict]) -> str:
    header = (
        "| Блок | Традиционное сравнение | OR (95% CI) | ML-фактор | OR (95% CI) | "
        "Направление ML | Вывод |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    body = "\n".join(
        f"| {r['block']} | {r['traditional_comparison']} | "
        f"{r['traditional_or']:.2f} ({r['traditional_ci']}) | {r['ml_factor']} | "
        f"{r['ml_or']:.2f} ({r['ml_ci']}) | {r['ml_direction']} | {r['verdict']} |"
        for r in rows
    )
    note = (
        "\n\nНаправления совпадают там, где ML-интервал не включает 1. "
        "Для клетчатки и длительности сна ML-связь слабая (CI включает 1), "
        "поэтому вывод — «направление согласуется, значимость не доказана». "
        "Традиционный OR не поправлен на конфаундеры и потому обычно больше.\n"
    )
    return header + body + note


def _card(
    primary,
    trad,
    contract: dict,
    out_dir: Path,
    kt3_rows: list[dict],
    n_raw: int,
) -> str:
    m = primary["model"]
    b = primary["baseline"]
    split = contract["split"]
    kt3_lines = "\n".join(
        f"- **{r['block']}**: {r['verdict']} (ML OR {r['ml_or']:.2f}, "
        f"CI {r['ml_ci']})."
        for r in kt3_rows
    )
    return f"""# ML-A → ML-B handover

**Задача:** HAB-01, тема «Привычки и здоровье».
**Владелец:** ML-A (Шайбал Экрам). **Получатель:** ML-B (Павел Комов).
**Дата:** {contract['created_at']}.

## Что передаётся

| Артефакт | Что внутри |
|---|---|
| `model.joblib` | обученный `Pipeline`: `StandardScaler` + `OneHotEncoder` + `LogisticRegression` |
| `model_dataset.csv` | полная модельная выборка, колонка `split` = train/test |
| `test_set.csv` | только test, для permutation importance |
| `contract.json` | seed, метрика, target, признаки, блоки, хеши, метрики |
| `metrics.json` | краткая карточка метрик |
| `kt3_consistency.md` | сверка направлений ML и «Традиционного способа» |

## Контракт

- Seed: **{contract['seed']}**, split: **{split['n_train']} train / {split['n_test']} test**,
  stratify по target, test_size = {split['test_size']}.
- Target: **{TARGET}** — {contract['target_definition']}.
- Метрика: **{METRIC}**; baseline AUC = {b['roc_auc']:.3f}.
- Признаки: {len(FEATURES)}; блоки: {", ".join(BLOCKS)}.
- Модель: L2-логистическая регрессия, `max_iter=2000`, `random_state={contract['seed']}`.

## Метрики (test)

| Метрика | Baseline | Logit |
|---|---:|---:|
| ROC AUC | {b['roc_auc']:.3f} | {m['roc_auc']:.3f} |
| PR AUC | {b['pr_auc']:.3f} | {m['pr_auc']:.3f} |
| Accuracy | {b['accuracy']:.3f} | {m['accuracy']:.3f} |
| Balanced accuracy | {b['balanced_accuracy']:.3f} | {m['balanced_accuracy']:.3f} |
| Brier | {b['brier']:.3f} | {m['brier']:.3f} |

CV ROC AUC (5-fold, train): **{primary['cv_mean']:.3f} ± {primary['cv_sd']:.3f}**.

## Хеши данных

| Файл | sha256 |
|---|---|
| `model_dataset.csv` | `{contract['data_sha256']['model_dataset']}` |
| `test_set.csv` | `{contract['data_sha256']['test_set']}` |

## KT-3: ML vs «Традиционный способ»

{kt3_lines}

Подробная таблица — `kt3_consistency.md`. Традиционный OR не поправлен на
конфаундеры; ML-OR — с контролем. Это ассоциации, не причинность.

## Как воспроизвести

```bash
cd works/w1-hab
python analysis.py                 # полный конвейер + handover
python -m unittest discover -s ml_a/tests -v
python handover/verify.py
python handover/importance.py --repeats 1000
```

`handover/importance.py` читает `model.joblib`, `test_set.csv` и `contract.json`,
пишет `handover/importance.csv` и `handover/importance_blocks.csv`.

## Что не входит в handover

- Bootstrap-CI и устойчивость (seed’ы, подвыборки) — зона ML-B.
- Отчёт и «Традиционный способ» — зона аналитика.
- Причинность не заявляется: только ассоциации и гипотезы.

## Ограничения

- Complete-case: {primary['n_model']} из {n_raw} строк исходного файла
  (см. `out/metrics.json` и паспорт) — выборка смещена к полным наблюдениям.
- Один 24-ч дневник питания, самоотчёт о сне, PHQ-9 — прокси стресса.
- Абсолютные потребления нутриентов могут отражать размер тела и недоучёт.
"""


def write_handover(prep, primary, trad, out_dir: Path = HANDOVER) -> dict:
    """Serialize the fitted model, split, contract and KT-3 check."""
    validate_contract()
    out_dir.mkdir(parents=True, exist_ok=True)

    full = prep["model"].copy()
    full["split"] = "train"
    full.loc[primary["test_index"], "split"] = "test"

    id_columns = ["SEQN"] if "SEQN" in full.columns else []
    data_columns = id_columns + FEATURES + [TARGET]
    _write_csv(full[data_columns + ["split"]], out_dir / "model_dataset.csv")
    _write_csv(
        full.loc[primary["test_index"], data_columns], out_dir / "test_set.csv"
    )

    model_path = out_dir / "model.joblib"
    joblib.dump(primary["pipe"], model_path)

    kt3_rows = _kt3_table(primary, trad)
    kt3_csv = pd.DataFrame(kt3_rows)
    _write_csv(kt3_csv, out_dir / "kt3_consistency.csv")
    (out_dir / "kt3_consistency.md").write_text(
        "# KT-3: ML vs «Традиционный способ»\n\n" + _kt3_markdown(kt3_rows),
        encoding="utf-8",
    )

    contract = {
        "task": "HAB-01",
        "owner": "ML-A",
        "recipient": "ML-B",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "seed": SEED,
        "metric": METRIC,
        "target": TARGET,
        "target_definition": "BMI >= 30 kg/m2 (measured height and weight)",
        "split": {
            "test_size": TEST_SIZE,
            "stratify": True,
            "n_train": int(primary["n_train"]),
            "n_test": int(primary["n_test"]),
            "test_events": int(primary["test_events"]),
            "test_prevalence": float(primary["test_events"] / primary["n_test"]),
        },
        "features": FEATURES,
        "numeric": NUMERIC,
        "categorical": CATEGORICAL,
        "blocks": BLOCKS,
        "block_order": BLOCK_ORDER,
        "feature_to_block": FEATURE_TO_BLOCK,
        "model": {
            "type": "LogisticRegression",
            "params": {"max_iter": 2000, "random_state": SEED},
            "preprocessing": "StandardScaler(num) + OneHotEncoder(drop='first')(cat)",
            "fitted_on": "train only",
        },
        "metrics": {
            "baseline_auc": primary["baseline"]["roc_auc"],
            "test_auc": primary["model"]["roc_auc"],
            "test_pr_auc": primary["model"]["pr_auc"],
            "test_brier": primary["model"]["brier"],
            "cv_auc_mean": primary["cv_mean"],
            "cv_auc_sd": primary["cv_sd"],
            "n_model": int(primary["n_model"]),
            "events": int(primary["events"]),
        },
        "data_sha256": {
            "model_dataset": sha256_file(out_dir / "model_dataset.csv"),
            "test_set": sha256_file(out_dir / "test_set.csv"),
        },
        "model_sha256": sha256_file(model_path),
        "versions": {
            "python": sys.version.split()[0],
            "scikit-learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "artifacts": {
            "model": "handover/model.joblib",
            "dataset": "handover/model_dataset.csv",
            "test": "handover/test_set.csv",
            "kt3": "handover/kt3_consistency.md",
        },
        "how_to": [
            "python handover/verify.py",
            "python handover/importance.py --repeats 1000",
            "load joblib model and predict on handover/test_set.csv",
        ],
    }
    (out_dir / "contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "metrics.json").write_text(
        json.dumps(
            {
                "task": "HAB-01",
                "owner": "ML-A",
                "seed": SEED,
                "metric": METRIC,
                **contract["metrics"],
                **contract["split"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "CARD.md").write_text(
        _card(primary, trad, contract, out_dir, kt3_rows, prep["n_raw"]),
        encoding="utf-8",
    )

    return {
        "dir": str(out_dir.relative_to(out_dir.parent)),
        "model": "handover/model.joblib",
        "test": "handover/test_set.csv",
        "contract": "handover/contract.json",
        "kt3": "handover/kt3_consistency.md",
        "model_sha256": sha256_file(model_path),
        **contract["data_sha256"],
    }
