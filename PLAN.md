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
                         #   (Memory Analyzer, BPA, Report BPA, Delta Analyzer,
                         #    Prototype, Model Diagram, Script Runner, About)
  _ui_components.py      # Shared theme, icons, tree-building, layout helpers
  _model_explorer.py     # Model Explorer tab (renamed from _sm_explorer.py at v1.2.119)
  _report_explorer.py    # Report Explorer tab
  _perspective_editor.py # Perspective Editor tab
  report/                # Report fixers + standalone modules
    _Fix_PieChart.py
    _Fix_BarChart.py
    _Fix_ColumnChart.py
    _Fix_PageSize.py
    _Fix_HideVisualFilters.py
    _Fix_UpgradeToPbir.py
    _Fix_MigrateSlicerToSlicerbar.py
    _Fix_VisualAlignment.py
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
    _Setup_IncrementalRefresh.py  # Incremental refresh setup (Phase 27)
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

## Tab Layout (v1.2.152)

| Tab | Icon | Source | Description |
| --- | --- | --- | --- |
| Semantic Model | 📊 | `_model_explorer.py` | Tree + DAX preview + table data preview + properties + scan + search filter + actions dropdown |
| Report | 📄 | `_report_explorer.py` | Tree + visual preview + properties + format overview + scan + search filter + actions dropdown |
| Fixer | ⚡ | `_pbi_fixer.py` (inline) | Checkbox-based fixer selection, God Button, Scan/Fix/Scan+Fix modes |
| Perspectives | 👁 | `_perspective_editor.py` | Perspective Editor (based on m-kovalsky) |
| Memory Analyzer | 💾 | `_pbi_fixer.py` (`_vertipaq_tab`) | Vertipaq stats with model dropdown, subtab DataFrames |
| BPA | 📋 | `_pbi_fixer.py` (`_bpa_tab`) | Model BPA with category tabs, severity badges, grouped checkbox fixers for 19 rule types |
| Report BPA | 📄 | `_pbi_fixer.py` (`_report_bpa_tab`) | Report BPA via `run_report_bpa()`, auto-converts PBIRLegacy |
| Delta Analyzer | 📐 | `_pbi_fixer.py` (`_delta_analyzer_tab`) | Delta table analysis: summary, parquet files, row groups, column chunks |
| Prototype | 📐 | `report/_report_prototype.py` | Report prototype with SVG + Excalidraw export, optional page screenshots |
| Model Diagram | 🗺 | `_pbi_fixer.py` (`_diagram_tab`) | SVG relationship diagram between tables |
| About | ℹ️ | `_pbi_fixer.py` (inline) | Author info, links, tech credits |

* **Fixer tab** is hidden by default (`show_fixer_tab=False`); all fixers are accessible via actions dropdowns in SM and Report tabs.
* **Script Runner tab** exists but is disabled pending security review.
* Tab order: SM → Report → Fixer (if enabled) → Perspectives → Memory Analyzer → BPA → Report BPA → Delta Analyzer → Prototype → Model Diagram → About.

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
| Migrate Slicer to Slicerbar | `_Fix_MigrateSlicerToSlicerbar.py` | `fix_migrate_slicer_to_slicerbar()` | ✅ | ❌ | ❌ |

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
| Format All DAX | _(inline in `_pbi_fixer.py`)_ | `tom.format_dax()` | ❌ | ❌ | ✅ |

### BPA Auto-Fixers (19 total — standalone files + grouped checkbox UI in `_bpa_tab`)

These fix specific Model BPA violations. Each has a **standalone fixer file** in `semantic_model/` with `scan_only` support. The BPA tab organizes them into 6 category groups with select-all checkboxes (Phase 41).

| # | BPA Rule | Fix Action | Category |
|---|----------|------------|----------|
| 1 | Do not use floating point data types | Column DataType → Decimal | 🔢 Data Types |
| 2 | Set IsAvailableInMdx to false | `IsAvailableInMDX = False` | 📡 MDX |
| 3 | Set IsAvailableInMdx to true | `IsAvailableInMDX = True` | 📡 MDX |
| 4 | Visible objects with no description (Measures) | Set description to DAX expression | 📝 Documentation |
| 5 | Provide format string for 'Date' columns | Format → `mm/dd/yyyy` | 📊 Formatting |
| 6 | Provide format string for 'Month' columns | Format → `MMMM yyyy` | 📊 Formatting |
| 7 | Provide format string for measures | Format → `#,0` | 📊 Formatting |
| 8 | Percentages should be formatted | Format → `#,0.0%;-#,0.0%;#,0.0%` | 📊 Formatting |
| 9 | Format flag columns as Yes/No | Format → `"Yes";"Yes";"No"` | 📊 Formatting |
| 10 | Hide foreign keys | `IsHidden = True` | 🔗 Schema |
| 11 | Do not summarize numeric columns | `SummarizeBy = None` | 🔗 Schema |
| 12 | Mark primary keys | `IsKey = True` | 🔗 Schema |
| 13 | Objects should not start or end with a space | Trim whitespace | 🏷 Naming |
| 14 | First letter must be capitalized | Capitalize first letter | 🏷 Naming |
| 15 | Use the DIVIDE function for division | Regex-replace `/ ` → `DIVIDE()` | 📊 Formatting |
| 16 | Avoid adding 0 to a measure | Strip `0+` prefix | 📊 Formatting |
| 17 | Whole numbers should be formatted | Format → `#,0` | 📊 Formatting |
| 18 | Month (as a string) must be sorted | Set SortByColumn | 📊 Formatting |
| 19 | Add data category for columns | Set DataCategory by naming convention | 📊 Formatting |

### Optional / Not Now

| Fixer | File | Reason |
| --- | --- | --- |
| Set DataSource Version V3 | `semantic_model/_Fix_DefaultDataSourceVersion.py` | Requires Large SM storage format; not broadly available |

---

## Implementation Phases

### Completed (28 phases)

| # | Phase | Version | Summary |
|---|-------|---------|---------|
| 1 | Foundation | v1.1.0 | `_ui_components.py`, `_model_explorer.py`, `_report_explorer.py`, `_pbi_fixer.py` tab wrapper |
| 2 | SM Properties & Editing | v1.2.x | Properties panel, editable DAX, save button, Perspective Editor tab |
| 3 | Report Preview & Properties | v1.2.x | `powerbiclient.Report` embed, visual properties, page navigation, fixer actions dropdown |
| 4 | Multi-Item Connection & PBIR Gate | v1.2.8–1.2.24 | Comma-separated input, blank=all, PBIR format check, PBIRLegacy warnings, Convert All button |
| 5 | Fixer Tab Redesign | v1.2.8–1.2.24 | God Button, fixers in Explorer dropdowns, tab hidden by default, Format All DAX, MeasuresFromColumns, PYMeasures |
| 6 | UI Polish | v1.2.14–1.2.42 | Full-width layout, multi-select, deduplication, branded header, About tab, version footer |
| 7 | Scan Mode & Violation Counts | v1.2.26–1.2.43 | Scan button per tab, violation badges, "Fix this" buttons, re-scan after fix |
| 8 | VertipaqAnalyzer & Memory | v1.2.36–1.2.38 | 💾 Memory Analyzer tab with subtabs, tree, DataFrame rendering, cache |
| 9 | BPA Integration & Auto-Fixers | v1.2.44–1.2.99 | 📋 BPA tab + 📄 Report BPA tab, category tabs, Fix All/Fix Rule/Fix Row, Show Native |
| 10 | Delta Analyzer & Download | v1.2.44–1.2.99 | 📐 Delta Analyzer tab, ⬇ Download .pbix/.pbip buttons |
| 11 | UI Alignment & Consistency | v1.2.105 | Three-panel layout alignment, border/padding audit, full-width stretch |
| 12 | Dropdown Item Selector | v1.2.106 | `widgets.Combobox` with API-populated dropdown, icon prefixes 📄/📊, List Items button |
| 13 | Clone Report + Semantic Model | v1.2.107 | Clone via `getDefinition` → `createItem`, auto-increment suffix (_copy, _copy2, _copy3) |
| 14 | Extract BPA Fixers to Files | v1.2.108 | 7 BPA fixers → standalone files in `semantic_model/` with `scan_only` support |
| 15 | Clone Buttons & Name Mismatch | v1.2.110 | 📋 Clone Both/Report/Model buttons, name mismatch warning |
| 16 | Stop Load Button | v1.2.111 | ⏹ Stop button on both Explorers, `_cancel_load` flag |
| 17 | Native BPA & Memory Analyzer | v1.2.112 | BPA category ToggleButtons, Memory Analyzer subtabs (no tree, direct DataFrames) |
| 18 | Additional BPA Fix Scripts | v1.2.113 | 12 more BPA fixers → 19 total standalone files |
| 19 | Table Data Preview | v1.2.114 | Top N rows via `evaluate_dax(TOPN(...))` in Model Explorer preview panel |
| 20 | Search & Filter Tree | v1.2.141 | `widgets.Text` filter above both Explorer trees, real-time keystroke filtering |
| 21 | Incremental Refresh Setup | v1.2.142 | `_Setup_IncrementalRefresh.py`, auto date column detection, Model Explorer action |
| 22 | Fix Visual Alignment | v1.2.143 | `_Fix_VisualAlignment.py`, customizable `tolerance_pct` (2%), Report Explorer action |
| 23 | Design Theme Editor | v1.2.144 | `_report_theme.py` — `get/set/update_theme_colors()`, `show_theme_summary()` |
| 24 | Format Overview | v1.2.145 | Report Explorer subtab, workspace-wide PBIR/PBIRLegacy status, Convert All Legacy |
| 25 | Model Diagram Tab | v1.2.146 | 🗺 SVG relationship diagram, auto layout, model dropdown, export SVG |
| 26 | Report Prototyping | v1.2.123–1.2.153 | 📐 Prototype tab, SVG + Excalidraw, optional page screenshots (Export API), progress bar, suppressed output |
| 27 | Script Runner Tab | v1.2.147 | ⚙️ Python script runner with TOM in scope. Disabled pending security review. |
| 28 | Grouped BPA Fixer Checkboxes | v1.2.152 | 6 category groups (Data Types, Formatting, Naming, Schema, MDX, Documentation) with select-all + Fix Selected |

---

## Remaining Work

### Phase 29 — Extended Model Explorer Properties

* **Columns**: encoding hint, sort-by column, is-key, is-nullable, lineage tag, data category.
* **Tables**: mode (Import/DirectLake/Dual), row count, source expression (M/partition query), data category, lineage tag.
* **Measures**: is-hidden, lineage tag, KPI properties (if any).
* **Relationships**: cross-filter direction, security filtering, is-active, rely-on-referential-integrity.

### Phase 30 — Editable Report Explorer Properties

* **Pages**: editable display name, width, height, background color, hidden flag.
* **Visuals**: editable position (x, y), size (width, height), title text, hidden flag.
* Save button with dirty-state tracking. Writes via `connect_report` in read-write mode.

### Phase 31 — Read Stats from Data Toggle

* `read_stats_from_data=True` checkbox in Memory Analyzer nav row for Direct Lake models.

### Phase 32 — Measure Dependency Tree

* Measure dependency tree/DAG visualization leveraging `anytree` patterns in SLL.
* Show which measures reference which other measures/columns.

### Phase 33 — Export Scan Results

* Export scan results to DataFrame / CSV for external reporting.
* "Export" button next to the Scan button.

### Phase 34 — Batch Fixer Presets

* Presets (e.g. "IBCS Standard" = pie fix + bar fix + page size fix + slicer migration).
* Preset dropdown in the Fixer tab or as a top-level action.

### Phase 35 — Background Editor

* Set/change page backgrounds: solid color picker (hex input), transparency slider (0–100%).
* Apply to current page or all pages. Modifies PBIR page `background` property.

### Phase 36 — Logo Uploader

* Add a logo/image to report pages via URL input.
* Preview inline, insert as Image visual at configurable position/size.

### Phase 37 — Standard Design Themes

* Dropdown of built-in Microsoft theme presets applied in one click.
* Source from Microsoft's official theme gallery. Apply via `updateDefinition`.

### Phase 38 — Enhanced Fix Page Size

* Extend `_Fix_PageSize.py`: proportionally resize all visuals + scale font sizes.
* `resize_visuals=True` and `resize_fonts=True` parameters. `scan_only` compatible.

### Phase 39 — Fix Variance Charts

* IBCS-style variance chart fixer (`report/_Fix_VarianceChart.py`).
* Positive/negative color formatting, axis/label cleanup, waterfall chart support.

### Phase 40 — Design Preview Before Fix

* Show 2–4 design preset previews (HTML/SVG mockups) before applying a fix.
* User selects preset, confirms with "Apply". Framework in `_ui_components.py`.

### Phase 41 — AI Assistant

* Integrate SLL AI/Copilot chat interface as a tab or slide-out panel.
* Context-aware: pass loaded model/report metadata (tables, measures, relationships) to AI.
* Quick-action buttons from AI suggestions (e.g. "Hide this column" → one-click XMLA apply).
* Research Michael Kovalsky's `sempy_labs._ai` / `sempy_labs.rti._copilot` integration points.

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
| `_pbi_fixer.py` | ✅ Pushed (v1.2.152) |
| `_ui_components.py` | ✅ Pushed |
| `_model_explorer.py` | ✅ Pushed |
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
4. Add the fixer to the appropriate Explorer actions dropdown (`_rpt_fixer_cbs` or `_model_fixer_cbs`)
5. The fixer will automatically appear in the Fixer tab UI and/or the Explorer actions
6. The fixer **must** also work standalone: `fix_your_fixer(report="X", workspace="Y", scan_only=False)`
