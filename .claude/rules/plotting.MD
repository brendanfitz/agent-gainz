---
paths:
  - "notebooks/**/*.py"
  - "notebooks/**/*.ipynb"
  - "src/viz.py"
  - "src/**/*plot*.py"
---

# Plotting

Destination: `.claude/rules/plotting.md`

## Stack

Plotly for anything a human other than me will see. Matplotlib is fine for a throwaway
diagnostic that gets deleted in the same session.

## You cannot see a Plotly figure

Claude Code renders nothing interactive. `fig.show()` tells you nothing. After building a
figure:

```python
save(fig, "churn_by_tenure")   # writes outputs/figs/churn_by_tenure.png
```

Then Read that PNG and check it. Look for overlapping tick labels, clipped titles, an
unreadable legend, and whether the chart actually shows the thing being claimed. Do not
report a figure as finished before reading its PNG.

## Rules

- **Sort bars by value** unless the category has a natural order (time, ordinal buckets,
  a funnel).
- **Bars start at zero.** Lines do not have to, but say so on the axis if they do not.
- **Axis titles carry units.** "Revenue ($K)", "Latency (p95, ms)", "Share of accounts (%)".
- **Format the numbers**: `tickformat=",.0f"`, `"$,.0f"`, `".1%"`, `"~s"` for SI.
  - Always format numbers with commas where needed and round appropriately.
  - Months in charts format as mmm yy, so January 2025 reads Jan 25.
- **Data Labels** Always add data labels unless there's a lot of datapoints (i.e. more than ~30). Data labels use the same formatting as the numbers.
