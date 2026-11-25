# ML-A package (`ml_a`)

ML-A отвечает за окружение, Pipeline, seed, первый и финальный fit, ROC AUC,
permutation importance по блокам и передачу модели ML-B.

Пакет выделен из `analysis.py`, чтобы у ML-A был **явный контракт**, который
можно проверить тестами и передать без чтения всего проекта.

## Состав

| Файл | Назначение |
|---|---|
| `config.py` | seed, split, метрика, target, список признаков и блоков; сверка с `out/feature_map.json` |
| `pipeline.py` | `StandardScaler` + `OneHotEncoder` + `LogisticRegression`, split, permutation importance по закодированным признакам |
| `handover.py` | запись `handover/`: модель, test set, contract, CARD, KT-3 |
| `run.py` | `python ml_a/run.py` — обучить и собрать handover |
| `tests/test_contract.py` | контрактные тесты (split, утечка, importance, roundtrip) |

## Контракт

- **Seed:** 42, **split:** 75/25, stratify по target.
- **Target:** `obesity` = ИМТ ≥ 30 (измеренный).
- **Метрика:** ROC AUC.
- **Признаки:** 18, четыре блока привычек + контроль.
- **Модель:** L2-логистическая регрессия, `max_iter=2000`.
- **Один fit на train:** evaluated-модель не видит test; preprocessing
  (`StandardScaler`, `OneHotEncoder`) обучается внутри Pipeline на train.

## Запуск

```bash
cd works/w1-hab
python ml_a/run.py                      # ≈1,5 мин: fit + 1000 bootstrap + 1000 permutation
python -m unittest discover -s ml_a/tests -v
python handover/verify.py
python handover/importance.py --repeats 1000
```

`analysis.py` вызывает тот же `fit_primary`, поэтому отчёт и handover не
расходятся по числам.

## Почему так

- **AUC, а не accuracy:** классы несбалансированы (43% событий), accuracy
  обманчива; AUC показывает разделение на всём диапазоне порогов.
- **Permutation importance на test:** важность измеряется на данных, которые
  модель не видела; иначе она показывает запоминание train.
- **Permutation по закодированным столбцам:** иначе все one-hot уровни одной
  категории получают одинаковую важность и таблица вводит в заблуждение.
- **Блочная permutation:** перемешиваем все столбцы блока вместе — это отвечает
  на вопрос «сколько теряет модель без блока», а не «какой столбец самый
  важный».
- **log1p для нутриентов и MVPA:** распределения с длинным правым хвостом;
  лог уменьшает влияние экстремумов, обратное преобразование не требуется,
  потому что OR считается на 1 SD лога.
- **`drop="first"` в one-hot:** убирает линейную зависимость между dummies;
  референсный уровень фиксирован и указан в отчёте.

## Границы

- Это ассоциативная модель, не причинная.
- Абсолютные нутриенты коррелируют с размером тела и недоучётом; OR не «эффект».
- Survey-веса не применялись; выводы описательные.
- Bootstrap-CI и устойчивость (seed’ы, подвыборки) — зона ML-B, не этого пакета.
