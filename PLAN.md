# PBI Fixer — Development Plan

## Vision

Evolve the PBI Fixer from a single-purpose fixer tool into a comprehensive Power BI development environment running natively in Fabric Notebooks. The UI follows a three-panel layout (object tree on the left, preview top-right, properties bottom-right) with the ability to switch between **Semantic Model**, **Report**, **Fixer**, and **Perspectives** views.

The tool connects to an entire workspace of semantic models and reports (displayed as a unified tree), with optional comma-separated filtering. A PBIR format check runs automatically on load — non-PBIR reports are flagged and can be converted in-place before any fixers run.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ ┌─────────────────────────────────────────────────┐      │
│ │ Workspace [_______________]  Report/SM [_,_,_]  │      │
│ │                              [Load]             │      │
│ └─────────────────────────────────────────────────┘      │
│  [📊 Semantic Model]  [📄 Report]  [⚡ Fixer]  [🔍 ...]  │
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
  _pbi_fixer.py          # Tab wrapper + Fixer UI + PBIR check gate
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
```

---

## Connection & Loading

### Single Workspace, Multiple Items
- **Workspace input**: single text field — one workspace name or ID. No comma separation for workspaces.
- **Report / SM input**: supports **comma-separated** names or IDs (e.g. `"Sales Report, Finance Report"` or `"abc-123, def-456"`).
  - If left **blank** → load **all** reports and semantic models in the workspace.
  - If specific names/IDs given → load only those items.
- **Load button**: triggers connecting to the workspace and fetching metadata for all matching items.

### Timeout
- Hard timeout of **5 minutes** (300s) for the full load operation.
- If loading all items in a large workspace, iterate items sequentially and abort with a partial result + warning if the 5-minute wall clock limit is reached.
- Individual item connections (TOM / connect_report) should have a per-item timeout of **60s**.

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
- On load, check every report's format via the Fabric REST API (`GET /v1.0/myorg/groups/{ws}/reports`).
- Reports in **PBIR** format: shown normally.
- Reports in **PBIRLegacy** format: shown with a ⚠️ warning badge in the tree. A banner appears at the top of the Report tab: _"N report(s) are in PBIRLegacy format. Convert to PBIR to enable fixers."_ with a **Convert All** button.
- Reports in other formats (RDL, etc.): shown greyed out, not actionable.
- **All report fixers require PBIR**. If a user attempts to run a fixer on a PBIRLegacy report, the UI should offer to convert first rather than silently failing.

### Convert to PBIR
Two conversion approaches exist in Semantic Link Labs:
1. **`_Fix_UpgradeToPbir.fix_upgrade_to_pbir()`** — REST round-trip (`getDefinition` → `updateDefinition`). Preferred for single reports within the Fixer UI. Already follows the fixer interface (`report`, `page_name`, `workspace`, `scan_only`).
2. **`report._upgrade_to_pbir.upgrade_to_pbir()`** — Batch upgrade via embed + save. Supports `List[str|UUID]` for reports and workspaces. Better for bulk operations. Already merged in upstream SLL.

The UI should:
- Use approach 1 (`fix_upgrade_to_pbir`) for individual report conversion triggered from the tree context menu or the "Convert" button next to a single report.
- Use approach 2 (`upgrade_to_pbir`) for the "Convert All" bulk button, passing the list of PBIRLegacy report IDs.
- After conversion, re-check format and update the tree badge accordingly.

---

## Implementation Phases

### Phase 1 — Foundation (v1.1.0) ✅
- [x] `_ui_components.py` — shared theme constants, icon dict, `build_tree_items()`, `create_three_panel_layout()`, connection bar helpers
- [x] `_sm_explorer.py` — Semantic Model Explorer with tree + DAX preview + properties placeholder
- [x] `_report_explorer.py` — Report Explorer with tree + preview/properties placeholders
- [x] `_pbi_fixer.py` — Tab wrapper (Fixer | Semantic Model | Report)
- [x] `PLAN.md` — this file

### Phase 2 — Semantic Model Properties & Editing (v1.2.x) ✅
- [x] Properties panel in SM Explorer: data type, format string, description, display folder, is_hidden
- [x] Editable DAX for measures and calc items with Save Expression button
- [x] Editable properties (write back via XMLA) with save button and confirmation
- [x] Collapsible trees with expand/collapse all
- [x] Perspective Editor tab (based on upstream m-kovalsky/perspective_editor)

### Phase 3 — Report Preview & Properties (v1.2.x) ✅
- [x] Report preview via `powerbiclient.Report` widget (live embedded report)
- [x] Properties panel: visual position, size, type, filter config
- [x] Page navigation in preview when selecting page in tree
- [x] Fixer actions dropdown in Report Explorer (runs fixers on selected page)

### Phase 4 — Multi-Item Connection & PBIR Gate (v1.2.8–1.2.24) ✅
- [x] Shared Load button next to input field — triggers SM + Report loading at once
- [x] Comma-separated report/SM input (e.g. `"Bad Report, Slicerbar Testing"`)
- [x] Blank input = load all semantic models / reports in the workspace via REST API
- [x] Multi-model tree grouping (expand/collapse per model)
- [x] Multi-report tree grouping (expand/collapse per report)
- [x] Per-item progress status during loading (`Model 1/9: loading 'X'…`)
- [x] 5-minute hard timeout on full load
- [x] PBIR format check via REST API, skips non-PBIR reports for fixers
- [x] "Upgrade to PBIR" checkbox in Fixer (runs first in chain)
- [x] "Convert to PBIR" in Report Explorer actions dropdown
- [ ] PBIRLegacy warning badges in tree + banner with "Convert All" button
- [ ] After conversion, re-check and update tree badges

### Phase 5 — Fixer Tab Redesign (v1.2.8–1.2.24) ✅
- [x] **"God Button"** (⚡ Fix Everything) — selects all fixers + confirms XMLA, runs
- [x] Report fixers in Report Explorer actions dropdown (Fix Pie Charts, Fix Bar Charts, etc.)
- [x] SM fixers in SM Explorer actions dropdown (Discourage Implicit Measures, Calendar, etc.)
- [x] Fixer tab hidden by default (`show_fixer_tab=False`); pass `True` to restore
- [x] Tab order: SM → Report → Fixer → Perspectives
- [x] All fixer scripts continue to work standalone via `print()` + `redirect_stdout`
- [x] New SM actions: "Auto-Create Measures from Columns", "Add PY Measures (Y-1)" — inline fallback in `_pbi_fixer.py`

### Phase 6 — UI Polish (v1.2.14–1.2.42) ✅
- [x] Full-width layout (`width=100%`, no max-width cap)
- [x] Wider tree panels (400px) and input fields (400px)
- [x] Multi-select via `SelectMultiple` (Ctrl+click / Shift+click)
- [x] Single-click expand/collapse coexists with multi-select (len==1 triggers toggle)
- [x] Duplicate display strings deduplicated with zero-width spaces
- [x] Properties panel strips model prefix from table names
- [x] Inline status per tab (progress, errors, completion)
- [x] Fixer stdout captured via `redirect_stdout` (no notebook scroll)
- [x] Split toolbar into two rows: nav (Load/Expand/Collapse) + actions (Scan/dropdown/Run)
- [x] Select-then-run pattern: dropdown selects action, ⚡ Run button executes
- [x] SummarizeBy property shown for columns in SM Explorer properties
- [x] Save Expression/Properties correctly extracts model name from multi-model keys
- [x] Auto-expand all items after load
- [x] Unified save button with dirty state tracking (green ✓/red ⚠️)
- [x] Branded header with accent color + wrench icon + bottom border
- [x] Version footer with author + actionablereporting.com link
- [x] Tab button width optimized (130px for 8 tabs)
- [x] Input box with light grey background for visual separation
- [x] ℹ️ About tab with author info, website, source repos, tech credits
- [x] Perspectives tab icon changed to 👁 (eye) to distinguish from 🔍 Scan

### Phase 7 — Scan Mode & Violation Counts (v1.2.26–1.2.43) ✅
- [x] **Scan button** (`[🔍 Scan]`) on both SM Explorer and Report Explorer toolbars
- [x] Report Explorer: fast local scan using loaded visual type data (no API calls)
  — checks for pie charts, bar charts, column charts, hidden filters
- [x] SM Explorer: scan runs all SM fixers in `scan_only=True` mode
- [x] Tree items annotated with `⚠️N` violation badges after scan
- [x] Scan results stored in `_scan_results` + `_scan_details` dicts
- [x] Summary status: `"🔍 Scan complete: 14 finding(s) across 2 report(s)."`
- [x] Properties panel shows violation details for selected flagged visual
- [x] One-click "Fix this" buttons per violation (runs specific fixer on that page)
- [ ] Re-scan after fix to update counts automatically
- [ ] More granular page-level attribution for report scan

### Phase 8 — VertipaqAnalyzer & Memory Integration (v1.2.36–1.2.38) ✅
- [x] **📈 Vertipaq tab** — dedicated tab with on-demand loading
  - Tree: models → tables (sorted by size) → columns (sorted by size)
  - Each node shows size (KB/MB/GB), row count, cardinality, encoding, % DB
  - Properties panel shows full stats for selected table/column
  - Single-click expand/collapse, multi-select compatible
- [x] **💾 Memory tab** — visual dashboard of memory usage
  - Top 10 tables by size with colored bar indicators (red >30%, orange >10%, green <10%)
  - Top 10 column hotspots (largest columns with cardinality + encoding)
  - Relationship summary with missing rows highlight
- [x] Both tabs use `vertipaq_analyzer()` from semantic-link-labs
- [x] Both inline in `_pbi_fixer.py` (no external file dependency)
- [x] Relationships shown in SM Explorer tree (expand/collapse per model)
- [x] Perspectives listed in SM Explorer tree (read-only, names only)
- [x] Visual → SM measure navigation (list_visual_objects + clickable buttons)
- [ ] `read_stats_from_data=True` toggle for Direct Lake models
- [ ] Cache Vertipaq results across tab switches

### Phase 9 — Remaining & Advanced Features
- [ ] Re-scan after fix to auto-update violation counts
- [ ] Report BPA integration — highlight issues directly on tree nodes
- [ ] Model BPA integration — surface best-practice findings alongside the tree
- [ ] Relationship visualization (simple text-based or HTML diagram)
- [ ] Measure dependency tree (leverage existing `anytree` patterns in Semantic Link Labs)
- [ ] Search/filter input above the tree for large models (100+ tables)
- [ ] PBIRLegacy warning badges in tree + "Convert All" button
- [ ] After PBIR conversion, re-check and update tree badges

---

## UI Consistency — Box Styling

Currently some boxes use `#fafafa` background (light grey) while others inherit darker greys or have no background. **All section boxes** across all tabs must use the same style:

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

Audit all boxes across `_pbi_fixer.py`, `_sm_explorer.py`, `_report_explorer.py`, `_perspective_editor.py`, and `_ui_components.py` and ensure:
- Same `background_color`, `border`, `border_radius`, `padding`, and `gap` values
- Same width where applicable (full-width within their parent container)
- If a box intentionally needs a different style (e.g. XMLA warning = `#ffc107` border), document the exception

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
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

---

## API Dependencies

| Feature | Semantic Link Labs API | Notes |
|---------|----------------------|-------|
| SM tree | `connect_semantic_model(readonly=True)` → `tm.model.Tables`, `.Columns`, `.Measures`, `.Hierarchies` | TOM object model via .NET interop |
| DAX preview | `measure.Expression`, `calc_item.Expression` | Pre-fetched during Load |
| Report tree | `connect_report(readonly=True)` → `rw.list_pages()`, `rw.list_visuals()` | Returns DataFrames |
| Report format | `GET /v1.0/myorg/groups/{ws}/reports` → `.format` field | REST API, no TOM needed |
| PBIR upgrade (single) | `fix_upgrade_to_pbir(report, workspace=ws)` | REST round-trip: getDefinition → updateDefinition |
| PBIR upgrade (bulk) | `upgrade_to_pbir(report=[...], workspace=ws)` | Embed + save approach, already in upstream SLL |
| Vertipaq stats | `vertipaq_analyzer(dataset, workspace)` | Returns `dict[str, pd.DataFrame]` with Model/Tables/Columns/Partitions/Relationships |
| Fixers | `fix_piecharts()`, `fix_barcharts()`, etc. | Existing fixer functions, unchanged |

---

## PR / Submission Status

### Already pushed to fork (`KornAlexander/semantic-link-labs`) — separate feature branches

| File | Branch | Status |
|------|--------|--------|
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
|------|--------|
| `_pbi_fixer.py` | ✅ Pushed (v1.2.44) |
| `_ui_components.py` | ✅ Pushed |
| `_sm_explorer.py` | ✅ Pushed |
| `_report_explorer.py` | ✅ Pushed |
| `_perspective_editor.py` | ✅ Pushed |
| `semantic_model/_Add_MeasuresFromColumns.py` | ✅ Pushed (also inline fallback in `_pbi_fixer.py`) |
| `semantic_model/_Add_PYMeasures.py` | ✅ Pushed (also inline fallback in `_pbi_fixer.py`) |

### NOT yet pushed / still need PRs to upstream `microsoft/semantic-link-labs`

| File | Notes |
|------|-------|
| `report/_Fix_UpgradeToPbir.py` | New file — REST round-trip PBIR upgrade fixer. On `feature/pbi-fixer-ui` branch but needs own PR. |
| `report/_Fix_MigrateSlicerToSlicerbar.py` | New file — slicer migration fixer. On `feature/pbi-fixer-ui` branch but needs own PR. |
| `semantic_model/_Fix_DefaultDataSourceVersion.py` | New file — sets DefaultPowerBIDataSourceVersion. On `feature/pbi-fixer-ui` branch but needs own PR. Currently removed from UI (requires Large SM storage format). |
| `report/_upgrade_to_pbir.py` | **Already in upstream SLL** (not a new file) — batch upgrade via embed+save. No PR needed. |
| `report/_generate_embed_token.py` | **Already in upstream SLL** — embed token helper. No PR needed. |

### Summary of what still needs individual PRs

1. `_Fix_UpgradeToPbir.py` → needs `feature/fix-upgrade-to-pbir` branch + PR
2. `_Fix_MigrateSlicerToSlicerbar.py` → needs `feature/fix-migrate-slicer` branch + PR
3. `_Fix_DefaultDataSourceVersion.py` → needs `feature/fix-default-datasource-version` branch + PR (low priority, requires Large SM storage format)

---

## Contributing

To add a new fixer:
1. Create `_Fix_YourFixer.py` in `report/` or `semantic_model/`
2. Add a lazy import in `_pbi_fixer.py`
3. Add a checkbox row and wire it into the `report_fixers` or `sm_fixers` list
4. The fixer will automatically appear in the Fixer tab UI
5. The fixer **must** also work standalone: `fix_your_fixer(report="X", workspace="Y", scan_only=False)`
