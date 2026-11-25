"""Load and verify the ML-A handover without reading `analysis.py`.

Rules:
* the contract is the source of truth for seed, split, target and features;
* train/test are taken from the `split` column, never re-split silently;
* content hashes are checked before anything is computed.

Windows note: git may check CSVs out with CRLF while the contract hashes were
computed on LF bytes. Such a file is reported as `line_endings: "crlf"` with
`content_ok: true`; only a real content mismatch is fatal.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .config import HANDOVER


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_normalized(path: Path) -> str:
    """Hash with CRLF collapsed to LF, so a Windows checkout is comparable."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk.replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def load_contract(handover: Path = HANDOVER) -> dict:
    return json.loads((handover / "contract.json").read_text(encoding="utf-8"))


def verify_handover(handover: Path = HANDOVER) -> tuple[dict, dict]:
    """Check hashes and split sizes; return (contract, hash report)."""
    contract = load_contract(handover)
    problems: list[str] = []
    hash_report: dict[str, dict] = {}

    expected_files = {
        "model_dataset": handover / "model_dataset.csv",
        "test_set": handover / "test_set.csv",
    }
    for key, path in expected_files.items():
        if not path.exists():
            problems.append(f"нет файла {path.name}")
            continue
        expected = contract["data_sha256"][key]
        actual_bytes = sha256(path)
        actual_content = sha256_normalized(path)
        byte_match = actual_bytes == expected
        content_match = actual_content == expected
        hash_report[key] = {
            "file": path.name,
            "expected": expected,
            "sha256_bytes": actual_bytes,
            "sha256_lf_normalized": actual_content,
            "byte_match": byte_match,
            "content_match": content_match,
            "line_endings": "crlf" if actual_bytes != actual_content else "lf",
        }
        if not content_match:
            problems.append(
                f"{path.name}: sha256 не совпадает с контрактом "
                f"(bytes {actual_bytes[:12]}…, LF {actual_content[:12]}…, "
                f"контракт {expected[:12]}…)"
            )

    model_path = handover / "model.joblib"
    if not model_path.exists():
        problems.append("нет файла model.joblib")
    else:
        actual = sha256(model_path)
        match = actual == contract["model_sha256"]
        hash_report["model"] = {
            "file": model_path.name,
            "expected": contract["model_sha256"],
            "sha256_bytes": actual,
            "byte_match": match,
            "content_match": match,
        }
        if not match:
            problems.append("model.joblib: sha256 не совпадает с контрактом")

    df = pd.read_csv(expected_files["model_dataset"], encoding="utf-8")
    counts = df["split"].value_counts().to_dict()
    if counts.get("train") != contract["split"]["n_train"]:
        problems.append(
            f"train: {counts.get('train')} != {contract['split']['n_train']}"
        )
    if counts.get("test") != contract["split"]["n_test"]:
        problems.append(
            f"test: {counts.get('test')} != {contract['split']['n_test']}"
        )

    missing = [
        column
        for column in contract["features"] + [contract["target"], "split"]
        if column not in df.columns
    ]
    if missing:
        problems.append(f"в model_dataset.csv нет колонок: {missing}")

    if problems:
        raise RuntimeError("handover не прошёл проверку: " + "; ".join(problems))

    return contract, hash_report


def load_split(handover: Path = HANDOVER, contract: dict | None = None):
    """Return (train, test, contract) with original rows preserved."""
    contract = contract or load_contract(handover)
    df = pd.read_csv(handover / "model_dataset.csv", encoding="utf-8")
    train = df[df["split"] == "train"].copy()
    test = df[df["split"] == "test"].copy()

    if len(train) != contract["split"]["n_train"]:
        raise RuntimeError(f"train rows: {len(train)} != {contract['split']['n_train']}")
    if len(test) != contract["split"]["n_test"]:
        raise RuntimeError(f"test rows: {len(test)} != {contract['split']['n_test']}")
    if int(test[contract["target"]].sum()) != contract["split"]["test_events"]:
        raise RuntimeError("test events do not match the contract")

    if "SEQN" in train.columns and "SEQN" in test.columns:
        overlap = set(train["SEQN"]) & set(test["SEQN"])
        if overlap:
            raise RuntimeError(f"SEQN пересекается между train и test: {len(overlap)}")

    return train, test, contract
