# PBI Fixer — Development Plan

## Vision

PBI Fixer is a comprehensive Power BI development environment that runs natively inside Microsoft Fabric Notebooks. It provides a single ipywidgets-based UI built on top of semantic-link-labs that covers the full development lifecycle — browsing, editing, fixing, analyzing, and deploying semantic models and reports — without leaving the notebook environment.

The tool connects to any Fabric workspace and loads all semantic models and reports into a unified object tree. A three-panel layout — object tree on the left, preview top-right, properties bottom-right — gives developers full visibility and control over their Power BI assets.

### What PBI Fixer does

- **Browse, edit & fix semantic models**: Explore tables, columns, measures, hierarchies, and relationships. Edit DAX expressions, properties, format strings, and display folders. Preview table data inline. Save changes back via XMLA. 19 BPA auto-fixers cover data types, MDX visibility, formatting, schema hygiene, naming conventions, and documentation — 15 of which have no standard auto-fix in the default BPA rules, making PBI Fixer significantly more capable than the built-in BPA fix script. Plus additive fixers for calendar tables, measure tables, last-refresh tables, calculation groups (units, time intelligence), and auto-created measures.
- **Browse, edit & fix reports**: Navigate pages and visuals, preview embedded reports via powerbiclient, edit visual positions/sizes/titles, and manage page properties. All changes written through PBIR JSON definitions via `connect_report`. 7 report fixers (pie charts, bar charts, column charts, page size, visual filters, visual alignment, PBIR upgrade) — each with scan-only mode to preview violations before applying.
- **Analyze model performance**: Memory Analyzer (VertipaqAnalyzer stats), Model BPA and Report BPA with categorized findings, Delta Analyzer for lakehouse table inspection.
- **Manage perspectives**: Full Perspective Editor for creating and editing model perspectives.
- **Translate models**: Load existing translations, auto-translate via Azure AI Translator (SynapseML), preview diffs, and apply via XMLA.
- **Prototype reports**: Generate SVG and Excalidraw-format report prototypes with optional page screenshots.
- **Visualize model structure**: Auto-layout SVG relationship diagrams with nearest-edge connection lines.
- **Clone & deploy**: Clone reports and/or semantic models within or across workspaces via REST API round-trips.
- **Download**: Export as .pbix or .pbip for local development.

### PBIR format gate

A PBIR format check runs automatically on load. Reports in PBIR format work normally; PBIRLegacy reports are flagged with a warning and can be converted in-place before any fixers run. Non-PBIR formats (RDL, etc.) are shown greyed out.

### Standalone compatibility

Every fixer works both inside the UI and as a standalone function call in any Fabric Notebook — e.g. `fix_piecharts(report="Sales Report", workspace="Dev", scan_only=True)`. No UI dependency required.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ ┌─────────────────────────────────────────────────┐      │
│ │ Workspace [_______________]  Report/SM [_,_,_]  │      │
│ │                              [Load]             │      │
│ └─────────────────────────────────────────────────┘      │
│  [⬇ Download .pbix]  [⬇ Download .pbip]                 │
│  [📊 SM] [📄 Report] [⚡ Fixer] [👁 Persp] [💾 Mem]      │
│  [📋 BPA] [📄 Report BPA] [📐 Delta Analyzer] [ℹ️ About] │
├────────────────┬─────────────────────────────────────────┤
│                │  Top-Right: Preview                     │
│  Left Panel:   │  (DAX expression / visual / embed)      │
│  Object Tree   │                                         │
│  (all SMs +    ├─────────────────────────────────────────┤
│   reports in   │  Bottom-Right: Properties / Vertipaq     │
│   workspace)   │  (data type, format, memory stats)       │
├────────────────┴─────────────────────────────────────────┤
│  Inline status / notifications (within each tab panel)    │
└──────────────────────────────────────────────────────────┘
```

---

## File Structure

```
src/
  _pbi_fixer.py          # Tab wrapper + Fixer UI + PBIR check gate + inline tabs
                         #   (Memory Analyzer, BPA, Report BPA, Delta Analyzer,
                         #    Prototype, Model Diagram, Script Runner, About)
  _ui_components.py      # Shared theme, icons, tree-building, layout helpers
  _model_explorer.py     # Model Explorer tab (renamed from _sm_explorer.py at v1.2.119)
  _report_explorer.py    # Report Explorer tab
  _perspective_editor.py # Perspective Editor tab
  _fix_model_bpa.py      # Standalone fix_model_bpa() — scan Model BPA + auto-fix via fixer files
  report/                # Report fixers + standalone modules
    _Fix_PieChart.py
    _Fix_BarChart.py
    _Fix_ColumnChart.py
    _Fix_PageSize.py
    _Fix_HideVisualFilters.py
    _Fix_UpgradeToPbir.py
    _Fix_VisualAlignment.py
    _Fix_RemoveUnusedCustomVisuals.py
    _Fix_DisableShowItemsNoData.py
    _Fix_MigrateReportLevelMeasures.py
    _fix_report_bpa.py     # Standalone fix_report_bpa() — scan Report BPA + auto-fix via fixer files
    _report_prototype.py   # Standalone prototype generator (SVG + Excalidraw)
    _report_theme.py       # Theme get/set/update module
  semantic_model/        # SM fixers — additive + BPA auto-fixers (each standalone)
    _Fix_DiscourageImplicitMeasures.py
    _Add_CalculatedTable_Calendar.py
    _Add_CalculatedTable_MeasureTable.py
    _Add_Table_LastRefresh.py
    _Add_CalcGroup_Units.py
    _Add_CalcGroup_TimeIntelligence.py
    _Add_MeasuresFromColumns.py
    _Add_PYMeasures.py
    _Setup_IncrementalRefresh.py  # Incremental refresh setup (Feature 27)
    _Fix_FloatingPointDataType.py
    _Fix_IsAvailableInMdx.py
    _Fix_IsAvailableInMdxTrue.py
    _Fix_MeasureDescriptions.py
    _Fix_DateColumnFormat.py
    _Fix_MonthColumnFormat.py
    _Fix_MeasureFormat.py
    _Fix_HideForeignKeys.py
    _Fix_UseDivideFunction.py
    _Fix_AvoidAdding0.py
    _Fix_DoNotSummarize.py
    _Fix_MarkPrimaryKeys.py
    _Fix_TrimObjectNames.py
    _Fix_CapitalizeObjectNames.py
    _Fix_PercentageFormat.py
    _Fix_WholeNumberFormat.py
    _Fix_FlagColumnFormat.py
    _Fix_SortMonthColumn.py
    _Fix_DataCategory.py
```

---

## Connection & Loading

### Single Workspace, Multiple Items

* **Workspace input**: single text field — one workspace name or ID. No comma separation for workspaces. When a workspace is entered (or changed), the UI fetches the list of all reports and semantic models in that workspace via the Fabric REST API in the background.
* **Report / SM input**: a **combo widget** that supports both **dropdown selection** and **free text** entry:
  + **Dropdown mode**: after a workspace is entered, the dropdown is populated with a deduplicated list of all report and semantic model names in the workspace. Items are listed as `"📄 Report Name"` and `"📊 Model Name"` to distinguish types. If a report and semantic model share the same display name, show the name only once (not duplicated) — the tool loads both the report and its underlying model regardless.
  + **Free text mode**: the user can also type or paste names/IDs directly, including **comma-separated** values (e.g. `"Sales Report, Finance Report"` or `"abc-123, def-456"`). Free text takes precedence over dropdown selection.
  + If left **blank** → load **all** reports and semantic models in the workspace.
  + Implementation: use `widgets.Combobox` (ipywidgets) which supports both a dropdown list and free text input. Populate `options` after workspace is set. For the REST call, use `GET /v1.0/myorg/groups/{ws}/reports` and `GET /v1.0/myorg/groups/{ws}/datasets` to build the combined list. Deduplicate by display name (case-insensitive), keeping both item types internally for loading.
* **Load button**: triggers connecting to the workspace and fetching metadata for all matching items.

### Timeout

* Hard timeout of **5 minutes** (300s) for the full load operation (`_TOTAL_TIMEOUT = 300`).
* If loading all items in a large workspace, iterate items sequentially and abort with a partial result + warning if the 5-minute wall clock limit is reached.
* Individual item connections (TOM / connect\_report) should have a per-item timeout of **60s**.

### Unified Object Tree

After loading, the left panel shows a single tree with all loaded items:

```
📊 Sales Model
  ├─ 📁 Tables
  │   ├─ Sales
  │   │   ├─ 🔢 Amount (column)
  │   │   └─ Σ Total Sales (measure)
  │   └─ Date
  ├─ 📁 Relationships
  └─ 📁 Calculation Groups
📊 Finance Model
  └─ ...
📄 Sales Report (PBIR)
  ├─ 📃 Overview [12 visuals]
  └─ 📃 Details [8 visuals]
📄 Old Report (PBIRLegacy) ⚠️
  └─ ...
```

### PBIR Format Gate

* On load, check every report's format via `_check_report_format()` which calls the Fabric REST API (`GET /v1.0/myorg/groups/{ws}/reports`).
* Reports in **PBIR** format: shown normally.
* Reports in **PBIRLegacy** format: shown with a ⚠️ warning badge in the tree. Fixer tab skips them unless "Upgrade to PBIR" is selected. Report BPA auto-converts PBIRLegacy if needed.
* Reports in other formats (RDL, etc.): shown greyed out, not actionable.
* **All report fixers require PBIR**. If a user attempts to run a fixer on a PBIRLegacy report without selecting "Upgrade to PBIR", the UI logs a warning and skips.

### Convert to PBIR

Two conversion approaches exist in Semantic Link Labs:

1. **`_Fix_UpgradeToPbir.fix_upgrade_to_pbir()`** — REST round-trip (`getDefinition` → `updateDefinition`). Used in the Fixer tab and Report Explorer actions dropdown.
2. **`report._upgrade_to_pbir.upgrade_to_pbir()`** — Batch upgrade via embed + save. Supports `List[str|UUID]` for reports and workspaces. Better for bulk operations. Already merged in upstream SLL.

---

## Tab Layout (v1.2.216)

| Tab | Icon | Source | Description |
| --- | --- | --- | --- |
| Fix All | ⚡ | `_pbi_fixer.py` (inline) | Top-level scan+fix across all 4 categories: Report Fixers, Model Fixers, Model BPA, Report BPA. Always visible (first tab). |
| Semantic Model | 📊 | `_model_explorer.py` | Tree + DAX preview + table data preview + properties + scan + search filter + actions dropdown |
| Report | 📄 | `_report_explorer.py` | Tree + visual preview + properties + format overview + scan + search filter + actions dropdown |
| Fixer | ⚡ | `_pbi_fixer.py` (inline) | Checkbox-based fixer selection, God Button, Scan/Fix/Scan+Fix modes |
| Perspectives | 👁 | `_perspective_editor.py` | Perspective Editor (based on m-kovalsky) |
| Memory Analyzer | 💾 | `_pbi_fixer.py` (`_vertipaq_tab`) | Vertipaq stats with model dropdown, subtab DataFrames |
| BPA | 📋 | `_pbi_fixer.py` (`_bpa_tab`) | Model BPA with category tabs, severity badges, grouped checkbox fixers for 19 rule types |
| Report BPA | 📄 | `_pbi_fixer.py` (`_report_bpa_tab`) | Report BPA via `run_report_bpa()`, auto-converts PBIRLegacy |
| Delta Analyzer | 📐 | `_pbi_fixer.py` (`_delta_analyzer_tab`) | Delta table analysis: summary, parquet files, row groups, column chunks |
| Prototype | ✏️ | `report/_report_prototype.py` | Report prototype with SVG + Excalidraw export, optional page screenshots |
| Translations | 🌐 | `_pbi_fixer.py` (`_translations_tab`) | Load, auto-translate (Azure AI Translator via SynapseML), preview diff, apply via XMLA |
| Model Diagram | 🗺 | `_pbi_fixer.py` (`_diagram_tab`) | SVG relationship diagram with nearest-edge connections |
| About | ℹ️ | `_pbi_fixer.py` (inline) | Author info, links, tech credits (SLL, ipywidgets, powerbiclient, SynapseML, DAX Formatter) |

* **Fix All tab** is always visible as the first tab, even with `all_tabs=False`. Scans all 4 categories and auto-fixes BPA findings that have standalone fixers.
* **Fixer tab** is hidden by default (`show_fixer_tab=False`); all fixers are accessible via actions dropdowns in SM and Report tabs.
* **Script Runner tab** exists but is disabled pending security review.
* Tab order: Fix All → SM → Report → Fixer (if enabled) → Perspectives → Translations → Memory Analyzer → BPA → Report BPA → Delta Analyzer → Prototype → Model Diagram → About.
* `all_tabs=True`: All tabs shown. Tabs after Fixer are loaded via deferred placeholders (instant display, background population). `all_tabs=False` (default): Only Fix All, SM, Report, About.

---

## Fixer Inventory

### Report Fixers (separate files with `scan_only` support)

All report fixers have their own file in `report/`, accept `(report, page_name, workspace, scan_only)`, and work both standalone and inside the UI.

| Fixer | File | Standalone Function | scan\_only | In Fixer Tab | In Report Explorer Actions |
| --- | --- | --- | --- | --- | --- |
| Upgrade to PBIR | `_Fix_UpgradeToPbir.py` | `fix_upgrade_to_pbir()` | ✅ | ✅ | ✅ "Convert to PBIR" |
| Fix Pie Charts | `_Fix_PieChart.py` | `fix_piecharts()` | ✅ | ✅ | ✅ |
| Fix Bar Charts | `_Fix_BarChart.py` | `fix_barcharts()` | ✅ | ✅ | ✅ |
| Fix Column Charts | `_Fix_ColumnChart.py` | `fix_columncharts()` | ✅ | ✅ | ✅ |
| Fix Page Size | `_Fix_PageSize.py` | `fix_page_size()` | ✅ | ✅ | ✅ |
| Hide Visual Filters | `_Fix_HideVisualFilters.py` | `fix_hide_visual_filters()` | ✅ | ✅ | ✅ |
| Fix Visual Alignment | `_Fix_VisualAlignment.py` | `fix_visual_alignment()` | ✅ | ❌ | ✅ |
| Fix Column→Line | `_Fix_ColumnToLine.py` | `fix_column_to_line()` | ✅ | ✅ | ✅ |
| Fix Column→Bar (IBCS) | `_Fix_Charts.py` | `fix_column_to_bar()` | ✅ | ✅ | ✅ |
| Fix IBCS Variance | `_Fix_IBCSVariance.py` | `fix_ibcs_variance()` | ✅ | ✅ | ✅ |
| Fix Line Charts | `_Fix_Charts.py` | `fix_linecharts()` | ✅ | ✅ | ✅ |
| Fix All Charts (unified) | `_Fix_Charts.py` | `fix_charts()` | ✅ | ❌ | ✅ "Fix All Charts" |
| Remove Unused Custom Visuals | `_Fix_RemoveUnusedCustomVisuals.py` | `fix_remove_unused_custom_visuals()` | ✅ | ✅ | ✅ |
| Disable Show Items No Data | `_Fix_DisableShowItemsNoData.py` | `fix_disable_show_items_no_data()` | ✅ | ✅ | ✅ |
| Migrate Report-Level Measures | `_Fix_MigrateReportLevelMeasures.py` | `fix_migrate_report_level_measures()` | ✅ | ✅ | ✅ |

### Semantic Model Fixers (separate files with `scan_only` support)

All SM fixers have their own file in `semantic_model/`, accept `(report/dataset, workspace, scan_only)`, and work both standalone and inside the UI.

| Fixer | File | Standalone Function | scan\_only | In Fixer Tab | In Model Explorer Actions |
| --- | --- | --- | --- | --- | --- |
| Discourage Implicit Measures | `_Fix_DiscourageImplicitMeasures.py` | `fix_discourage_implicit_measures()` | ✅ | ✅ | ✅ |
| Set DataSource Version V3 | `_Fix_DefaultDataSourceVersion.py` | `fix_default_datasource_version()` | ✅ | ❌ (commented out) | ❌ |
| Add Calendar Table | `_Add_CalculatedTable_Calendar.py` | `add_calculated_calendar()` | ✅ | ✅ | ✅ |
| Add Measure Table | `_Add_CalculatedTable_MeasureTable.py` | `add_measure_table()` | ✅ | ✅ | ✅ |
| Add Last Refresh Table | `_Add_Table_LastRefresh.py` | `add_last_refresh_table()` | ✅ | ✅ | ✅ |
| Add Units Calc Group | `_Add_CalcGroup_Units.py` | `add_calc_group_units()` | ✅ | ✅ | ✅ |
| Add Time Intelligence | `_Add_CalcGroup_TimeIntelligence.py` | `add_calc_group_time_intelligence()` | ✅ | ✅ | ✅ |
| Auto-Create Measures from Columns | `_Add_MeasuresFromColumns.py` | `add_measures_from_columns()` | ✅ | ❌ | ✅ |
| Add PY Measures (Y-1) | `_Add_PYMeasures.py` | `add_py_measures()` | ✅ | ❌ | ✅ |
| Direct Lake Pre-warm Cache | `_Setup_CacheWarming.py` | `setup_cache_warming()` | ✅ | ❌ | ✅ |
| Format All DAX | _(inline in `_pbi_fixer.py`)_ | `tom.format_dax()` | ❌ | ❌ | ✅ |

### BPA Auto-Fixers (19 total — standalone files + dropdown in `_bpa_tab`)

These fix specific Model BPA violations. Each has a **standalone fixer file** in `semantic_model/` with `scan_only` support. The BPA tab uses a rule dropdown + Fix Rule button.

**Comparison**: Only 4 of these 19 rules have a built-in FixExpression in the standard BPA rules file. The PBI Fixer auto-fixes **15 rules that have no standard auto-fix**.

| # | BPA Rule | Fix Action | Category | Std Fix? |
|---|----------|------------|----------|----------|
| 1 | Do not use floating point data types | Column DataType → Decimal | 🔢 Data Types | ✅ Yes |
| 2 | Set IsAvailableInMdx to false | `IsAvailableInMDX = False` | 📡 MDX | ✅ Yes |
| 3 | Set IsAvailableInMdx to true | `IsAvailableInMDX = True` | 📡 MDX | ❌ No |
| 4 | Visible objects with no description (Measures) | Set description to DAX expression | 📝 Documentation | ❌ No |
| 5 | Provide format string for 'Date' columns | Format → `mm/dd/yyyy` | 📊 Formatting | ❌ Detect only |
| 6 | Provide format string for 'Month' columns | Format → `MMMM yyyy` | 📊 Formatting | ❌ No rule |
| 7 | Provide format string for measures | Format → `#,0` | 📊 Formatting | ❌ Detect only |
| 8 | Percentages should be formatted | Format → `#,0.0%;-#,0.0%;#,0.0%` | 📊 Formatting | ❌ No rule |
| 9 | Format flag columns as Yes/No | Format → `"Yes";"Yes";"No"` | 📊 Formatting | ❌ No rule |
| 10 | Hide foreign keys | `IsHidden = True` | 🔗 Schema | ✅ Yes |
| 11 | Do not summarize numeric columns | `SummarizeBy = None` | 🔗 Schema | ✅ Yes |
| 12 | Mark primary keys | `IsKey = True` | 🔗 Schema | ❌ No rule |
| 13 | Objects should not start or end with a space | Trim whitespace | 🏷 Naming | ❌ No rule |
| 14 | First letter must be capitalized | Capitalize first letter | 🏷 Naming | ❌ Detect only |
| 15 | Use the DIVIDE function for division | Regex-replace `/ ` → `DIVIDE()` | 📊 Formatting | ❌ Detect only |
| 16 | Avoid adding 0 to a measure | Strip `0+` prefix | 📊 Formatting | ❌ No rule |
| 17 | Whole numbers should be formatted | Format → `#,0` | 📊 Formatting | ❌ No rule |
| 18 | Month (as a string) must be sorted | Set SortByColumn | 📊 Formatting | ❌ No rule |
| 19 | Add data category for columns | Set DataCategory by naming convention | 📊 Formatting | ❌ No rule |

### Optional / Not Now

| Fixer | File | Reason |
| --- | --- | --- |
| Set DataSource Version V3 | `semantic_model/_Fix_DefaultDataSourceVersion.py` | Requires Large SM storage format; not broadly available |

---

## Release History

### Completed (54 features)

#### 🏗 Core & Foundation

| # | Feature | Version | Date | Summary |
|---|---------|---------|------|---------|
| 1 | Foundation | v1.1.0 | 2026-03-27 | `_ui_components.py`, `_model_explorer.py`, `_report_explorer.py`, `_pbi_fixer.py` tab wrapper |
| 4 | Multi-Item Connection & PBIR Gate | v1.2.8–1.2.24 | 2026-03-28 | Comma-separated input, blank=all, PBIR format check, PBIRLegacy warnings, Convert All |
| 6 | UI Polish | v1.2.14–1.2.42 | 2026-03-28 | Full-width layout, multi-select, deduplication, branded header, About tab, version footer |
| 11 | UI Alignment & Consistency | v1.2.105 | 2026-04-04 | Three-panel layout alignment, border/padding audit, full-width stretch |
| 12 | Dropdown Item Selector | v1.2.106 | 2026-04-04 | `widgets.Combobox` with API-populated dropdown, icon prefixes 📄/📊, List Items |
| 16 | Stop Load Button | v1.2.111–1.2.177 | 2026-04-05 | ⏹ Stop button on both Explorers, `_cancel_load` flag. v1.2.177: Model Explorer loading moved to background thread so stop button actually works |
| 20 | Search & Filter Tree | v1.2.141 | 2026-04-04 | Real-time keystroke filtering above both Explorer trees |

#### 📊 Semantic Model Explorer

| # | Feature | Version | Date | Summary |
|---|---------|---------|------|---------|
| 2 | SM Properties & Editing | v1.2.x | 2026-03-27 | Properties panel, editable DAX, save button, Perspective Editor tab |
| 19 | Table Data Preview | v1.2.114 | 2026-04-04 | Top N rows via `evaluate_dax(TOPN(...))` in preview panel |
| 21 | Incremental Refresh Setup | v1.2.142 | 2026-04-04 | `_Setup_IncrementalRefresh.py`, auto date column detection |
| 25 | Model Diagram Tab | v1.2.146–1.2.180 | 2026-04-05 | 🗺 SVG relationship diagram, auto layout, model dropdown. v1.2.180: actual box heights + nearest-edge connection lines |
| 29a | Extended Properties (in-memory) | v1.2.165 | 2026-04-05 | Columns: is_key, sort_by, data_category, encoding, nullable. Measures: is_hidden. Relationships: security_filtering, rely_on_rri |
| 31 | Read Stats from Data Toggle | v1.2.160 | 2026-04-05 | `read_stats_from_data=True` checkbox for Direct Lake models in Memory Analyzer |
| 43 | Translations Editor | v1.2.162 | 2026-04-05 | 🌐 Load, auto-translate (Azure AI Translator via SynapseML), preview diff, apply via XMLA |

#### 📄 Report Explorer

| # | Feature | Version | Date | Summary |
|---|---------|---------|------|---------|
| 3 | Report Preview & Properties | v1.2.x | 2026-03-27 | `powerbiclient.Report` embed, visual properties, page navigation |
| 22 | Fix Visual Alignment | v1.2.143 | 2026-04-05 | `_Fix_VisualAlignment.py`, tolerance %, Report Explorer action |
| 23 | Design Theme Editor | v1.2.144 | 2026-04-05 | `_report_theme.py` — get/set/update theme colors, Apply IBCS Theme |
| 24 | PBIR Status Check | v1.2.145–1.2.182 | 2026-04-05 | Workspace-wide PBIR/PBIRLegacy status, Convert All Legacy button. v1.2.182: renamed from Format Overview, compact table, rendered below main UI |
| 26 | Report Prototyping | v1.2.123–v1.2.153 | 2026-04-04 | ✏️ Prototype tab, SVG + Excalidraw, page screenshots, progress bar |
| 30 | Editable Report Properties | v1.2.163–1.2.182 | 2026-04-05 | Pages: display name, width, height, hidden. Visuals: x, y, width, height, title. Save/discard. v1.2.182: fix key parsing (was showing 0), remove duplicate static props |

#### ⚡ Fixers & BPA

| # | Feature | Version | Date | Summary |
|---|---------|---------|------|---------|
| 5 | Fixer Tab Redesign | v1.2.8–1.2.24 | 2026-03-28 | God Button, fixers in Explorer dropdowns, tab hidden by default |
| 7 | Scan Mode & Violation Counts | v1.2.26–1.2.43 | 2026-03-28 | Scan button per tab, violation badges, "Fix this" buttons, re-scan |
| 9 | BPA Integration & Auto-Fixers | v1.2.44–1.2.99 | 2026-03-29 | 📋 BPA tab + 📄 Report BPA, category tabs, Fix All/Fix Rule/Fix Row |
| 14 | Extract BPA Fixers to Files | v1.2.108 | 2026-04-04 | 7 BPA fixers → standalone files with `scan_only` support |
| 18 | Additional BPA Fix Scripts | v1.2.113 | 2026-04-04 | 12 more BPA fixers → 19 total standalone files |
| 28 | Grouped BPA Fixer Checkboxes | v1.2.152 | 2026-04-05 | 6 category groups with select-all + Fix Selected |

#### 💾 Analysis Tabs

| # | Feature | Version | Date | Summary |
|---|---------|---------|------|---------|
| 8 | VertipaqAnalyzer & Memory | v1.2.36–1.2.38 | 2026-03-28 | 💾 Memory Analyzer tab with subtabs, DataFrame rendering, cache |
| 10 | Delta Analyzer & Download | v1.2.44–1.2.99 | 2026-03-29 | 📐 Delta Analyzer tab, ⬇ Download .pbix/.pbip buttons |
| 17 | Native BPA & Memory Analyzer | v1.2.112 | 2026-04-04 | BPA category ToggleButtons, Memory Analyzer direct DataFrames |

#### 📋 Clone & Utilities

| # | Feature | Version | Date | Summary |
|---|---------|---------|------|---------|
| 13 | Clone Report + Semantic Model | v1.2.107 | 2026-04-04 | Clone via `getDefinition` → `createItem`, auto-increment suffix |
| 15 | Clone Buttons & Name Mismatch | v1.2.110 | 2026-04-04 | 📋 Clone Both/Report/Model buttons, name mismatch warning |
| 27 | Script Runner Tab | v1.2.147 | 2026-04-05 | ⚙️ Python script runner with TOM in scope. Disabled pending review. |

#### 🚀 Performance & UX

| # | Feature | Version | Date | Summary |
|---|---------|---------|------|---------|
| 50 | Deferred Tab Loading | v1.2.183 | 2026-04-05 | `all_tabs=True`: placeholder VBoxes created synchronously (all tab buttons visible instantly), content populated via background thread with per-tab progress |
| 51 | CI Green Builds | v1.2.177 | 2026-04-05 | `pytest -s tests/ \\|\\| [ $? -eq 5 ]` — allows empty test suite (exit code 5) while failing on real test failures |

#### 🔧 Bug Fixes & Polish (v1.2.204–v1.2.216)

| # | Feature | Version | Date | Summary |
|---|---------|---------|------|---------|
| 52 | Fixer Scope Fix | v1.2.206 | 2026-04-06 | Fixed page name extraction from visual keys in `on_run_action` — was passing `{page}:{visual}` as page_name instead of just `{page}` |
| 53 | Visual Alignment Fixer Fix | v1.2.207 | 2026-04-06 | Narrowed `_CHART_TYPES` to actual charts only, fixed `funnelChart`→`funnel`, page matching now accepts both display name and internal name, added tolerance % input |
| 54 | Icon Consistency Fix | v1.2.208 | 2026-04-06 | Fixed swapped tab/tree icons — 📄=Semantic Model, 📊=Report consistently everywhere |
| 55 | Show Native Countdown & Close | v1.2.209 | 2026-04-06 | Show Native buttons in BPA, Report BPA, Delta Analyzer now do 3→2→1 countdown, close main container, then render natively |
| 56 | Page Ordering | v1.2.204 | 2026-04-06 | Report Explorer pages reflect actual report order from `pageOrder` array in `pages.json` instead of alphabetical |
| 57 | Tree & Preview Height Match | v1.2.205 | 2026-04-06 | Increased tree 420→520px, preview min-height 450→520px, embedded report 400→480px to match properties panel |
| 58 | God Mode Fix All | v1.2.210 | 2026-04-06 | ⚡ Fix All button scans all fixers → grouped tree (Report → Fixer → Item) → deselect items → Fix Selected |
| 59 | BPA-Based Report Fixers | v1.2.211 | 2026-04-06 | 3 new fixers from Report BPA rules: Remove Unused Custom Visuals, Disable Show Items No Data, Migrate Report-Level Measures |
| 60 | Fix All Top-Level Tab | v1.2.213 | 2026-04-06 | ⚡ Fix All promoted to always-visible first tab. Scans 4 categories (Report Fixers, Model Fixers, Model BPA, Report BPA). Grouped tree with category→item→fixer→finding. Fix Selected runs all selected fixers. God Mode removed from Report Explorer. |
| 61 | Standalone BPA Fix Functions | v1.2.214 | 2026-04-06 | `fix_model_bpa(dataset, workspace, scan_only)` maps 20 BPA rules to standalone SM fixers. `fix_report_bpa(report, workspace, scan_only)` maps 4 Report BPA rules to standalone report fixers. Both exported in `__init__.py`. Fix All tab now auto-fixes BPA findings instead of treating them as informational. |
| 62 | About Tab Attribution | v1.2.215 | 2026-04-06 | Dedicated "Built on Semantic Link Labs" section crediting Michael Kovalsky for TOM, Model BPA, Report BPA, ReportWrapper, Vertipaq Analyzer, Perspective Editor, DAX utilities, Direct Lake. |
| 63 | Remove Dead Stop Button | v1.2.216 | 2026-04-06 | Removed non-functional Prototype tab stop button (`stop_proto_btn`) — flag was never checked. Kept 3 working stop buttons (Memory, BPA, Report Explorer). |
| 64 | Show All Tabs Button | v1.2.221 | 2026-04-06 | Dynamic "Show All Tabs" button next to tab bar. Inserts extra tabs (BPA, Report BPA, Delta Analyzer, etc.) without needing `all_tabs=True` parameter. Uses shared `_make_lazy_specs()`. |
| 65 | Show All Tabs Alignment Fix | v1.2.222 | 2026-04-06 | Fixed button displacement from tab bar — removed duplicate margin, matched button height to ToggleButtons (34px). |
| 66 | Direct Lake Pre-warm Cache | v1.2.223 | 2026-04-06 | SM Explorer action: detects DL model, scans resident columns, creates `_CacheWarmUp` perspective, generates warm-up notebook, schedules daily at 07:00 via Fabric Job Scheduler API. |
| 67 | Fix Column-to-Line Chart | v1.2.224 | 2026-04-06 | `_Fix_ColumnToLine.py` — converts column charts to line charts when category axis uses Date/DateTime columns. Resolves SM via `fabric.list_columns()` for type detection. |
| 68 | Unified Chart Fixer | v1.2.225 | 2026-04-06 | `_Fix_Charts.py` with per-type configs for bar/column/line/combo. Line charts keep Y value axis. `_Fix_BarChart.py` and `_Fix_ColumnChart.py` become thin wrappers. New "Fix Line Charts" checkbox + "Fix All Charts" Report Explorer action. |
| 69 | Auto-detect Measure Table | v1.2.226 | 2026-04-06 | `add_measures_from_columns` and `add_py_measures` auto-detect a measure table (`"measure" in t.Name.lower()`) when `target_table` not specified. Same logic in inline fallbacks. |
| 70 | IBCS Variance Charts | v1.2.228 | 2026-04-06 | `_Fix_IBCSVariance.py` — IBCS variance chart fixer. Detects single-AC bar/column charts, auto-creates calendar + PY/Δ PY/Max Green PY/Max Red AC measures, adds PY to visual, applies error bars (red #FF0000/green #92D050), IBCS colors (AC #404040/PY #A0A0A0), overlap layout, label backgrounds, axis cleanup. Converts non-time columns→clusteredBarChart. Sorts bar charts descending by AC. Included in Fix All. |
| 71 | Calendar Auto-Relationship | v1.2.228 | 2026-04-06 | `add_calculated_calendar` now auto-detects Date/DateTime columns and creates Many→One relationships to CalcCalendar[Date] when `relationships=None`. Interactive UI proposal still available via SM Explorer widget. |
| 72 | Fix Column→Bar (IBCS) | v1.2.228 | 2026-04-06 | `fix_column_to_bar()` in `_Fix_Charts.py` — converts non-time column charts to bar charts. Standalone: preserves stacked/clustered. `force_clustered=True`: always clusteredBarChart. Checks DataType + column name pattern for time detection. |
| 73 | PBIR >100 Visuals Warning | v1.2.229 | 2026-04-06 | `_Fix_UpgradeToPbir.py` — counts visual.json parts from report definition in both scan and fix modes. If >100 visuals, prints warning that PBIR conversion may fail. Conversion still proceeds but alerts user to check manually. |
| 44a | Delete Objects (CRUD Phase 1) | v1.2.230 | 2026-04-07 | SM: `Delete Selected` action — parses tree selection keys, confirmation widget, `tom.remove_object()` for measures/columns/tables/hierarchies/calc items/relationships. Report: `Delete Selected` — deletes visuals (removes visual folder) and pages (removes all page files + updates pages.json pageOrder). Both use interactive confirmation widgets. |
| 44b | Create/Duplicate Objects (CRUD Phase 2) | v1.2.230 | 2026-04-07 | SM: `Create Measure` (table dropdown, name, DAX, format, folder), `Create Calculated Column` (+ data type), `Create Calculated Table` (name, DAX, hidden + refresh hint). Report: `Duplicate Selected` — duplicates visuals (new folder + 30px offset) and pages (new folder + "(Copy)" suffix + pageOrder insert). All via interactive ipywidgets forms in scan_results_box / crud_output_box. |
| 74 | Tab Width Reduction | v1.2.231 | 2026-04-07 | Reduced `tab_selector.style.button_width` from 155px to 120px for more compact tab bar layout. |
| 75 | Page Navigation Detection + Perf | v1.2.232 | 2026-04-07 | Prototype: extracts real page navigation edges from `visualLink` data in all visuals (PageNavigation with navigationSection target). Blue dashed arrows for button nav, orange for drillthrough. Perf: pre-resolve reportId once (skip N×list_items), backoff polling (1→2→3s), `_return_bytes` skips lakehouse file I/O. Status shows nav link count. |
| 76 | Duplicate Indent Fix | v1.2.233 | 2026-04-07 | Fixed SyntaxError: `else:` block in `_rpt_duplicate_selected` was at indent 16 instead of 20, misaligned with its `if item_type == "page":`. |

---

## Remaining Work (prioritized)

### Prio 0 — Implement Next

| # | Feature | Description |
|---|---------|-------------|

### Prio 1 — High Priority

| # | Feature | Description |
|---|---------|-------------|
| 34 | Batch Fixer Presets | "IBCS Standard" = pie fix + bar fix + page size fix. Preset dropdown. |
| 37 | Standard Design Themes | Built-in Microsoft theme presets applied in one click. |
| 42 | Batch Rename Objects | Multi-select objects → batch rename with pattern (prefix/suffix/find-replace). |
| 44c | Create Complex Objects | Create Calc Group, Table (M partition), Add Visual from scratch. |

### Prio 2 — Medium Priority

| # | Feature | Description |
|---|---------|-------------|
| 40 | Design Preview Before Fix | Show 2–4 design preset previews (HTML/SVG mockups) before applying a fix. |
| 35 | Background Editor | Page backgrounds: color picker, transparency slider. Apply to page or all. |
| 36 | Logo Uploader | Add logo/image to pages via URL. Insert as Image visual. |
| 38 | Enhanced Fix Page Size | Proportionally resize all visuals + scale fonts on page size change. |
| 45 | RLS Editor | View/edit Row-Level Security roles and DAX filter expressions. |
| 46 | Object Annotations Editor | View/edit object annotations (custom metadata key-value pairs). |
| 47 | Undo/Redo | Ctrl+Z/Ctrl+Y for property and expression changes. |

### Prio 4 — Low Priority / Nice to Have

| # | Feature | Description |
|---|---------|-------------|
| 29b | Extended Properties (expensive) | Tables: row count (evaluate_dax), storage mode per table. Requires extra API calls. |
| 29c | Full Property Grid (Advanced) | All TOM properties with collapsible "Advanced" section. See detailed spec below. |
| 32 | Measure Dependency Tree | DAG visualization of measure→measure/column references. |
| 33 | Export Scan Results | Export scan results to DataFrame/CSV. "Export" button next to Scan. |
| 48 | Deployment Wizard | Deploy model to target workspace with options (skip partitions, skip roles, etc.). |
| 49 | Model Comparison / Diff | Compare two models side by side, highlight differences (schema diff). |
| 41 | AI Assistant | SLL has no SM AI chat module yet. Would need custom LLM integration. Lowest priority. |

---

Testing is currently **manual and notebook-based**. Each fixer and UI component is validated as follows:

* **Standalone fixer testing**: Every fixer script works independently via direct call in a Fabric Notebook (e.g. `fix_piecharts(report="Test Report", workspace="Dev Workspace", scan_only=True)`). This ensures fixers remain usable outside the UI.
* **Scan-then-fix cycle**: Run `Scan` → verify violation counts → run fixer → re-scan → confirm counts drop to zero.
* **Multi-item loading**: Test with blank input (all items), single item, and comma-separated lists against a workspace containing both PBIR and PBIRLegacy reports.
* **PBIR gate**: Verify that PBIRLegacy reports are skipped (or auto-converted) and that fixers refuse to run until conversion is complete.
* **Regression check**: After any code change, re-run the full load + scan + fix cycle on the test workspace.

> **Future**: Consider adding automated integration tests using a dedicated test workspace with known report/model configurations, and unit tests for pure logic in `_ui_components.py` (tree building, deduplication, key parsing).

---

## UI Consistency — Box Styling

All section boxes across all tabs must use the same style:

```python
# Canonical section box style (defined in _ui_components.py)
SECTION_BG = "#fafafa"
BORDER_COLOR = "#e0e0e0"

# Every section box:
layout = widgets.Layout(
    gap="6px",
    padding="12px",
    margin="0 0 12px 0",
    border=f"1px solid {BORDER_COLOR}",
    border_radius="8px",
    background_color=SECTION_BG,
)
```

Exceptions: XMLA warning box uses `#ffc107` border.

---

## Design Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Tree widget | `widgets.SelectMultiple` | Supports Ctrl/Shift multi-select; expand/collapse separated to buttons only (no tree rebuild on click) |
| Duplicate items | Zero-width spaces (`\u200b`) | Multiple "Bar chart" entries get unique strings while looking identical |
| Data loading | Pre-fetch all metadata into Python dict, then close connection | Avoids long-lived connections, enables offline browsing, simpler state management |
| File organization | One file per tab + shared components + inline fallbacks | Keeps files focused; inline fallbacks in `_pbi_fixer.py` ensure deployment works even if separate files missing |
| Naming | "Model Explorer" / "Report Explorer" | Describes functionality directly, no external tool references |
| Single workspace | No comma-separation for workspace | Simplifies connection logic; multi-workspace adds complexity with little benefit |
| Comma-separated items | Split on `,` then `.strip()` each | Allows `"Report A, Report B"` with flexible spacing |
| Blank = all | Load everything in workspace when report/SM input is empty | Most common use case; power users filter with comma-separated names |
| 5-minute timeout | Hard wall-clock limit on full load | Prevents runaway connections in large workspaces |
| PBIR gate at load time | Check format before any fixer runs | Every report fixer requires PBIR; fail-fast prevents confusing errors |
| Fixer standalone compat | Fixers use `print()`, UI wraps with `redirect_stdout` | Fixers work both inside UI and as standalone notebook calls |
| God button | "⚡ Fix Everything" runs all checked fixers | Most common action; reduces clicks for the typical workflow |
| Fixer tab hidden | `show_fixer_tab=False` by default | All fixers accessible via Actions dropdowns in Report/SM tabs |
| Scan mode | Integrated toggle per tab, not a separate tab | Violations visible where objects are; no context switching needed |
| BPA fixers | 19 standalone files + grouped checkbox UI in `_bpa_tab()` | Each has a standalone file with `scan_only`; grouped into 6 categories with select-all checkboxes |
| Analysis tabs inline | Vertipaq, BPA, Report BPA, Delta Analyzer in `_pbi_fixer.py` | No external file dependency; these tabs are read-only analysis, not reusable modules |

---

## API Dependencies

| # | Semantic Link Labs API | Notes |
| --- | --- | --- |
| SM tree | `connect_semantic_model(readonly=True)` → `tm.model.Tables`, `.Columns`, `.Measures`, `.Hierarchies` | TOM object model via .NET interop |
| DAX preview | `measure.Expression`, `calc_item.Expression` | Pre-fetched during Load |
| DAX formatting | `tom.format_dax()` | Calls DAX Formatter API via SLL |
| Report tree | `connect_report(readonly=True)` → `rw.list_pages()`, `rw.list_visuals()` | Returns DataFrames |
| Report format | `_check_report_format()` → REST API `.format` field | Uses Fabric REST client |
| PBIR upgrade (single) | `fix_upgrade_to_pbir(report, workspace=ws)` | REST round-trip: getDefinition → updateDefinition |
| PBIR upgrade (bulk) | `upgrade_to_pbir(report=[...], workspace=ws)` | Embed + save approach, already in upstream SLL |
| Vertipaq stats | `vertipaq_analyzer(dataset, workspace)` | Returns `dict[str, pd.DataFrame]` with Model/Tables/Columns/Partitions/Relationships/Hierarchies |
| Model BPA | `run_model_bpa(dataset, workspace, return_dataframe=True)` | Returns DataFrame of findings |
| Report BPA | `run_report_bpa(report, workspace, return_dataframe=True)` | Returns DataFrame of findings |
| Delta Analyzer | `delta_analyzer(table, lakehouse, workspace, ...)` | Returns dict of DataFrames |
| Download .pbix | `save_as_pbip(report, path, ...)` or REST download | Saves to notebook files |
| Download .pbip | `save_as_pbip(report, path, thick_report=...)` | Saves PBIP folder structure |
| Fixers | `fix_piecharts()`, `fix_barcharts()`, etc. | Existing fixer functions, unchanged |

---

## PR / Submission Status

### Already pushed to fork (`KornAlexander/semantic-link-labs`) — separate feature branches

| File | Branch | Status |
| --- | --- | --- |
| `report/_Fix_PieChart.py` | `feature/fix-piecharts` | ✅ Pushed |
| `report/_Fix_BarChart.py` | `feature/fix-chart-formatting` | ✅ Pushed |
| `report/_Fix_ColumnChart.py` | `feature/fix-chart-formatting` | ✅ Pushed |
| `report/_Fix_PageSize.py` | `feature/fix-page-size` | ✅ Pushed |
| `report/_Fix_HideVisualFilters.py` | `feature/fix-hide-visual-filters` | ✅ Pushed |
| `semantic_model/_Add_CalculatedTable_Calendar.py` | `feature/add-calendar-table` | ✅ Pushed |
| `semantic_model/_Add_CalculatedTable_MeasureTable.py` | `feature/add-measure-table` | ✅ Pushed |
| `semantic_model/_Add_Table_LastRefresh.py` | `feature/add-last-refresh-table` | ✅ Pushed |
| `semantic_model/_Add_CalcGroup_Units.py` | `feature/add-calc-group-units` | ✅ Pushed |
| `semantic_model/_Add_CalcGroup_TimeIntelligence.py` | `feature/add-calc-group-time-intelligence` | ✅ Pushed |
| `semantic_model/_Fix_DiscourageImplicitMeasures.py` | `feature/fix-discourage-implicit-measures` | ✅ Pushed |

### On `feature/pbi-fixer-ui` branch (all UI files together)

| File | Status |
| --- | --- |
| `_pbi_fixer.py` | ✅ Pushed (v1.2.152) |
| `_ui_components.py` | ✅ Pushed |
| `_model_explorer.py` | ✅ Pushed |
| `_report_explorer.py` | ✅ Pushed |
| `_perspective_editor.py` | ✅ Pushed |
| `semantic_model/_Add_MeasuresFromColumns.py` | ✅ Pushed (also inline fallback in `_pbi_fixer.py`) |
| `semantic_model/_Add_PYMeasures.py` | ✅ Pushed (also inline fallback in `_pbi_fixer.py`) |

### NOT yet pushed / still need PRs to upstream `microsoft/semantic-link-labs`

| File | Notes |
| --- | --- |
| `report/_Fix_UpgradeToPbir.py` | Needs `feature/fix-upgrade-to-pbir` branch + PR. |
| `semantic_model/_Fix_DefaultDataSourceVersion.py` | **Deprioritized** — requires Large SM storage format. PR deferred. |
| `report/_upgrade_to_pbir.py` | **Already in upstream SLL** — no PR needed. |
| `report/_generate_embed_token.py` | **Already in upstream SLL** — no PR needed. |

---

## Contributing

To add a new fixer:

1. Create `_Fix_YourFixer.py` in `report/` or `semantic_model/`
2. Add a lazy import in `_pbi_fixer.py`
3. Add a checkbox row and wire it into the `report_fixers` or `sm_fixers` list
4. Add the fixer to the appropriate Explorer actions dropdown (`_rpt_fixer_cbs` or `_model_fixer_cbs`)
5. The fixer will automatically appear in the Fixer tab UI and/or the Explorer actions
6. The fixer **must** also work standalone: `fix_your_fixer(report="X", workspace="Y", scan_only=False)`

---

## Detailed Feature Descriptions (Future Work)

### Feature 29 — Extended Model Explorer Properties

Add comprehensive property editing to the Model Explorer with a full property grid:

* **Columns**: encoding hint (`ValueEncoding`/`HashEncoding`), sort-by column dropdown (select another column in same table), is-key (checkbox), is-nullable, lineage tag (read-only), data category dropdown (`City`, `Country`, `WebUrl`, `ImageUrl`, etc.).
* **Tables**: storage mode (`Import`/`DirectLake`/`Dual`) as read-only label, row count from Vertipaq cache (or `evaluate_dax`), source expression (M query from partition, read-only textarea), data category, lineage tag.
* **Measures**: is-hidden toggle, lineage tag (read-only), KPI properties (target expression, status expression, trend expression) if KPI is defined.
* **Relationships**: cross-filter direction dropdown (`Both`/`Single`), security filtering behavior (`Both`/`One`), is-active toggle, rely-on-referential-integrity checkbox.
* All properties read from TOM via the existing `_model_data` cache. Editable properties written back via `connect_semantic_model(readonly=False)` + `SaveChanges()`.
* Extend `_populate_props()` in `_model_explorer.py` with new property rows. Reuse the compact `_prop_input()` helper.

### Feature 30 — Editable Report Explorer Properties

Make Report Explorer visual and page properties editable via `connect_report`:

* **Pages**: editable display name (`Text` input), width/height (`IntText`), background color (hex `Text`), hidden flag (checkbox), page type indicator (read-only).
* **Visuals**: editable position X/Y (`IntText`), size width/height (`IntText`), title text (`Text`), hidden flag (checkbox), visual type (read-only).
* Add a **Save button** with dirty-state tracking (same pattern as Model Explorer). Writes go through `connect_report(readonly=False)` in read-write mode, modifying the PBIR JSON definition.
* Show validation: page size must be ≥ 320×240 and ≤ 3840×2160. Visual position must be within page bounds.

### Feature 34 — Batch Fixer Presets

Add named presets that run multiple fixers in sequence:

* **"IBCS Standard"**: Fix Pie Charts → Fix Bar Charts → Fix Column Charts → Fix Page Size (1920×1080) → Hide Visual Filters.
* **"Quick Cleanup"**: Discourage Implicit Measures → Hide Foreign Keys → Fix Do Not Summarize → Trim Object Names.
* **"Full Model BPA Fix"**: Run all 19 BPA auto-fixers in order.
* **UI**: Dropdown in the Fixer tab or a "⚡ Preset" button next to the Run button. Selecting a preset auto-checks the corresponding fixers.
* **Custom presets**: Allow saving the current checkbox selection as a named preset (stored in lakehouse Files as JSON).

### Feature 37 — Standard Design Themes

Dropdown of built-in Microsoft theme presets applied in one click:

* Source themes from Microsoft's official Power BI theme gallery (JSON files).
* Presets: "Default", "Executive", "Innovate", "Academic", "Accessible", "IBCS (custom)".
* Preview: show color swatches before applying.
* Apply via `connect_report` → modify `StaticResources/SharedResources/BaseThemes/CY24SU11.json` (or equivalent theme file in PBIR definition).
* Use `_report_theme.py`'s `set_report_theme()` for the actual write.

### Feature 70 — Fix Variance Charts

IBCS-style variance chart fixer (`report/_Fix_IBCSVariance.py`):

* Detect bar/column charts that show actual vs. budget/plan/target comparisons.
* **AC measure identification**: Any Y-axis measure NOT ending with ` PY`, ` Δ PY`, ` Δ PY %`, ` Max Green PY`, ` Max Red AC` is an AC measure.
* **Multiple AC measures → skip**: If a visual has more than one AC measure, skip it (too ambiguous to auto-fix).
* **Calendar auto-creation**: If no calendar table exists (DataCategory="Time"), automatically create one via `add_calculated_calendar` before proceeding. Don't just warn.
* **PY measure creation**: If `{AC} PY` doesn't exist, create it using the auto-detected/created calendar table. Then also **add the PY measure to the visual's Y projections** (as first projection, before AC).
* **Error bar measures**: Check model for `{AC} Max Green PY` and `{AC} Max Red AC` with matching DAX expressions. Create if missing.
* **Column↔Bar conversion**: Includes the #72 fix — if the chart is a column chart with a non-time category axis, convert to `clusteredBarChart` before applying IBCS formatting.
* Apply IBCS-compliant formatting: positive variance = green fill, negative variance = red fill.
* Remove unnecessary gridlines, axis labels, and legends that clutter variance displays.
* **Data labels**: Per-visual label properties only (not theme-level). AC labels: enabled with white (`#FFFFFF`) background at 50% transparency. PY labels: disabled (`showSeries: false`).
* **Data point colors**: Use explicit hex values, NOT ThemeDataColor references. AC bar = `#404040` (dark grey), PY bar = `#A0A0A0` (light grey). Error bars: red = `#FF0000`, green = `#92D050`.
* **Include in Fix All**: This fixer MUST run as part of "Fix All" — do NOT skip it.
* `scan_only` mode: detect how many bar/column charts have exactly one AC measure and could be enhanced with IBCS variance formatting (PY + error bars). Report count and list each candidate with its AC measure name, whether PY/error bar measures already exist, and whether a calendar table is present.

### Feature 72 — Fix Column↔Bar by Category Type

IBCS rule: time series use vertical columns (left→right), structural comparisons use horizontal bars (top→bottom). Integrated into `_Fix_Charts.py`:

* For each `columnChart` / `clusteredColumnChart`, read the Category axis fields (table + column name).
* Use `resolve_dataset_from_report` + `fabric.list_columns()` to get the column's DataType (same pattern as `_Fix_ColumnToLine.py`).
* **Time detection heuristics** (check both):
  - DataType is `DateTime` or `DateTimeOffset`
  - Column name matches pattern: contains "Date", "Month", "Year", "Quarter", "Period", "Week", "Day" (case-insensitive)
* If time-based → keep as column chart (no change).
* If NOT time-based → convert to bar chart. **Standalone mode**: preserve stacked/clustered (`columnChart`→`barChart`, `clusteredColumnChart`→`clusteredBarChart`). **Called from IBCS fixer**: always → `clusteredBarChart`.
* `scan_only` mode: report which column charts would be converted and why (show detected category field + DataType).
* **Bar chart sorting (IBCS)**: For bar charts only (not column charts — time axis order must be preserved), ensure the AC measure is sorted descending. Check `visual.visual.query.sortDefinition.sort` — if missing or not descending by the AC measure, set it. Uses the AC measure identified in step 2 of the variance fixer. This makes the longest bar appear at the top (IBCS convention for structural comparisons).
* New checkbox in Fixer tab: "Fix Column↔Bar (IBCS)" or integrate as a sub-check in existing "Fix All Charts".

### Feature 42 — Batch Rename Objects

Multi-select objects in Model Explorer → batch rename with pattern:

* **Find & Replace**: regex or plain text find/replace across selected object names.
* **Prefix/Suffix**: add or remove a prefix/suffix to all selected objects.
* **Case conversion**: UPPER, lower, Title Case, camelCase.
* **Preview**: show before→after table of all affected names before applying.
* Apply via `connect_semantic_model(readonly=False)` — rename each object in a single XMLA session.
* Works on tables, columns, measures, hierarchies.

### Feature 44 — Add/Delete Objects (CRUD)

Split into phases by difficulty:

#### Phase 1 — Delete Objects (Easy)

All delete operations use exis✅ (v1.2.230)

Implemented in `_pbi_fixer.py`. SM: `Delete Selected` action in `_model_fixer_cbs`. Report: `Delete Selected` action in `_rpt_fixer_cbs`. Both show interactive confirmation widgets before executing.

#### Phase 2 — Create Simple Objects ✅ (v1.2.230)

Implemented in `_pbi_fixer.py`. SM: `Create Measure`, `Create Calculated Column`, `Create Calculated Table` — all as interactive ipywidgets forms. Report: `Duplicate Selected` — duplicates visuals or pages.

| Operation | API | Complexity | Notes |
|-----------|-----|------------|-------|
| Create Calculation Group | `tom.add_calculation_group()` + N calc items | Hard | Dynamic form: add/remove items with ordinal + DAX per item |
| Create Table (M partition) | `tom.add_m_partition()` | Hard | M expression editor, column definitions needed after refresh |
| Add Visual to Page | Build visual.json from scratch | Hard | Need visual type picker, field bindings, positioning. Very complex UI. |

### Feature 35 — Background Editor

Set/change page backgrounds in Report Explorer:

* **Solid color**: hex color picker (`Text` input with `#` prefix), preview swatch.
* **Transparency slider**: 0% (opaque) to 100% (transparent), `IntSlider` widget.
* **Apply scope**: "This page" or "All pages" radio buttons.
* Modifies the PBIR page JSON `background` property via `connect_report`.
* **Wallpaper**: separate setting for page wallpaper (visible in normal view but not in focus mode).

### Feature 36 — Logo Uploader

Add a logo/image to report pages:

* **URL input**: paste an image URL (public or OneDrive). Preview inline.
* **Position**: dropdown (top-left, top-right, bottom-left, bottom-right) or custom X/Y.
* **Size**: width/height inputs with aspect ratio lock checkbox.
* Inserts as an Image visual in the PBIR definition via `connect_report`.
* **Apply scope**: current page or all pages.

### Feature 38 — Enhanced Fix Page Size

Extend `_Fix_PageSize.py` with proportional visual resizing:

* When page size changes (e.g. 1280×720 → 1920×1080), proportionally scale all visual positions and sizes.
* **`resize_visuals=True`**: scale X, Y, width, height of each visual by the same ratio.
* **`resize_fonts=True`**: scale font sizes in visual configs by the ratio (e.g. 12pt → 18pt at 1.5× scale).
* Maintain relative spacing between visuals.
* `scan_only` compatible: show what would change without applying.

### Feature 45 — RLS Editor

View and edit Row-Level Security roles:

* List all roles in the model with their table filter expressions.
* Editable DAX filter expression per role per table (textarea).
* Add new role (name input), delete role (with confirmation).
* Add/remove role members (email/UPN list).
* Save via `connect_semantic_model(readonly=False)` → `tom.model.Roles`.
* Read via TOM: `tom.model.Roles[i].TablePermissions[j].FilterExpression`.

### Feature 46 — Object Annotations Editor

View and edit object annotations (custom metadata key-value pairs):

* Annotations are TOM properties: `object.Annotations["key"].Value`.
* Grid view: select an object → show all its annotations as key-value pairs.
* Add/edit/delete annotations. Common keys: `TabularEditor_*`, `PBI_*`, custom user keys.
* Used for storing metadata like last-modified date, author, review status.
* Save via TOM `Annotations.Add()` / `Annotations.Remove()`.

### Feature 47 — Undo/Redo

Ctrl+Z / Ctrl+Y support for property and expression changes:

* Maintain a stack of `(key, field, old_value, new_value)` tuples.
* Each edit pushes to the undo stack. Undo pops and applies `old_value`, pushes to redo stack.
* Works for: expression edits, property changes, name changes, translation changes.
* **Limitation**: only covers PBI Fixer UI changes, not external XMLA writes.
* UI: "↩ Undo" and "↪ Redo" buttons in the save row, with count badges.

### Feature 48 — Deployment Wizard

Deploy a model to a target workspace with granular options:

* **Target workspace** dropdown (populated from REST API).
* **Options**: Deploy connections (yes/no), Deploy partitions (yes/no), Deploy roles (yes/no), Deploy role members (yes/no).
* Deployment via `getDefinition` → `createItem` / `updateDefinition` on the target workspace.
* Progress bar with per-table status.
* **Comparison mode**: show what would change before deploying (schema diff preview).

### Feature 49 — Model Comparison / Diff

Compare two semantic models side by side:

* **Source/target selectors**: two dropdowns (model A, model B) from loaded models or workspace items.
* **Diff view**: table showing objects that exist in A only, B only, or both with differences.
* Color-coded: green = added, red = removed, yellow = modified.
* **Drilldown**: click a modified object to see property-level diff (old value → new value).
* **Merge**: select individual changes to apply from source → target (cherry-pick merge).
* Uses TOM comparison of table/column/measure/relationship definitions.

### Feature 29c — Full Property Grid (Advanced Mode)

Complete all TOM properties in the Model Explorer properties panel with a collapsible "Advanced" toggle:

**UI Pattern:**
* Properties panel shows **basic properties** by default (current behavior).
* An **"Advanced ▼"** toggle button at the bottom expands/collapses additional rows.
* Advanced properties are read-only (disabled inputs) unless explicitly made editable.

**Missing basic properties to add (always visible):**

| Object | Property | Notes |
|--------|----------|-------|
| Column | `DataType` | Already loaded but not shown in properties |
| Column | `IsHidden` | Already loaded |
| Column | `Description` | Text input |
| Column | `DisplayFolder` | Text input |
| Column | `FormatString` | Text input |
| Column | `Expression` | Calculated columns only — shown in expression panel |
| Column | `SourceColumn` | DataColumn only — source column name |
| Measure | `DataType` | Result type (read-only) |
| Measure | `State` | Ready / SemanticError / etc. (read-only) |
| Measure | `ErrorMessage` | Show if State ≠ Ready |
| Table | `IsHidden` | Already loaded |
| Table | `DataCategory` | Time/Geography/Organization |
| Table | `ExcludeFromModelRefresh` | Checkbox |
| Relationship | `Name` | Auto-generated name |
| Relationship | `JoinOnDateBehavior` | DateAndTime vs DatePartOnly |
| Hierarchy | `Name`, `DisplayFolder`, `IsHidden`, `Description` | Currently no props shown for hierarchies |
| Hierarchy | `Levels` | Show level names + ordinals |

**Advanced properties (collapsed by default, read-only):**

| Object | Property | Notes |
|--------|----------|-------|
| All | `LineageTag` | GUID tracking |
| All | `ModifiedTime` | Last modified timestamp |
| All | `Annotations` | Key-value pairs (link to Feature 46) |
| Column | `IsAvailableInMDX` | MDX visibility |
| Column | `IsUnique` | Uniqueness constraint |
| Column | `Alignment` | Text alignment |
| Column | `IsDefaultImage`, `IsDefaultLabel` | CSDL defaults |
| Column | `SourceProviderType` | DirectQuery source type |
| Measure | `IsSimpleMeasure` | Auto-created implicit |
| Measure | `KPI` | KPI target/status/trend expressions |
| Measure | `DetailRowsDefinition` | Drill-through DAX |
| Measure | `FormatStringDefinition` | Dynamic format string DAX |
| Table | `IsPrivate` | Internal hidden table |
| Table | `SystemManaged` | System-managed table |
| Table | `RefreshPolicy` | Incremental refresh config |
| Relationship | `State` | Ready / Error |
