# Project context for Claude

## Purpose
A **learning project**. The owner wants to understand every step: explain what you are doing, how and why, show the commands you run, and explain errors and their fixes. Talk to the user in Portuguese; code, notebooks, docs and commit messages in English.

## Roadmap
1. Local exploration with pandas (done in v0.1.0)
2. Data larger than RAM: pandas vs Polars vs DuckDB on FHVHV 2024 + 2025
3. GCS + BigQuery external tables
4. dbt staging with tests
5. Kimball star schema
6. Dashboards
7. Airflow orchestration
Optional later: Kafka → MinIO

## Environment
- Windows 11, 64 GB RAM, Python 3.14 in `.venv`, pandas 3.1 (strings are Arrow-backed by default)
- Run notebooks with the `.venv` kernel. The `python3` kernelspec calls `python` from PATH, so when executing with `nbconvert` from a shell, put `.venv/Scripts` first in PATH
- Some `.exe` entry points (e.g. `jupyter-kernelspec`) are blocked by Windows Application Control: use `python -m <module>` instead
- Data lives in `datasets/` (not versioned): yellow, green, fhv, fhvhv for 2024 and 2025 + `taxi_zone_lookup.csv`

## Git workflow
- **git-flow**, chosen to learn it: `main` (releases only, tagged `vX.Y.Z`), `develop`, `feature/*`, `release/*`, `hotfix/*`
- Merge with `--no-ff`; use plain git commands, not the `git flow` extension
- Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`)
- Notebook outputs are stripped on commit by nbstripout (local copies keep them)

## Decisions and findings
- **Do not drop rows with nulls in FHVHV**: `on_scene_datetime` and `originating_base_num` are null for ~99.7% of Lyft trips (Lyft does not report them). Dropping nulls removes almost all Lyft data
- 2024 files have no `cbd_congestion_fee` (Manhattan congestion pricing started in January 2025). Code must tolerate the missing column
- Memory: one FHVHV month is 4.36 GB raw / 1.80 GB optimized (category for text, float32, int32/int16). FHVHV 2024 + 2025 ≈ 103 GB raw / 43 GB optimized
- Automatic EDA uses **Sweetviz**: ydata-profiling does not support Python 3.14 and skimpy breaks with pandas 3. Sweetviz needs text columns forced as categorical (`force_cat`) for comparisons
- Measure instead of estimating: earlier estimates of memory were wrong by 2–3x
