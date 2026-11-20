# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/). Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `03_benchmark.ipynb` and `benchmarks/fhvhv_aggregate.py`: the same aggregation over all 24 FHVHV months (483M rows) with pandas, Polars and DuckDB. Measures time and peak memory, with all threads and with one thread, and checks that the results match
- `psutil` in requirements (peak memory measurement)

## [0.1.0] - 2026-11-20

Local exploration with pandas.

### Added
- `01_memory_analysis.ipynb`: RAM per column for one FHVHV month, pandas backends, dtype optimization (2.4x smaller), projection for 2024 + 2025
- `02_eda_quality.ipynb`: 28 data quality checks on one FHVHV month, with findings mapped to dbt staging rules
- `02b_eda_auto.ipynb`: automatic EDA with Sweetviz (one month, Uber vs Lyft, 2025 vs 2024)
- Project setup: README, pinned requirements, `.gitignore`, nbstripout filter, `CLAUDE.md`
