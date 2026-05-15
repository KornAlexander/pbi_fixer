<p align="center">
  <img src="https://kornalexander.github.io/pbi_fixer/assets/img/report-explorer.png" alt="PBI Fixer — Report Explorer" width="720"/>
</p>

<p align="center">
  <a href="https://github.com/KornAlexander/pbi_fixer/blob/main/LICENSE" target="_blank">
    <img src="https://badgen.net/github/license/KornAlexander/pbi_fixer" alt="License">
  </a>
  <a href="https://github.com/KornAlexander/pbi_fixer/stargazers" target="_blank">
    <img src="https://badgen.net/github/stars/KornAlexander/pbi_fixer" alt="Stars">
  </a>
  <a href="https://github.com/KornAlexander/pbi_fixer/network/members" target="_blank">
    <img src="https://badgen.net/github/forks/KornAlexander/pbi_fixer" alt="Forks">
  </a>
  <a href="https://github.com/KornAlexander/pbi_fixer/issues" target="_blank">
    <img src="https://badgen.net/github/issues/KornAlexander/pbi_fixer" alt="Issues">
  </a>
  <a href="https://github.com/KornAlexander/pbi_fixer/commits/main" target="_blank">
    <img src="https://badgen.net/github/commits/KornAlexander/pbi_fixer" alt="Commits">
  </a>
  <a href="https://kornalexander.github.io/pbi_fixer/" target="_blank">
    <img src="https://badgen.net/badge/website/pbi_fixer/blue" alt="Website">
  </a>
</p>

---

# PBI Fixer: a one-line Power BI development environment for Microsoft Fabric

A Python-based accelerator that turns a single line — `pbi_fixer()` — in a Microsoft Fabric Notebook into a full, interactive Power BI development environment. Browse, scan and fix reports and semantic models, run the BPA with one-click auto-fix, analyze Vertipaq memory and delta tables, manage perspectives and translations, generate model diagrams and report prototypes — all without leaving the notebook.

PBI Fixer is open source and built on top of [Semantic Link Labs](https://github.com/microsoft/semantic-link-labs) by [Michael Kovalsky](https://www.linkedin.com/in/michaelkovalsky/), which provides the core `connect_report()` (PBIR) and `connect_semantic_model()` (TOM/XMLA) abstractions.

> 📌 The PBI Fixer currently lives in a fork of Semantic Link Labs (`feature/pbi-fixer-ui`). It is not yet part of the official package — once (if) it gets merged, the install becomes a true one-liner: `%pip install semantic-link-labs`.

## 🚀 Features

- **Cloud-native**: runs entirely inside a Microsoft Fabric Notebook — no local install, no downloads, no Desktop, no external tools.
- **45+ automated fixers across 12 interactive tabs**: 15 report fixers, 11 semantic model fixers, 19 BPA auto-fixers — every one supports a read-only **Scan mode**.
- **Report Explorer**: tree view of pages and visuals, live embedded preview, scan & fix actions, PBIR auto-detection and conversion.
- **Semantic Model Explorer**: full object tree, DAX editing with Save/Discard, create measures / calculated columns / calculated tables, table data preview, undo/redo with change tracking.
- **Model BPA with one-click auto-fix**: 19 best practice rules across 6 categories (Data Types, MDX, Documentation, Formatting, Schema, Naming) with Fix All / Fix Rule / Fix Row granularity. 15 of these auto-fixers have no equivalent in any other tool.
- **Memory Analyzer**: Vertipaq stats by table / column / partition / relationship / hierarchy with color-coded size bars, plus Direct Lake column residency and temperature.
- **IBCS implementation**: end-to-end variance charts (calendar table → date relationship → PY measures → error bars → IBCS formatting), pie-chart replacement, column → horizontal bar conversion.
- **Translations Editor** with one-click Azure AI auto-translate (no API key required) across 20 built-in language codes.
- **Perspective Editor** with tri-state checkboxes (● Full / ◐ Partial / ○ None) for visual CRUD on model perspectives.
- **Model Diagram & Prototype**: auto-generated SVG model diagram, plus full-report screenshot capture with navigation/drillthrough detection and Excalidraw / SVG export.
- **Delta Analyzer**: parquet file, row group and column chunk inspection for Direct Lake optimization.
- **Standalone API**: every fixer is also a stateless Python function — call them from your own notebooks, batch scripts, CI/CD quality gates or AI agents.

📺 Watch the walkthrough below or visit the project website for a quick overview: [kornalexander.github.io/pbi_fixer](https://kornalexander.github.io/pbi_fixer/).

## 🎬 Demo

[![Watch the PBI Fixer walkthrough on YouTube](https://img.youtube.com/vi/BQdSo6ZnmKY/maxresdefault.jpg)](https://www.youtube.com/watch?v=BQdSo6ZnmKY)

> 🎥 Click the thumbnail to watch on YouTube: [PBI Fixer walkthrough](https://www.youtube.com/watch?v=BQdSo6ZnmKY).

## Table of Contents

- [Installation](#hammer_and_wrench-installation)
- [Getting Started](#rocket-getting-started)
  - [Prerequisites](#clipboard-prerequisites)
  - [Launch the UI](#zap-launch-the-ui)
  - [Optional Parameters](#wrench-optional-parameters)
- [The Tabs](#bookmark_tabs-the-tabs)
- [The Complete Fix Arsenal](#books-the-complete-fix-arsenal)
- [Standalone API](#robot-standalone-api)
- [Modes — Scan / Fix / Scan + Fix](#repeat-modes--scan--fix--scan--fix)
- [Important Notes](#warning-important-notes)
- [How It Works](#gear-how-it-works)
- [Project Structure](#file_folder-project-structure)
- [Built On](#hammer-built-on)
- [Feedback & Contributing](#raising_hand-feedback--contributing)
- [License](#scroll-license)
- [Trademarks](#shield-trademarks)

## :hammer_and_wrench: Installation

Make sure you are running inside a **Microsoft Fabric Notebook** (Python 3.10+ via the Fabric Spark runtime). Then, in a notebook cell:

```python
%pip install git+https://github.com/KornAlexander/semantic-link-labs.git@feature/pbi-fixer-ui
```

This installs the PBI Fixer fork of Semantic Link Labs. Once (if) the fixer is merged into the upstream `semantic-link-labs` package, you will be able to use `%pip install semantic-link-labs` instead.

# :rocket: Getting Started

Follow the [Prerequisites](#clipboard-prerequisites), then [Launch the UI](#zap-launch-the-ui). If you run into any issues, wish for new features or just want to let us know that you like the tool, please open an issue or [reach out on LinkedIn](https://www.linkedin.com/in/alexanderkorn/).

## :clipboard: Prerequisites

Before installing and running this solution, ensure you have:

- A **Microsoft Fabric** workspace on an F or P capacity (or a Fabric trial capacity).
- A **Fabric Notebook** in that workspace.
- **PBIR format** for the reports you want to fix (the tool detects PBIRLegacy and offers an in-place conversion).
- **XMLA read/write** enabled at the tenant level — required for any semantic model operation.
- **Large semantic model storage format** enabled in the workspace settings — required for XMLA write.

| Feature | Tenant Setting | Path in Admin Portal |
|---|---|---|
| Prototype screenshots | "Export reports as image files" | Admin Portal → Tenant settings → Export and sharing |
| Download .pbix | "Download reports" | Admin Portal → Tenant settings → Export and sharing |

> 📌 If "Export reports as image files" is disabled (the default in many tenants), the Prototype tab falls back to text-only page boxes instead of screenshots. The setting can take a few minutes to propagate after enabling.

## :zap: Launch the UI

In a notebook cell, run:

```python
from sempy_labs import pbi_fixer

pbi_fixer()
```

That is all. The interactive UI renders directly in the cell output. Type your workspace name and report name, select your fixers, and click **Run**.

## :wrench: Optional Parameters

```python
# Pre-fill workspace and report
pbi_fixer(workspace="My Workspace", report="Sales Dashboard")

# Load multiple reports / models (comma-separated)
pbi_fixer(workspace="My Workspace", report="Sales Dashboard, Finance Report")

# Load ALL items in a workspace
pbi_fixer(workspace="My Workspace")
```

# :bookmark_tabs: The Tabs

| Tab | Icon | Description |
|---|---|---|
| Fix All | ⚡ | One-click scan & fix across all categories — report fixers, model fixers, Model BPA, Report BPA. |
| Model Explorer | 📊 | Tree view of tables/columns/measures, DAX editing, table data preview, properties, actions dropdown. |
| Report Explorer | 📄 | Tree view of pages/visuals, live preview, properties, scan & fix actions. |
| Perspectives | 👁 | Perspective editor with tri-state checkboxes. |
| Translations | 🌐 | Multi-language metadata grid with one-click AI auto-translate. |
| Memory Analyzer | 💾 | Vertipaq stats: models → tables → columns by size, color-coded percentage bars. |
| Model BPA | 📋 | 19 BPA rules across 6 categories with Fix All / Fix Rule / Fix Row granularity. |
| Report BPA | 📄 | Report-level BPA with auto PBIRLegacy conversion before scanning. |
| Delta Analyzer | 📐 | Delta table inspection: parquet files, row groups, column chunks, statistics. |
| Prototype | ✏️ | Page screenshots with auto-detected navigation; export to Excalidraw / SVG. |
| Model Diagram | 🗺 | Auto-generated SVG diagram with table boxes, columns, measures and relationship lines. |
| About | ℹ️ | Version info, credits and links. |

# :books: The Complete Fix Arsenal

Every fixer supports `scan_only=True` — a read-only pass that tells you what would change without modifying anything.

## Report Fixers (15)

| # | Fixer | What it does |
|---|---|---|
| 1 | Fix Pie Charts | Replaces pie charts with clustered bar charts |
| 2 | Fix Bar Charts | Removes axis clutter, adds data labels, removes gridlines |
| 3 | Fix Column Charts | Same clean-up applied to column charts |
| 4 | Fix Line Charts | Standardized line chart formatting |
| 5 | Fix All Charts | Unified formatting pass across all chart types |
| 6 | Column → Line | Converts column charts to line charts (date axis) |
| 7 | Column → Bar (IBCS) | Converts column charts to horizontal bar charts |
| 8 | Fix IBCS Variance | End-to-end IBCS variance implementation |
| 9 | Fix Page Size | Upgrades default pages to Full HD (1920×1080) |
| 10 | Hide Visual Filters | Hides visual-level filters from consumers |
| 11 | Fix Visual Alignment | Snaps misaligned visuals to consistent positions |
| 12 | Remove Unused Custom Visuals | Cleans up unused custom visual registrations |
| 13 | Disable Show Items No Data | Turns off "Show Items with No Data" |
| 14 | Migrate Report-Level Measures | Moves report-level measures into the semantic model |
| 15 | Convert to PBIR | Upgrades PBIRLegacy to PBIR format |

## Semantic Model Fixers (11)

| # | Fixer | What it does |
|---|---|---|
| 1 | Discourage Implicit Measures | Prevents implicit measure usage (required for calc groups) |
| 2 | Add Calendar Table | 20-column calculated calendar with 3 hierarchies + auto-relationship |
| 3 | Add Measure Table | Empty calculated table to centralize measures |
| 4 | Add Last Refresh Table | M partition with refresh timestamp + measure |
| 5 | Add Units Calc Group | Thousand & Million items with % skip logic |
| 6 | Add Time Intelligence Calc Group | AC / Y-1 / Y-2 / Y-3 / YTD + absolute / relative / achievement variances (21 items) |
| 7 | Measures from Columns | Auto-create explicit measures from `SummarizeBy` settings |
| 8 | Add PY Measures | PY + ΔPY + ΔPY% for selected measures |
| 9 | Setup Incremental Refresh | Auto date column detection + policy configuration |
| 10 | Cache Pre-warm | Direct Lake warm-up perspective + notebook generation |
| 11 | Prep for AI | Descriptions, synonyms, linguistic metadata for Copilot readiness |

## Model BPA Auto-Fixers (19)

| # | Fixer | Category |
|---|---|---|
| 1 | Fix Floating Point Types (Double → Decimal) | 🔢 Data Types |
| 2 | Fix IsAvailableInMDX (False on non-attribute) | 📡 MDX |
| 3 | Fix IsAvailableInMDX (True on key/hierarchy) | 📡 MDX |
| 4 | Fix Measure Descriptions | 📝 Documentation |
| 5 | Fix Date Column Format (`mm/dd/yyyy`) | 📊 Formatting |
| 6 | Fix Month Column Format (`MMMM yyyy`) | 📊 Formatting |
| 7 | Fix Measure Format (`#,0`) | 📊 Formatting |
| 8 | Fix Percentage Format (`#,0.0%`) | 📊 Formatting |
| 9 | Fix Whole Number Format (`#,0`) | 📊 Formatting |
| 10 | Fix Flag Column Format (Yes/No) | 📊 Formatting |
| 11 | Fix Sort Month Column | 📊 Formatting |
| 12 | Fix Data Category | 📊 Formatting |
| 13 | Fix DIVIDE Function | 📊 Formatting |
| 14 | Fix Avoid Adding 0 prefix | 📊 Formatting |
| 15 | Hide Foreign Keys | 🔗 Schema |
| 16 | Fix Do Not Summarize | 🔗 Schema |
| 17 | Mark Primary Keys | 🔗 Schema |
| 18 | Trim Object Names | 🏷 Naming |
| 19 | Capitalize Object Names | 🏷 Naming |

# :robot: Standalone API

Every fixer is a stateless Python function with a predictable signature — perfect for AI agents, CI/CD quality gates, and batch processing.

```python
# Replace all pie charts in a report
from sempy_labs.report._Fix_PieChart import fix_piecharts
fix_piecharts("Sales Report", workspace="Production")

# Scan first (read-only)
fix_piecharts("Sales Report", workspace="Production", scan_only=True)

# IBCS variance — end to end
from sempy_labs.report._Fix_IBCSVariance import fix_ibcs_variance
fix_ibcs_variance("Sales Report", workspace="Production")

# Batch process multiple reports
from sempy_labs.report._Fix_PageSize import fix_page_size

reports = ["Sales", "Finance", "HR"]
for report in reports:
    fix_piecharts(report, workspace="Production")
    fix_page_size(report, workspace="Production")
```

A complete function reference is available in [`STANDALONE_API.md`](./STANDALONE_API.md) and on the project website: [kornalexander.github.io/pbi_fixer](https://kornalexander.github.io/pbi_fixer/#api).

# :repeat: Modes — Scan / Fix / Scan + Fix

| Mode | Behavior |
|---|---|
| **Fix** | Applies the selected fixers directly. |
| **Scan** | Read-only — assesses what would change without modifying anything. Always safe. |
| **Scan + Fix** | Scans first (shows what would change), then applies the fixes. |

# :warning: Important Notes

- **XMLA write is irreversible.** Once a semantic model is modified via the XMLA endpoint, the Power BI Desktop `.pbix` can no longer contain embedded data. The UI shows a confirmation checkbox before applying any semantic model fix.
- **Calculation groups can impact performance.** The Units and Time Intelligence calc groups are powerful but should be used judiciously on very large models.
- **Idempotent by design.** Each fixer checks whether its target change already exists and skips if so — running the tool multiple times is safe.
- **Beta software.** Test on a non-production workspace first. Expect rough edges and please report them.

# :gear: How It Works

1. **Report fixers** use the **PBIR** (Power BI Enhanced Report Format) definition. The tool reads each `visual.json` and `page.json`, applies the selected changes (swapping visual types, setting properties, generating measures, etc.), and writes the report definition back through the Fabric REST API.
2. **Semantic model fixers** use the **XMLA endpoint** via the **Tabular Object Model (TOM)**. The tool connects to the model backing the report, checks whether the target object already exists, and only creates it if it is missing.
3. **The orchestrator** (`_pbi_fixer.py`) is an `ipywidgets` UI that renders inline in the notebook output. It exposes the fixers, modes, and explorer tabs, and coordinates the XMLA write confirmation gate and live progress log.

# :file_folder: Project Structure

```
src/
├── _pbi_fixer.py                       # Main orchestrator + inline tabs
├── _ui_components.py                   # Shared theme, icons, tree-building, layout
├── _model_explorer.py                  # Semantic Model Explorer tab
├── _report_explorer.py                 # Report Explorer tab
├── _perspective_editor.py              # Perspective Editor tab
├── _fix_model_bpa.py                   # SM BPA scan runner
├── _fix_report_bpa.py                  # Report BPA scan runner
├── _report_helper.py                   # Report helper utilities
├── _report_prototype.py                # Auto-generate report prototypes
├── _report_theme.py                    # Extract and apply report themes
│
├── # ── Report Fixers (15) ──
├── _Fix_PieChart.py                    # Replace pie charts with bar charts
├── _Fix_BarChart.py                    # Clean up bar chart formatting
├── _Fix_ColumnChart.py                 # Clean up column chart formatting
├── _Fix_Charts.py                      # Consolidated chart fixer
├── _Fix_ColumnToLine.py                # Column-to-line for date axes
├── _Fix_PageSize.py                    # Upgrade page size to Full HD
├── _Fix_HideVisualFilters.py           # Hide visual-level filters
├── _Fix_DisableShowItemsNoData.py      # Disable "Show items with no data"
├── _Fix_RemoveUnusedCustomVisuals.py   # Remove unused custom visuals
├── _Fix_MigrateReportLevelMeasures.py  # Migrate report-level measures
├── _Fix_VisualAlignment.py             # Align and distribute visuals
├── _Fix_UpgradeToPbir.py               # PBIRLegacy → PBIR
├── _Fix_MigrateSlicerToSlicerbar.py    # Migrate slicers to slicerbar
├── _Fix_IBCSVariance.py                # IBCS-compliant variance charts
│
├── # ── SM Additive Fixers (11) ──
├── _Fix_DiscourageImplicitMeasures.py
├── _Add_CalculatedTable_Calendar.py
├── _Add_CalculatedTable_MeasureTable.py
├── _Add_Table_LastRefresh.py
├── _Add_CalcGroup_Units.py
├── _Add_CalcGroup_TimeIntelligence.py
├── _Add_MeasuresFromColumns.py
├── _Add_PYMeasures.py
├── _Add_CacheWarming.py
├── _Add_IncrementalRefresh.py
├── _Add_PrepForAI.py
│
└── # ── BPA Auto-Fixers (19) ──
    _Fix_FloatingPointDataType.py, _Fix_IsAvailableInMdx.py,
    _Fix_IsAvailableInMdxTrue.py, _Fix_MeasureDescriptions.py,
    _Fix_DateColumnFormat.py, _Fix_MonthColumnFormat.py,
    _Fix_MeasureFormat.py, _Fix_PercentageFormat.py,
    _Fix_WholeNumberFormat.py, _Fix_FlagColumnFormat.py,
    _Fix_SortMonthColumn.py, _Fix_DataCategory.py,
    _Fix_UseDivideFunction.py, _Fix_AvoidAdding0.py,
    _Fix_HideForeignKeys.py, _Fix_DoNotSummarize.py,
    _Fix_MarkPrimaryKeys.py, _Fix_TrimObjectNames.py,
    _Fix_CapitalizeObjectNames.py
```

# :hammer: Built On

- **[Semantic Link Labs](https://github.com/microsoft/semantic-link-labs)** by [Michael Kovalsky](https://www.linkedin.com/in/michaelkovalsky/) — TOM connectivity, Model BPA, Report BPA, Vertipaq Analyzer, ReportWrapper, Perspective Editor, DAX utilities, Direct Lake support.
- **[SQLBI](https://www.sqlbi.com/)** — DAX Formatter API for clean DAX formatting.
- **[Lukasz Obst](https://www.linkedin.com/in/lukasz-obst-3672083a2/)** — original Prep for AI implementation.
- **ipywidgets**, **powerbiclient**, **SynapseML** (Azure AI Translator), **Microsoft Fabric Notebooks**.

# :raising_hand: Feedback & Contributing

Feedback — positive or negative — is what drives this project forward. The fastest channels:

- 🐛 [Open an issue](https://github.com/KornAlexander/pbi_fixer/issues)
- 💬 [Reach out on LinkedIn](https://www.linkedin.com/in/alexanderkorn/)
- ✍️ Read the deep-dive write-up: [PBI Fixer v2 — From 11 Fixers to a Full Power BI Development Environment](https://actionablereporting.com/2026/04/07/pbi-fixer-v2-from-11-fixers-to-a-full-power-bi-development-environment/)
- 🌐 Project website: [kornalexander.github.io/pbi_fixer](https://kornalexander.github.io/pbi_fixer/)

Pull requests are welcome. Because PBI Fixer currently lives in a fork of Semantic Link Labs (`feature/pbi-fixer-ui`), code changes that touch the fixer logic should be opened against [`KornAlexander/semantic-link-labs`](https://github.com/KornAlexander/semantic-link-labs/tree/feature/pbi-fixer-ui); changes to docs, samples and the standalone API stay in this repo.

# :scroll: License

This project is released under the MIT License — see the [LICENSE](./LICENSE) file for details.

# :shield: Trademarks

This project may contain trademarks or logos for projects, products, or services. Use of Microsoft trademarks or logos is subject to and must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general). Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship. Any use of third-party trademarks or logos are subject to those third-party's policies.
