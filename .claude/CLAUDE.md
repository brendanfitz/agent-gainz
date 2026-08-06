# CLAUDE.md

<!-- Destination: repo root. Target under 200 lines. Anything longer or narrower
     belongs in .claude/rules/ (path-scoped) or a skill (loaded on demand). -->

## Project

- Data lives in `data/` and can use `data/interim/` (parquet cache).
- Notebooks are either in root or `notebooks/` depending on if it's pure analysis
- Reusable code in `src/` or `utils` depending on repository
- If it's an analysis
  - `load.py` (ingest, header hygiene, dtype coercion, scope masks)
  - `transforms.py` (derived fields, cohort builders)
  - `viz.py` (plotly template + chart helpers)
  - `checks.py` (validation and row-count helpers)
  - `defs.py` (canonical definition constants mirroring definitions.md).
- Figures in `outputs/figs/`.

## Jupyter Notebooks

In jupyter notebooks, we're typically running exploratory analysis, not production software.
Write like a strong Kaggle notebook, not like an enterprise service.

- No docstrings, type hints, or `try`/`except` in notebook cells. Use all three in `src/`.
- Validate with bare `assert`, one line. Add a message only when the failure would be
  cryptic.
  - `assert df.order_id.is_unique`
  - `assert df.amount.ge(0).all()`
  - `assert set(X_train.columns) == set(X_test.columns)`
- No `logging`, no `print("Loading data...")` progress narration, no banner separators.
- Prefer chained pandas (`.assign()`, `.query()`, `.pipe()`) over a ladder of `df2`, `df3`.
- Short names in cells (`df`, `X`, `y`, `fig`). Descriptive names in `src/`.
- Comments say why, never what. If a comment restates the code, delete it.
- One idea per cell. End every cell with something that displays.
- Extract to a function on the third repetition, not the first.
- Notebooks run %autoreload 2, so module edits go live without re-running everything if using `src` or `utils`

## Charts

See `.claude/rules/plotting.md`