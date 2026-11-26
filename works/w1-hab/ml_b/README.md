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
| `out/factors.csv` | **каноническая** таблица OR/CI (train-only) в публичной схеме + `ci_scope`, `n_boot`, `sign_stability`, `conclusion` |
| `handover/stability.json` | seed’ы, подвыборки, CV, ранжирование блоков, KT-3 |
| `handover/MLB_SUMMARY.md` | человекочитаемая сводка ML-B |
| `handover/report_mlb_section.html` | готовый HTML-фрагмент для обоих отчётов |
| `report/importance_ci.svg` | важность блоков с 95% CI (без matplotlib) |
| `out/metrics.json` | секция `ml_b` (ci_scope, n_boot, seed/подвыборки/CV, ranking) |

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

## Канонический CI

`out/factors.csv` — **каноническая** таблица: β и bootstrap-CI посчитаны только
на train (n = 2988), test в ресэмплирование не входит; это же отражено в
`ci_scope = train (n=2988; test excluded)`.

Ранее ML-A писал в `out/factors.csv` β/CI на полной выборке (n = 3984, включая
test). Эти числа больше не используются для OR/CI. Историческое сравнение
сохранено в `stability.json → mla_comparison`; у части факторов (`phq_mean`,
`log_kcal`, отдельные уровни `RIDRETH1`) train-CI включает 1, поэтому их
направление — `unclear`. `MLB_SUMMARY.md` фиксирует, какой CI канонический.

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
