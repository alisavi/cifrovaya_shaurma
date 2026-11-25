"""ML-A contract for w1-hab.

Single source of truth for the modelling split, seed, metric, feature blocks
and the exchange format handed to ML-B.

The contract is intentionally explicit (not inferred at runtime): ML-B must be
able to load the handover without reading `analysis.py`.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
HANDOVER = ROOT / "handover"
RAW = ROOT / "data" / "raw"

SEED = 42
TEST_SIZE = 0.25
N_PERM = 1000
N_BOOT = 1000
METRIC = "roc_auc"
TARGET = "obesity"

# Ordered exactly as the primary model sees them. Order is part of the contract:
# changing it changes the coefficient/permutation tables.
FEATURES = [
    # nutrition
    "log_kcal",
    "log_prot",
    "log_fat",
    "log_carb",
    "log_fiber",
    "log_pota",
    "log_water",
    # sleep
    "SLD012",
    "SLQ120",
    "SLQ050",
    # stress proxy
    "phq_mean",
    # activity
    "log_mvpa",
    "sed",
    # control
    "RIDAGEYR",
    "RIAGENDR",
    "RIDRETH1",
    "DMDEDUC2",
    "SMQ020",
]

CATEGORICAL = ["RIAGENDR", "RIDRETH1", "DMDEDUC2", "SMQ020", "SLQ050"]
NUMERIC = [f for f in FEATURES if f not in CATEGORICAL]

# Blocks used for permutation importance. "контроль" is a reference block,
# not a habit block; it is reported separately.
BLOCKS = {
    "питание": ["log_kcal", "log_prot", "log_fat", "log_carb", "log_fiber", "log_pota", "log_water"],
    "сон": ["SLD012", "SLQ120", "SLQ050"],
    "стресс": ["phq_mean"],
    "активность": ["log_mvpa", "sed"],
    "контроль": ["RIDAGEYR", "RIAGENDR", "RIDRETH1", "DMDEDUC2", "SMQ020"],
}
BLOCK_ORDER = ["питание", "сон", "стресс", "активность", "контроль"]

FEATURE_TO_BLOCK = {
    feature: block for block, features in BLOCKS.items() for feature in features
}


def validate_contract(feature_map_path: Path | None = None) -> None:
    """Fail loudly if the hard-coded contract drifts from out/feature_map.json."""
    path = feature_map_path or (OUT / "feature_map.json")
    if not path.exists():
        return
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    mapped = {
        item["column"]
        for block, items in payload.get("blocks", {}).items()
        for item in items
    }
    missing = sorted(set(FEATURES) - mapped)
    extra = sorted(mapped - set(FEATURES))
    if missing or extra:
        raise RuntimeError(
            f"ML-A contract out of sync with {path}: missing={missing}, extra={extra}"
        )
    if payload.get("target", {}).get("name") != TARGET:
        raise RuntimeError("ML-A target does not match out/feature_map.json")
