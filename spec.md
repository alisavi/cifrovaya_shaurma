# spec.md — HAB-01, КТ-1 (согласовано: A, ML-A, ML-B)

## Решение по блоку «Питание»: вариант C

- **Primary (все 100 участников):** DS2 `lifestyle.csv` — water_ml, daily_meals,
  appetite, alcohol, fermented_perc, distilled_perc, meals_weekdays_out,
  meals_weekdays_home, meals_weekend_out, meals_weekend_home.
- **Secondary (25 участников с DS3):** агрегаты из FoodNExtDB — число приёмов
  пищи/день, доли category (Vegetables and Fruits, Protein Sources,
  Cereals and Legumes, Beverages, Oils and Fats), доли cooking_style
  (Fresh, Fried, Grilled, Boiled or Steamed, Oven-Baked).
- **НЕ используем:** ккал / Б / Ж / У / граммы — в DS3 нет данных о порциях;
  без внешней таблицы состава (BEDCA) их не вычислить.

## Целевые переменные

| Метка | Источник | Правило | Доля «1» на baseline | Роль |
|---|---|---|---|---|
| y_obesity | DS1 bmi_kg_m2 | >= 30 | 50.0 % (50/100) | primary |
| y_hypertension | DS6 SBP/DBP | SBP >= 130 or DBP >= 80 | 54.5 % (54/99) | primary |
| y_high_hr | DS6 heart_rate_bpm | >= 80 | 20.2 % (20/99) | primary |
| y_sleep_disturbance | DS2 insomnia or somnolence | == 1 | 31.0 % (31/100) | primary |

Baseline = V0 для DS1/DS6; для DS2 — единственная строка на участника;
для DS3 — агрегат за ~14-дневное окно (к какому визиту относится — фиксируем
в протоколе: окно DS3 соответствует периоду интервенции, связываем с V0/V2
по `id`, без точной привязки к визиту).

## 4 блока признаков

**Общий принцип:** DS2 — «ядро» всех четырёх блоков, доступно 100 участникам
на baseline. DS7 / DS8 / DS9 / DS3 — «обогащение» для подвыборки
(group 2 — 50 участников для DS7/DS8/DS9; DS3 — 25 участников).
Признаки с 50 % пропусков ML-A обрабатывает через импутацию в Pipeline,
ML-B отдельно проверяет устойчивость важности на подвыборке group 2.

### Питание (primary — DS2, secondary — DS3)
**DS2 (primary, 100 участников):** water_ml, daily_meals (ordinal-encode),
appetite, alcohol (ordinal), fermented_perc, distilled_perc,
meals_weekdays_out, meals_weekdays_home, meals_weekend_out,
meals_weekend_home.
**DS3 (secondary, 25 участников):** meals_per_day, food_window_hours,
share_vegetables_fruits, share_protein, share_cereals, share_beverages,
share_oils_fats, share_fresh, share_fried, share_grilled.

### Сон (primary — DS2, secondary — DS8 Oviedo)
**DS2 (primary, 100 участников):** sleep_weekdays, sleep_weekend,
insomnia, somnolence.
**DS8 Oviedo (secondary, 50 участников group 2):** insomnia_score,
somnolence_score, total_score, 6a_hours_sleep — только visit 0 (бывший V1).

### Стресс (primary — DS2, secondary — DS9 DASS-21)
**DS2 (primary, 100 участников):** stress, anxiety, depression (бинарные).
**DS9 DASS-21 (secondary, 50 участников group 2):** stress_score,
anxiety_score, depression_score, total_score — только visit 0 (бывший V1).

### Активность (primary — DS2, secondary — DS7 IPAQ)
**DS2 (primary, 100 участников):** exercise (ordinal-encode).
**DS7 IPAQ (secondary, 50 участников group 2):** total_met,
categorical_score (ordinal), vigorous_met, moderate_met, walking_met —
только visit 0 (бывший V1).

## Протокол ML-A → ML-B

- Метрика: ROC AUC на test; stratified split 70/30, seed=42.
- Один fit на train; Pipeline (импутация → масштабирование → логрегрессия)
  целиком fit'ится на train, transform — на test.
- Permutation importance агрегируется по 4 блокам (среднее по признакам блока).
- ML-B получает: модель, test-набор, код importance, seed, протокол агрегации.
- DS3-secondary: отдельная модель на 25 участниках; результаты — только как
  проверка направления связей, не для финального ранжирования факторов.

## Ограничения (зафиксировано на КТ-1)

1. BRFSS 2024 не содержит SLEPTIM1, АД, пульса. Цели из BRFSS — только
   y_obesity по `_BMI5 >= 3000`. Для сна/АД/пульса BRFSS не используем.
2. DS3 покрывает 25 из 100; ккал/Б/Ж/У из DS3 не вычисляем.
3. Oviedo insomnia_score на baseline V1 — только 50 участников (group 2).
4. DS3: 117 невалидных timestamp, выброс 2014-07-27, `cooking_style` NA 34.6 %
   (структурный — напитки, свежие фрукты).
5. DS7 (IPAQ), DS8 (Oviedo), DS9 (DASS-21) на baseline (visit 0 после
   унификации) доступны только 50 участникам — group 2. Group 1 проходила
   эти опросники на других визитах. В связи с этим DS7/DS8/DS9 — secondary;
   primary-признаки блоков «Сон», «Стресс», «Активность» — из DS2.
6. `fermented_perc` / `distilled_perc` — 35 % NaN (непьющие); ML-A обрабатывает
   через импутацию, ML-B проверяет устойчивость без этих признаков.
7. Связь ≠ причинность. Все выводы — гипотезы об ассоциации.
