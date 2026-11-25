# w1-hab — Привычки и здоровье

## Вопрос

Связаны ли характеристики **питания, сна, стресса и физической активности** с
бинарным исходом здоровья, и насколько эти связи устойчивы? Для каждого фактора
нужны направление, сила и 95% доверительный интервал.

Причинность не устанавливается: данные наблюдательные.

## Данные

| Параметр | Значение |
|---|---|
| Источник | NHANES 2017–2018 (основная), BRFSS 2024 и AI4FoodDB (внешние проверки); ссылки в `data/PASSPORT.md` |
| Лицензия | NHANES/BRFSS — public domain; AI4FoodDB — CC BY-NC-ND 4.0 |
| Целостность | sha256 в `data/PASSPORT.md`, сверяется с файлом |
| Файлы | `data/raw/` |
| Загрузка | `python data/fetch.py` или `data/fetch.sh <url> [filename]` |
| Единица наблюдения | человек (NHANES, BRFSS, AI4FoodDB); независимые выборки |
| Целевая переменная | **ожирение**: ИМТ ≥ 30 кг/м² (NHANES — измеренный; BRFSS — самоотчёт) |

Паспорт заполнен, хеши сверены; анализ воспроизводится через `python analysis.py`.

## КТ-1: контракт целей и передачи

### 1. Метки, роли и пороги

| Метка | Роль | Определение | Данные | Порог |
|---|---|---|---|---|
| `obesity` | **primary** | ИМТ ≥ 30 кг/м² | NHANES (измеренный); BRFSS — внешняя проверка | 30 |
| `hypertension` | secondary | САД ≥130 или ДАД ≥80 или приём гипотензивных | NHANES | 130/80 |
| `hypertension_140_90` | sensitivity | САД ≥140 или ДАД ≥90 или приём гипотензивных | NHANES | 140/90 |
| `high_pulse_80` | secondary | пульс ≥80 уд/мин | NHANES | 80 |
| `high_pulse` | sensitivity | пульс >90 уд/мин | NHANES | 90 |
| `sleep_disorder` | secondary | диагностированное нарушение сна (`SLQ050=1`) | NHANES | диагноз |
| `sleep_disturbance_ai4` | external secondary | DS2 insomnia или somnolence | AI4FoodDB DS2 (n=100) | любой симптом |

**Решение:** primary — только `obesity`; гипертензия 130/80 и пульс ≥80 —
secondary; 140/90 и пульс >90 — sensitivity. `DS2 insomnia/somnolence` и
Oviedo — внешний secondary AI4FoodDB, **не primary**. Цифры 50 / 54.5 / 20.2 /
31% — это AI4FoodDB baseline V0 (DS1/DS6/DS2, n=99–100), они воспроизводятся
и записаны в корневом `PASSPORT.md`; к NHANES они не относятся.

**Два паспорта:** корневой `PASSPORT.md` (команда, AI4FoodDB V0 primary,
NHANES 2021–2023) — источник меток и порогов; рабочий
`works/w1-hab/data/PASSPORT.md` (NHANES 2017–2018) — фактическая модель ML-A.
Для HAB-01 ML-A использует NHANES как primary: n=3 984 против 100 и все четыре
блока измерены на человеке; AI4FoodDB остаётся внешней проверкой. Разница
циклов NHANES (2017–2018 vs 2021–2023) — известное ограничение, а не скрытая
подмена данных. Если команда решит сделать AI4FoodDB primary, ML-A нужно
переобучить на AI4 и пересобрать отчёт.

### 2. Четыре блока признаков

| Блок | Колонки | Смысл |
|---|---|---|
| Питание | `log_kcal`, `log_prot`, `log_fat`, `log_carb`, `log_fiber`, `log_pota`, `log_water` | энергия, макронутриенты, клетчатка, калий, вода |
| Сон | `SLD012`, `SLQ120`, `SLQ050` | длительность, восстановление, диагноз нарушения сна |
| Стресс | `phq_mean` | средний балл PHQ-9, прокси эмоционального дистресса |
| Активность | `log_mvpa`, `sed` | MVPA, сидячее время |
| Контроль | `RIDAGEYR`, `RIAGENDR`, `RIDRETH1`, `DMDEDUC2`, `SMQ020` | возраст, пол, раса, образование, курение |

ИМТ (`BMXBMI`) — target, не признак. Точное соответствие — `out/feature_map.json`.

### 3. Паспорт ML-A

| Параметр | Значение |
|---|---|
| Seed | 42 |
| Split | 75/25, stratify, 2 988 train / 996 test |
| Метрика | ROC AUC |
| Target | `obesity` (ИМТ ≥ 30) |
| Модель | L2-логистическая регрессия, `max_iter=2000` |
| Preprocessing | `StandardScaler` + `OneHotEncoder(drop="first")` внутри Pipeline |
| Важность | permutation importance на test, 1 000 повторов; отдельно признаки и блоки |
| Выход | `out/metrics.json`, `out/factors.csv`, `handover/` |

### 4. Паспорт ML-B

| Вход | Что делает | Выход |
|---|---|---|
| `handover/model.joblib` | не переобучает на test | — |
| `handover/test_set.csv` | permutation importance и проверка | метрики |
| `handover/model_dataset.csv` | bootstrap-CI по train/full | `out/factors.csv` |
| `handover/contract.json` | seed, split, features, blocks, hashes | — |

ML-B принимает: β, OR, 95% bootstrap CI, направление, силу; проверяет
устойчивость по seed’ам/подвыборкам и сверяет ранжирование с
`handover/kt3_consistency.md`. Если 95% CI пересекаются — ранг не объявляется.

### 5. Формат передачи ML-A → ML-B

| Артефакт | Формат | Содержание |
|---|---|---|
| `handover/model.joblib` | joblib / sklearn Pipeline | обученная модель (только train) |
| `handover/test_set.csv` | CSV, UTF-8 | 996 строк: `SEQN`, признаки, target |
| `handover/model_dataset.csv` | CSV, UTF-8 | 3 984 строки + колонка `split` |
| `handover/contract.json` | JSON | seed, метрика, target, признаки, блоки, split, sha256, версии |
| `handover/CARD.md` | Markdown | человекочитаемая карточка |
| `handover/importance.py` | Python CLI | permutation importance на test |
| `handover/verify.py` | Python | проверка модели, test set и contract |

Проверка: `python handover/verify.py` → `handover OK`; `python handover/importance.py --repeats 1000`.

## Блоки признаков

Состав блоков зафиксирован в КТ-1 выше; точное соответствие колонок —
`out/feature_map.json`.

## Метод

1. Проверка паспорта и хешей.
2. Сбор четырёх блоков, явное определение target.
3. Очистка: типы, пропуски, дубликаты, выбросы. **Средним не заполняем**;
   для модели — complete-case, категории кодируются one-hot (неизвестные
   уровни в тесте игнорируются).
4. Baseline (доля положительного класса) → логистическая регрессия
   (стандартизация, one-hot, stratify, фиксированный seed).
5. Permutation importance на test, 1000 перестановок; bootstrap 1000 для
   коэффициентов и 95% CI.
6. `out/metrics.json`, `out/factors.csv`, `report/report.html`,
   `report/report_engineer.html`.
7. Проверка checker по `shared/rubric/practice-v1.json`.

## Границы

- Наблюдательные данные: ассоциации, не причины.
- Самоотчёт подвержен смещению; возможны конфаундеры и обратная причинность.
- Пропуски и отбор участников ограничивают обобщение.
- Результат — гипотезы для дальнейших исследований, а не рекомендации.

## Артефакты

```
works/w1-hab/
  spec.md
  analysis.py
  notebook.ipynb
  requirements.txt
  ml_a/                      контракт, Pipeline, тесты, handover
  handover/                  модель, test set, contract, CARD, KT-3
  data/{PASSPORT.md,fetch.py,fetch.sh,raw/}
  out/{metrics.json,factors.csv,feature_map.json}
  report/{report.html,report_engineer.html}
  review/{report.json,llm_report_review.md}
```

## Готово, когда

- паспорт полон, sha256 совпадает;
- все четыре блока размечены, очистка описана с n до/после;
- baseline и модель сравнены, у факторов есть направление/сила/95% CI;
- отчёт содержит секцию «Традиционный способ»;
- отчёт собран в двух стилях — яркий и инженерный;
- выводы сформулированы как гипотезы;
- checker записал `review/report.json` (оценку ставит человек).
