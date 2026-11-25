#!/usr/bin/env python
"""Train the ML-A pipeline and write the ML-B handover.

This is the ML-A deliverable script. The full project report additionally runs
`analysis.py`; this script focuses on the model/test/importance handover.

Usage:
    cd works/w1-hab
    python ml_a/run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis import fit_primary, prepare_nhanes, traditional  # noqa: E402
from ml_a.handover import write_handover  # noqa: E402


def main() -> int:
    print("ML-A: подготовка NHANES…")
    prep = prepare_nhanes()
    print(f"  rows={len(prep['model'])}, features={len(prep['features'])}")

    print("ML-A: один fit на train + permutation importance…")
    primary = fit_primary(prep)

    print("ML-A: традиционный анализ для KT-3…")
    trad = traditional(prep["model"], primary["cv_mean"])

    print("ML-A: handover ML-B…")
    paths = write_handover(prep, primary, trad)
    print(f"  model: {paths['model']} (sha256 {paths['model_sha256'][:12]}…)")
    print(f"  test:  {paths['test']}")
    print(f"  card:  handover/CARD.md")
    print(
        f"  test AUC={primary['model']['roc_auc']:.3f}, "
        f"CV AUC={primary['cv_mean']:.3f} ± {primary['cv_sd']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
