# PBI Fixer — Development Plan

## Vision

Evolve the PBI Fixer from a single-purpose fixer tool into a comprehensive Power BI development environment running natively in Fabric Notebooks. The UI follows a three-panel layout (object tree on the left, preview top-right, properties bottom-right) with the ability to switch between **Semantic Model**, **Report**, **Fixer**, and **Perspectives** views — plus dedicated analysis tabs for Vertipaq/Memory, BPA, Report BPA, and Delta Analyzer.

The tool connects to an entire workspace of semantic models and reports (displayed as a unified tree), with optional comma-separated filtering. A PBIR format check runs automatically on load — non-PBIR reports are flagged and can be converted in-place before any fixers run.

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
                         #   (Vertipaq, BPA, Report BPA, Delta Analyzer, About)
  _ui_components.py      # Shared theme, icons, tree-building, layout helpers
  _sm_explorer.py        # Semantic Model Explorer tab
  _report_explorer.py    # Report Explorer tab
  _perspective_editor.py # Perspective Editor tab
  report/                # Individual report fixers (each runs standalone too)
    _Fix_PieChart.py
    _Fix_BarChart.py
    _Fix_ColumnChart.py
    _Fix_PageSize.py
    _Fix_HideVisualFilters.py
    _Fix_UpgradeToPbir.py       # REST round-trip upgrade (getDefinition → updateDefinition)
    _Fix_MigrateSlicerToSlicerbar.py
    _upgrade_to_pbir.py         # Batch upgrade via embed+save (already in upstream SLL)
    _generate_embed_token.py    # Embed token helper for upgrade_to_pbir
  semantic_model/        # Individual SM fixers (each runs standalone too)
    _Fix_DiscourageImplicitMeasures.py
    _Fix_DefaultDataSourceVersion.py
    _Add_CalculatedTable_Calendar.py
    _Add_CalculatedTable_MeasureTable.py
    _Add_Table_LastRefresh.py
    _Add_CalcGroup_Units.py
    _Add_CalcGroup_TimeIntelligence.py
    _Add_MeasuresFromColumns.py
    _Add_PYMeasures.py
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
  ├─ 📄 Overview [12 visuals]
  └─ 📄 Details [8 visuals]
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

## Tab Layout (v1.2.99)

| Tab | Icon | Source | Description |
| --- | --- | --- | --- |
| Semantic Model | 📊 | `_sm_explorer.py` | Tree + DAX preview + properties + scan + actions dropdown |
| Report | 📄 | `_report_explorer.py` | Tree + visual preview + properties + scan + actions dropdown + visual→SM navigation |
| Fixer | ⚡ | `_pbi_fixer.py` (inline) | Checkbox-based fixer selection, God Button, Scan/Fix/Scan+Fix modes |
| Perspectives | 👁 | `_perspective_editor.py` | Perspective Editor (based on m-kovalsky) |
| Memory Analyzer | 💾 | `_pbi_fixer.py` (`_vertipaq_tab`) | Vertipaq stats: models → tables → columns, size/cardinality/encoding |
| BPA | 📋 | `_pbi_fixer.py` (`_bpa_tab`) | Model BPA with auto-fix for 7 rule types |
| Report BPA | 📄 | `_pbi_fixer.py` (`_report_bpa_tab`) | Report BPA via `run_report_bpa()`, auto-converts PBIRLegacy |
| Delta Analyzer | 📐 | `_pbi_fixer.py` (`_delta_analyzer_tab`) | Delta table analysis: summary, parquet files, row groups, column chunks |
| About | ℹ️ | `_pbi_fixer.py` (inline) | Author info, links, tech credits |

* **Fixer tab** is hidden by default (`show_fixer_tab=False`); all fixers are accessible via actions dropdowns in SM and Report tabs.
* Tab order: SM → Report → Fixer (if enabled) → Perspectives → Memory Analyzer → BPA → Report BPA → Delta Analyzer → About.

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
| Migrate Slicer to Slicerbar | `_Fix_MigrateSlicerToSlicerbar.py` | `fix_migrate_slicer_to_slicerbar()` | ✅ | ❌ | ❌ |

### Semantic Model Fixers (separate files with `scan_only` support)

All SM fixers have their own file in `semantic_model/`, accept `(report/dataset, workspace, scan_only)`, and work both standalone and inside the UI.

| Fixer | File | Standalone Function | scan\_only | In Fixer Tab | In SM Explorer Actions |
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
| Format All DAX | _(inline in `_pbi_fixer.py`)_ | `tom.format_dax()` | ❌ | ❌ | ✅ |

### BPA Auto-Fixers (inline in `_bpa_tab`, no separate files)

These are small inline fix functions in `_pbi_fixer.py` that auto-fix specific Model BPA violations. They do **not** have separate fixer files or `scan_only` support — they operate on individual BPA findings via Fix/Fix All buttons in the BPA tab.

| BPA Rule | Fix Action | Has Separate File |
| --- | --- | --- |
| Do not use floating point data types | Change column DataType from Double to Decimal | ❌ |
| Set IsAvailableInMdx to false | Set `IsAvailableInMDX = False` on column | ❌ |
| Visible objects with no description (Measures) | Set measure description to its DAX expression | ❌ |
| Provide format string for 'Date' columns | Set format to `mm/dd/yyyy` | ❌ |
| Provide format string for 'Month' columns | Set format to `MMMM yyyy` | ❌ |
| Provide format string for measures | Set format to `#,0` | ❌ |
| Hide foreign keys | Set `IsHidden = True` on column | ❌ |

### Optional / Not Now

These fixers have separate files with full `scan_only` support but are **deprioritized** — will not be wired into the UI in the near term:

| Fixer | File | Reason |
| --- | --- | --- |
| Migrate Slicer to Slicerbar | `report/_Fix_MigrateSlicerToSlicerbar.py` | Low demand; slicerbar adoption still limited |
| Set DataSource Version V3 | `semantic_model/_Fix_DefaultDataSourceVersion.py` | Requires Large SM storage format; not broadly available |

---

## Implementation Phases

### Phase 1 — Foundation (v1.1.0) ✅

* `_ui_components.py` — shared theme constants, icon dict, `build_tree_items()`, `create_three_panel_layout()`, connection bar helpers
* `_sm_explorer.py` — Semantic Model Explorer with tree + DAX preview + properties placeholder
* `_report_explorer.py` — Report Explorer with tree + preview/properties placeholders
* `_pbi_fixer.py` — Tab wrapper (Fixer | Semantic Model | Report)
* `PLAN.md` — this file

### Phase 2 — Semantic Model Properties & Editing (v1.2.x) ✅

* Properties panel in SM Explorer: data type, format string, description, display folder, is\_hidden
* Editable DAX for measures and calc items with Save Expression button
* Editable properties (write back via XMLA) with save button and confirmation
* Collapsible trees with expand/collapse all
* Perspective Editor tab (based on upstream m-kovalsky/perspective\_editor)

### Phase 3 — Report Preview & Properties (v1.2.x) ✅

* Report preview via `powerbiclient.Report` widget (live embedded report)
* Properties panel: visual position, size, type, filter config
* Page navigation in preview when selecting page in tree
* Fixer actions dropdown in Report Explorer (runs fixers on selected page)

### Phase 4 — Multi-Item Connection & PBIR Gate (v1.2.8–1.2.24) ✅

* Shared Load button next to input field — triggers SM + Report loading at once
* Comma-separated report/SM input (e.g. `"Bad Report, Slicerbar Testing"`)
* Blank input = load all semantic models / reports in the workspace via REST API
* Multi-model tree grouping (expand/collapse per model)
* Multi-report tree grouping (expand/collapse per report)
* Per-item progress status during loading (`Model 1/9: loading 'X'…`)
* 5-minute hard timeout on full load
* PBIR format check via `_check_report_format()`, skips non-PBIR reports for fixers
* "Upgrade to PBIR" checkbox in Fixer (runs first in chain)
* "Convert to PBIR" in Report Explorer actions dropdown
* PBIRLegacy warning badges in tree + banner with "Convert All" button
* After conversion, re-check and update tree badges

### Phase 5 — Fixer Tab Redesign (v1.2.8–1.2.24) ✅

* **"God Button"** (⚡ Fix Everything) — selects all fixers + confirms XMLA, runs
* Report fixers in Report Explorer actions dropdown (Fix Pie Charts, Fix Bar Charts, etc.)
* SM fixers in SM Explorer actions dropdown (Discourage Implicit Measures, Calendar, etc.)
* Fixer tab hidden by default (`show_fixer_tab=False`); pass `True` to restore
* Tab order: SM → Report → Fixer → Perspectives → ...
* All fixer scripts continue to work standalone via `print()` + `redirect_stdout`
* New SM actions: "Auto-Create Measures from Columns", "Add PY Measures (Y-1)" — inline fallback in `_pbi_fixer.py`
* "Format All DAX" action in SM Explorer (calls `tom.format_dax()`)

### Phase 6 — UI Polish (v1.2.14–1.2.42) ✅

* Full-width layout (`width=100%`, no max-width cap)
* Wider tree panels (400px) and input fields (400px)
* Multi-select via `SelectMultiple` (Ctrl+click / Shift+click)
* Single-click expand/collapse coexists with multi-select (len==1 triggers toggle)
* Duplicate display strings deduplicated with zero-width spaces
* Properties panel strips model prefix from table names
* Inline status per tab (progress, errors, completion)
* Fixer stdout captured via `redirect_stdout` (no notebook scroll)
* Split toolbar into two rows: nav (Load/Expand/Collapse) + actions (Scan/dropdown/Run)
* Select-then-run pattern: dropdown selects action, ⚡ Run button executes
* SummarizeBy property shown for columns in SM Explorer properties
* Save Expression/Properties correctly extracts model name from multi-model keys
* Auto-expand all items after load
* Unified save button with dirty state tracking (green ✓/red ⚠️)
* Branded header with accent color + wrench icon + bottom border
* Version footer with author + actionablereporting.com link
* Tab button width optimized (130px for 8 tabs)
* Input box with light grey background for visual separation
* ℹ️ About tab with author info, website, source repos, tech credits
* Perspectives tab icon changed to 👁 (eye) to distinguish from 🔍 Scan

### Phase 7 — Scan Mode & Violation Counts (v1.2.26–1.2.43) ✅

* **Scan button** (`[🔍 Scan]`) on both SM Explorer and Report Explorer toolbars
* Report Explorer: fast local scan using loaded visual type data (no API calls)
  — checks for pie charts, bar charts, column charts, hidden filters
* SM Explorer: scan runs all SM fixers in `scan_only=True` mode
* Tree items annotated with `⚠️N` violation badges after scan
* Scan results stored in `_scan_results` + `_scan_details` dicts
* Summary status: `"🔍 Scan complete: 14 finding(s) across 2 report(s)."`
* Properties panel shows violation details for selected flagged visual
* One-click "Fix this" buttons per violation (runs specific fixer on that page)
* Re-scan after fix to update counts automatically
* More granular page-level attribution for report scan

### Phase 8 — VertipaqAnalyzer & Memory Integration (v1.2.36–1.2.38) ✅

* **💾 Memory Analyzer tab** (renamed from "Vertipaq") — dedicated tab with on-demand loading
  + Tree: models → tables (sorted by size) → columns (sorted by size)
  + Each node shows size (KB/MB/GB), row count, cardinality, encoding, % DB
  + Properties panel shows full stats for selected table/column
  + Single-click expand/collapse, multi-select compatible
  + Subtab selector: Model Summary | Tables | Partitions | Columns | Relationships | Hierarchies
  + Full DataFrame HTML rendering per subtab with row highlighting
* Both inline in `_pbi_fixer.py` (no external file dependency)
* Relationships shown in SM Explorer tree (expand/collapse per model)
* Perspectives listed in SM Explorer tree (read-only, names only)
* Visual → SM measure navigation (list\_visual\_objects + clickable buttons)
* Cache Vertipaq results across tab switches

### Phase 9 — BPA Integration & Auto-Fixers (v1.2.44–1.2.99) ✅

* **📋 BPA tab** — runs `run_model_bpa()` on loaded semantic models
  + Results table with Rule Name, Category, Object Name, Object Type, Severity
  + Auto-fix buttons per row for 7 fixable rule types (see Fixer Inventory above)
  + "Fix All" button per rule — bulk-fixes all violations of a single rule
  + "Fix Rule" dropdown — select a rule and fix all its violations
  + "Show Native" button — renders full BPA DataFrame in native output
* **📄 Report BPA tab** — runs `run_report_bpa()` on loaded reports
  + Results table with Report, Rule Name, Category, Object, Severity
  + Auto-converts PBIRLegacy reports before running BPA
  + "Show Native" button for full DataFrame output

### Phase 10 — Delta Analyzer & Download (v1.2.44–1.2.99) ✅

* **📐 Delta Analyzer tab** — analyses delta tables in the lakehouse
  + Inputs: table name, lakehouse (optional), schema (optional), column stats toggle, cardinality toggle
  + Subtabs: Summary | Parquet Files | Row Groups | Column Chunks | Columns
  + Full DataFrame HTML rendering per subtab
  + "Show Native" button for full DataFrame output
* **Download buttons** — between input box and tabs
  + ⬇ Download .pbix — saves report as .pbix file
  + ⬇ Download .pbip — saves report as .pbip file (with optional thick\_report support)

---

## Remaining Work

### Phase 11 — UI Alignment & Consistency Fix (v1.2.105) ✅

Fix visual inconsistencies in the three-panel layout across all tabs:

* **Report Explorer panel alignment**: the three columns (Tree | Properties | Preview) do not align consistently with the panels in other tabs (SM Explorer, Perspectives, etc.). Ensure all tabs use the same column widths, borders, and spacing.
* **Panel height consistency**: all three panels should have the same minimum height so the layout doesn't jump when switching tabs or when one panel has more content than others.
* **Border and padding audit**: verify that every section box across all tabs uses the canonical style from `_ui_components.py` (`SECTION_BG`, `BORDER_COLOR`, `border_radius: 8px`, `padding: 12px`). Some panels may be using inline styles that drift from the shared constants.
* **Header alignment**: "REPORT STRUCTURE", "PROPERTIES", "PREVIEW" headers should be at the same vertical position and use the same font size, weight, and color as the corresponding headers in the SM Explorer.
* **Full-width stretch**: ensure the three-panel HBox fills the full available width consistently, with no gap between the outer panels and the tab container edge.

### Phase 12 — Dropdown Item Selector (v1.2.106) ✅

Replace the current free-text-only Report/SM input with a **combo widget** (`widgets.Combobox`) that supports both dropdown selection and free text entry:

* When the workspace is entered and the user clicks **Load** (or on workspace change), fetch the list of all reports and semantic models via the Fabric REST API (`GET /v1.0/myorg/groups/{ws}/reports` + `GET /v1.0/myorg/groups/{ws}/datasets`).
* Populate the dropdown with a **deduplicated** combined list. If a report and semantic model share the same display name, show the name **only once** — the tool loads both the report and its underlying model regardless.
* Items are prefixed with icons to distinguish types: `"📄 Report Name"` and `"📊 Model Name"`. Shared-name items show without prefix (or with a combined indicator).
* The user can **select from the dropdown** (click to pick one or multiple items) or **type/paste free text** including comma-separated values. Free text takes precedence over dropdown selection.
* If left **blank** → load **all** items in the workspace (current behavior, unchanged).
* Deduplicate by display name (case-insensitive), keeping both item types internally for the load logic.
* Implementation: `widgets.Combobox` with `options` populated after workspace is set. For multi-select, consider a `SelectMultiple` or `TagsInput` widget alongside the Combobox.

### Phase 13 — Clone Report + Semantic Model (v1.2.107) ✅

Add an action (button or dropdown entry) that clones the currently loaded report and its underlying semantic model into the same workspace with a new name. The user enters a new name (or a suffix like `"_copy"` / `"_v2"` is appended automatically), and the tool:

* Clones the semantic model via `clone_semantic_model()` or `create_semantic_model_from_bim()` using the current model's BIM/TMDL definition.
* Clones the report via `getDefinition` → modify the report name and dataset binding → `createItem` with the new definition pointing to the cloned model.
* Optionally allows cloning to a **different workspace** (target workspace dropdown).
* Shows progress and confirms both items were created successfully.
* Useful for creating dev/test copies, versioning before applying fixers, or templating.

### Phase 14 — Extract BPA Fixers to Standalone Files (v1.2.108) ✅

The 7 BPA auto-fixers currently live inline in `_bpa_tab()`. For consistency with the fixer pattern (standalone + UI), consider extracting to separate files:

| Inline Fixer | Proposed File | Proposed Function |
| --- | --- | --- |
| Fix floating point | `semantic_model/_Fix_FloatingPointDataType.py` | `fix_floating_point_datatype()` |
| Fix IsAvailableInMDX | `semantic_model/_Fix_IsAvailableInMdx.py` | `fix_isavailable_in_mdx()` |
| Fix measure descriptions | `semantic_model/_Fix_MeasureDescriptions.py` | `fix_measure_descriptions()` |
| Fix date format | `semantic_model/_Fix_DateColumnFormat.py` | `fix_date_column_format()` |
| Fix month format | `semantic_model/_Fix_MonthColumnFormat.py` | `fix_month_column_format()` |
| Fix measure format (#,0) | `semantic_model/_Fix_MeasureFormat.py` | `fix_measure_format()` |
| Hide foreign keys | `semantic_model/_Fix_HideForeignKeys.py` | `fix_hide_foreign_keys()` |

Each should follow the standard pattern: `(dataset, workspace, scan_only)` with standalone `print()` output.

### Phase 15 — Native BPA & Memory Analyzer Integration (Planned)

Replace the custom inline BPA and Memory Analyzer tab implementations with the **original upstream HTML renderers** from Semantic Link Labs, integrated as copied source code within the PBI Fixer codebase. The goal is to use the rich, tabbed HTML visualizations from `run_model_bpa()` and `vertipaq_analyzer()` directly, rather than maintaining a separate simplified version.

#### Approach

* **Copy, don't rewrite**: Take the HTML rendering logic from `_model_bpa.py` (the styled tab UI with tooltips, severity summaries, clickable rules, URL links) and `_vertipaq.py` (the vertipaq_map, formatted HTML tables with data type icons, size formatting) and embed them as local copies inside the PBI Fixer source tree (e.g. `_bpa_native.py`, `_vertipaq_native.py`). This avoids drift from upstream while allowing amendments.
* **Preserve amendments**: Layer the PBI Fixer-specific additions on top of the native output:
  + **BPA tab**: Keep the auto-fix buttons (Fix All, Fix Rule, Fix Row), the fixable-rule dropdown, the row-level fix buttons, and the "Show Full BPA" button. Render the native BPA HTML (with its category tabs, severity badges, tooltips, rule URLs) as the primary results view. Append fix controls below or beside each row where a fixer is available.
  + **Memory Analyzer tab**: Keep the tree view (models → tables → columns with size/cardinality), properties panel, and subtab selector. Use the native `vertipaq_analyzer()` dict of DataFrames as the data source (already done), but render each subtab using the upstream's formatted HTML rendering (with data type icons, number formatting, % DB column) instead of the current raw `.to_html()`. Keep the Load button, Expand/Collapse, and caching behavior.
  + **Report BPA tab**: Use `run_report_bpa()` output as-is, keeping the "Show Native" button and PBIRLegacy auto-conversion logic.
* **Delta Analyzer**: no change — already uses its own rendering; upstream has no equivalent.

#### Source Files to Copy

| Upstream Source | Local Copy | What to Extract |
| --- | --- | --- |
| `_model_bpa.py` | `_bpa_native.py` | HTML rendering: `styles`, `tab_html`, `content_html`, `script` generation + the `vertipaq_map`-style formatting for the results table |
| `_model_bpa_rules.py` | (import directly) | BPA rule definitions — no copy needed, import from `sempy_labs` |
| `_vertipaq.py` | `_vertipaq_native.py` | HTML rendering: `vertipaq_map` with data type icons + format strings, table/column/partition/relationship formatting, the `_format_size()` helper |
| `_icons.py` | (import directly) | Icon constants (`data_type_string`, `int_format`, etc.) — import from `sempy_labs._icons` |

#### Key Constraints

* **Do not fork the data-fetching logic** — continue calling `run_model_bpa(return_dataframe=True)` and `vertipaq_analyzer()` as the data sources. Only copy the *rendering/HTML generation* code.
* **Keep inline fallbacks** — if the copied native renderers fail (e.g. missing icons module in a non-SLL environment), fall back to the current simplified HTML tables.
* **Maintain fix button wiring** — the fix buttons must still reference the `_fix_map` and `_apply_fix` functions from the BPA tab. Augment the native HTML with fix button columns or overlay ipywidgets buttons alongside the HTML output.
* **`IPython.display` vs `ipywidgets.HTML`** — the upstream functions use `display(HTML(...))` which renders directly in notebook output. For the PBI Fixer, capture the HTML string (not the display call) and inject it into an `ipywidgets.HTML` widget inside the tab panel. Use the `return_dataframe=True` path for BPA and the dict return for vertipaq_analyzer to get data, then apply the copied formatting logic to produce the HTML string.

### Phase 16 — Advanced Features (Planned)

* **Table data preview** in SM Explorer: when a table node is selected in the tree, automatically show the top 10 rows as a preview in the properties/preview panel. Add a toggle or dropdown to switch between Top 10 / Top 100 / All rows. Use `fabric.evaluate_dax()` or `TOPN()` DAX query against the semantic model to fetch the data. Render as an HTML table in the properties panel.
* `read_stats_from_data=True` toggle for Direct Lake models in Memory Analyzer
* Measure dependency tree (leverage existing `anytree` patterns in Semantic Link Labs)
* Relationship visualization (simple text-based or HTML diagram)
* Search/filter input above the tree for large models (100+ tables)
* Keyboard shortcuts for common actions (Scan, Fix, Expand All, Collapse All)
* Export scan results to DataFrame / CSV for external reporting
* Batch fixer presets (e.g. "IBCS Standard" = pie fix + bar fix + page size fix + slicer migration)
* **Incremental refresh setup** in SM Explorer: when a table is selected, offer a one-click action (via the actions dropdown or a dedicated button in the properties panel) to configure an incremental refresh policy on that table. The implementation should mirror the Tabular Editor C# approach for setting `RefreshPolicy` on a table (RangeStart/RangeEnd parameters, rolling window, incremental detection expression, pollingExpression, etc.) — research the exact TE C# / TOM API calls needed before implementation. The UI should present a simple form: date column picker, lookback window (e.g. 30 days / 1 year / custom), incremental rows count, and a confirm button that writes the policy via XMLA. Note: SLL already has `add_incremental_refresh_policy()` and `update_incremental_refresh_policy()` — evaluate whether these can be used directly or if lower-level TOM access is needed for the full feature set.

### Phase 17 — Report Visual Layout & Theming (Planned)

* **Fix Visual Alignment & Size** in Report Explorer: a new fixer (or action in the Report Explorer dropdown) that detects and corrects misaligned or undersized chart visuals on a page. Proposed approach:
  + Scan all visuals on a page and identify **chart-type visuals** (bar, column, line, area, combo, scatter, waterfall — exclude cards, slicers, tables, textboxes, shapes, images).
  + Flag charts whose width × height is **less than 1% of the total page area** (e.g. < 10,800 px² on a 1920×1080 page) as "too small" — likely accidental residuals or broken visuals. Offer to delete or resize them.
  + For alignment: group visuals by approximate row (y-position within a tolerance band, e.g. ±5px) and column (x-position ±5px). Within each row, snap all visuals to the same y/height. Within each column, snap to the same x/width. This gives a grid-snap effect without requiring a rigid layout.
  + Expose as a fixer file (`report/_Fix_VisualAlignment.py`) with `scan_only` support: scan mode reports misalignments and tiny visuals, fix mode applies corrections.
  + Add to Report Explorer actions dropdown and optionally to the Fixer tab.

* **Design Theme Editor**: a new tab or sub-panel in the Report Explorer that allows editing the report's JSON theme. Features:
  + Load the current theme from the report definition (PBIR `theme.json` / `CL*.json`).
  + Visual editor for core theme properties: primary/secondary/tertiary colors, background color, foreground/text color, table accent, hyperlink color.
  + Font family and size overrides per visual type.
  + Preview swatches showing the selected palette.
  + Save back to the report definition via `connect_report` / `updateDefinition`.

* **Background Editor**: within the Report Explorer or Theme Editor, allow setting/changing page backgrounds:
  + Solid color picker (hex input or color swatch grid).
  + Transparency slider (0–100%).
  + Apply to current page or all pages.
  + Modify the page `background` property in the PBIR page definition.

* **Logo Uploader**: add a logo/image to report pages:
  + Input via **URL** (preferred — avoids file upload complexity in Fabric Notebooks). Paste an image URL, preview it inline, then insert as an Image visual at a specified position (e.g. top-left corner with configurable offset and size).
  + Optionally support file path for images already in the lakehouse/OneLake.
  + Apply to current page or all pages (bulk insert).
  + Uses `connect_report` to add an Image visual to the page definition.

* **Standard Design Themes from Microsoft**: include a dropdown of built-in Microsoft theme presets that can be applied to a report in one click. Source the theme JSONs from Microsoft's official theme gallery (e.g. the themes available in Power BI Desktop under View → Themes → Theme gallery). Store a curated set of theme JSON files (or URLs) and apply via `updateDefinition` on the report's theme file.

* **Enhanced Fix Page Size** (`_Fix_PageSize.py` update): extend the existing page size fixer beyond just changing the page dimensions from 720×1280 to 1080×1920. The enhanced version should also:
  + **Proportionally resize all visuals** on the page when the page size changes (scale x, y, width, height by the same ratio as the page dimension change).
  + **Proportionally scale font sizes** in visual title, axis labels, data labels, and legend text (scale by the height ratio, rounded to the nearest 0.5pt).
  + Add a `resize_visuals=True` parameter (default True) to control whether visual resizing is applied alongside the page size change.
  + Add a `resize_fonts=True` parameter (default True) to control font scaling.
  + Maintain scan\_only compatibility: in scan mode, report what would be resized without applying changes.

* **Fix Variance Charts (Inline)** in Report Explorer: an IBCS-style variance chart fixer that transforms standard bar/column charts into proper variance visualizations. Proposed as `report/_Fix_VarianceChart.py` with `scan_only` support, plus wired into the Report Explorer actions dropdown. Approach:
  + **Detection**: scan visuals for bar/column charts whose measure names or DAX expressions contain variance indicators (e.g. `"Δ"`, `"Var"`, `"Variance"`, `"Diff"`, `"abs"`, `"rel"`, `"%"` combined with comparison keywords). Also detect charts that have exactly two data series where one is likely an actual vs. comparison pair (AC vs PY, AC vs BU/FC).
  + **Conditional formatting for sign**: set data color conditional formatting so that positive values are green (or IBCS-compliant solid black for absolute variances) and negative values are red. Apply via the visual's `objects` → `dataPoint` → `fill` rules in the PBIR definition, using a conditional formatting rule based on the field value (`>= 0` → positive color, `< 0` → negative color).
  + **Axis and label cleanup**: apply the same cleanup as the existing bar/column fixers (remove axis titles, remove gridlines, add data labels) to keep variance charts consistent with the IBCS formatting standard.
  + **Integrated variance waterfall detection**: optionally detect waterfall chart visuals and apply the same positive/negative color coding to the waterfall breakdown bars.
  + Expose in Report Explorer actions dropdown as "Fix Variance Charts" alongside the existing chart fixers.

* **Design Preview Before Fix** — a general pattern for all chart fixers (variance, bar, column, pie replacement, alignment). Instead of applying a fix immediately, offer the user a choice of **design presets** rendered as visual previews before committing. Implementation:
  + When a fixer is triggered from the Report Explorer actions dropdown, show a **preview panel** (in the properties/bottom-right area) with 2–4 design options rendered as thumbnail previews.
  + Each preview is a small HTML/SVG mockup illustrating the proposed visual style. The user clicks one to select, then confirms with an "Apply" button. "Cancel" discards without changes.
  + **Variance chart presets**:
    - **IBCS Standard**: solid black bars for absolute variance, no fill for relative; red for negative, green for positive. No axis titles, data labels on bars.
    - **IBCS Strict**: same as Standard but with hatched/patterned fills for previous year (PY) values and outline-only bars for budget/forecast (BU/FC) comparisons.
    - **Traffic Light**: green/yellow/red coloring based on threshold bands (e.g. >5% green, -5%–5% yellow, <-5% red). User can configure thresholds.
    - **Monochrome**: dark grey for positive, light grey for negative. Suitable for print or minimalist dashboards.
  + **Bar/Column chart presets**:
    - **IBCS Clean**: no axis titles, no gridlines, data labels on bars, single accent color.
    - **IBCS Grouped**: same cleanup but with category-based color assignment from the theme palette.
    - **Minimal**: remove all chrome (titles, legends, gridlines, axis lines), data labels only.
  + **Pie chart replacement presets** (shown when Fix Pie Charts is triggered):
    - **Clustered Bar** (current default): horizontal bars sorted by value.
    - **Stacked Bar 100%**: shows proportions as a single stacked bar.
    - **Treemap**: area-based proportional visualization.
  + **Technical approach**: the preview mockups are generated as inline HTML/SVG in `ipywidgets.HTML`, not live Power BI embeds (which would be too slow). Use simple colored rectangles, labels, and arrows to represent the chart style. The actual fix applies the selected preset's formatting rules to the PBIR visual definition. Store preset definitions as dicts in the fixer file (e.g. `PRESETS = {"ibcs_standard": {...}, "traffic_light": {...}}`).
  + **Extensibility**: the preview framework should be generic enough that future fixers can register their own presets. A helper function `show_design_preview(presets, on_select)` in `_ui_components.py` handles rendering the preview grid and returning the user's choice.

### Phase 18 — Workspace Report Format Overview (Planned)

Add a **report format overview** panel or subtab (e.g. in the Report tab or as a standalone section) that lists all reports in the workspace with their PBIR/PBIRLegacy format status at a glance.

* Use `sempy_labs.report.list_reports()` to fetch the full report list including the `Format` column.
* Display a DataFrame table showing `Report Name`, `Report Id`, and `Format` (PBIR / PBIRLegacy / etc.).
* Color-code or badge: PBIR = green, PBIRLegacy = orange/warning, other = grey.
* Optionally add a **"Convert All Legacy"** button that batch-converts all PBIRLegacy reports to PBIR via `upgrade_to_pbir()`.
* This provides a quick workspace-level health check before loading individual reports.

### Phase 19 — Model Diagram Tab (Planned)

Add a new **🗺 Model Diagram** tab that visualizes relationships between tables as an interactive diagram.

* **Diagram rendering**: render relationship lines between table boxes using inline HTML/SVG in an `ipywidgets.HTML` widget. Each table is a box showing the table name and key columns; relationship lines connect foreign key → primary key with cardinality labels (1:*, *:1, 1:1, *:*).
* **Data source**: use the already-loaded TOM model relationships (`tm.model.Relationships`) from the SM Explorer — no additional API calls needed.
* **Layout algorithm**: automatic layout using a simple force-directed or layered approach:
  + Place fact tables (tables with the most relationships) in the center.
  + Dimension tables radiate outward.
  + Minimize crossing lines.
  + Allow manual repositioning via drag (if feasible in ipywidgets; otherwise fixed layout with zoom/pan via CSS `transform`).
* **Subtab per model**: if multiple semantic models are loaded, show a subtab selector (like Memory Analyzer) to switch between models.
* **Filtering**: option to show only tables related to a selected table (click a table in the diagram or select from tree → highlight its neighborhood).
* **SM Explorer integration — Create Diagram action**: in the SM Explorer actions dropdown, add a **"🗺 Create Diagram"** action. When triggered on a selected table:
  + Automatically select the table and all directly related tables (via relationships).
  + Generate a **TMDL diagram file** saved to the model's TMDL definition if supported by the TMDL format. TMDL diagram files (`.tmdl` in the `diagrams/` folder) store layout metadata: which tables are included, their x/y positions, and relationship line routing.
  + If TMDL diagram persistence is not supported (TMDL format does not have a `diagrams/` concept), fall back to saving diagram layout as a JSON file alongside the model definition or in the lakehouse.
  + The diagram starts with all related tables included and arranged automatically; the user can then reposition and save.
* **Research needed**: verify whether TMDL supports diagram definitions (Tabular Editor stores diagrams in `.tmd` / BIM files under `model.diagrams[]`). If TMDL has a `diagrams/` folder, use it. Otherwise, store as a sidecar JSON.

### Phase 20 — AI Assistant (Planned)

* **AI Assistant window** (Michael's AI window): integrate the Semantic Link Labs AI/Copilot chat interface into the PBI Fixer as an additional tab or slide-out panel. This leverages the existing `sempy_labs._ai` module and/or the `sempy_labs.rti._copilot` module. The AI window should:
  + Provide a chat interface where users can ask natural-language questions about their loaded semantic model or report (e.g. "Which measures are unused?", "Suggest DAX optimizations", "Explain this measure").
  + Have context awareness — automatically pass the currently loaded model/report metadata (table names, measure expressions, relationships) as context to the AI.
  + Support quick actions from AI suggestions (e.g. AI suggests hiding a column → one-click button to apply via XMLA).
  + Research Michael Kovalsky's existing AI window implementation in SLL to determine the correct integration points and API surface.

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
| Naming | "Semantic Model Explorer" / "Report Explorer" | Describes functionality directly, no external tool references |
| Single workspace | No comma-separation for workspace | Simplifies connection logic; multi-workspace adds complexity with little benefit |
| Comma-separated items | Split on `,` then `.strip()` each | Allows `"Report A, Report B"` with flexible spacing |
| Blank = all | Load everything in workspace when report/SM input is empty | Most common use case; power users filter with comma-separated names |
| 5-minute timeout | Hard wall-clock limit on full load | Prevents runaway connections in large workspaces |
| PBIR gate at load time | Check format before any fixer runs | Every report fixer requires PBIR; fail-fast prevents confusing errors |
| Fixer standalone compat | Fixers use `print()`, UI wraps with `redirect_stdout` | Fixers work both inside UI and as standalone notebook calls |
| God button | "⚡ Fix Everything" runs all checked fixers | Most common action; reduces clicks for the typical workflow |
| Fixer tab hidden | `show_fixer_tab=False` by default | All fixers accessible via Actions dropdowns in Report/SM tabs |
| Scan mode | Integrated toggle per tab, not a separate tab | Violations visible where objects are; no context switching needed |
| BPA fixers inline | 7 small fix functions inside `_bpa_tab()` | Simple one-liner fixes; separate files would be overkill until they need `scan_only` or reuse |
| Analysis tabs inline | Vertipaq, BPA, Report BPA, Delta Analyzer in `_pbi_fixer.py` | No external file dependency; these tabs are read-only analysis, not reusable modules |

---

## API Dependencies

| Feature | Semantic Link Labs API | Notes |
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
| `_pbi_fixer.py` | ✅ Pushed (v1.2.99) |
| `_ui_components.py` | ✅ Pushed |
| `_sm_explorer.py` | ✅ Pushed |
| `_report_explorer.py` | ✅ Pushed |
| `_perspective_editor.py` | ✅ Pushed |
| `semantic_model/_Add_MeasuresFromColumns.py` | ✅ Pushed (also inline fallback in `_pbi_fixer.py`) |
| `semantic_model/_Add_PYMeasures.py` | ✅ Pushed (also inline fallback in `_pbi_fixer.py`) |
| `report/_Fix_MigrateSlicerToSlicerbar.py` | ✅ Pushed (file exists, **not yet wired into UI**) |

### NOT yet pushed / still need PRs to upstream `microsoft/semantic-link-labs`

| File | Notes |
| --- | --- |
| `report/_Fix_UpgradeToPbir.py` | Needs `feature/fix-upgrade-to-pbir` branch + PR. |
| `report/_Fix_MigrateSlicerToSlicerbar.py` | **Deprioritized** — file exists, not wired into UI. PR deferred. |
| `semantic_model/_Fix_DefaultDataSourceVersion.py` | **Deprioritized** — requires Large SM storage format. PR deferred. |
| `report/_upgrade_to_pbir.py` | **Already in upstream SLL** — no PR needed. |
| `report/_generate_embed_token.py` | **Already in upstream SLL** — no PR needed. |

---

## Contributing

To add a new fixer:

1. Create `_Fix_YourFixer.py` in `report/` or `semantic_model/`
2. Add a lazy import in `_pbi_fixer.py`
3. Add a checkbox row and wire it into the `report_fixers` or `sm_fixers` list
4. Add the fixer to the appropriate Explorer actions dropdown (`_rpt_fixer_cbs` or `_sm_fixer_cbs`)
5. The fixer will automatically appear in the Fixer tab UI and/or the Explorer actions
6. The fixer **must** also work standalone: `fix_your_fixer(report="X", workspace="Y", scan_only=False)`
