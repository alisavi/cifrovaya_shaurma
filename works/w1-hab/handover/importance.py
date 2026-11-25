#!/usr/bin/env python
"""ML-B entry point: permutation importance on the ML-A handover.

Example:
    python handover/importance.py --repeats 1000

Reads `handover/model.joblib`, `handover/test_set.csv` and `handover/contract.json`,
writes `handover/importance.csv` and `handover/importance_blocks.csv`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml_a.pipeline import EncodedPermutation, block_indices, raw_of_encoded  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Permutation importance on ML-A handover")
    parser.add_argument("--handover", type=Path, default=ROOT / "handover")
    parser.add_argument("--repeats", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    handover = args.handover
    contract = json.loads((handover / "contract.json").read_text(encoding="utf-8"))
    test = pd.read_csv(handover / "test_set.csv", encoding="utf-8")
    features = contract["features"]
    target = contract["target"]
    missing = [c for c in features + [target] if c not in test.columns]
    if missing:
        raise SystemExit(f"test_set.csv is missing columns: {missing}")

    model = joblib.load(handover / "model.joblib")
    perm = EncodedPermutation(model, test[features], test[target])
    seed = args.seed if args.seed is not None else contract["seed"]
    rng = np.random.default_rng(seed)

    rows = []
    for index, encoded_name in enumerate(perm.names):
        mean, low, high = perm.drop([index], args.repeats, rng)
        raw = raw_of_encoded(encoded_name)
        rows.append(
            {
                "encoded_feature": encoded_name,
                "feature": raw,
                "block": contract["feature_to_block"].get(raw, ""),
                "perm_importance": mean,
                "ci_low": low,
                "ci_high": high,
                "repeats": args.repeats,
            }
        )
    importance = pd.DataFrame(rows).sort_values("perm_importance", ascending=False)
    importance.to_csv(
        handover / "importance.csv", index=False, encoding="utf-8", lineterminator="\n"
    )

    blocks = block_indices(perm.names, contract["feature_to_block"])
    block_rows = []
    for block in contract["block_order"]:
        mean, low, high = perm.drop(blocks[block], args.repeats, rng)
        block_rows.append(
            {
                "block": block,
                "perm_importance": mean,
                "ci_low": low,
                "ci_high": high,
                "repeats": args.repeats,
            }
        )
    block_frame = pd.DataFrame(block_rows)
    block_frame.to_csv(
        handover / "importance_blocks.csv",
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )

    print(f"baseline test AUC: {perm.base_auc:.4f}")
    print(block_frame.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nTop encoded features:")
    print(
        importance.head(8)[["feature", "block", "perm_importance", "ci_low", "ci_high"]]
        .to_string(index=False, float_format=lambda x: f"{x:.4f}")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
