# Handover ML-A → ML-B

Это готовый пакет для ML-B: модель уже обучена на train, test не трогали.

## Файлы

| Файл | Что делать |
|---|---|
| `model.joblib` | загрузить через `joblib.load`; это `Pipeline`, готовый к `predict_proba` |
| `test_set.csv` | использовать для permutation importance и метрик; **не обучать на нём** |
| `model_dataset.csv` | полная выборка с колонкой `split`; нужна для bootstrap-CI |
| `contract.json` | seed, метрика, признаки, блоки, split, хеши — читать программно |
| `metrics.json` | краткая карточка: AUC, CV, Brier, n |
| `CARD.md` | человекочитаемая карточка handover |
| `kt3_consistency.md` | сверка направлений ML и «Традиционного способа» |
| `importance.py` | готовый скрипт permutation importance |
| `importance.csv`, `importance_blocks.csv` | результат прогона 1000 повторов |

## Быстрый старт

```bash
cd works/w1-hab
python handover/verify.py
python handover/importance.py --repeats 1000
```

Скрипт печатает baseline test AUC, таблицу блоков и топ признаков; пишет
`importance.csv` и `importance_blocks.csv`.

## Что делать ML-B

1. Проверить `contract.json`: seed, split, target, features.
2. Взять `model_dataset.csv`, колонку `split` — train/test.
3. Bootstrap-CI для коэффициентов/OR: ресэмплировать **train**, при желании
   проверять на test; не подгонять preprocessing на test.
4. Устойчивость: seed’ы, подвыборки, CV.
5. Сравнить ранжирование блоков с `importance_blocks.csv` и с
   `kt3_consistency.md`.
6. Оформить `out/factors.csv` (β, 95% CI, вывод) и диаграмму важности с CI.

## Важно

- Тестовая выборка — 996 строк, 432 события; одна и та же для всех сравнений.
- `model.joblib` обучен только на train; не переобучать на полном наборе для
  метрик test.
- Направления в `kt3_consistency.md` — ассоциации; причинность не заявляется.
- Если меняешь seed/split — обнови `contract.json` и пересобери handover, иначе
  числа перестанут биться с отчётом.
