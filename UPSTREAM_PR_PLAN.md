# PBI Fixer — Upstream PR Plan (one PR per function)

Strategy: revisit the previous attempt at upstream contribution with a **strictly independent PR per public Python function**. Each PR is reviewable, mergeable, or rejectable on its own — no bundling, no dependencies between PRs. Maintainer (@m-kovalsky) can accept/decline each one without affecting the others.

## Previous PRs (all closed by KornAlexander, none merged)

| # | Branch | Title | Status |
|---|---|---|---|
| 1123 | `feature/fix-piecharts` | Add fix_piecharts | closed (not merged) |
| 1124 | `feature/fix-chart-formatting` | Add fix_barcharts and fix_columncharts | closed (bundled 2 funcs) |
| 1125 | `feature/fix-page-size` | Add fix_page_size | closed (not merged) |
| 1126 | `feature/fix-hide-visual-filters` | Add fix_hide_visual_filters | closed (not merged) |
| 1127 | `feature/add-calendar-table` | Add add_calculated_calendar | closed (not merged) |
| 1128 | `feature/add-measure-table` | Add add_measure_table | closed (not merged) |
| 1129 | `feature/add-calc-group-time-intelligence` | Add add_calc_group_time_intelligence | closed (not merged) |
| 1130 | `feature/add-calc-group-units` | Add add_calc_group_units | closed (not merged) |
| 1131 | `feature/fix-discourage-implicit-measures` | Add fix_discourage_implicit_measures | closed (not merged) |
| 1132 | `feature/add-last-refresh-table` | Add add_last_refresh_table | closed (not merged) |
| 1133 | `feature/pbi-fixer-ui` | Add pbi_fixer (UI) | closed (not merged) |

PR 1124 violated the "one function per PR" rule. The new plan splits everything strictly by function.

---

## Submission Approach (no batches — each PR independent)

**Goal:** Michael can accept/decline each function in isolation.

**Mechanics:**
- Each PR branches from the **latest `microsoft/semantic-link-labs:main`** at the moment of opening. No PR depends on another.
- Each PR adds **exactly one** `_*.py` source file plus one line in the matching `__init__.py`.
- No shared helper modules across PRs. If two functions need the same helper, the helper is duplicated (or kept private inside one file). Once a function is merged, the next PR can rebase to use the now-public helper.
- All PRs are opened **in one batch** — no cadence, no waves. Maintainer picks them up at his pace.
- Each PR carries the prefix `[pbi-fixer]` in its title so Michael can filter them.
- A central **tracking issue** (one GitHub issue listing all 40 functions with checkboxes) links to each PR — gives Michael a single dashboard with accept/decline status.

The groups below are organizational only — they do **not** mean "submit together". Each row is one independent PR.

---

## Function Catalog (40 PRs)

### Group A — Report visual fixers (one per visual type)

| # | Function | Branch | File | Description |
|---|---|---|---|---|
| 1 | `fix_pie_chart` | `feature/fix-pie-chart` | `report/_Fix_PieChart.py` | Replaces all pie/donut chart visuals in a PBIR report with a target visual type (default `clusteredBarChart`). Pie/donut charts are widely discouraged in BI best-practice (IBCS, Stephen Few): humans cannot accurately compare angles. Scans the PBIR JSON, swaps `visualType`, preserves field wells where compatible. Supports `scan_only`, `page_name` filter, and `target_visual_type` override. |
| 2 | `fix_bar_chart` | `feature/fix-bar-chart` | `report/_Fix_BarChart.py` | Applies IBCS best-practice formatting to all bar chart visuals (`barChart`, `clusteredBarChart`): hides X axis title + values, hides Y axis title, enables data labels, removes gridlines. Optional `convert_time_axis_to_column` rule converts time-series bar charts into column charts (time belongs on the X axis). Per-rule opt-in via `rules: set[str]`. |
| 3 | `fix_column_chart` | `feature/fix-column-chart` | `report/_Fix_ColumnChart.py` | Applies IBCS best-practice formatting to column chart visuals (`columnChart`, `clusteredColumnChart`): hides X/Y axis titles + Y values, enables data labels, removes gridlines. Optional rules: `convert_non_time_to_bar` (categorical column → bar) and `convert_date_axis_to_line` (date-axis column → line). |
| 4 | `fix_line_chart` | `feature/fix-line-chart` | `report/_Fix_LineChart.py` | Applies IBCS best-practice formatting to line and combo chart visuals (`lineChart`, `lineClusteredColumnComboChart`): hides axis titles, enables data labels, removes gridlines. Keeps the Y value axis visible (lines need scale context). |

### Group B — Report page / layout / definition fixers

| # | Function | Branch | File | Description |
|---|---|---|---|---|
| 5 | `fix_page_size` | `feature/fix-page-size` | `report/_Fix_PageSize.py` | Changes report pages that use the default 720×1280 size to 1080×1920 (Full HD). Pages already sized differently are left untouched. Improves readability on modern 1080p+ monitors and projector setups. |
| 6 | `fix_visual_alignment` | `feature/fix-visual-alignment` | `report/_Fix_VisualAlignment.py` | Aligns chart visuals on report pages by snapping nearly-aligned visuals (within a tolerance) to a common edge. Cleans up sloppy hand-placed layouts that look almost-but-not-quite aligned. |
| 7 | `fix_hide_visual_filters` | `feature/fix-hide-visual-filters` | `report/_Fix_HideVisualFilters.py` | Hides visual-level filters from the end-user filter pane by setting `isHiddenInViewMode=True` on every filter in every visual. Visual filters are typically design-time concerns and should not clutter the consumer-facing filter pane. |
| 8 | `fix_disable_show_items_no_data` | `feature/fix-disable-show-items-no-data` | `report/_Fix_DisableShowItemsNoData.py` | Disables the "Show items with no data" property on all visuals. This setting can severely degrade query performance, especially on Direct Lake / DirectQuery models, by forcing the engine to evaluate empty cross-joins. |
| 9 | `fix_remove_unused_custom_visuals` | `feature/fix-remove-unused-custom-visuals` | `report/_Fix_RemoveUnusedCustomVisuals.py` | Removes custom visuals that are registered in the report metadata but not used by any visual on any page. Reduces report load time and removes unnecessary marketplace dependencies. |
| 10 | `fix_migrate_report_level_measures` | `feature/fix-migrate-report-level-measures` | `report/_Fix_MigrateReportLevelMeasures.py` | Migrates report-level measures from the report into the underlying semantic model. Best practice: measures belong in the semantic model so they can be reused across reports and audited centrally. |
| 11 | `fix_ibcs_variance` | `feature/fix-ibcs-variance` | `report/_Fix_IBCSVariance.py` | Transforms existing bar/column chart visuals **in place** into IBCS-conformant variance charts. Per visual: switches stacked → clustered, identifies the AC measure, ensures PY / Δ PY / Max Green PY / Max Red AC measures exist on the model (creates them if missing), adds the PY measure to the Y axis, applies IBCS colors (dark grey AC, light grey PY), enables deviation error bars (red/green) for Δ PY, configures overlap, labels, axes, and category sort. Warns if no Year slicer is present on the page. |

### Group C — Semantic model cleanup fixers

| # | Function | Branch | File | Description |
|---|---|---|---|---|
| 12 | `fix_capitalize_object_names` | `feature/fix-capitalize-object-names` | `semantic_model/_Fix_CapitalizeObjectNames.py` | Capitalizes the first letter of every table, column, measure, hierarchy, and partition name. Enforces consistent capitalization across the model for a cleaner field list. |
| 13 | `fix_trim_object_names` | `feature/fix-trim-object-names` | `semantic_model/_Fix_TrimObjectNames.py` | Trims leading/trailing whitespace from table, column, measure, hierarchy, and partition names. Eliminates invisible-but-painful name-mismatch bugs. |
| 14 | `fix_data_category` | `feature/fix-data-category` | `semantic_model/_Fix_DataCategory.py` | Sets appropriate `DataCategory` on columns based on naming conventions (City, Country, PostalCode, WebUrl, ImageUrl, etc.). Enables Power BI's geo-visualization and image rendering features automatically. |
| 15 | `fix_date_column_format` | `feature/fix-date-column-format` | `semantic_model/_Fix_DateColumnFormat.py` | Sets the format string of `Date`-typed columns to `mm/dd/yyyy`. Provides consistent date display across all reports. |
| 16 | `fix_month_column_format` | `feature/fix-month-column-format` | `semantic_model/_Fix_MonthColumnFormat.py` | Sets the format string of "Month" columns to `MMMM yyyy` (full month name + year). |
| 17 | `fix_sort_month_column` | `feature/fix-sort-month-column` | `semantic_model/_Fix_SortMonthColumn.py` | Sets `SortByColumn` on month name (string) columns to point to a month number column. Fixes the classic "January, February, ..." vs. alphabetical sort issue automatically. |
| 18 | `fix_flag_column_format` | `feature/fix-flag-column-format` | `semantic_model/_Fix_FlagColumnFormat.py` | Sets a `Yes/No` format on integer flag columns (names starting with `Is` or ending with `Flag`). Replaces opaque 0/1 values with human-readable labels in tooltips and tables. |
| 19 | `fix_percentage_format` | `feature/fix-percentage-format` | `semantic_model/_Fix_PercentageFormat.py` | Sets a percentage format string on measures whose name contains `%`, `Percent`, or `Pct`. Removes the need to manually format every ratio measure. |
| 20 | `fix_whole_number_format` | `feature/fix-whole-number-format` | `semantic_model/_Fix_WholeNumberFormat.py` | Sets format string to `#,0` on integer-typed measures without a format string. Adds thousands separators consistently. |
| 21 | `fix_floating_point_datatype` | `feature/fix-floating-point-datatype` | `semantic_model/_Fix_FloatingPointDataType.py` | Converts columns that use the `Double` (floating-point) data type to `Decimal` where lossless. Avoids subtle rounding errors and improves Vertipaq compression. |
| 22 | `fix_do_not_summarize` | `feature/fix-do-not-summarize` | `semantic_model/_Fix_DoNotSummarize.py` | Sets `SummarizeBy=None` on numeric data columns (typically keys, IDs, year/month numbers). Prevents accidental implicit `SUM` aggregations when users drag the column into a visual. |
| 23 | `fix_hide_foreign_keys` | `feature/fix-hide-foreign-keys` | `semantic_model/_Fix_HideForeignKeys.py` | Hides columns that participate as foreign keys (the `From` side of relationships). FK columns should not be exposed to report authors — they relate tables, they don't represent a business attribute. |
| 24 | `fix_mark_primary_keys` | `feature/fix-mark-primary-keys` | `semantic_model/_Fix_MarkPrimaryKeys.py` | Sets `IsKey=True` on columns that are the primary key (`To` side) of relationships. Required for several Vertipaq optimizations and Power BI's relationship view. |
| 25 | `fix_isavailable_in_mdx` | `feature/fix-isavailable-in-mdx` | `semantic_model/_Fix_IsAvailableInMdx.py` | Sets `IsAvailableInMDX=False` on hidden columns. Reduces model dictionary size and speeds up Excel/MDX clients. |
| 26 | `fix_isavailable_in_mdx_true` | `feature/fix-isavailable-in-mdx-true` | `semantic_model/_Fix_IsAvailableInMdxTrue.py` | Sets `IsAvailableInMDX=True` on visible key/attribute columns that incorrectly have it disabled — restores Excel pivot-table support. |
| 27 | `fix_discourage_implicit_measures` | `feature/fix-discourage-implicit-measures` | `semantic_model/_Fix_DiscourageImplicitMeasures.py` | Sets the model-level `DiscourageImplicitMeasures=True` property. Required for calculation groups to function correctly and a recognized BPA best practice. |
| 28 | `fix_measure_format` | `feature/fix-measure-format` | `semantic_model/_Fix_MeasureFormat.py` | Sets the format string of measures that have no format string to `#,0`. Catches measures created via the formula bar that lack an explicit format. |
| 29 | `fix_measure_descriptions` | `feature/fix-measure-descriptions` | `semantic_model/_Fix_MeasureDescriptions.py` | Sets the description of visible measures (that have no description) to their DAX expression. Provides instant tooltips in Power BI Desktop and Copilot context. |
| 30 | `fix_avoid_adding_zero` | `feature/fix-avoid-adding-zero` | `semantic_model/_Fix_AvoidAdding0.py` | Removes `0+` or `0 +` prefix from measure expressions. Cleans up the legacy "force-numeric" pattern that's no longer needed and trips up DAX formatters. |
| 31 | `fix_use_divide_function` | `feature/fix-use-divide-function` | `semantic_model/_Fix_UseDivideFunction.py` | Replaces simple division operators (`/`) in measure expressions with `DIVIDE()`. Avoids divide-by-zero errors and is a long-standing DAX best practice. |

### Group D — Semantic model additive builders

| # | Function | Branch | File | Description |
|---|---|---|---|---|
| 32 | `add_calculated_calendar` | `feature/add-calculated-calendar` | `semantic_model/_Add_CalculatedTable_Calendar.py` | Checks whether a calendar table (`DataCategory='Time'`) exists. If not, adds a comprehensive `CalcCalendar` calculated table with 20 columns (Year/Quarter/Month/Week/Day variants) and 3 hierarchies (Year-Quarter-Month-Day, Year-Week-Day, Year-Month). Auto-detects min/max date from existing fact tables. |
| 33 | `add_measure_table` | `feature/add-measure-table` | `semantic_model/_Add_CalculatedTable_MeasureTable.py` | Checks whether a "Measure" table exists. If not, adds an empty calculated table for centralizing measures, marks it as the default measure home, and hides its single placeholder column. |
| 34 | `add_last_refresh_table` | `feature/add-last-refresh-table` | `semantic_model/_Add_Table_LastRefresh.py` | Checks whether a "Last Refresh" table exists. If not, adds a 1-row table with an M partition that returns `DateTime.LocalNow()` so reports can display the data refresh timestamp. |
| 35 | `add_calc_group_units` | `feature/add-calc-group-units` | `semantic_model/_Add_CalcGroup_Units.py` | Adds a Units calculation group with calculation items for No Scaling, Thousand (K), Million (M), Billion (B). Lets report authors swap measure scaling via a slicer instead of duplicating measures. |
| 36 | `add_calc_group_time_intelligence` | `feature/add-calc-group-time-intelligence` | `semantic_model/_Add_CalcGroup_TimeIntelligence.py` | Adds a Time Intelligence calculation group with the standard set of items (YTD, MTD, QTD, PY, PY YTD, YoY, YoY %, ...). Single calc group serves all measures, eliminates dozens of repetitive YTD/PY measure definitions. |
| 37 | `add_measures_from_columns` | `feature/add-measures-from-columns` | `semantic_model/_Add_MeasuresFromColumns.py` | Auto-creates explicit measures from numeric columns based on their `SummarizeBy` property (Sum, Average, Count, ...). Replaces implicit aggregations with named measures so authors get DAX-grade behaviour. |
| 38 | `add_py_measures` | `feature/add-py-measures` | `semantic_model/_Add_PYMeasures.py` | Creates Prior Year (PY) time intelligence measures for each specified base measure, using `CALCULATE(..., SAMEPERIODLASTYEAR(...))`. Good fallback when a calc group is not desired. |
| 39 | `add_incremental_refresh` | `feature/add-incremental-refresh` | `semantic_model/_Add_IncrementalRefresh.py` | High-level wrapper that sets up an incremental refresh policy on a table: detects the date column, configures `RangeStart` / `RangeEnd` parameters, partition window, refresh granularity. Wraps the lower-level `add_incremental_refresh_policy` TOM method with sensible defaults. |
| 40 | `add_prep_for_ai` | `feature/add-prep-for-ai` | `semantic_model/_Add_PrepForAI.py` | Auto-generates and writes Prep-for-AI metadata for a semantic model: synonyms, descriptions, linguistic schema, suggested questions. Improves Copilot in Power BI accuracy. `scan_only` mode previews without writing. |

---

## Excluded from upstream PRs

- **UI files** — `_pbi_fixer.py`, `_ui_components.py`, `_model_explorer.py`, `_report_explorer.py`, `_perspective_editor.py` (stay on `feature/pbi-fixer-ui` for `pip install` distribution only)
- `fix_upgrade_to_pbir` (Alexander's prototype — `upgrade_to_pbir` already in upstream)
- `fix_report_bpa`, `fix_model_bpa` (BPA orchestrators — out of scope)
- `fix_default_datasource_version` (deferred — needs Large SM storage format)
- `fix_charts`, `fix_column_to_bar`, `fix_bar_to_column`, `fix_column_to_line` (consolidated into per-visual functions in Group A)
- `fix_migrate_slicer_to_slicerbar` (slicerbar — not needed)
- `add_cache_warming` (already upstream as `warm_direct_lake_cache_perspective` / `warm_direct_lake_cache_isresident` in `directlake/_warm_cache.py`)

---

## PR Body Template

Same shape as PR #1127 (the most detailed of the previous batch):

```
Adds a <report|semantic model> fixer `<func_name>()` that <one-sentence description>.

<Detailed description from the table above — 2-4 sentences explaining what it does and why it matters.>

Uses <PBIR JSON via connect_report | XMLA/TOM via connect_semantic_model> (Fabric notebook only).

Supports `scan_only=True` to preview findings without writing.

**Part of the PBI Fixer contribution.** Tracking issue: #<issue-number>
```

---

## Per-PR Workflow

```powershell
# 1. From the fork repo, sync with upstream main
cd c:\Users\alkorn\repos\PBI-Fixer\semantic-link-labs
git fetch upstream
git checkout main
git merge upstream/main
git push origin main

# 2. Create fresh branch from main
git checkout -b feature/<func-name> main

# 3. Copy single file from dev mirror
Copy-Item ..\pbi_fixer\src\<area>\_<File>.py src\sempy_labs\<area>\_<File>.py

# 4. Update __init__.py to re-export the function

# 5. Commit + push + open PR
git add src/sempy_labs/<area>/
git commit -m "Add <func_name>: <one-line purpose>"
git push -u origin feature/<func-name>
gh pr create --repo microsoft/semantic-link-labs --base main --head KornAlexander:feature/<func-name> `
  --title "[pbi-fixer] Add <func_name>: <purpose>" `
  --body-file PR_BODY.md
```
