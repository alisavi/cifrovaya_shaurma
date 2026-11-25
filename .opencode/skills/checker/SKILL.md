---
name: checker
description: Проверяет работу w1-hab по рубрике shared/rubric/practice-v1.json и пишет review/report.json со статусами ok / partial / missing. Оценку не выставляет.
version: 1
---

# Checker: проверка по рубрике

## Входы

- `shared/rubric/practice-v1.json` — критерии, веса, обязательные артефакты.
- `works/w1-hab/` — проверяемая работа.
- `spec.md` — заявленные вопрос, данные и границы.

## Порядок проверки

1. Прочитай рубрику. Если её нет — запиши blocker `rubric_missing` и не
   придумывай критерии.
2. Проверь наличие обязательных артефактов из `required_artifacts`.
3. По каждому критерию собери **evidence**: путь к файлу, фрагмент, число.
4. Присвой статус:
   - `ok` — все проверки критерия выполнены;
   - `partial` — выполнена часть, есть устранимый пробел;
   - `missing` — критерий не выполнен или артефакта нет.
5. Проверь запреты (`forbidden`): причинные формулировки, заполнение пропусков
   средним, отсутствие паспорта, выдуманные ссылка/лицензия/хеш.
6. Ничего не исправляй в работе и не выставляй итоговую оценку человеку.

## Выход: `review/report.json`

```json
{
  "rubric": "practice-v1",
  "checked_at": "ISO-8601",
  "artifacts": { "out/metrics.json": "ok", "out/factors.csv": "missing" },
  "criteria": [
    {
      "id": "passport",
      "status": "ok",
      "weight": 0.12,
      "evidence": ["data/PASSPORT.md: url, license, sha256"],
      "blockers": []
    }
  ],
  "summary": {
    "weighted_compliance": 0.0,
    "blockers": 0,
    "status": "ok | partial | missing"
  },
  "note": "Оценку выставляет человек; здесь только соответствие рубрике."
}
```

`weighted_compliance` — сумма `weight × score(status)` по критериям, где
`ok = 1`, `partial = 0.5`, `missing = 0`. Это не оценка за практику, а
техническая доля выполненных критериев.

## Границы

- Не меняй `out/`, `report/`, `data/`.
- Не запускай модель заново, если артефакты уже есть.
- Не скрывай blockers и не смягчай формулировки.
