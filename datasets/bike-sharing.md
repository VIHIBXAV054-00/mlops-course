# Data Dictionary — UCI Bike Sharing (hourly)

An **urban-mobility, regression** alternative — and the **only catalogue option with a real time axis**. Hourly counts of bike rentals in the Washington DC Capital Bikeshare system over 2011–2012, with weather and calendar context. Predict the rental count `cnt`. Because it is genuinely temporal, it is the easiest place to demonstrate **authentic seasonal/temporal drift** and real data **versioning** without simulation.

## What the dataset is

- File: `hour.csv` · Rows: **17,379** (one per hour) · Columns: 17
- Span: 2011-01-01 → 2012-12-31, Capital Bikeshare (Washington DC)
- Task: **regression** — predict `cnt` (total hourly rentals). (`day.csv`, 731 rows, is the daily aggregate.)

## Feature dictionary

| Column | Meaning | Type / values | Notes |
| :--- | :--- | :--- | :--- |
| `instant` | Record index | int | **Drop** — row id. |
| `dteday` | Date | date | The time axis; combine with `hr` for a timestamp. |
| `season` | Season | int 1–4 (1:winter…4:fall) | Categorical encoded as int — don't treat as continuous. |
| `yr` | Year | `0` = 2011, `1` = 2012 | Ridership grows 2011→2012 (a built-in trend). |
| `mnth` | Month | int 1–12 | Categorical/cyclical. |
| `hr` | Hour | int 0–23 | Strong daily cycle (commute peaks). Cyclical. |
| `holiday` | Holiday flag | 0 / 1 | |
| `weekday` | Day of week | int 0–6 | Categorical. |
| `workingday` | Working day (not weekend/holiday) | 0 / 1 | |
| `weathersit` | Weather situation | int 1–4 (1:clear … 4:severe) | Ordinal/categorical. |
| `temp` | Temperature, normalized | float ~0–1 | Normalized to [0,1] (commonly cited divisor 41 °C). See dataset `Readme.txt` for exact constants. |
| `atemp` | "Feels-like" temperature, normalized | float ~0–1 | Normalized (commonly cited divisor 50). |
| `hum` | Humidity, normalized | float 0–1 | Divided by 100. |
| `windspeed` | Wind speed, normalized | float 0–1 | Divided by 67. |
| `casual` | Count of casual (non-registered) users | int | **Leakage** — see notes. |
| `registered` | Count of registered users | int | **Leakage** — see notes. |
| `cnt` | Total rentals (**target**) | int | `cnt = casual + registered`. |

## Domain-expert notes (the gotchas)

- **Target leakage.** `cnt = casual + registered` exactly. If you predict `cnt`, you must **drop `casual` and `registered`** or the task is trivial.
- **Integer-coded categoricals.** `season`, `mnth`, `weekday`, `weathersit` are categories stored as integers; feeding them as continuous numbers is a common mistake. `hr` and `mnth` are also **cyclical** (hour 23 is next to hour 0).
- **Pre-normalized weather.** `temp`, `atemp`, `hum`, `windspeed` are already scaled to ~[0,1]; don't double-scale, and remember they're not in physical units.
- **Drop `instant`; engineer from `dteday`/`hr`.** Build the timestamp and any lag/rolling features from these.

## How this dataset "changes over time" in the course

This one needs **no simulation** — it has a real time axis. For data **versioning** (Week 4), reveal it month by month ("the next month's data arrived"). For **drift** (Weeks 11–12) you get authentic signals: strong **seasonality** (winter vs summer), daily commute cycles, and a real **upward trend** from 2011 (`yr=0`) to 2012 (`yr=1`) — train on 2011, watch the 2012 distribution shift. This is the most realistic option for the monitoring weeks.

## Source & licence

UCI Machine Learning Repository, "Bike Sharing Dataset" (id 275), licensed **CC BY 4.0**. Cite: Fanaee-T, H. & Gama, J. (2014), *Event labeling combining ensemble detectors and background knowledge*, Progress in Artificial Intelligence.

_Last updated: 2026-06. Verify source and licence before use; consult the dataset Readme.txt for exact normalization constants._
