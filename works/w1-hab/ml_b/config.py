"""ML-B settings for w1-hab.

ML-B does not redefine the model contract: seed, split, target, features and
blocks are read from `handover/contract.json`. Only analysis settings that
belong to ML-B live here.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOVER = ROOT / "handover"
OUT = ROOT / "out"
REPORT = ROOT / "report"

# Bootstrap of coefficients: resample train rows only, 1000 draws.
N_BOOT = 1000
CI_PERCENTILES = (2.5, 97.5)

# Stability across alternative stratified splits. Seed 42 reproduces the
# handover split; the rest are a sensitivity analysis, not new reported metrics.
SEEDS = [42, 1, 2, 3, 4, 5, 6, 7, 8, 9]

# Subsample stability: 80% of train, without replacement.
N_SUBSAMPLES = 200
SUBSAMPLE_FRACTION = 0.8

# CV on train.
CV_FOLDS = 5

# Block permutation on each seed's test split (cheap ranking check).
BLOCK_PERM_REPEATS = 30

# Percentile bootstrap for subsample ORs.
OR_PERCENTILES = (2.5, 97.5)
