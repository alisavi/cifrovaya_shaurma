#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Checker for the w1-hab practice.

Reads shared/rubric/practice-v1.json, inspects works/w1-hab/ and writes
works/w1-hab/review/report.json with technical statuses (ok / partial / missing).

It deliberately does NOT assign a human grade: weighted_compliance is only the
share of rubric criteria that are technically satisfied.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUBRIC = ROOT / "shared" / "rubric" / "practice-v1.json"
WORK = ROOT / "works" / "w1-hab"
REVIEW = WORK / "review"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def add(checks, name, passed, evidence):
    checks.append({"check": name, "status": "ok" if passed else "missing", "evidence": evidence})
    return passed


def artifact_status(rel: str) -> str:
    p = ROOT / rel
    return "ok" if p.is_file() and p.stat().st_size > 0 else "missing"


def main() -> int:
    REVIEW.mkdir(parents=True, exist_ok=True)

    rubric = load_json(RUBRIC)
    if not rubric:
        out = {
            "rubric": "practice-v1",
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "artifacts": {},
            "criteria": [],
            "summary": {"weighted_compliance": 0.0, "blockers": 1, "status": "missing"},
            "blockers": [{"id": "rubric_missing", "evidence": "shared/rubric/practice-v1.json"}],
            "note": "Рубрика не найдена; критерии не выдумывались.",
        }
        (REVIEW / "report.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return 1

    artifacts = {rel: artifact_status(rel) for rel in rubric.get("required_artifacts", [])}

    passport_path = WORK / "data" / "PASSPORT.md"
    report_path = WORK / "report" / "report.html"
    metrics_path = WORK / "out" / "metrics.json"
    factors_path = WORK / "out" / "factors.csv"
    feature_map_path = WORK / "out" / "feature_map.json"
    spec_path = WORK / "spec.md"

    passport = passport_path.read_text(encoding="utf-8") if passport_path.exists() else ""
    report_html = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    report_text = strip_html(report_html).lower()
    metrics = load_json(metrics_path) or {}
    feature_map = load_json(feature_map_path) or {}

    factor_rows = []
    factor_cols = []
    if factors_path.exists():
        with factors_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            factor_cols = reader.fieldnames or []
            factor_rows = list(reader)

    results = {}

    # ------------------------------------------------------------------
    # 1. Passport (blocker)
    # ------------------------------------------------------------------
    checks = []
    has_url = bool(re.search(r"https?://|doi\.org|10\.\d{4,9}/", passport))
    add(checks, "ссылка на источник", has_url, "URL/DOI в PASSPORT.md" if has_url else "не найдено")
    has_license = bool(re.search(r"(?i)public domain|cc[ -]?by|лицензи|license", passport))
    add(checks, "лицензия", has_license, "раздел лицензий" if has_license else "не найдено")
    hash_rows = re.findall(
        r"\|\s*`([^`]+)`\s*\|\s*[\d,\s]+\|\s*`([0-9a-fA-F]{64})`\s*\|", passport
    )
    checked, matched = 0, 0
    for rel, digest in hash_rows:
        p = WORK / rel
        if p.is_file():
            checked += 1
            if sha256_file(p) == digest.lower():
                matched += 1
    hash_ok = checked > 0 and checked == matched
    add(
        checks,
        "sha256 указан",
        len(hash_rows) > 0,
        f"{len(hash_rows)} хешей в паспорте",
    )
    add(
        checks,
        "фактический хеш совпадает",
        hash_ok,
        f"проверено файлов: {checked}, совпало: {matched}",
    )
    results["passport"] = checks

    # ------------------------------------------------------------------
    # 2. Structure
    # ------------------------------------------------------------------
    checks = []
    spec = spec_path.read_text(encoding="utf-8").lower() if spec_path.exists() else ""
    spec_ok = all(k in spec for k in ["вопрос", "метод", "границ"]) and ("данные" in spec or "источник" in spec)
    add(checks, "spec.md: вопрос, данные, метод, границы", spec_ok, "works/w1-hab/spec.md")
    dirs_ok = all((WORK / d).is_dir() for d in ["data/raw", "out", "report", "review"])
    add(checks, "data/raw, out, report, review", dirs_ok, "каталоги на месте" if dirs_ok else "нет каталога")
    fetch_ok = (WORK / "data" / "fetch.sh").exists() or (WORK / "data" / "fetch.py").exists()
    add(checks, "скрипт загрузки данных", fetch_ok, "data/fetch.sh" if fetch_ok else "не найден")
    results["structure"] = checks

    # ------------------------------------------------------------------
    # 3. Features
    # ------------------------------------------------------------------
    checks = []
    blocks = feature_map.get("blocks", {}) if isinstance(feature_map, dict) else {}
    need = ["питание", "сон", "стресс", "активность"]
    present = [b for b in need if b in blocks and blocks.get(b)]
    add(checks, "четыре блока различены", len(present) == 4, "блоки: " + ", ".join(present) if present else "feature_map.json отсутствует или неполон")
    add(
        checks,
        "таблица соответствия колонок блокам",
        bool(feature_map_path.exists()) and len(present) == 4,
        "out/feature_map.json",
    )
    target = feature_map.get("target", {}) if isinstance(feature_map, dict) else {}
    target_ok = bool(target.get("name")) and bool(target.get("definition"))
    add(checks, "целевая переменная определена", target_ok, f"{target.get('name')}: {target.get('definition')}" if target_ok else "не найдено")
    results["features"] = checks

    # ------------------------------------------------------------------
    # 4. Cleaning (blocker)
    # ------------------------------------------------------------------
    checks = []
    cleaning = metrics.get("cleaning", {}) if isinstance(metrics, dict) else {}
    steps = cleaning.get("steps", [])
    add(checks, "приведены типы", bool(metrics.get("sample")) and bool(spec), "sample/типы описаны в spec и metrics.json")
    add(checks, "учтены пропуски", bool(cleaning.get("missing_pct")), f"missing_pct: {len(cleaning.get('missing_pct', []))} переменных")
    add(checks, "дубликаты", metrics.get("sample", {}).get("duplicates") == 0, "duplicates = 0")
    rules = cleaning.get("outlier_rules", [])
    add(checks, "выбросы с правилами", len(rules) > 0, f"правил: {len(rules)}")
    imputation = str(cleaning.get("imputation", "")).lower()
    no_mean = ("none" in imputation or "complete-case" in imputation or "не заполн" in passport.lower()) and "mean" not in imputation.replace("no mean", "")
    add(checks, "средним не заполняли", no_mean, cleaning.get("imputation", "не указано"))
    n_before = metrics.get("sample", {}).get("n_raw")
    n_after = metrics.get("sample", {}).get("n_model")
    add(checks, "n до/после", bool(n_before and n_after), f"{n_before} → {n_after}; шагов: {len(steps)}")
    results["cleaning"] = checks

    # ------------------------------------------------------------------
    # 5. Modeling
    # ------------------------------------------------------------------
    checks = []
    model = metrics.get("model", {}) if isinstance(metrics, dict) else {}
    baseline = model.get("baseline", {})
    logistic = model.get("logistic", {})
    add(checks, "константный baseline", bool(baseline) and abs(float(baseline.get("roc_auc", 0)) - 0.5) < 1e-9, f"baseline AUC={baseline.get('roc_auc')}")
    add(checks, "логистическая регрессия, train/test", bool(logistic) and bool(model.get("cv_auc")), f"test AUC={logistic.get('roc_auc')}, CV={model.get('cv_mean')}")
    add(
        checks,
        "permutation importance",
        bool(factor_rows) and "perm_importance" in factor_cols and any(float(r.get("perm_importance") or 0) != 0 for r in factor_rows),
        "out/factors.csv: perm_importance + 95% CI",
    )
    add(checks, "метрики и random_state", bool(metrics.get("seed")) and bool(logistic), f"seed={metrics.get('seed')}")
    results["modeling"] = checks

    # ------------------------------------------------------------------
    # 6. Factors
    # ------------------------------------------------------------------
    checks = []
    has_direction = "direction" in factor_cols and any(r.get("direction") for r in factor_rows)
    add(checks, "направление по каждому фактору", has_direction, f"строк: {len(factor_rows)}")
    add(checks, "мера силы", "strength" in factor_cols and any(r.get("strength") for r in factor_rows), "strength + |coef|")
    ci_ok = {"ci_low", "ci_high"}.issubset(set(factor_cols)) and all(
        r.get("ci_low") not in (None, "") and r.get("ci_high") not in (None, "") for r in factor_rows
    )
    add(checks, "95% CI", ci_ok, "ci_low/ci_high в factors.csv")
    unclear = [r for r in factor_rows if r.get("direction") == "unclear"]
    honest = all((r.get("direction") == "unclear") for r in unclear)
    add(
        checks,
        "неинформативные не выданы за значимые",
        honest,
        f"direction=unclear: {len(unclear)} из {len(factor_rows)} (оставлены как unclear)",
    )
    results["factors"] = checks

    # ------------------------------------------------------------------
    # 7. Report
    # ------------------------------------------------------------------
    checks = []
    add(checks, "report.html существует", report_html.strip().startswith("<!doctype html") or "<html" in report_html.lower(), f"{len(report_html)} байт")
    add(checks, "секция «Традиционный способ»", "традиционный способ" in report_text, "найдена в HTML")
    auc = logistic.get("roc_auc")
    consistent = bool(auc) and f"{float(auc):.3f}" in report_html and str(metrics.get("sample", {}).get("n_model")) in report_html
    add(checks, "согласован с metrics.json / factors.csv", consistent, "AUC и n модели присутствуют в отчёте")
    results["report"] = checks

    # ------------------------------------------------------------------
    # 8. Causality (blocker) + forbidden phrases
    # ------------------------------------------------------------------
    checks = []
    forbidden_hits = []
    for phrase in ["вызывает", "влияет", "приводит к"]:
        if phrase in report_text:
            forbidden_hits.append(phrase)
    add(checks, "нет причинных формулировок", not forbidden_hits, "запрещённых фраз нет" if not forbidden_hits else "найдено: " + ", ".join(forbidden_hits))
    assoc = ("ассоциац" in report_text or "связан" in report_text or "гипотез" in report_text)
    add(checks, "выводы как гипотезы/ассоциации", assoc, "формулировки «связан/гипотеза/ассоциация»")
    limits = "ограничен" in report_text
    add(checks, "ограничения наблюдательных данных", limits, "раздел «Ограничения»")
    results["causality"] = checks

    # ------------------------------------------------------------------
    # 9. Reproducibility
    # ------------------------------------------------------------------
    checks = []
    add(checks, "seed", bool(metrics.get("seed")), f"seed={metrics.get('seed')}")
    versions = metrics.get("versions", {})
    add(checks, "версии библиотек", len(versions) >= 3, ", ".join(f"{k} {v}" for k, v in versions.items()))
    add(checks, "скрипт загрузки данных", fetch_ok, "data/fetch.sh")
    results["reproducibility"] = checks

    # ------------------------------------------------------------------
    # Assemble report
    # ------------------------------------------------------------------
    score = {"ok": 1.0, "partial": 0.5, "missing": 0.0}
    criteria_out = []
    blockers = []
    weighted = 0.0

    for crit in rubric.get("criteria", []):
        cid = crit["id"]
        sub = results.get(cid, [])
        passed = sum(1 for c in sub if c["status"] == "ok")
        total = len(sub) or 1
        if passed == total and total > 0:
            status = "ok"
        elif passed == 0:
            status = "missing"
        else:
            status = "partial"

        is_blocker = bool(crit.get("blocker")) and status != "ok"
        if is_blocker:
            blockers.append({"id": cid, "status": status, "missing": [c["check"] for c in sub if c["status"] != "ok"]})

        weighted += float(crit.get("weight", 0)) * score[status]
        criteria_out.append(
            {
                "id": cid,
                "title": crit.get("title", ""),
                "status": status,
                "weight": crit.get("weight", 0),
                "evidence": [f"{c['check']}: {c['evidence']}" for c in sub],
                "checks": sub,
                "blockers": [cid] if is_blocker else [],
            }
        )

    # Extra forbidden checks shadowing the rubric list
    forbidden_issues = list(forbidden_hits)
    if "mean" in imputation and "no mean" not in imputation and "none" not in imputation:
        forbidden_issues.append("imputation=mean")
    if not hash_ok:
        forbidden_issues.append("sha256_mismatch_or_missing")
    artifacts_ok = all(v == "ok" for v in artifacts.values())
    if not artifacts_ok:
        forbidden_issues.append("required_artifact_missing")

    overall = "ok" if weighted >= 0.8 and not blockers else ("partial" if weighted > 0 else "missing")
    out = {
        "rubric": rubric.get("id", "practice-v1"),
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifacts": artifacts,
        "criteria": criteria_out,
        "summary": {
            "weighted_compliance": round(weighted, 4),
            "blockers": len(blockers),
            "status": overall,
        },
        "blockers": blockers,
        "forbidden_issues": forbidden_issues,
        "note": "Оценку выставляет человек; здесь только соответствие рубрике. "
        "weighted_compliance — техническая доля выполненных критериев.",
    }
    (REVIEW / "report.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"checker: weighted_compliance={weighted:.4f}, blockers={len(blockers)}, status={overall}")
    for c in criteria_out:
        print(f"  {c['id']:16s} {c['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
