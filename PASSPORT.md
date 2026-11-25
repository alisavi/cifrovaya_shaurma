# PASSPORT.md — паспорт данных проекта

**Дата создания:** 2026-11-25  
**Корень проекта:** `/home/alisavi/shaurma_data`  
**Рабочая директория для всех путей:** `~/shaurma_data` (пути ниже — относительные)  
**Навык:** `data-passport`  
**Версия:** 2.0

---

## 0. Назначение и охват

Паспорт описывает табличные и справочные файлы в `data/raw/`: смысл переменных, единицы, фактические диапазоны, пропуски, невозможные/подозрительные значения и правила формирования целевых переменных. Документ предназначен для очистки, валидации, объединения источников и статистического анализа (включая ROC AUC).

**Источники:**
- `data/raw/AI4FoodDB/` — основная когорта (DS1, DS2, DS4, DS6–DS10 + `participant_information.csv`), чтение через `pandas.read_csv`.
- `data/raw/LLCP2024.ASC` — BRFSS 2024, ASCII фиксированной ширины; **не читался напрямую**. Имена и диапазоны взяты из кодбука `data/raw/USCODE24_LLCP_082125.HTML`.
- `data/raw/DEMO_L.xpt`, `data/raw/BMX_L.xpt`, `data/raw/BPXO_L.xpt` — NHANES (август 2021 – август 2023), чтение через `pandas.read_sas(format="xport")`; сверка с `DEMO_L.htm`, `BMX_L.htm`, `BPXO_L.htm`.

> Файлы `.htm` и `.HTML` используются **только как описания** (кодбуки), не как данные.

---

## 1. Общие соглашения

### 1.1. Идентификаторы и ключи

- AI4FoodDB: участник — `id` вида `A4F_XXXXX`; продольный ключ — `(id, visit)`. Дубликатов `(id, visit)` в основных таблицах нет.
- BRFSS 2024: запись — `SEQNO`, ПСЕ-единица — `_PSU`, страта — `_STSTR`, вес — `_LLCPWT`.
- NHANES: участник — `SEQN`; объединение таблиц по `SEQN` (DEMO — полная выборка, BMX/BPXO — подвыборки).

### 1.2. Коды визитов (важно: несогласованы между наборами)

| Набор | Коды визитов в данных | Комментарий |
|---|---|---|
| `participant_information.csv` | — | одна строка на участника |
| DS1 `anthropometrics.csv` | `0`, `2`, `3` | V0 = baseline, V2 = середина, V3 = конец |
| DS6 `vital_signs.csv` | `0`, `2`, `3` | V0/V2/V3 |
| DS4 `biomarkers.csv` | `1`, `3` | DS4-README обещает `0/2/3`, верхнеуровневый README — V1/V3; в данных **1 и 3** |
| DS7 `IPAQ.csv` | `1`, `2`, `3` | baseline обозначен `1`, а не `0` |
| DS8 `OviedoSleepQuestionnaire.csv` | `1`, `2`, `3` | baseline = `1` |
| DS9 `DASS-21.csv` | `1`, `2`, `3` | baseline = `1` |
| DS10 `SUS.csv` | `2`, `3` | только конец интервенции |

> **Правило:** перед объединением привести baseline к единому коду (`0`), сопоставив `1 → 0` в DS4/DS7/DS8/DS9. Не полагаться на README вслепую.

### 1.3. Коды пропусков

| Код | Где встречается | Значение |
|---|---|---|
| `NA` | AI4FoodDB (README и часть CSV) | пропуск |
| пустая строка `""` | `participant_information.csv`, `lifestyle.csv`, `vital_signs.csv`, `OviedoSleepQuestionnaire.csv`, `DASS-21.csv` | пропуск |
| `\N` | `OviedoSleepQuestionnaire.csv`, `DASS-21.csv`, `SUS.csv` | MySQL NULL / пропуск |
| `-1` | `DS8_SleepActivity/respiratory_rate` (отдельные фазы сна) | «не вычислено» |
| `0.002–0.005` | DS1 `fat_mass_perc`, `muscle_mass_perc` при V2/V3 | placeholder: BIA не выполнялась |
| `<0.003` | DS4 `crp_mg_dl` | цензурировано слева (ниже LOD) |
| `<2` | DS4 `ige_ui_ml` | цензурировано слева (ниже LOD) |
| `BLANK`, `7`, `9`, `77`, `99`, `777`, `999`, `9999` | BRFSS 2024 | пропуск / Don't know / Refused / Not asked (см. §4.2) |
| `.` (SAS missing) | NHANES | пропуск; `pandas.read_sas` возвращает `NaN` |

### 1.4. Проценты хранятся долями

В AI4FoodDB переменные `*_perc` — это **доля от 1**, а не проценты: `fat_mass_perc` 0.002–0.536, `hematocrit_perc` 0.378–0.511, `hba1c_perc` 0.043–0.063, лейкоцитарная формула — доли. Для процентов умножать на 100.

### 1.5. Часовой пояс

Все `timestamp` в per-participant CSV AI4FoodDB — с явным смещением `+02:00` (CEST). Хранить как `datetime` с TZ, при объединении приводить к одному поясу.

---

## 2. Сводка по источникам

| Источник / путь | Тип | Объём | Статус |
|---|---|---|---|
| `data/raw/AI4FoodDB/` | 10 основных CSV + 15 каталогов временных рядов | 100 участников | проанализирован |
| `data/raw/AI4FoodDB/DS3_Nutrition/` | — | — | **отсутствует: ожидает распаковки `FoodNExtDB.zip`** (архив лежит в `Al4FoodDB/FoodNExtDB.zip`, ~1.86 ГБ) |
| `data/raw/LLCP2024.ASC` | BRFSS 2024, fixed-width ASCII | 457 670 записей × 2063 байта; 297 переменных | кодбук разобран, ASC не читался |
| `data/raw/USCODE24_LLCP_082125.HTML` | кодбук BRFSS 2024 | 1.61 МБ | справочник |
| `data/raw/DEMO_L.xpt` | NHANES XPORT | 11 933 × 27 | прочитан |
| `data/raw/BMX_L.xpt` | NHANES XPORT | 8 860 × 22 | прочитан |
| `data/raw/BPXO_L.xpt` | NHANES XPORT | 7 801 × 12 | прочитан |
| `data/raw/*.htm`, `*.HTML` | кодбуки | — | только описания, не данные |

---

## 3. AI4FoodDB

### 3.1. `data/raw/AI4FoodDB/participant_information.csv` — 100 × 9

| Переменная | Тип | Пропуски | Диапазон / значения | Единицы | Смысл |
|---|---|---|---|---|---|
| `id` | identifier | 0 | 100 уникальных | — | Анонимизированный ID участника (A4F_XXXXX) |
| `group` | numeric | 0 | 1 – 2 (медиана 1.5) | — | Группа интервенции: 1 или 2 |
| `age` | numeric | 0 | 18 – 67 (медиана 50) | лет | Возраст, полных лет |
| `sex` | category | 0 | Female: 69; Male: 31 | — | Пол: Female / Male |
| `usual_weight_kg` | numeric | 0 | 59 – 126 (медиана 80) | кг | Обычный вес |
| `weight_5years_kg` | numeric | 3 | 57 – 125 (медиана 76) | кг | Вес 5 лет назад |
| `height_cm` | numeric | 0 | 150.5 – 192.5 (медиана 163.7) | см | Рост |
| `intervention_diet_kcal` | numeric | 3 | 1,500 – 3,100 (медиана 2,000) | ккал/сут | Предписанная калорийность рациона |
| `finished_intervention` | binary | 0 | 0: 7, 1: 93 | — | Завершил интервенцию: 1 = да, 0 = нет |

Факты: 50/50 по группам; 69 женщин, 31 мужчина; 93 завершили интервенцию, 7 — нет; возраст 18–67 лет; пропуски: `weight_5years_kg` — 3, `intervention_diet_kcal` — 3.

### 3.2. `data/raw/AI4FoodDB/DS1_AnthropometricMeasurements/anthropometrics.csv` — 291 × 11

| Переменная | Тип | Пропуски | Диапазон / значения | Единицы | Смысл |
|---|---|---|---|---|---|
| `id` | identifier | 0 | 100 уникальных | — | ID участника |
| `visit` | ordinal | 0 | 0 – 3 (медиана 2) | — | Визит: 0 (V0), 2 (V2), 3 (V3) |
| `period` | binary | 0 | 0: 274, 1: 17 | — | Менструальный период/предменструальные дни: 1 = да, 0 = нет |
| `current_weight_kg` | numeric | 0 | 60.5 – 127.6 (медиана 81.2) | кг | Текущий вес |
| `bmi_kg_m2` | numeric | 0 | 24.3 – 38.5 (медиана 29.7) | кг/м² | ИМТ |
| `fat_mass_perc` | numeric | 0 | 0.002 – 0.536 (медиана 0.005) | доля (×100 = %) | Доля жировой массы (BIA) |
| `muscle_mass_perc` | numeric | 0 | 0.002 – 0.4 (медиана 0.003) | доля (×100 = %) | Доля мышечной массы (BIA) |
| `visceral_fat_level` | numeric | 0 | 5 – 122 (медиана 10) | уровень (б/р) | Уровень висцерального жира (оценка нутрициолога/BIA) |
| `basal_metabolism` | numeric | 0 | 160 – 2,358 (медиана 1,535) | ккал/сут | Базальный метаболизм (расчётный) |
| `waist_cm` | numeric | 0 | 73.5 – 125.7 (медиана 97.5) | см | Обхват талии |
| `hip_cm` | numeric | 0 | 11.3 – 126.7 (медиана 112) | см | Обхват бёдер |

Наблюдения: 100 строк V0, 98 — V2, 93 — V3. ИМТ 24.3–38.5 (вся когорта с избыточной массой/ожирением), поэтому порог «избыточный вес» ИМТ ≥ 25 почти не разделяет выборку.

#### Невозможные / подозрительные значения DS1

| Переменная | Значение | id / визит | Диагноз |
|---|---|---|---|
| `visceral_fat_level` | 122 | A4F_62344 / V2 | физиологически невозможный уровень висцерального жира (типичный диапазон 1–59); вероятна опечатка/сбой BIA |
| `hip_cm` | 11.3 | A4F_13368 / V0 | обхват бедра 11.3 см невозможен (типично 80–130 см); вероятна потеря разряда/десятичной запятой |
| `basal_metabolism` | 160 | A4F_40008 / V2 | 160 ккал/сут несовместимо с жизнью; при весе 79.1 кг ожидаемо ~1500–1900 ккал |
| `basal_metabolism` | 166 | A4F_71665 / V0 | то же; при весе 89.1 кг ожидаемо ~1700–2100 ккал |

Дополнительно: `fat_mass_perc` и `muscle_mass_perc` содержат placeholder `0.002–0.005` в **191** строке (98 из 98 на V2 и 93 из 93 на V3; на V0 таких нет) — BIA на этих визитах не выполнялась. Это не реальные 0.2–0.5 %, а пропуск.

### 3.3. `data/raw/AI4FoodDB/DS2_LifestyleHealth/health.csv` — 100 × 25

| Переменная | Тип | Пропуски | Диапазон / значения | Единицы | Смысл |
|---|---|---|---|---|---|
| `id` | identifier | 0 | 100 уникальных | — | ID участника |
| `oral_contraceptive` | binary | 0 | 0: 96, 1: 4 | — | Приём препарата/группы «oral_contraceptive»: 1 = да, 0 = нет |
| `ring_contraceptive` | binary | 0 | 0: 100, 1: 0 | — | Приём препарата/группы «ring_contraceptive»: 1 = да, 0 = нет |
| `antidepressants` | binary | 0 | 0: 92, 1: 8 | — | Приём препарата/группы «antidepressants»: 1 = да, 0 = нет |
| `antiacids` | binary | 0 | 0: 99, 1: 1 | — | Приём препарата/группы «antiacids»: 1 = да, 0 = нет |
| `antihistamines` | binary | 0 | 0: 95, 1: 5 | — | Приём препарата/группы «antihistamines»: 1 = да, 0 = нет |
| `antiinflamatory` | binary | 0 | 0: 96, 1: 4 | — | Приём препарата/группы «antiinflamatory»: 1 = да, 0 = нет |
| `iron` | binary | 0 | 0: 97, 1: 3 | — | Приём препарата/группы «iron»: 1 = да, 0 = нет |
| `calcium` | binary | 0 | 0: 92, 1: 8 | — | Приём препарата/группы «calcium»: 1 = да, 0 = нет |
| `antihypertensives` | binary | 0 | 0: 86, 1: 14 | — | Приём препарата/группы «antihypertensives»: 1 = да, 0 = нет |
| `thyroid_hormone` | binary | 0 | 0: 87, 1: 13 | — | Приём препарата/группы «thyroid_hormone»: 1 = да, 0 = нет |
| `antibiotics` | binary | 0 | 0: 99, 1: 1 | — | Приём препарата/группы «antibiotics»: 1 = да, 0 = нет |
| `other_medication` | binary | 0 | 0: 33, 1: 67 | — | Приём препарата/группы «other_medication»: 1 = да, 0 = нет |
| `no_medication` | binary | 0 | 0: 72, 1: 28 | — | Не принимает лекарств: 1 = да |
| `hyperthyroidism` | binary | 0 | 0: 98, 1: 2 | — | Наличие состояния «hyperthyroidism»: 1 = да, 0 = нет |
| `hypothyroidism` | binary | 0 | 0: 93, 1: 7 | — | Наличие состояния «hypothyroidism»: 1 = да, 0 = нет |
| `hypercholesterolemia` | binary | 0 | 0: 77, 1: 23 | — | Наличие состояния «hypercholesterolemia»: 1 = да, 0 = нет |
| `triglyceridemia` | binary | 0 | 0: 94, 1: 6 | — | Наличие состояния «triglyceridemia»: 1 = да, 0 = нет |
| `hypertension` | binary | 0 | 0: 84, 1: 16 | — | Наличие состояния «hypertension»: 1 = да, 0 = нет |
| `depression` | binary | 0 | 0: 99, 1: 1 | — | Наличие состояния «depression»: 1 = да, 0 = нет |
| `diabetes` | binary | 0 | 0: 99, 1: 1 | — | Наличие состояния «diabetes»: 1 = да, 0 = нет |
| `lactose_intolerance` | binary | 0 | 0: 98, 1: 2 | — | Наличие состояния «lactose_intolerance»: 1 = да, 0 = нет |
| `other_illness` | binary | 0 | 0: 58, 1: 42 | — | Наличие состояния «other_illness»: 1 = да, 0 = нет |
| `no_illness` | binary | 0 | 0: 62, 1: 38 | — | Не имеет заболеваний: 1 = да |
| `menopause` | binary | 0 | 0: 59, 1: 41 | — | Менопауза: 1 = да |

Все 24 клинических признака — бинарные (`0/1`), пропусков нет. Редкие признаки: `ring_contraceptive` — 0 положительных, `diabetes`/`depression` — по 1, `antiacids`/`antibiotics` — по 1.

### 3.4. `data/raw/AI4FoodDB/DS2_LifestyleHealth/lifestyle.csv` — 100 × 28

| Переменная | Тип | Пропуски | Диапазон / значения | Единицы | Смысл |
|---|---|---|---|---|---|
| `id` | identifier | 0 | 100 уникальных | — | ID участника |
| `appetite` | numeric | 0 | 1 – 5 (медиана 4) | баллы 1–5 | Самооценка аппетита, 1 (низкий) – 5 (высокий) |
| `daily_meals` | category | 0 | 3: 37; 4: 34; 5: 18; 2: 7; >5: 4 | категория | Число приёмов пищи в день (категории, строки) |
| `meals_weekdays_out` | numeric | 0 | 0 – 2.5 (медиана 0) | приёмов/день | Приёмов пищи вне дома в будни, в день |
| `meals_weekdays_home` | numeric | 0 | 0.5 – 6 (медиана 3) | приёмов/день | Приёмов пищи дома в будни, в день |
| `meals_weekend_out` | numeric | 0 | 0 – 3.5 (медиана 0.5) | приёмов/день | Приёмов пищи вне дома в выходные, в день |
| `meals_weekend_home` | numeric | 0 | 0.5 – 5.5 (медиана 3) | приёмов/день | Приёмов пищи дома в выходные, в день |
| `defecation` | category | 0 | daily: 82; every_two: 12; more_two: 6 | — | Частота дефекации: daily / every_two / more_two |
| `urination` | category | 0 | >5: 56; 5: 25; 4: 13; 3: 4; 2: 1; 1: 1 | — | Мочеиспусканий в день (1…>5) |
| `water_ml` | numeric | 0 | 0 – 2,500 (медиана 1,250) | мл/сут | Вода, мл/сут |
| `others_ml` | numeric | 1 | 50 – 3,000 (медиана 500) | мл/сут | Прочие напитки, мл/сут |
| `cigarettes_day` | category | 0 | 0: 89; 1-5: 6; 10-20: 3; 5-10: 2 | категория | Сигарет в день (категории, строки) |
| `cigars_day` | binary | 0 | 0: 100, 1: 0 | шт/сут | Сигар в день |
| `pipe_day` | binary | 0 | 0: 100, 1: 0 | шт/сут | Трубок в день |
| `alcohol` | category | 1 | 0-5: 42; 0: 39; 5-10: 13; >15: 3; 10-15: 2 | категория | Алкоголь, порций в неделю (категории, строки) |
| `fermented_perc` | numeric | 35 | 0 – 1 (медиана 1) | доля | Доля ферментированного алкоголя (0–1) |
| `distilled_perc` | numeric | 35 | 0 – 1 (медиана 0) | доля | Доля дистиллированного алкоголя (0–1) |
| `exercise` | category | 0 | 0: 37; 2: 18; 3: 17; 4-5: 12; >5: 9; 1: 7 | категория | Занятий спортом в неделю (категории, строки) |
| `stress` | binary | 0 | 0: 69, 1: 31 | — | Самоотчёт о стрессе: 1 = да |
| `anxiety` | binary | 0 | 0: 76, 1: 24 | — | Самоотчёт о тревоге: 1 = да |
| `depression` | binary | 0 | 0: 95, 1: 5 | — | Самоотчёт о депрессии: 1 = да |
| `eating_disorder` | binary | 0 | 0: 97, 1: 3 | — | Расстройство пищевого поведения: 1 = да |
| `others_psychological` | binary | 0 | 0: 100, 1: 0 | — | Другие психологические состояния: 1 = да |
| `no_psychological` | binary | 0 | 0: 48, 1: 52 | — | Нет психологических состояний: 1 = да |
| `sleep_weekdays` | numeric | 0 | 4.5 – 10 (медиана 6.75) | ч | Сон в будни, ч/ночь |
| `sleep_weekend` | numeric | 0 | 4.5 – 10 (медиана 7.5) | ч | Сон в выходные, ч/ночь |
| `insomnia` | binary | 0 | 0: 80, 1: 20 | — | Бессонница: 1 = да |
| `somnolence` | binary | 0 | 0: 86, 1: 14 | — | Дневная сонливость: 1 = да |

Пропуски: `others_ml` — 1, `alcohol` — 1, `fermented_perc`/`distilled_perc` — по 35 (логично: 39 непьющих + 1 пропуск). Категориальные шкалы (`daily_meals`, `cigarettes_day`, `alcohol`, `exercise`, `defecation`, `urination`) хранятся **строками**, включая `>5`, `4-5`, `10-20`; перед моделированием их нужно упорядоченно закодировать.

### 3.5. `data/raw/AI4FoodDB/DS4_Biomarkers/biomarkers.csv` — 193 × 41

| Переменная | Тип | Пропуски | Диапазон / значения | Единицы | Смысл |
|---|---|---|---|---|---|
| `id` | identifier | 0 | 100 уникальных | — | ID участника |
| `visit` | numeric | 0 | 1 – 3 (медиана 1) | — | Визит: 1 (baseline) и 3 (конец); 0/2 в данных отсутствуют |
| `leukocytes_10e3_ul` | numeric | 0 | 3.14 – 11.8 (медиана 5.93) | 10³/мкл | Лейкоциты |
| `plats_10e3_ul` | numeric | 0 | 134 – 393 (медиана 237) | 10³/мкл | Тромбоциты |
| `lympho_10e3_ul` | numeric | 0 | 0.9 – 3.91 (медиана 1.99) | 10³/мкл | Лимфоциты |
| `mono_10e3_ul` | numeric | 0 | 0.19 – 0.84 (медиана 0.35) | 10³/мкл | Моноциты |
| `seg_10e3_ul` | numeric | 0 | 1.34 – 8.53 (медиана 3.21) | 10³/мкл | Сегментоядерные нейтрофилы |
| `eos_10e3_ul` | numeric | 0 | 0.04 – 1.08 (медиана 0.17) | 10³/мкл | Эозинофилы |
| `baso_10e3_ul` | numeric | 0 | 0.01 – 0.1 (медиана 0.04) | 10³/мкл | Базофилы |
| `erythrocytes_10e6_ul` | numeric | 0 | 4.16 – 6.01 (медиана 4.81) | 10⁶/мкл | Эритроциты |
| `hgb_g_dl` | numeric | 0 | 11.6 – 16.5 (медиана 14.2) | г/дл | Гемоглобин |
| `hematocrit_perc` | numeric | 0 | 0.378 – 0.511 (медиана 0.434) | доля | Гематокрит (доля) |
| `mcv_fl` | numeric | 0 | 78.2 – 100.8 (медиана 90.1) | фл | MCV |
| `mpv_fl` | numeric | 0 | 6.9 – 12.5 (медиана 9) | фл | MPV |
| `mch_pg` | numeric | 0 | 24.9 – 33.6 (медиана 29.6) | пг | MCH |
| `mchc_g_dl` | numeric | 0 | 30.6 – 35.1 (медиана 32.8) | г/дл | MCHC |
| `rdw_perc` | numeric | 0 | 0.112 – 0.155 (медиана 0.13) | доля | RDW (доля) |
| `lympho_perc` | numeric | 0 | 0.125 – 0.552 (медиана 0.346) | доля | Лимфоциты, доля лейкоцитов |
| `mono_perc` | numeric | 0 | 0.036 – 0.098 (медиана 0.061) | доля | Моноциты, доля |
| `seg_perc` | numeric | 0 | 0.358 – 0.804 (медиана 0.554) | доля | Сегментоядерные, доля |
| `eos_perc` | numeric | 0 | 0.007 – 0.127 (медиана 0.029) | доля | Эозинофилы, доля |
| `baso_perc` | numeric | 0 | 0.001 – 0.017 (медиана 0.006) | доля | Базофилы, доля |
| `hba1c_perc` | numeric | 0 | 0.043 – 0.063 (медиана 0.055) | доля | HbA1c (доля) |
| `hba1ifcc_mmol_mol` | numeric | 0 | 23.5 – 45.4 (медиана 36.6) | ммоль/моль | HbA1c в IFCC |
| `insulin_uui_ml` | numeric | 0 | 1.8 – 51 (медиана 8.2) | мкМЕ/мл | Инсулин |
| `homa` | numeric | 0 | 0.28 – 11.8 (медиана 1.73) | б/р | HOMA-IR |
| `glu_mg_dl` | numeric | 0 | 62 – 106 (медиана 82) | мг/дл | Глюкоза натощак |
| `chol_mg_dl` | numeric | 0 | 103 – 275 (медиана 193) | мг/дл | Общий холестерин |
| `tri_mg_dl` | numeric | 0 | 28 – 281 (медиана 91) | мг/дл | Триглицериды |
| `hdl_mg_dl` | numeric | 0 | 32 – 103 (медиана 54) | мг/дл | Холестерин ЛПВП |
| `ldl_mg_dl` | numeric | 0 | 51.8 – 182.2 (медиана 113.2) | мг/дл | Холестерин ЛПНП |
| `homocysteine_umol_l` | numeric | 0 | 10.1 – 58.3 (медиана 15.4) | мкмоль/л | Гомоцистеин |
| `alb_g_dl` | numeric | 0 | 3.8 – 5 (медиана 4.5) | г/дл | Альбумин |
| `prealbumin_mg_dl` | numeric | 0 | 14.4 – 39.8 (медиана 25.7) | мг/дл | Преальбумин |
| `crp_mg_dl` | category | 0 | 0.026: 3; 0.016: 3; 0.023: 3; 0.126: 3; <0.003: 3; 0.04: 3; 0.02: 3; 0.032: 3 | мг/дл | С-реактивный белок (есть цензурирование `<0.003`) |
| `igg_mg_dl` | numeric | 0 | 540 – 2,078 (медиана 1,042) | мг/дл | Иммуноглобулин G |
| `iga_mg_dl` | numeric | 0 | 39 – 522 (медиана 208) | мг/дл | Иммуноглобулин A |
| `igm_mg_dl` | numeric | 0 | 32 – 830 (медиана 106) | мг/дл | Иммуноглобулин M |
| `ige_ui_ml` | category | 0 | <2: 15; 6: 8; 7: 5; 10: 5; 11: 5; 4: 5; 30: 4; 54: 4 | МЕ/мл | Иммуноглобулин E (есть цензурирование `<2`) |
| `tnf_a_ui_ml` | numeric | 0 | 0.41 – 26.1 (медиана 4.3) | МЕ/мл | TNF-α |
| `adiponectin_ug_ml` | numeric | 0 | 1.17 – 36.5 (медиана 10.7) | мкг/мл | Адипонектин |

Пропусков в числовых столбцах нет. `crp_mg_dl` и `ige_ui_ml` — строковые из-за цензурированных значений: `<0.003` (3 строки) и `<2` (15 строк). Их нельзя молча приводить к числу: либо заменять на LOD/2, либо использовать цензурированную модель. Визиты: 100 (V1) + 93 (V3) = 193.

### 3.6. `data/raw/AI4FoodDB/DS4_Biomarkers/glucose_levels/` — CGM (97 файлов)

Один файл на участника: `A4F_XXXXX_glucose_levels.csv`. Схема (пример `A4F_10021_glucose_levels.csv`, 874 строки):

| Переменная | Тип | Пропуски | Диапазон (пример) | Единицы | Смысл |
|---|---|---|---|---|---|
| `timestamp` | datetime (+02:00) | 0 | 2022-06-06 … 2022-06-19 | — | момент измерения |
| `glucose_value_in_mg_dl` | float | 0 | 46 – 170 | мг/дл | глюкоза (CGM, ~15 мин) |

Это временные ряды, а не одна таблица: **не** объединять все 97 файлов в широкий формат без агрегации. Для моделирования рассчитывать суточные признаки (mean, SD, TIR, CV, GMI) на участника/день.

### 3.7. `data/raw/AI4FoodDB/DS6_VitalSigns/vital_signs.csv` — 291 × 5

| Переменная | Тип | Пропуски | Диапазон / значения | Единицы | Смысл |
|---|---|---|---|---|---|
| `id` | identifier | 0 | 100 уникальных | — | ID участника |
| `visit` | ordinal | 0 | 0 – 3 (медиана 2) | — | Визит: 0 (V0), 2 (V2), 3 (V3) |
| `systolic_blood_pressure_mmhg` | numeric | 2 | 81 – 166 (медиана 120) | мм рт. ст. | Систолическое АД |
| `dyastolic_blood_pressure_mmhg` | numeric | 2 | 8 – 102 (медиана 77) | мм рт. ст. | Диастолическое АД (в файле опечатка «dyastolic») |
| `heart_rate_bpm` | numeric | 2 | 42 – 111 (медиана 69) | уд/мин | ЧСС в покое |

Пропуски — по 2 в каждом физиологическом показателе. **Невозможное значение:** диастолическое АД = **8 мм рт. ст.** у `A4F_53145` (V3) при систолическом 116 — вероятна потеря разряда (должно быть ~80). Также насторожить: `A4F_92332` V2 — ЧСС 111 при АД 111/84 (возможен стресс/аритмия, требует проверки, но не невозможно).

#### `DS6_VitalSigns/heart_rate/` — 95 файлов

`A4F_XXXXX_heart_rate.csv`: `timestamp` (datetime +02:00), `heart_rate` (int, уд/мин). Пример `A4F_10021`: 121 628 строк, ЧСС 46–168. Непрерывный PPG-ряд (5–10 с); агрегировать по дням/ночам.

#### `DS6_VitalSigns/electrocardiogram/` — 94 файла

| Переменная | Тип | Пропуски | Значения (пример) | Смысл |
|---|---|---|---|---|
| `timestamp` | datetime (+02:00) | 0 | — | время ЭКГ-сессии (30 с) |
| `result_classification` | category | 0 | NSR / AFIB / UNCLASSIFIABLE / UNREADABLE | классификация ритма; по всем файлам встречаются все 4 класса |
| `average_heart_rate` | int | 0 | 57–72 | средняя ЧСС за сессию, уд/мин |
| `heart_rate_alert` | category | 0 | NONE / (иные флаги) | флаг тревоги |
| `waveform_samples` | string (list) | 0 | ~7500 значений | сырая ЭКГ 250 Гц; не парсить как число |

### 3.8. `data/raw/AI4FoodDB/DS7_PhysicalActivity/IPAQ.csv` — 195 × 13

| Переменная | Тип | Пропуски | Диапазон / значения | Единицы | Смысл |
|---|---|---|---|---|---|
| `id` | identifier | 0 | 99 уникальных | — | ID участника |
| `visit` | ordinal | 0 | 1 – 3 (медиана 2) | — | Визит: 1 (baseline), 2, 3 |
| `vigorous_n_days` | numeric | 0 | 0 – 5 (медиана 0) | дней | Дней интенсивной активности |
| `vigorous_min_day` | numeric | 0 | 0 – 120 (медиана 0) | мин/день | Минут интенсивной активности в день |
| `vigorous_met` | numeric | 0 | 0 – 4,800 (медиана 0) | MET-мин/нед | MET-минуты интенсивной активности |
| `moderate_n_days` | numeric | 0 | 0 – 7 (медиана 2) | дней | Дней умеренной активности |
| `moderate_min_day` | numeric | 0 | 0 – 270 (медиана 30) | мин/день | Минут умеренной активности в день |
| `moderate_met` | numeric | 0 | 0 – 4,200 (медиана 240) | MET-мин/нед | MET-минуты умеренной активности |
| `walking_n_days` | numeric | 0 | 0 – 7 (медиана 6) | дней | Дней ходьбы |
| `walking_min_day` | numeric | 0 | 0 – 540 (медиана 60) | мин/день | Минут ходьбы в день |
| `walking_met` | numeric | 0 | 0 – 4,158 (медиана 808.5) | MET-мин/нед | MET-минуты ходьбы |
| `total_met` | numeric | 0 | 0 – 6,612 (медиана 1,617) | MET-мин/нед | Суммарные MET-минуты/неделя |
| `categorical_score` | category | 0 | high: 103; moderate: 66; low: 26 | категория | Категория активности: low / moderate / high |

99 участников; визиты 1/2/3 = 50/98/47. Пропусков нет. `visit=1` — это baseline (в README ошибочно указан 0).

#### Цифровые подкаталоги DS7 (описание по одному примеру)

| Каталог (файлов) | Файл-пример | Колонки и смысл |
|---|---|---|
| `active_minutes/` (95) | `A4F_10021_active_minutes.csv` (9 строк) | `timestamp`; `fat_burn_minutes`, `cardio_minutes`, `peak_minutes` — минуты в зонах упражнения; `sedentary_minutes`, `lightly_active_minutes`, `moderately_active_minutes`, `very_active_minutes` — минуты по уровням повседневной активности |
| `additional_physical_activity_data/` (95) | `A4F_10021_additional_physical_activity_data.csv` (11 строк) | `timestamp`; `resting_heart_rate` (уд/мин), `altitude` (м), `calories` (ккал), `steps` (шаги), `distance` (в примере 330 700–1 198 000 — **похоже на метры, а не км**, вопреки README), `minutes_below_default_zone_1` и `minutes_in_default_zone_1..3` |
| `estimated_VO2/` (94) | `A4F_10021_estimated_vo2.csv` (12 строк) | `timestamp`; `demographic_vo2_max`, `demographic_vo2_max_error`, `filtered_demographic_vo2_max`, `filtered_demographic_vo2_max_error` (мл/кг/мин, ошибка — те же единицы) |
| `physical_activity_reports/` (95) | `A4F_10021_physical_activity_reports.csv` (6 строк) | `timestamp`, `activity_name` (Walk/Run/Bike), `average_heart_rate`, `duration`/`active_duration` (мин), `calories`, `steps`, минуты и границы ЧСС по зонам (sedentary, lightly/fairly/very active, out_of_range, fat_burn, cardio, peak) + калории по зонам. Колонка `_lightly_active_minutes` начинается с подчёркивания |

### 3.9. `data/raw/AI4FoodDB/DS8_SleepActivity/OviedoSleepQuestionnaire.csv` — 196 × 27

| Переменная | Тип | Пропуски | Диапазон / значения | Единицы | Смысл |
|---|---|---|---|---|---|
| `id` | identifier | 0 | 100 уникальных | — | ID участника |
| `visit` | ordinal | 1 | 1 – 3 (медиана 2) | — | Визит: 1 (baseline), 2, 3 |
| `1_satisfaction_sleep` | numeric | 1 | 1 – 7 (медиана 4) | баллы | Удовлетворённость сном (1–7) |
| `2_1_initiate_sleep` | numeric | 2 | 1 – 5 (медиана 2) | баллы | Трудности засыпания (1–5) |
| `2_2_remain_asleep` | numeric | 2 | 1 – 5 (медиана 2) | баллы | Трудности поддержания сна (1–5) |
| `2_3_restorative_sleep` | numeric | 1 | 1 – 5 (медиана 2) | баллы | Восстанавливающий сон (1–5) |
| `2_4_usual_waking_up` | numeric | 2 | 1 – 5 (медиана 1) | баллы | Обычное пробуждение (1–5) |
| `2_5_excessive_somnolence` | numeric | 2 | 1 – 5 (медиана 1) | баллы | Избыточная дневная сонливость (1–5) |
| `3_fall_asleep` | numeric | 1 | 1 – 5 (медиана 1) | баллы | Время засыпания (1–5) |
| `4_wake_up_night` | numeric | 1 | 1 – 5 (медиана 2) | баллы | Ночные пробуждения (1–5) |
| `5_wake_up_earlier` | numeric | 1 | 1 – 5 (медиана 1) | баллы | Раннее пробуждение (1–5) |
| `6a_hours_sleep` | numeric | 4 | 2.5 – 9 (медиана 6.5) | ч | Часы сна |
| `6b_hours_bed` | numeric | 5 | 1 – 10 (медиана 7) | ч | Часы в постели |
| `6c_sleep_efficiency` | numeric | 2 | 1 – 5 (медиана 2) | баллы | Эффективность сна (1–5) |
| `7_tiredness_not_sleep` | numeric | 1 | 1 – 4 (медиана 2) | баллы | Дневная усталость не из-за сна (1–4) |
| `8_somnolence_days` | numeric | 1 | 1 – 5 (медиана 1) | баллы | Дни с сонливостью (1–5) |
| `9_somnolence_effects` | numeric | 1 | 1 – 5 (медиана 1) | баллы | Влияние сонливости (1–5) |
| `10a_snoring` | numeric | 2 | 1 – 5 (медиана 1) | баллы | Храп (1–5) |
| `10b_snoring_suffocation` | numeric | 2 | 1 – 5 (медиана 1) | баллы | Остановки дыхания/удушье (1–5) |
| `10c_leg_movements` | numeric | 2 | 1 – 5 (медиана 1) | баллы | Движения ног (1–5) |
| `10d_nightmares` | numeric | 2 | 1 – 5 (медиана 1) | баллы | Кошмары (1–5) |
| `10e_others` | numeric | 2 | 1 – 5 (медиана 1) | баллы | Другие нарушения сна (1–5) |
| `11_sleep_aids` | numeric | 1 | 1 – 5 (медиана 1) | баллы | Снотворные/средства для сна (1–5) |
| `sleep_satisfaction_score` | numeric | 1 | 1 – 7 (медиана 4) | баллы | Балл удовлетворённости сном (1–7) |
| `insomnia_score` | numeric | 1 | 9 – 39 (медиана 17) | баллы | Балл бессонницы (9–39 в данных) |
| `somnolence_score` | numeric | 1 | 3 – 14 (медиана 4) | баллы | Балл сонливости (3–14) |
| `total_score` | numeric | 1 | 14 – 54 (медиана 26) | баллы | Общий балл нарушений сна (14–54) |

Пропуски — 1–5 на разные пункты (максимум у `6b_hours_bed` — 5). Шкалы пунктов: 1–5 (иногда 1–4/1–7); направление шкал нужно сверять с оригинальным OSQ — не все пункты монотонны (например, удовлетворённость сном). `insomnia_score` 9–39, `somnolence_score` 3–14, `total_score` 14–54. Один участник без визита (196 строк на 100 ID).

#### Цифровые подкаталоги DS8 (описание по одному примеру)

| Каталог (файлов) | Файл-пример | Колонки и смысл |
|---|---|---|
| `additional_sleep_data/` (95) | `A4F_10021_additional_sleep_data.csv` (11 строк) | `sleep_id`; `start_time`, `end_time`; `duration`, `minutes_asleep`, `minutes_awake`, `minutes_in_bed` (мин); `main_sleep` (bool); `minutes_in_deep_sleep`, `minutes_in_light_sleep`, `minutes_in_rem` (мин; `NA` для дневного сна) |
| `heart_rate_variability/` (95) | `A4F_10021_heart_rate_variability.csv` (9 строк) | `timestamp`; `rmssd` (мс), `nrem_hr` (уд/мин), `entropy` (б/р) |
| `oxygen_saturation/` (128; 2 файла на участника) | `A4F_10021_daily_oxygen_saturation.csv` (8 строк) | `timestamp`; `sleep_average_oxygen_saturation`, `lower_bound_oxygen_saturation`, `upper_bound_oxygen_saturation` (%). Второй файл — `*_oxygen_saturation_by_minute.csv` (`timestamp`, `oxygen_saturation_by_minute`) |
| `respiratory_rate/` (93) | `A4F_10021_respiratory_rate.csv` (9 строк) | `timestamp`; для фаз full/deep/light/rem — `*_breathing_rate` (вдохов/мин), `*_standard_deviation`, `*_signal_to_noise`. В части файлов `-1` = не вычислено |
| `skin_temperature/` (190; 2 файла на участника) | `A4F_10021_computed_temperature.csv` (7 строк) | `start_sleep`, `end_sleep`; `temperature_samples`; `nightly_temperature` (°C); `baseline_relative_sample_sum`, `..._sum_of_squares`, `..._nightly_standard_deviation`, `..._sample_standard_deviation`. Второй файл — `*_wrist_temperature.csv` (`timestamp`, `temperature_difference`) |
| `sleep_quality/` (94) | `A4F_10021_sleep_quality.csv` (9 строк) | `sleep_id`, `start_time`, `end_time`; `overall_score`, `composition_score`, `revitalization_score`, `duration_score` (баллы); `resting_heart_rate` (уд/мин); `restlessness` (доля/индекс) |

### 3.10. `data/raw/AI4FoodDB/DS9_EmotionalState/DASS-21.csv` — 196 × 27

| Переменная | Тип | Пропуски | Диапазон / значения | Единицы | Смысл |
|---|---|---|---|---|---|
| `id` | identifier | 0 | 100 уникальных | — | ID участника |
| `visit` | ordinal | 1 | 1 – 3 (медиана 2) | — | Визит: 1 (baseline), 2, 3 |
| `1_wind_down` | numeric | 2 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Трудно успокоиться (0–3) |
| `2_mouth_dryness` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Сухость во рту (0–3) |
| `3_no_positive_feelings` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Нет положительных чувств (0–3) |
| `4_difficulty_breathing` | binary | 1 | 0: 177, 1: 18 | баллы 0–3 | Пункт DASS-21: Затруднение дыхания (0–3) |
| `5_no_initiative` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Трудно начать дело (0–3) |
| `6_overreact` | numeric | 1 | 0 – 3 (медиана 1) | баллы 0–3 | Пункт DASS-21: Склонность перереагировать (0–3) |
| `7_trembling` | numeric | 1 | 0 – 2 (медиана 0) | баллы 0–3 | Пункт DASS-21: Дрожь (0–3) |
| `8_nervous_energy` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Нервное напряжение (0–3) |
| `9_panic` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Близость к панике (0–3) |
| `10_no_prospects` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Нет перспектив (0–3) |
| `11_agitation` | numeric | 1 | 0 – 3 (медиана 1) | баллы 0–3 | Пункт DASS-21: Агитация (0–3) |
| `12_no_relax` | numeric | 1 | 0 – 3 (медиана 1) | баллы 0–3 | Пункт DASS-21: Трудно расслабиться (0–3) |
| `13_downhearted` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Подавленность (0–3) |
| `14_intolerance` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Нетерпимость к помехам (0–3) |
| `15_close_to_panic` | numeric | 1 | 0 – 2 (медиана 0) | баллы 0–3 | Пункт DASS-21: Близко к панике (0–3) |
| `16_no_enthusiasm` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Нет энтузиазма (0–3) |
| `17_selfworth` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Низкая самоценность (0–3) |
| `18_touchy` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Обидчивость (0–3) |
| `19_heart` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Ощущение сердца (0–3) |
| `20_scared` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Испуг без причины (0–3) |
| `21_meaningless` | numeric | 1 | 0 – 3 (медиана 0) | баллы 0–3 | Пункт DASS-21: Жизнь бессмысленна (0–3) |
| `depression_score` | numeric | 1 | 0 – 19 (медиана 1) | баллы | Сумма по субшкале депрессии (0–19 в данных) |
| `stress_score` | numeric | 1 | 0 – 19 (медиана 4) | баллы | Сумма по субшкале стресса (0–19) |
| `anxiety_score` | numeric | 1 | 0 – 14 (медиана 1) | баллы | Сумма по субшкале тревоги (0–14) |
| `total_score` | numeric | 1 | 0 – 50 (медиана 6) | баллы | Общий балл DASS-21 (0–50) |

Пропуски — 1–2 на пункты; один участник без визита. Ряд пунктов имеет неполный диапазон: 4 (0–1), 7 и 15 (0–2). Баллы DASS-21 в данных не умножены на 2 (в классической методике субшкалы часто ×2). Если сравнивать с валидированными порогами, умножить на 2 и указать это явно.

#### Цифровые подкаталоги DS9

| Каталог (файлов) | Файл-пример | Колонки и смысл |
|---|---|---|
| `eda_sessions/` (93) | `A4F_10021_eda_sessions.csv` (8 строк) | `timestamp`; `average_heart_rate`, `start_heart_rate`, `end_heart_rate` (уд/мин; `average_heart_rate` местами `NA`); `hrv_baseline` (б/р); `skin_conductance_levels` — **строковое представление массива** (не скаляр), требует парсинга |
| `stress_score/` (39) | `A4F_10021_stress_score.csv` (9 строк) | `timestamp`; `stress_score` (0–100), `sleep_points`, `responsiveness_points`, `exertion_points` (вклад компонент) |

### 3.11. `data/raw/AI4FoodDB/DS10_AdditionalInformation/SUS.csv` — 96 × 16

| Переменная | Тип | Пропуски | Диапазон / значения | Единицы | Смысл |
|---|---|---|---|---|---|
| `id` | identifier | 0 | 96 уникальных | — | ID участника |
| `visit` | ordinal | 0 | 2 – 3 (медиана 2) | — | Визит: 2 или 3 |
| `1_like_to_use` | numeric | 0 | 1 – 5 (медиана 4) | баллы 1–5 | Пункт SUS «1_like_to_use» (1–5) |
| `2_complex` | numeric | 0 | 1 – 4 (медиана 1.5) | баллы 1–5 | Пункт SUS «2_complex» (1–5) |
| `3_easy_to_use` | numeric | 0 | 2 – 5 (медиана 5) | баллы 1–5 | Пункт SUS «3_easy_to_use» (1–5) |
| `4_technical_support` | numeric | 0 | 1 – 4 (медиана 1) | баллы 1–5 | Пункт SUS «4_technical_support» (1–5) |
| `5_well_integrated` | numeric | 0 | 1 – 5 (медиана 4) | баллы 1–5 | Пункт SUS «5_well_integrated» (1–5) |
| `6_inconsistency` | numeric | 0 | 1 – 4 (медиана 2) | баллы 1–5 | Пункт SUS «6_inconsistency» (1–5) |
| `7_quick_to_learn` | numeric | 0 | 1 – 5 (медиана 4) | баллы 1–5 | Пункт SUS «7_quick_to_learn» (1–5) |
| `8_cumbersome` | numeric | 1 | 1 – 5 (медиана 2) | баллы 1–5 | Пункт SUS «8_cumbersome» (1–5) |
| `9_confident` | numeric | 0 | 2 – 5 (медиана 4) | баллы 1–5 | Пункт SUS «9_confident» (1–5) |
| `10_need_to_learn` | numeric | 0 | 1 – 5 (медиана 2) | баллы 1–5 | Пункт SUS «10_need_to_learn» (1–5) |
| `positive_score` | numeric | 0 | 8 – 20 (медиана 15) | баллы | Сумма позитивных пунктов |
| `negative_score` | numeric | 0 | 7 – 20 (медиана 15.5) | баллы | Сумма негативных пунктов |
| `sum` | numeric | 0 | 19 – 40 (медиана 31) | баллы | Сырая сумма |
| `total_score` | numeric | 0 | 48 – 100 (медиана 78) | 0–100 | Итоговый SUS 0–100 |

96 участников (49 на V2, 47 на V3). Пропуск только в `8_cumbersome` — 1. Итоговый `total_score` 48–100 (медиана 78).

### 3.12. DS3 — Nutrition: отсутствует

> **Статус: ожидает распаковки `FoodNExtDB.zip`.** Каталог `data/raw/AI4FoodDB/DS3_Nutrition/` в проекте отсутствует. Архив найден по пути `Al4FoodDB/FoodNExtDB.zip` (~1.86 ГБ). После распаковки ожидаются per-participant CSV с временными метками приёмов пищи и семантическими метками блюд/ингредиентов (см. `README.md` DS3). До этого DS3 нельзя использовать в анализе.

---

## 4. BRFSS 2024 (`data/raw/LLCP2024.ASC`)

### 4.1. Общее описание и важное расхождение по ширине

- Формат: ASCII fixed-width, одна запись = один респондент; данные **не читались напрямую** (запрещено условием).
- Записей: **457 670**; переменных в кодбуке: **297**.
- Кодбук определяет колонки с 1 по **2060**.
- Фактический размер файла: **944 173 210 байт**. `944 173 210 / 457 670 = 2063.0` байт на запись. То есть реальная ширина записи — **2063 байта** (3 неописанных байта на запись, вероятно padding), а не 2111, как указано в постановке. При чтении ориентироваться на 2063 и на колонки кодбука; для `pandas.read_fwf` задавать `widths` из кодбука, а не 2111.
- Кодировка: кодбук сгенерирован SAS с `charset=windows-1252`; текстовые значения читать в `cp1252`/`latin1`.

### 4.2. Коды пропусков BRFSS

| Код | Значение |
|---|---|
| `BLANK` (пробелы) | Not asked / Missing |
| `7` | Don't know / Not sure |
| `9` | Refused |
| `77` | Don't know / Not sure (для 2-значных шкал) |
| `99` | Refused (для 2-значных шкал) |
| `777` / `999` | Don't know / Refused для роста/веса (`HTM4`, `WTKG3`) |
| `9999` | Missing для `_BMI5` |

**Правило:** для каждой переменной сверять её собственную таблицу значений в кодбуке; нельзя слепо отбрасывать только `7` и `9` — у вычисляемых переменных свои коды (`9`, `14`, `9999`).

### 4.3. Запрошенные переменные блоков

| Переменная | Метка | Секция | Колонка | Тип | Коды / диапазон | Частоты (valid) |
|---|---|---|---|---|---|---|
| `_BMI5` | Computed body mass index | Calculated Variables | 1994–1997 | Num | `1–9999`, 2 implied decimals (ИМТ×100); `BLANK` = DK/Refused/Missing | 414 633 (blank 43 037); формула `WTKG3/(HTM4²)` |
| `_SMOKER3` | Computed Smoking Status | Calculated Variables | 2019 | Num | 1 = everyday smoker; 2 = someday smoker; 3 = former; 4 = never; 9 = DK/Refused/Missing | 1: 33 118; 2: 13 976; 3: 119 598; 4: 258 956; 9: 32 022 |
| `_TOTINDA` | Leisure Time Physical Activity Calculated Variable | Calculated Variables | 1902 | Num | 1 = had physical activity/exercise; 2 = none in last 30 days; 9 = DK/Refused/Missing | 1: 350 061; 2: 106 294; 9: 1 315 |
| `SLEPTIM1` | — (в кодбуке 2024 отсутствует) | — | — | — | **Переменной нет среди 297 переменных 2024 LLCP; слово «sleep» в кодбуке не встречается** | — |
| `GENHLTH` | General Health | Health Status | 101 | Num | 1 = Excellent; 2 = Very good; 3 = Good; 4 = Fair; 5 = Poor; 7 = DK; 9 = Refused; BLANK | 1: 64 217; 2: 145 791; 3: 156 229; 4: 67 919; 5: 22 204; 7: 915; 9: 390; blank: 5 |
| `_AGEG5YR` | Reported age in five-year age categories | Calculated Variables | 1977–1978 | Num | 1 = 18–24 … 13 = 80+; 14 = DK/Refused/Missing | 1: 29 692 … 13: 41 756; 14: 8 310 |
| `_LLCPWT` | Final weight: Land-line and cell-phone data | Weighting Variables | 1749–1758 | Num | положительный float (raking-derived) | 457 670; значения не печатаются (HIDDEN) |
| `_STSTR` | Sample Design Stratification Variable | Weighting Variables | 1410–1415 | Num | float; страта дизайна | 457 670; значения не печатаются (HIDDEN) |
| `_PSU` | Primary Sampling Unit | Record Identification | 36–45 | Num | float; PSU = annual sequence number | 457 670; значения не печатаются (HIDDEN) |

#### Важные ограничения BRFSS 2024

- **`SLEPTIM1` отсутствует** в кодбуке 2024 (проверено: 0 вхождений «sleep», 297 переменных). Исторически `SLEPTIM1` — «часы сна за сутки», но в этом файле её нет. Для задач о нарушениях сна BRFSS 2024 непригоден; нужен другой год/источник.
- **Нет измеренного АД и пульса.** В кодбуке 2024 нет переменных `BPHIGH*`, `BPMEDS`, `PULSE`; единственный антропометрический блок — `WEIGHT2`, `HEIGHT3`, `HTM4`, `WTKG3`, `_BMI5`, `_BMI5CAT`, `_RFBMI5`. Значит, целевые «давление» и «пульс» из BRFSS 2024 построить нельзя.
- `_BMI5` имеет **2 подразумеваемых десятичных знака**: ИМТ 29.7 хранится как `2970`. Порог ожирения — `_BMI5 >= 3000`.
- Для дизайна анализа использовать `_LLCPWT`, `_STSTR`, `_PSU`; для стратифицированных оценок — `survey`/`srvyr` с учётом весов и PSU.

---

## 5. NHANES (XPT)

### 5.1. Файлы, размеры и ключ

| Файл | Строк | Колонок | Роль |
|---|---|---|---|
| `data/raw/DEMO_L.xpt` | 11 933 | 27 | демография, веса, дизайн |
| `data/raw/BMX_L.xpt` | 8 860 | 22 | антропометрия (MEC) |
| `data/raw/BPXO_L.xpt` | 7 801 | 12 | осциллометрическое АД (8+ лет) |

`SEQN` — ключ; диапазон 130 378–142 310. DEMO — полная выборка; BMX/BPXO — только прошедшие MEC/измерения. Внутреннее объединение по `SEQN` даёт подвыборку; для взвешенных оценок использовать `WTMEC2YR` (MEC) или `WTINT2YR` (интервью) и дизайн `SDMVSTRA`/`SDMVPSU`.

### 5.2. Ключевые переменные (сверено с `.htm`)

| Переменная | Метка (кодбук) | Файл | Диапазон в XPT | Пропуски | Смысл / особенности |
|---|---|---|---|---|---|
| `SEQN` | Respondent sequence number | DEMO/BMX/BPXO | 130 378–142 310 | 0 | идентификатор; читается как float — приводить к int |
| `WTINT2YR` | Full sample 2-year interview weight | DEMO | 4 584.46–170 968.34 | 0 | вес интервью; положительный |
| `WTMEC2YR` | Full sample 2-year MEC exam weight | DEMO | 4 581.60–227 108.30 **и 0** | 0 (0 = не прошёл MEC, 3 073) | вес MEC; **0 читается pandas как `5.39761e-79` — это ноль, не пропуск** |
| `SDMVSTRA` | Masked variance pseudo-stratum | DEMO | 173–187 (15 страт) | 0 | страта дизайна |
| `SDMVPSU` | Masked variance pseudo-PSU | DEMO | 1–2 | 0 | PSU дизайна |
| `BMXBMI` | Body Mass Index (kg/m**2) | BMX | 11.1–74.8 | 389 | ИМТ; target 2+ лет |
| `BPXOSY1` | Systolic - 1st oscillometric reading | BPXO | 61–232 | 284 | систолическое АД, 1-е измерение, мм рт. ст. |
| `BPXODI1` | Diastolic - 1st oscillometric reading | BPXO | 33–142 | 284 | диастолическое АД, 1-е измерение, мм рт. ст. |

### 5.3. `DEMO_L.xpt` — все переменные
| Переменная | Тип | Пропуски | Диапазон / значения | Метка (SAS Label) | Целевая популяция |
|---|---|---|---|---|---|
| `SEQN` | float | 0 | 130,378 – 142,310 (медиана 136,344) | Respondent sequence number | Both males and females 0 YEARS - 150 YEARS |
| `SDDSRVYR` | coded | 0 | 12: 11933 | Data release cycle | Both males and females 0 YEARS - 150 YEARS |
| `RIDSTATR` | coded | 0 | 1: 3073; 2: 8860 | Interview/Examination status | Both males and females 0 YEARS - 150 YEARS |
| `RIAGENDR` | coded | 0 | 1: 5575; 2: 6358 | Gender | Both males and females 0 YEARS - 150 YEARS |
| `RIDAGEYR` | float | 0 | 0 – 80 (медиана 37) | Age in years at screening | Both males and females 0 YEARS - 150 YEARS |
| `RIDAGEMN` | float | 11556 | 0 – 24 (медиана 11) | Age in months at screening - 0 to 24 mos | Both males and females 0 YEARS - 2 YEARS |
| `RIDRETH1` | coded | 0 | 1: 1117; 2: 1373; 3: 6217; 4: 1597; 5: 1629 | Race/Hispanic origin | Both males and females 0 YEARS - 150 YEARS |
| `RIDRETH3` | coded | 0 | 1: 1117; 2: 1373; 3: 6217; 4: 1597; 6: 681; 7: 948 | Race/Hispanic origin w/ NH Asian | Both males and females 0 YEARS - 150 YEARS |
| `RIDEXMON` | coded | 3073 | 1: 4251; 2: 4609 | Six-month time period | Both males and females 0 YEARS - 150 YEARS |
| `RIDEXAGM` | float | 9146 | 0 – 239 (медиана 122) | Age in months at exam - 0 to 19 years | Both males and females 0 YEARS - 19 YEARS |
| `DMQMILIZ` | coded | 3632 | 1: 694; 2: 7606; 7: 1 | Served active duty in US Armed Forces | Both males and females 17 YEARS - 150 YEARS |
| `DMDBORN4` | coded | 19 | 1: 10039; 2: 1875 | Country of birth | Both males and females 0 YEARS - 150 YEARS |
| `DMDYRUSR` | coded | 10058 | 1: 101; 2: 260; 3: 225; 4: 160; 5: 158; 6: 912; 77: 13; 99: 46 | Length of time in US | Both males and females 0 YEARS - 150 YEARS |
| `DMDEDUC2` | coded | 4139 | 1: 373; 2: 666; 3: 1749; 4: 2370; 5: 2625; 9: 11 | Education level - Adults 20+ | Both males and females 20 YEARS - 150 YEARS |
| `DMDMARTZ` | coded | 4141 | 1: 4136; 2: 2022; 3: 1625; 77: 4; 99: 5 | Marital status | Both males and females 20 YEARS - 150 YEARS |
| `RIDEXPRG` | coded | 10430 | 1: 41; 2: 1065; 3: 397 | Pregnancy status at exam | Females only 20 YEARS - 44 YEARS |
| `DMDHHSIZ` | coded | 0 | 1: 1916; 2: 3056; 3: 1912; 4: 2284; 5: 1418; 6: 723; 7: 624 | Total number of people in the Household | Both males and females 0 YEARS - 150 YEARS |
| `DMDHRGND` | coded | 7818 | 1: 1793; 2: 2322 | HH ref person’s gender | Both males and females 0 YEARS - 19 YEARS |
| `DMDHRAGZ` | coded | 7809 | 1: 83; 2: 1985; 3: 1804; 4: 252 | HH ref person’s age in years | Both males and females 0 YEARS - 19 YEARS |
| `DMDHREDZ` | coded | 8187 | 1: 550; 2: 2004; 3: 1192 | HH ref person’s education level | Both males and females 0 YEARS - 19 YEARS |
| `DMDHRMAZ` | coded | 7913 | 1: 2947; 2: 614; 3: 459 | HH ref person’s marital status | Both males and females 0 YEARS - 19 YEARS |
| `DMDHSEDZ` | coded | 9806 | 1: 300; 2: 942; 3: 885 | HH ref person’s spouse’s education level | Both males and females 0 YEARS - 19 YEARS |
| `WTINT2YR` | float | 0 | 4,584.5 – 170,968.3 (медиана 21,670.2) | Full sample 2-year interview weight | Both males and females 0 YEARS - 150 YEARS |
| `WTMEC2YR` | float | 0 | 0 – 227,108.3 (медиана 21,717.8) | Full sample 2-year MEC exam weight | Both males and females 0 YEARS - 150 YEARS |
| `SDMVSTRA` | float | 0 | 173 – 187 (медиана 180) | Masked variance pseudo-stratum | Both males and females 0 YEARS - 150 YEARS |
| `SDMVPSU` | coded | 0 | 1: 6065; 2: 5868 | Masked variance pseudo-PSU | Both males and females 0 YEARS - 150 YEARS |
| `INDFMPIR` | float | 2041 | 0 – 5 (медиана 2.5) | Ratio of family income to poverty | Both males and females 0 YEARS - 150 YEARS |

> **Артефакт XPT:** в `RIDAGEYR` (189), `RIDAGEMN` (17), `RIDEXAGM` (4), `WTMEC2YR` (3 073), `INDFMPIR` (100) значение `5.39761e-79` — это **фактический ноль**, а не пропуск. Проверено: у строк с `RIDAGEYR=5.39761e-79` значение `RIDAGEMN=2` (возраст 0 лет, 2 месяца); `WTMEC2YR=5.39761e-79` строго соответствует `RIDSTATR=1` (только интервью, без MEC). Перед анализом заменить `5.39761e-79 → 0`.

### 5.4. `BMX_L.xpt` — все переменные
| Переменная | Тип | Пропуски | Диапазон / значения | Метка (SAS Label) | Целевая популяция |
|---|---|---|---|---|---|
| `SEQN` | float | 0 | 130,378 – 142,310 (медиана 136,377.5) | Respondent sequence number | Both males and females 0 YEARS - 150 YEARS |
| `BMDSTATS` | coded | 0 | 1: 8235; 2: 147; 3: 409; 4: 69 | Body Measures Component Status Code | Both males and females 0 YEARS - 150 YEARS |
| `BMXWT` | float | 106 | 2.7 – 248.2 (медиана 71.7) | Weight (kg) | Both males and females 0 YEARS - 150 YEARS |
| `BMIWT` | coded | 8515 | 1: 30; 3: 296; 4: 19 | Weight Comment | Both males and females 0 YEARS - 150 YEARS |
| `BMXRECUM` | float | 8406 | 48.5 – 118.8 (медиана 84.7) | Recumbent Length (cm) | Both males and females 0 MONTHS - 47 MONTHS |
| `BMIRECUM` | coded | 8842 | 1: 18 | Recumbent Length Comment | Both males and females 0 MONTHS - 47 MONTHS |
| `BMXHEAD` | float | 8790 | 34.4 – 46.5 (медиана 42.4) | Head Circumference (cm) | Both males and females 0 MONTHS - 6 MONTHS |
| `BMIHEAD` | coded | 8860 | — | Head Circumference Comment | Both males and females 0 MONTHS - 6 MONTHS |
| `BMXHT` | float | 361 | 79.1 – 200.7 (медиана 163.6) | Standing Height (cm) | Both males and females 2 YEARS - 150 YEARS |
| `BMIHT` | coded | 8726 | 1: 46; 3: 88 | Standing Height Comment | Both males and females 2 YEARS - 150 YEARS |
| `BMXBMI` | float | 389 | 11.1 – 74.8 (медиана 26.4) | Body Mass Index (kg/m**2) | Both males and females 2 YEARS - 150 YEARS |
| `BMDBMIC` | coded | 6368 | 1: 92; 2: 1469; 3: 372; 4: 559 | BMI Category - Children/Youth | Both males and females 2 YEARS - 19 YEARS |
| `BMXLEG` | float | 1525 | 24.9 – 51.6 (медиана 38.1) | Upper Leg Length (cm) | Both males and females 8 YEARS - 150 YEARS |
| `BMILEG` | coded | 8464 | 1: 396 | Upper Leg Length Comment | Both males and females 8 YEARS - 150 YEARS |
| `BMXARML` | float | 292 | 10 – 49.2 (медиана 36.5) | Upper Arm Length (cm) | Both males and females 2 MONTHS - 150 YEARS |
| `BMIARML` | coded | 8660 | 1: 200 | Upper Arm Length Comment | Both males and females 2 MONTHS - 150 YEARS |
| `BMXARMC` | float | 298 | 12 – 63.3 (медиана 31.2) | Arm Circumference (cm) | Both males and females 2 MONTHS - 150 YEARS |
| `BMIARMC` | coded | 8655 | 1: 205 | Arm Circumference Comment | Both males and females 2 MONTHS - 150 YEARS |
| `BMXWAIST` | float | 670 | 39.8 – 187 (медиана 92.7) | Waist Circumference (cm) | Both males and females 2 YEARS - 150 YEARS |
| `BMIWAIST` | coded | 8513 | 1: 347 | Waist Circumference Comment | Both males and females 2 YEARS - 150 YEARS |
| `BMXHIP` | float | 2084 | 69.9 – 187.1 (медиана 103.7) | Hip Circumference (cm) | Both males and females 12 YEARS - 150 YEARS |
| `BMIHIP` | coded | 8499 | 1: 361 | Hip Circumference Comment | Both males and females 12 YEARS - 150 YEARS |

### 5.5. `BPXO_L.xpt` — все переменные
| Переменная | Тип | Пропуски | Диапазон / значения | Метка (SAS Label) | Целевая популяция |
|---|---|---|---|---|---|
| `SEQN` | float | 0 | 130,378 – 142,310 (медиана 136,382) | Respondent sequence number | Both males and females 8 YEARS - 150 YEARS |
| `BPAOARM` | string | 0 | R: 7603; : 147; L: 51 | Arm selected - oscillometric | Both males and females 8 YEARS - 150 YEARS |
| `BPAOCSZ` | coded | 190 | 2: 330; 3: 3404; 4: 3442; 5: 435 | Coded cuff size - oscillometric | Both males and females 8 YEARS - 150 YEARS |
| `BPXOSY1` | float | 284 | 61 – 232 (медиана 117) | Systolic - 1st oscillometric reading | Both males and females 8 YEARS - 150 YEARS |
| `BPXODI1` | float | 284 | 33 – 142 (медиана 72) | Diastolic - 1st oscillometric reading | Both males and females 8 YEARS - 150 YEARS |
| `BPXOSY2` | float | 296 | 59 – 233 (медиана 116) | Systolic - 2nd oscillometric reading | Both males and females 8 YEARS - 150 YEARS |
| `BPXODI2` | float | 296 | 32 – 139 (медиана 71) | Diastolic - 2nd oscillometric reading | Both males and females 8 YEARS - 150 YEARS |
| `BPXOSY3` | float | 321 | 50 – 232 (медиана 116) | Systolic - 3rd oscillometric reading | Both males and females 8 YEARS - 150 YEARS |
| `BPXODI3` | float | 321 | 24 – 136 (медиана 71) | Diastolic - 3rd oscillometric reading | Both males and females 8 YEARS - 150 YEARS |
| `BPXOPLS1` | float | 284 | 35 – 158 (медиана 71) | Pulse - 1st oscillometric reading | Both males and females 8 YEARS - 150 YEARS |
| `BPXOPLS2` | float | 296 | 32 – 141 (медиана 72) | Pulse - 2nd oscillometric reading | Both males and females 8 YEARS - 150 YEARS |
| `BPXOPLS3` | float | 321 | 31 – 154 (медиана 73) | Pulse - 3rd oscillometric reading | Both males and females 8 YEARS - 150 YEARS |

> `BPXO_L` — **осциллометрические** измерения (не ртутный сфигмоманометр): по 3 чтения `BPXOSY1..3`/`BPXODI1..3` + пульс `BPXOPLS1..3`. Для устойчивой оценки АД использовать среднее 2–3 чтений; `BPXOSY1`/`BPXODI1` — только первое чтение, пропусков меньше, но выше шум.

---

## 6. Сводные проблемы качества данных

| # | Проблема | Где | Что делать |
|---|---|---|---|
| 1 | Невозможные значения: `visceral_fat_level=122`, `hip_cm=11.3`, `basal_metabolism=160` и `166`, диастолическое АД `=8` | DS1, DS6 | Пометить `NA`; не исправлять без исходных карт. Задокументировать ID/визит (см. §3.2, §3.7) |
| 2 | Placeholder BIA `0.002–0.005` (191 строка) | DS1 V2/V3 | Считать пропуском, не реальным процентом |
| 3 | Проценты хранятся долями | DS1, DS4 | Умножить на 100 или явно указать долю |
| 4 | Цензурированные `<0.003` / `<2` | DS4 `crp_mg_dl`, `ige_ui_ml` | Заменять на LOD/2 или использовать Tobit/цензурированную модель |
| 5 | Разные коды baseline (`0` vs `1`) | DS1/DS6 vs DS4/DS7/DS8/DS9 | Унифицировать `1 → 0` для baseline |
| 6 | README DS4 обещает визиты `0/2/3`, в данных `1/3` | DS4 | Использовать фактические коды, README не считать истиной |
| 7 | Неполное покрытие per-participant файлов (39–97) | DS4/DS7/DS8/DS9 | При агрегации учитывать отсутствие файла, не путать с нулём |
| 8 | `distance` в DS7 похоже на метры, README говорит км | DS7 additional | Проверить единицы; в примере 330 700–1 198 000 |
| 9 | `skin_conductance_levels` — массив в строке | DS9 EDA | Парсить `numpy.fromstring`, агрегировать (mean/SD), не бросать как категорию |
| 10 | `-1` как «не вычислено» | DS8 respiratory | Заменить на `NA` |
| 11 | DS3 отсутствует | AI4FoodDB | Ждать распаковки `FoodNExtDB.zip` |
| 12 | BRFSS: нет `SLEPTIM1`, АД, пульса | BRFSS 2024 | Для этих целей BRFSS 2024 не использовать |
| 13 | BRFSS: ширина 2063, а не 2111 | LLCP2024.ASC | Задавать `widths` из кодбука; 3 лишних байта на запись |
| 14 | NHANES: `5.39761e-79` = 0 | DEMO_L.xpt | Заменить на 0; не считать пропуском |
| 15 | NHANES: веса и дизайн не применены | DEMO/BMX/BPXO | Взвешивать `WTMEC2YR`/`WTINT2YR`; `SDMVSTRA`/`SDMVPSU` для SE |
| 16 | DASS-21 баллы не ×2 | DS9 | Умножить на 2 для сравнения с валидированными порогами |

---

## 7. Рекомендации перед анализом

1. Привести пропуски к единому `NA`: `""`, `NA`, `\N`, `-1`, BIA-placeholder `0.002–0.005`; цензурированные CRP/IgE обрабатывать отдельно.
2. Унифицировать визиты: `1 → 0` для baseline в DS4/DS7/DS8/DS9; не смешивать `0` и `1` при merge.
3. Исправить/пометить невозможные значения DS1/DS6 (см. §3.2, §3.7) до расчёта ИМТ/АД/ЧСС-меток.
4. Для per-participant CSV сначала построить агрегаты на `(id, date)` (mean/SD/min/max/TIR), затем объединять с табличными DS; не разворачивать миллионы строк в широкий формат.
5. Для NHANES: заменить `5.39761e-79 → 0` в DEMO, привести `SEQN` к int, объединять по `SEQN`, применять веса и дизайн.
6. Для BRFSS: читать `read_fwf` с `widths` из кодбука (не 2111), кодировка `cp1252`, пропуски по правилам §4.2; целевые АД/пульс/сон из BRFSS 2024 не строить.
7. Для ROC AUC фиксировать пороги меток в конфиге/протоколе, стратифицировать CV, считать AUC с 95 % CI и калибровку (Brier, calibration curve).

---


---

## 8. Целевые переменные и бинаризация под ROC AUC

**Общие правила:**

1. Бинарную метку строить только там, где есть валидное измерение; пропуски метки исключать из обучения/оценки, а не кодировать нулём.
2. Для ROC AUC желателен баланс классов примерно 30–70 %. Пороги ниже подобраны так, чтобы не получать 1–5 % положительных (иначе AUC нестабилен).
3. Использовать **baseline** (V0/визит 1) для прогностических моделей, чтобы не было утечки из будущих визитов.
4. Для AI4FoodDB все пороги считать по строкам визитов; для одного участника можно брать baseline или агрегат (mean/max) — указать в протоколе.
5. Для NHANES обязательно учитывать веса и дизайн; для BRFSS — `_LLCPWT`/`_STSTR`/`_PSU`.

| Целевая переменная | Источник и поле | Правило бинаризации (primary) | Ожидаемая доля «1» | Альтернатива / комментарий |
|---|---|---|---|---|
| **Ожирение (ИМТ)** | AI4FoodDB `DS1.bmi_kg_m2` | `1`, если `bmi_kg_m2 >= 30` | **50.0 %** на baseline V0 (50/100); 47.1 % по всем визитам (137/291) | `>=25` даёт 99.3 % (100 % на V0) — не годится для ROC; `>=27` — 82.8 %; `>=32` — 32.3 % |
| **Ожирение (ИМТ)** | NHANES `BMX.BMXBMI` | `1`, если `BMXBMI >= 30` | 31.9 % (2 699/8 471) | `>=25` — 57.9 % |
| **Ожирение (ИМТ)** | BRFSS `_BMI5` | `1`, если `_BMI5 >= 3000` (2 implied decimals) | по кодбуку не считалось (нет микрочтения) | `_BMI5CAT` = 4 (Obese) эквивалентно; `>=2500` — overweight+ |
| **Артериальная гипертензия** | AI4FoodDB `DS6` | `1`, если `systolic >= 130` **или** `dyastolic >= 80` | **54.5 %** на baseline V0 (54/99); 47.1 % по всем визитам (136/289) | Клинический порог `>=140/90` даёт 19.2 % на V0 (16.3 % по всем) — лучше для скрининга, хуже для баланса; привести оба |
| **Артериальная гипертензия** | NHANES `BPXO` | `1`, если `BPXOSY1 >= 130` **или** `BPXODI1 >= 80` | 35.8 % (2 691/7 517) | `>=140/90` — 16.4 %; лучше усреднить 2–3 чтения |
| **Артериальная гипертензия** | BRFSS 2024 | — | — | **невозможно**: в кодбуке 2024 нет АД |
| **Повышенная ЧСС (пульс)** | AI4FoodDB `DS6.heart_rate_bpm` | `1`, если `heart_rate_bpm >= 80` | **20.2 %** на baseline V0 (20/99); 15.6 % по всем визитам (45/289) | `>=85` — 8.3 %; тахикардия `>100` — 0.3 % (слишком редко для AUC) |
| **Повышенная ЧСС (пульс)** | NHANES `BPXO.BPXOPLS1` (пульс 1-го чтения) | `1`, если `BPXOPLS1 >= 80` | не рассчитывалось в этом паспорте | Можно усреднить `BPXOPLS1..3`; в BRFSS 2024 пульса нет |
| **Нарушения сна** | AI4FoodDB `DS2.insomnia` / `somnolence` | `1`, если `insomnia == 1` **или** `somnolence == 1` | 31.0 % (31/100) | Отдельно: `insomnia` 20 %, `somnolence` 14 % |
| **Нарушения сна** | AI4FoodDB `DS8.Oviedo.insomnia_score` | `1`, если `insomnia_score >= 20` | **38.0 %** на baseline V1 (19/50); 36.7 % по всем визитам (72/196) | `>=17` — 60.0 % на V1; `>=25` — 12.0 %; **на baseline только 50 участников** (V1 есть лишь у группы 2), порог требует клинической валидации на DS2 |
| **Нарушения сна** | AI4FoodDB `DS2.sleep_weekdays` | `1`, если `sleep_weekdays < 6` | 15.0 % (15/100) | Короткий сон; альтернатива для ночного времени |
| **Нарушения сна** | BRFSS 2024 | — | — | **невозможно**: `SLEPTIM1` в кодбуке 2024 отсутствует |

**Рекомендованный набор меток для мультизадачного ROC-анализа AI4FoodDB:**

- `y_obesity = bmi_kg_m2 >= 30` (baseline V0);
- `y_hypertension = SBP >= 130 or DBP >= 80` (primary; отчёт также для 140/90);
- `y_high_hr = heart_rate_bpm >= 80`;
- `y_sleep_disturbance = (insomnia == 1 or somnolence == 1)` как **основной** (покрытие 100 % на baseline); `insomnia_score >= 20` (Oviedo) — как вторичный (на baseline V1 доступен только у 50 участников).

**Для NHANES:** `y_obesity = BMXBMI >= 30`; `y_hypertension = mean(BPXOSY1..3) >= 130 or mean(BPXODI1..3) >= 80`; `y_high_hr` — по среднему пульсу `BPXOPLS1..3 >= 80`. Для BRFSS доступна только `y_obesity` по `_BMI5 >= 3000`.

---

*Паспорт сформирован по фактическим данным (pandas 3.1.1) и кодбукам; все пути — относительно `/home/alisavi/shaurma_data`.*
