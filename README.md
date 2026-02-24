# Power BI Report Fixer

**One line of Python to assess, standardize, and fix any Power BI report.**

The Power BI Report Fixer is a free, open-source, notebook-native tool built on [Semantic Link Labs](https://github.com/microsoft/semantic-link-labs) that combines 11 fixers for both the report layer and the semantic model into a single interactive UI. No installs. No downloads. No license costs. Just one line of Python in a Microsoft Fabric Notebook.

---

## Quick Start — How to Use

### Step 1: Install

In a **Microsoft Fabric Notebook** cell, run:

```python
%pip install git+https://github.com/KornAlexander/semantic-link-labs.git
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

# Target a specific page
pbi_fixer(workspace="Your Workspace Name", report="My Report", page_name="Overview")
```

---

## What It Does

The `pbi_fixer()` function launches an interactive widget UI that combines **11 fixers** across two categories:

### Report Fixers (Visual Layer — PBIR Format)

| Fixer | What It Does |
|-------|-------------|
| **Fix Pie Charts** | Replaces all pie charts with clustered bar charts (or any target visual type) |
| **Fix Bar Charts** | Removes axis titles/values, adds data labels, removes gridlines |
| **Fix Column Charts** | Same clean-up as bar charts, applied to column charts |
| **Fix Page Size** | Upgrades default 720×1280 pages to 1080×1920 (Full HD) |
| **Hide Visual Filters** | Sets `isHiddenInViewMode` on all visual-level filters |

### Semantic Model Fixers (XMLA Endpoint)

| Fixer | What It Does |
|-------|-------------|
| **Discourage Implicit Measures** | Enables `DiscourageImplicitMeasures` (recommended and required for calculation groups) |
| **Add Calendar Table** | Generates a calculated calendar table with date-intelligence columns, hierarchies, and display folders — only if no date table is marked |
| **Add Measure Table** | Adds an empty calculated table to centralize measures |
| **Add Last Refresh Table** | Adds a table with an M partition and a measure showing the last refresh timestamp |
| **Add Units Calculation Group** | Creates Thousand and Million items, skipping percentage/ratio measures |
| **Add Time Intelligence Calculation Group** | Generates AC, Y-1/Y-2/Y-3, YTD, and absolute/relative/achievement variances |

---

## Modes

| Mode | Behavior |
|------|----------|
| **Fix** | Applies selected fixers directly |
| **Scan** | Assesses what would change without modifying anything |
| **Scan + Fix** | Scans first (shows what would change), then applies fixes |

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
├── _pbi_fixer.py                              # Main orchestrator & interactive UI (ipywidgets)
├── report/
│   ├── _Fix_PieChart.py                       # Replace pie charts with bar charts
│   ├── _Fix_BarChart.py                       # Clean up bar chart formatting
│   ├── _Fix_ColumnChart.py                    # Clean up column chart formatting
│   ├── _Fix_PageSize.py                       # Upgrade default page size to Full HD
│   └── _Fix_HideVisualFilters.py              # Hide visual-level filters from end users
└── semantic_model/
    ├── _Fix_DiscourageImplicitMeasures.py     # Set DiscourageImplicitMeasures = True
    ├── _Add_CalculatedTable_Calendar.py       # Add a full calculated calendar table
    ├── _Add_CalculatedTable_MeasureTable.py   # Add an empty measure table
    ├── _Add_Table_LastRefresh.py              # Add a Last Refresh table with M partition
    ├── _Add_CalcGroup_Units.py                # Add a Units calculation group
    └── _Add_CalcGroup_TimeIntelligence.py     # Add a Time Intelligence calculation group
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
