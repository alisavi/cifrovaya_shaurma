# ML-A → ML-B handover

**Задача:** HAB-01, тема «Привычки и здоровье».
**Владелец:** ML-A (Шайбал Экрам). **Получатель:** ML-B (Павел Комов).
**Дата:** 2026-11-26 16:16 UTC.

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

- Seed: **42**, split: **2988 train / 996 test**,
  stratify по target, test_size = 0.25.
- Target: **obesity** — BMI >= 30 kg/m2 (measured height and weight).
- Метрика: **roc_auc**; baseline AUC = 0.500.
- Признаки: 18; блоки: питание, сон, стресс, активность, контроль.
- Модель: L2-логистическая регрессия, `max_iter=2000`, `random_state=42`.

## Метрики (test)

| Метрика | Baseline | Logit |
|---|---:|---:|
| ROC AUC | 0.500 | 0.667 |
| PR AUC | 0.434 | 0.599 |
| Accuracy | 0.566 | 0.624 |
| Balanced accuracy | 0.500 | 0.606 |
| Brier | 0.246 | 0.224 |

CV ROC AUC (5-fold, train): **0.661 ± 0.034**.

## Хеши данных

| Файл | sha256 |
|---|---|
| `model_dataset.csv` | `cea4b68e0a62cae195ce2cb7d1ef6c091ceac2f101e048d6477340fb4950e29f` |
| `test_set.csv` | `00d01864f9e3fc9aeb215691083db3a27528345482a8fc56b90538ee15f91731` |

## KT-3: ML vs «Традиционный способ»

- **Питание: клетчатка**: направление согласуется, но ML CI включает 1 (ML OR 0.90, CI 0.80–1.00).
- **Сон**: направление согласуется, но ML CI включает 1 (ML OR 0.96, CI 0.91–1.03).
- **Стресс**: согласуется по направлению (ML OR 1.09, CI 1.01–1.18).
- **Активность**: согласуется по направлению (ML OR 1.22, CI 1.14–1.32).

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

- Complete-case: 3984 из 9254 строк исходного файла
  (см. `out/metrics.json` и паспорт) — выборка смещена к полным наблюдениям.
- Один 24-ч дневник питания, самоотчёт о сне, PHQ-9 — прокси стресса.
- Абсолютные потребления нутриентов могут отражать размер тела и недоучёт.
