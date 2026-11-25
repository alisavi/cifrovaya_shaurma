# w1-hab — Привычки и здоровье

Наблюдательный анализ связи четырёх блоков привычек — **питание, сон, стресс,
физическая активность** — с ожирением (ИМТ ≥ 30). Для каждого фактора:
направление, сила (OR на 1 SD или уровень против референса) и 95% CI.

> Это анализ **ассоциаций**, а не причинности. Все выводы в отчёте —
> гипотезы для дальнейшей проверки.

## Данные

| Массив | Роль | Что даёт | Лицензия |
|---|---|---|---|
| NHANES 2017–2018 | основная модель | измеренные ИМТ/давление/пульс, 24-ч дневник питания, сон, PHQ-9, активность | public domain |
| BRFSS 2024 | репликация | стресс, активность, самоотчётный ИМТ; n = 50 000 | public domain |
| AI4FoodDB | внешняя проверка | DASS-21, сон, IPAQ; n = 95 | CC BY-NC-ND 4.0 |

Ссылки, единицы, невозможные значения и sha256 — в
[`data/PASSPORT.md`](data/PASSPORT.md). Три массива независимы и не
соединяются по участникам.

> Командный корневой `PASSPORT.md` описывает AI4FoodDB baseline V0
> (n≈100). Рабочая модель ML-A построена на NHANES 2017–2018 (n=3 984);
> согласование меток и порогов — в [`spec.md`](spec.md), раздел КТ-1.
> AI4FoodDB остаётся внешней проверкой.

## Главные результаты

- Модель: n = 3 984, ожирение у 43,3%, test ROC AUC = 0,667, CV AUC = 0,661.
- Вклад блоков (Δ ROC AUC, 95% CI): питание 0,041 (0,022–0,060), сон 0,020
  (0,007–0,034), активность 0,016 (0,004–0,027), стресс 0,001 (−0,003–0,006).
  Точечно лидирует питание, но интервалы пересекаются — ранг между блоками
  не устойчив.
- Калий (прокси овощей/фруктов) OR 0,68 (0,59–0,77); калории 0,71
  (0,50–0,95); белок 1,31 (1,14–1,49); сидячее время 1,22 (1,14–1,32).
- Стресс (PHQ-9): OR 1,09 (1,01–1,18) в NHANES, 1,27 (1,20–1,34) в BRFSS,
  но permutation-вклад блока неотличим от нуля. Связь слабая.
- BRFSS: AUC in-sample 0,611, CV 0,610; AI4FoodDB: CV AUC 0,400, n = 95 —
  результат разведочный.
- Традиционный анализ (доли, χ², простые OR) и счёт из четырёх флагов —
  в разделе «Традиционный способ» обоих отчётов.

## Два стиля отчёта

- [`report/report.html`](report/report.html) — яркая версия для защиты:
  вывод в заголовке, три крупных числа, графики, «сколько это стоит».
- [`report/report_engineer.html`](report/report_engineer.html) — инженерная
  версия для проверки: метаданные, sha256, β и 95% CI по каждому фактору,
  плотные таблицы.

Содержание и числа в них одинаковые; меняется только подача. Оба отчёта
содержат секцию «Традиционный способ» и оговорку «связь ≠ причинность».

## Запуск

```bash
pip install -r requirements.txt
python data/fetch.py      # скачать сырые данные (≈1.2 ГБ, пропускает уже скачанное)
python analysis.py        # очистка → baseline → логит → permutation → отчёты → checker
```

`analysis.py` на этой машине занимает ≈1,5 мин: 1 000 bootstrap-ресэмплов и
1 000 permutation-повторов. Результаты:

- `out/metrics.json` — выборка, очистка, метрики модели, вклады блоков,
  традиционный анализ, внешние проверки, время прогона;
- `out/factors.csv` — OR, 95% CI, направление, сила, permutation importance,
  p-value по каждому фактору;
- `out/feature_map.json` — соответствие блоков и колонок;
- `report/report.html` и `report/report_engineer.html` — два стиля отчёта;
- `review/report.json` — техническая проверка по
  `shared/rubric/practice-v1.json` (оценку ставит человек);
- `review/llm_report_review.md` — журнал LLM-ревью отчёта.

## ML-A: модель и handover

ML-A-часть вынесена в пакет [`ml_a/`](ml_a/README.md):

- `ml_a/config.py` — контракт: seed 42, split 75/25, ROC AUC, 18 признаков,
  четыре блока + контроль; сверяется с `out/feature_map.json`.
- `ml_a/pipeline.py` — preprocessing внутри Pipeline, один fit на train,
  permutation importance по закодированным признакам и целым блокам.
- `ml_a/tests/` — 8 контрактных тестов (split, утечка, importance, roundtrip).
- [`handover/`](handover/README.md) — модель, test set, contract, CARD и KT-3
  для ML-B.

```bash
python ml_a/run.py
python -m unittest discover -s ml_a/tests -v
python handover/importance.py --repeats 1000
```

Handover: `model.joblib`, `test_set.csv` (996 строк), `model_dataset.csv`
(3 984 строки + split), `contract.json`, `CARD.md`, `kt3_consistency.md`.

## ML-B: bootstrap и устойчивость

ML-B-часть вынесена в пакет [`ml_b/`](ml_b/README.md):

- `ml_b/bootstrap.py` — bootstrap-CI коэффициентов и OR **только на train**,
  preprocessing обучается на train; direction/strength/устойчивость знака.
- `ml_b/stability.py` — 10 альтернативных split’ов, 200 подвыборок 80% train,
  5-fold CV, ранжирование блоков permutation importance.
- `ml_b/data.py` — проверка контракта, хешей (включая CRLF-нормализацию) и
  отсутствия пересечения train/test по `SEQN`.
- `ml_b/run.py` — сводный прогон и запись артефактов.
- `ml_b/tests/` — 9 тестов на bootstrap, direction, устойчивость, хеши, график.

```bash
python ml_b/run.py
python -m unittest discover -s ml_b/tests -v
```

Результаты: `handover/factors_mlb.csv`, `handover/stability.json`,
`handover/MLB_SUMMARY.md`, `report/importance_ci.svg`.

Важно: `out/factors.csv` ML-A считает β/CI на полной выборке (n = 3 984), а
ML-B — на train (n = 2 988). У `phq_mean` и `log_kcal` CI на train включает 1;
расхождение разобрано в `MLB_SUMMARY.md`.

## Структура

```
works/w1-hab/
  spec.md                    вопрос, данные, метод, границы
  analysis.py                весь конвейер и генерация двух отчётов
  notebook.ipynb             20 ячеек: паспорт → очистка → модель → факторы
  requirements.txt
  ml_a/                      ML-A: контракт, Pipeline, тесты, handover
  ml_b/                      ML-B: bootstrap, устойчивость, тесты
  handover/                  модель, test set, contract, CARD, KT-3, ML-B артефакты
  data/PASSPORT.md           источники, лицензии, единицы, sha256
  data/fetch.py              воспроизводимая загрузка
  out/                       итоговые артефакты
  report/report.html         яркая версия
  report/report_engineer.html инженерная версия
  report/importance_ci.svg   важность блоков с CI (ML-B)
  review/report.json         checker
  review/llm_report_review.md
```

## Ограничения

- Один 24-часовой дневник питания; самоотчёт о сне; PHQ-9 — прокси стресса,
  а не шкала стресса.
- Complete-case: 3 984 из 9 254 строк; выборка смещена к тем, у кого есть все
  измерения.
- Питание измерено с ошибкой; калории и вода отражают в том числе размер тела.
- NHANES/BRFSS survey-веса не применялись: оценки описательные, не
  популяционные.
- Причинность не устанавливается: возможны конфаундеры и обратная причинность.
