# Habits & Health: факторная связь привычек с ожирением

Практикум BMITECH × МФТИ, команда **T3 «Цифровая шаурма»**, Тема 1.
Наблюдательное исследование: как **питание, сон, стресс и физическая
активность** связаны с ожирением (ИМТ ≥ 30) и какой блок сильнее.

> Это анализ **ассоциаций**, а не причинности. Все выводы — гипотезы:
> возможны конфаундеры, обратная причинность и ошибка самоотчёта.

## Быстрые ссылки

- [Описание работы](works/w1-hab/README.md)
- [Яркий отчёт](works/w1-hab/report/report.html) ·
  [Инженерный отчёт](works/w1-hab/report/report_engineer.html)
- [Ноутбук с комментариями](works/w1-hab/notebook.ipynb)
- [Паспорт данных](works/w1-hab/data/PASSPORT.md)
- [Спецификация](works/w1-hab/spec.md)
- [Рубрика](shared/rubric/practice-v1.json) ·
  [Результат checker](works/w1-hab/review/report.json)

## Результаты

| Показатель | Значение |
|---|---|
| Выборка NHANES 2017–2018 | 3 984 человека, 1 726 событий (43,3%) |
| Test ROC AUC / CV AUC | 0,667 / 0,661 |
| Наибольшая точечная важность | питание: Δ AUC 0,041 (0,022–0,060); CI пересекается со сном |
| Сон / активность | 0,020 (0,007–0,034) / 0,016 (0,004–0,027) |
| Стресс (PHQ-9) | 0,001 (−0,003–0,006); OR 1,09 (1,01–1,18) |
| BRFSS 2024, стресс | OR 1,27 (1,20–1,34); CV AUC 0,610 |
| Checker | `weighted_compliance = 1.00`, блокеров 0 |

## Что сдано

- **HAB-01** — паспорт, четыре блока, очистка, baseline → логит →
  permutation importance, факторы с направлением/силой/95% CI, отчёт с
  секцией «Традиционный способ», выводы-гипотезы.
- **MIPT-11** — скиллы `executor` и `checker`, ноутбук из 20 ячеек с
  объяснением «зачем», `review/report.json`.
- **MIPT-12** — два стиля отчёта (яркий и инженерный), `.opencode/opencode.json`
  без ключей, папка работы `works/w1-hab`.

## Структура

```
workspace/
├─ .opencode/
│  ├─ opencode.json            модель, без ключей
│  └─ skills/
│     ├─ executor/SKILL.md     паспорт → очистка → модель → отчёт
│     └─ checker/SKILL.md      проверка по рубрике
├─ bundles/                    education.bundle.json + index.json
├─ shared/
│  ├─ rubric/practice-v1.json  критерии и веса
│  ├─ checker.py               техническая проверка
│  └─ glossary.md
└─ works/w1-hab/
   ├─ spec.md
   ├─ analysis.py              конвейер и два отчёта
   ├─ notebook.ipynb
   ├─ requirements.txt
   ├─ data/{PASSPORT.md,fetch.py,raw/}
   ├─ out/{metrics.json,factors.csv,feature_map.json}
   ├─ report/{report.html,report_engineer.html}
   └─ review/{report.json,llm_report_review.md}
```

## Запуск

```bash
cd works/w1-hab
pip install -r requirements.txt
python data/fetch.py      # ≈1.2 ГБ, пропускает уже скачанное
python analysis.py        # ≈1,5 мин: очистка, модель, два отчёта, checker
```

Проверка отдельно:

```bash
python shared/checker.py  # пишет works/w1-hab/review/report.json
```

## Данные и воспроизводимость

- **NHANES 2017–2018** — измеренные ИМТ, давление, пульс; 24-часовой дневник;
  сон; PHQ-9; активность. Public domain.
- **BRFSS 2024** — стресс, активность, самоотчётный ИМТ; случайные 50 000
  после фильтров. Public domain.
- **AI4FoodDB** — DASS-21, сон, IPAQ, антропометрия; n = 95.
  CC BY-NC-ND 4.0, только исследовательское использование.

Массивы независимы и не соединяются по участникам. Сырые данные в git не
коммитятся; скачивание — `data/fetch.py`, хеши — в паспорте. Seed = 42,
версии библиотек — в `out/metrics.json` и `requirements.txt`.

## Команда и роли

| Роль | Зона |
|---|---|
| ML-A | pipeline, baseline, логит, permutation importance |
| ML-B | bootstrap-CI, устойчивость, `out/factors.csv` |
| Аналитик | паспорт, очистка, EDA, «Традиционный способ», отчёт |

## Ограничения

- Один 24-часовой дневник питания; самоотчёт о сне; PHQ-9 — прокси стресса.
- Complete-case: 3 984 из 9 254 строк; выборка смещена к полным наблюдениям.
- NHANES/BRFSS survey-веса не применялись: оценки описательные.
- AI4FoodDB мал и интервенционный; его результат — разведочный.
- Причинность не устанавливается.
