#!/usr/bin/env python
"""Verify that the ML-A handover is internally consistent.

Checks:
* model and test-set hashes match contract.json;
* test n/events/features match the contract;
* test AUC reproduced from model + test set equals the contract value;
* model returns probabilities for every row.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import roc_auc_score

HANDOVER = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    contract = json.loads((HANDOVER / "contract.json").read_text(encoding="utf-8"))
    test = pd.read_csv(HANDOVER / "test_set.csv", encoding="utf-8")
    model = joblib.load(HANDOVER / "model.joblib")

    assert sha256(HANDOVER / "test_set.csv") == contract["data_sha256"]["test_set"]
    assert sha256(HANDOVER / "model.joblib") == contract["model_sha256"]

    features, target = contract["features"], contract["target"]
    assert set(features + [target]).issubset(test.columns)
    assert len(test) == contract["split"]["n_test"]
    assert int(test[target].sum()) == contract["split"]["test_events"]

    proba = model.predict_proba(test[features])[:, 1]
    assert len(proba) == len(test)
    auc = float(roc_auc_score(test[target], proba))
    expected = float(contract["metrics"]["test_auc"])
    assert abs(auc - expected) < 1e-9, (auc, expected)

    print(f"handover OK: n={len(test)}, events={int(test[target].sum())}, AUC={auc:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
