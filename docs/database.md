# Database

Every run is logged to PostgreSQL. In AUTO mode a row is written after **each
valid thickness measurement** and once more when the run stops; in MANUAL mode
one row is written when the run stops.

## Setup

```bash
sudo apt install postgresql
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'your-password';"
sudo -u postgres createdb rotation_platform
```

Put the same values in `.env` (see `.env.example`). The table is created — and
older tables are upgraded — automatically when the HMI starts.

## Table `history_log`

| Column             | Type        | Meaning |
|--------------------|-------------|---------|
| `id`               | SERIAL PK   | |
| `waktu`            | TIMESTAMP   | insert time (default `now`) |
| `bentuk_stick`     | VARCHAR(10) | `I`, `T`, `Y`, `3D` |
| `mode_operasi`     | VARCHAR(20) | `AUTO` / `MANUAL` |
| `target_ketebalan` | FLOAT       | target thickness entered by the operator (mm) |
| `target_waktu`     | FLOAT       | run duration entered by the operator (s) |
| `ketebalan_1..3`   | FLOAT       | measured thickness S1/S2/S3 (mm) |
| `suhu_akhir`       | FLOAT       | temperature at the time of the row (°C) |
| `pitch_sistem`     | FLOAT       | IMU pitch at the time of the row (°) |
| `response_time`    | FLOAT       | feedback latency: last valid laser reading → decision (ms) |

Column names stay in Indonesian so existing databases keep working.

## Useful queries

```sql
-- last 20 runs
SELECT * FROM history_log ORDER BY id DESC LIMIT 20;

-- mean ± std of the feedback response time
SELECT AVG(response_time), STDDEV(response_time)
FROM history_log WHERE mode_operasi = 'AUTO' AND response_time > 0;

-- export to CSV
\copy (SELECT * FROM history_log ORDER BY id) TO 'history.csv' CSV HEADER
```
