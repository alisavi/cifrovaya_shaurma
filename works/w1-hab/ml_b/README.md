# ML-B package (`ml_b`)

ML-B не переобучает модель «с нуля» и не меняет контракт. Задача — **независимо
проверить handover ML-A**, построить bootstrap-CI коэффициентов/OR **на train**,
проверить устойчивость и сверить выводы с KT-3.

## Запуск

```powershell
cd works/w1-hab
python handover/verify.py
python ml_b/run.py
python -m unittest discover -s ml_b/tests -v
```

`ml_b/run.py` читает только `handover/` и пишет:

| Файл | Что внутри |
|---|---|
| `handover/factors_mlb.csv` | β, OR, 95% bootstrap CI, direction, strength, устойчивость знака, вывод |
| `handover/stability.json` | seed’ы, подвыборки, CV, ранжирование блоков, KT-3, сверка с `out/factors.csv` |
| `handover/MLB_SUMMARY.md` | человекочитаемая сводка ML-B |
| `report/importance_ci.svg` | важность блоков с 95% CI (без matplotlib) |

## Метод

- **Данные:** `model_dataset.csv`, колонка `split`; test (996 строк) не участвует
  в обучении. SEQN train/test проверяются на пересечение.
- **Bootstrap:** preprocessing (`StandardScaler` + `OneHotEncoder`) обучается на
  train, затем 1000 раз ресэмплируются строки train и переобучается
  логистическая регрессия. 95% CI — перцентили 2.5/97.5.
- **Seed-устойчивость:** 10 альтернативных стратифицированных split’ов
  (seed 42 воспроизводит handover). Это sensitivity analysis; отчётная метрика
  остаётся на фиксированном test.
- **Подвыборки:** 200 × 80% train без возвращения.
- **CV:** 5-fold на train, ROC AUC.
- **Ранжирование блоков:** блочная permutation importance на test каждого
  альтернативного split’а, сравнение с `handover/importance_blocks.csv`.
- **KT-3:** сверка направления и значимости с `handover/kt3_consistency.csv`.

## Важное расхождение

`out/factors.csv` ML-A считает β и bootstrap-CI на **полной выборке** (n = 3984,
включая test). Handover требует ресэмплировать **train**. Поэтому ML-B считает
OR/CI на n = 2988; у части факторов (`phq_mean`, `log_kcal`, отдельные уровни
`RIDRETH1`) CI на train включает 1. Это зафиксировано в `MLB_SUMMARY.md` и
`stability.json → mla_comparison`. Для отчёта нужно выбрать одну таблицу OR/CI и
явно указать её выборку.

## Windows и sha256

Git может выгружать CSV с CRLF, тогда sha256 байтов не совпадает с контрактом,
хотя контент идентичен. `ml_b/data.py` проверяет и байтовый, и LF-нормализованный
хеш: расхождение только по переводам строк — предупреждение, реальное
расхождение контента — ошибка.

## Границы

- Только ассоциации, не причинность.
- Альтернативные split’ы и подвыборки — проверка устойчивости, а не новые
  отчётные метрики.
- Блочная permutation-важность зависит от корреляции блоков.
- Survey-веса не применялись; выборка complete-case.
