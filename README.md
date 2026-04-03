# Power BI Fixer

**One line of Python to assess, standardize, and fix any Power BI report.**

The Power BI Fixer is a free, open-source, notebook-native tool built on [Semantic Link Labs](https://github.com/microsoft/semantic-link-labs) that combines **34+ fixers** for both the report layer and the semantic model into a single interactive UI with 10 tabs. No installs. No downloads. No license costs. Just one line of Python in a Microsoft Fabric Notebook.

---

## Quick Start — How to Use

### Step 1: Install

In a **Microsoft Fabric Notebook** cell, run:

```python
%pip install git+https://github.com/KornAlexander/semantic-link-labs.git@feature/pbi-fixer-ui
```

### Step 2: Import and Launch

In the next cell, run:

```python
from sempy_labs import pbi_fixer

pbi_fixer()
```

That's it. An interactive widget UI will appear directly in the notebook output. Select your workspace, report, and the fixers you want to apply, then click **Run**.

### Optional Parameters

```python
# Specify workspace and report directly
pbi_fixer(workspace="Your Workspace Name", report="My Report")

# Load multiple reports/models (comma-separated)
pbi_fixer(workspace="Your Workspace Name", report="Report A, Report B")

# Leave report blank to load ALL items in the workspace
pbi_fixer(workspace="Your Workspace Name")
```

---

## UI Tabs

| Tab | Icon | Description |
|-----|------|-------------|
| Semantic Model | 📊 | Tree view of tables/columns/measures, DAX editing, table data preview, properties, actions dropdown |
| Report | 📄 | Tree view of pages/visuals, live preview, properties, scan & fix actions |
| Fixer | ⚡ | Checkbox-based fixer selection, God Button, Scan/Fix/Scan+Fix modes (hidden by default) |
| Perspectives | 👁 | Perspective editor with tri-state checkboxes |
| Memory Analyzer | 💾 | Vertipaq stats: models → tables → columns by size, model dropdown for multi-model |
| BPA | 📋 | Best Practice Analyzer with category tabs, severity badges, auto-fix buttons |
| Report BPA | 📄 | Report-level BPA with auto PBIRLegacy conversion |
| Delta Analyzer | 📐 | Delta table analysis: summary, parquet files, row groups, column chunks |
| About | ℹ️ | Author info, links, tech credits |

---

## What It Does

### Report Fixers (7 — Visual Layer, PBIR Format)

| Fixer | What It Does |
|-------|-------------|
| **Fix Pie Charts** | Replaces all pie charts with clustered bar charts (or any target visual type) |
| **Fix Bar Charts** | Removes axis titles/values, adds data labels, removes gridlines |
| **Fix Column Charts** | Same clean-up as bar charts, applied to column charts |
| **Fix Page Size** | Upgrades default 720×1280 pages to 1080×1920 (Full HD) |
| **Hide Visual Filters** | Sets `isHiddenInViewMode` on all visual-level filters |
| **Upgrade to PBIR** | Converts PBIRLegacy reports to PBIR via REST round-trip |
| **Migrate Slicer to Slicerbar** | Migrates slicers to the new slicerbar format (optional) |

### Semantic Model Fixers — Additive (8 — XMLA Endpoint)

| Fixer | What It Does |
|-------|-------------|
| **Discourage Implicit Measures** | Enables `DiscourageImplicitMeasures` (recommended & required for calc groups) |
| **Add Calendar Table** | Generates a calculated calendar table with hierarchies and display folders |
| **Add Measure Table** | Adds an empty calculated table to centralize measures |
| **Add Last Refresh Table** | Adds a table with M partition + measure showing last refresh timestamp |
| **Add Units Calc Group** | Creates Thousand & Million items, skipping percentage/ratio measures |
| **Add Time Intelligence Calc Group** | Generates AC, Y-1/Y-2/Y-3, YTD, absolute/relative/achievement variances |
| **Auto-Create Measures from Columns** | Creates measures from columns with SummarizeBy set |
| **Add PY Measures (Y-1)** | Creates PY, ΔPY, ΔPY% measures for all or selected measures |

### BPA Auto-Fixers (19 — Fix Best Practice Violations)

These fix specific violations found by `run_model_bpa()`. Available as per-row fix buttons in the BPA tab and as bulk actions in the SM Explorer dropdown.

| Fixer | What It Does |
|-------|-------------|
| **Fix Floating Point Types** | Changes Double columns to Decimal |
| **Fix IsAvailableInMDX (False)** | Sets `IsAvailableInMDX = False` on non-attribute columns |
| **Fix IsAvailableInMDX (True)** | Sets `IsAvailableInMDX = True` on key/hierarchy columns |
| **Fix Measure Descriptions** | Sets measure description to its DAX expression |
| **Fix Date Column Format** | Sets 'Date' columns to `mm/dd/yyyy` |
| **Fix Month Column Format** | Sets 'Month' columns to `MMMM yyyy` |
| **Fix Measure Format** | Sets unformatted measures to `#,0` |
| **Hide Foreign Keys** | Hides columns used as foreign keys in relationships |
| **Fix DIVIDE Function** | Replaces `/` operator with `DIVIDE()` in measure expressions |
| **Fix Avoid Adding 0** | Removes `0+` prefix from measure expressions |
| **Fix Do Not Summarize** | Sets `SummarizeBy = None` on numeric data columns |
| **Mark Primary Keys** | Sets `IsKey = True` on relationship To-side columns |
| **Trim Object Names** | Removes leading/trailing whitespace from object names |
| **Capitalize Object Names** | Capitalizes the first letter of object names |
| **Fix Percentage Format** | Sets percentage measures to `#,0.0%` format |
| **Fix Whole Number Format** | Sets unformatted measures to `#,0` |
| **Fix Flag Column Format** | Sets Yes/No format on integer flag columns |
| **Fix Sort Month Column** | Sets SortByColumn on month name columns |
| **Fix Data Category** | Sets DataCategory based on column naming conventions |

### Inline Actions (3)

| Action | What It Does |
|--------|-------------|
| **Format All DAX** | Formats all DAX expressions via daxformatter.com API |
| **Clone Report** | Clones a report (appends `_copy`) |
| **Clone Model** | Clones a semantic model via getDefinition + create_semantic_model_from_bim |

---

## Additional Features

| Feature | Description |
|---------|-------------|
| **Multi-item loading** | Load all or comma-separated reports/models in a workspace |
| **Combobox item selector** | Dropdown with 📋 List Items to browse workspace contents |
| **Clone buttons** | Clone Both / Clone Report / Clone Model buttons with name mismatch warning |
| **Download buttons** | Download .pbix / .pbip to lakehouse |
| **Stop Load** | ⏹ Stop button to cancel long-running load operations |
| **PBIR format gate** | Auto-detects PBIRLegacy, offers conversion before fixing |
| **Scan mode** | Detect violations without modifying anything |
| **God Button** | ⚡ Fix Everything — selects all fixers and runs |
| **Table data preview** | Top 10/100/All rows preview when selecting a table in SM Explorer |
| **BPA category tabs** | Native-style tabbed BPA results with severity summaries |
| **Memory Analyzer** | Vertipaq stats with model dropdown, tree view, subtab DataFrames |
| **Visual → SM navigation** | Click a visual to see its measures, then jump to the SM Explorer |
| **Dirty state tracking** | Unsaved changes indicator with save/discard for SM properties |
| **Partition refresh** | Refresh model/table/partition from the SM Explorer |

---

## Modes

| Mode | Behavior |
|------|----------|
| **Fix** | Applies selected fixers directly |
| **Scan** | Assesses what would change without modifying anything |
| **Scan + Fix** | Scans first (shows what would change), then applies fixes |

---

## Standalone Usage — Run Any Fixer Individually

Every fixer script can be called directly from a Fabric Notebook without the UI. Each follows the pattern `fix_xxx(report=..., workspace=..., scan_only=True/False)`.

### Report Fixers

```python
from sempy_labs.report._Fix_PieChart import fix_piecharts
fix_piecharts(report="My Report", workspace="My Workspace", scan_only=True)

from sempy_labs.report._Fix_BarChart import fix_barcharts
fix_barcharts(report="My Report", workspace="My Workspace", scan_only=False)

from sempy_labs.report._Fix_ColumnChart import fix_columncharts
fix_columncharts(report="My Report", workspace="My Workspace", scan_only=False)

from sempy_labs.report._Fix_PageSize import fix_page_size
fix_page_size(report="My Report", workspace="My Workspace", scan_only=True)

from sempy_labs.report._Fix_HideVisualFilters import fix_hide_visual_filters
fix_hide_visual_filters(report="My Report", workspace="My Workspace", scan_only=False)

from sempy_labs.report._Fix_UpgradeToPbir import fix_upgrade_to_pbir
fix_upgrade_to_pbir(report="My Report", workspace="My Workspace", scan_only=False)

from sempy_labs.report._Fix_MigrateSlicerToSlicerbar import fix_migrate_slicer_to_slicerbar
fix_migrate_slicer_to_slicerbar(report="My Report", workspace="My Workspace", scan_only=True)
```

### Semantic Model Fixers — Additive

```python
from sempy_labs.semantic_model._Fix_DiscourageImplicitMeasures import fix_discourage_implicit_measures
fix_discourage_implicit_measures(report="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Add_CalculatedTable_Calendar import add_calculated_calendar
add_calculated_calendar(report="My Model", workspace="My Workspace", scan_only=False)

from sempy_labs.semantic_model._Add_CalculatedTable_MeasureTable import add_measure_table
add_measure_table(report="My Model", workspace="My Workspace", scan_only=False)

from sempy_labs.semantic_model._Add_Table_LastRefresh import add_last_refresh_table
add_last_refresh_table(report="My Model", workspace="My Workspace", scan_only=False)

from sempy_labs.semantic_model._Add_CalcGroup_Units import add_calc_group_units
add_calc_group_units(report="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Add_CalcGroup_TimeIntelligence import add_calc_group_time_intelligence
add_calc_group_time_intelligence(report="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Add_MeasuresFromColumns import add_measures_from_columns
add_measures_from_columns(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Add_PYMeasures import add_py_measures
add_py_measures(dataset="My Model", workspace="My Workspace", scan_only=True)
```

### BPA Auto-Fixers

All BPA fixers take `(dataset, workspace, scan_only)`:

```python
from sempy_labs.semantic_model._Fix_FloatingPointDataType import fix_floating_point_datatype
fix_floating_point_datatype(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_IsAvailableInMdx import fix_isavailable_in_mdx
fix_isavailable_in_mdx(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_IsAvailableInMdxTrue import fix_isavailable_in_mdx_true
fix_isavailable_in_mdx_true(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_MeasureDescriptions import fix_measure_descriptions
fix_measure_descriptions(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_DateColumnFormat import fix_date_column_format
fix_date_column_format(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_MonthColumnFormat import fix_month_column_format
fix_month_column_format(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_MeasureFormat import fix_measure_format
fix_measure_format(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_HideForeignKeys import fix_hide_foreign_keys
fix_hide_foreign_keys(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_UseDivideFunction import fix_use_divide_function
fix_use_divide_function(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_AvoidAdding0 import fix_avoid_adding_zero
fix_avoid_adding_zero(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_DoNotSummarize import fix_do_not_summarize
fix_do_not_summarize(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_MarkPrimaryKeys import fix_mark_primary_keys
fix_mark_primary_keys(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_TrimObjectNames import fix_trim_object_names
fix_trim_object_names(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_CapitalizeObjectNames import fix_capitalize_object_names
fix_capitalize_object_names(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_PercentageFormat import fix_percentage_format
fix_percentage_format(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_WholeNumberFormat import fix_whole_number_format
fix_whole_number_format(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_FlagColumnFormat import fix_flag_column_format
fix_flag_column_format(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_SortMonthColumn import fix_sort_month_column
fix_sort_month_column(dataset="My Model", workspace="My Workspace", scan_only=True)

from sempy_labs.semantic_model._Fix_DataCategory import fix_data_category
fix_data_category(dataset="My Model", workspace="My Workspace", scan_only=True)
```

---

## Requirements

- **Microsoft Fabric** workspace (F or P capacity)
- **PBIR format** enabled for the report (required for report-layer fixes)
- **XMLA endpoint** enabled on the capacity (required for semantic model fixes)
- A Fabric Notebook to run the code

---

## Project Structure

```
src/
├── _pbi_fixer.py                              # Main orchestrator, inline tabs (Memory, BPA, Report BPA, Delta, About)
├── _ui_components.py                          # Shared theme, icons, tree-building, layout helpers
├── _sm_explorer.py                            # Semantic Model Explorer tab
├── _report_explorer.py                        # Report Explorer tab
├── _perspective_editor.py                     # Perspective Editor tab
├── report/
│   ├── _Fix_PieChart.py                       # Replace pie charts with bar charts
│   ├── _Fix_BarChart.py                       # Clean up bar chart formatting
│   ├── _Fix_ColumnChart.py                    # Clean up column chart formatting
│   ├── _Fix_PageSize.py                       # Upgrade default page size to Full HD
│   ├── _Fix_HideVisualFilters.py              # Hide visual-level filters
│   ├── _Fix_UpgradeToPbir.py                  # Convert PBIRLegacy → PBIR
│   └── _Fix_MigrateSlicerToSlicerbar.py       # Migrate slicers to slicerbar
└── semantic_model/
    ├── _Fix_DiscourageImplicitMeasures.py     # Set DiscourageImplicitMeasures = True
    ├── _Add_CalculatedTable_Calendar.py       # Add calculated calendar table
    ├── _Add_CalculatedTable_MeasureTable.py   # Add empty measure table
    ├── _Add_Table_LastRefresh.py              # Add Last Refresh table with M partition
    ├── _Add_CalcGroup_Units.py                # Add Units calculation group
    ├── _Add_CalcGroup_TimeIntelligence.py     # Add Time Intelligence calculation group
    ├── _Add_MeasuresFromColumns.py            # Auto-create measures from SummarizeBy columns
    ├── _Add_PYMeasures.py                     # Add PY time intelligence measures
    ├── _Fix_FloatingPointDataType.py          # BPA: Double → Decimal
    ├── _Fix_IsAvailableInMdx.py               # BPA: IsAvailableInMDX → False
    ├── _Fix_IsAvailableInMdxTrue.py           # BPA: IsAvailableInMDX → True
    ├── _Fix_MeasureDescriptions.py            # BPA: Set description to DAX expression
    ├── _Fix_DateColumnFormat.py               # BPA: Date columns → mm/dd/yyyy
    ├── _Fix_MonthColumnFormat.py              # BPA: Month columns → MMMM yyyy
    ├── _Fix_MeasureFormat.py                  # BPA: Unformatted measures → #,0
    ├── _Fix_HideForeignKeys.py                # BPA: Hide FK columns
    ├── _Fix_UseDivideFunction.py              # BPA: Replace / with DIVIDE()
    ├── _Fix_AvoidAdding0.py                   # BPA: Remove 0+ prefix
    ├── _Fix_DoNotSummarize.py                 # BPA: SummarizeBy → None
    ├── _Fix_MarkPrimaryKeys.py                # BPA: IsKey → True on PK columns
    ├── _Fix_TrimObjectNames.py                # BPA: Trim whitespace from names
    ├── _Fix_CapitalizeObjectNames.py          # BPA: Capitalize first letter
    ├── _Fix_PercentageFormat.py               # BPA: Percentage measures → #,0.0%
    ├── _Fix_WholeNumberFormat.py              # BPA: Whole number measures → #,0
    ├── _Fix_FlagColumnFormat.py               # BPA: Flag columns → Yes/No
    ├── _Fix_SortMonthColumn.py                # BPA: Sort month name by number
    └── _Fix_DataCategory.py                   # BPA: Set DataCategory by naming convention
```

---

## How It Works

1. **Report Fixers** use the **PBIR format** (Power BI Enhanced Report Format). The tool reads each `visual.json` and `page.json` file from the report definition, applies the selected fixes (e.g., swapping visual types, setting properties), and writes the changes back.

2. **Semantic Model Fixers** use the **XMLA endpoint** via the Tabular Object Model (TOM). The tool connects to the semantic model backing the report, checks whether the target object already exists (e.g., a calendar table, a calculation group), and only creates it if it is missing.

3. **The Orchestrator** (`_pbi_fixer.py`) is an `ipywidgets`-based interactive UI that lets you select fixers via checkboxes, choose a mode (Fix / Scan / Scan + Fix), and run everything with a single button click. It includes an XMLA write confirmation for semantic model changes and a live progress log.

---

## Important Notes

- **XMLA write warning:** Once a semantic model is modified via the XMLA endpoint, the Power BI Desktop `.pbix` file can no longer contain embedded data. This is irreversible. The UI shows a confirmation checkbox before applying semantic model fixes.
- **Calculation groups can impact performance.** The Units and Time Intelligence calculation groups are powerful but should be used judiciously with large models.
- **Idempotent by design.** Each fixer checks whether its target change already exists and skips if so. Running the tool multiple times is safe.

---

## Built With

- **Python** — all fixers are pure Python
- **[Semantic Link Labs](https://github.com/microsoft/semantic-link-labs)** — the open-source library that provides the report wrapper, TOM connection, and helper functions
- **ipywidgets** — for the interactive notebook UI
- **Microsoft Fabric** — Notebooks, PBIR format, XMLA endpoint
- **GitHub Copilot** — used extensively during development for code generation, refactoring, and documentation

---

## Author

**Alexander Korn** — [GitHub](https://github.com/KornAlexander)

---

## License

This project is part of [Semantic Link Labs](https://github.com/microsoft/semantic-link-labs) and is released under the MIT License.
