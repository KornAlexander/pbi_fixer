# Tabular Editor 3 vs PBI Fixer — Full Feature Mapping

## TE3 Features Already in PBI Fixer

| # | TE3 Feature | PBI Fixer Equivalent | Notes |
|---|-------------|---------------------|-------|
| 1 | **DAX Expression Editor** | ✅ DAX editing in properties panel | Basic text editing, no IntelliSense |
| 2 | **DAX Formatting** (F6) | ✅ `tom.format_dax()` | Same daxformatter.com API |
| 3 | **Best Practice Analyzer** | ✅ 19 model BPA rules + 4 report BPA rules | 15 auto-fixers have no TE3 standard equivalent |
| 4 | **BPA Auto-Fix** | ✅ 19 standalone auto-fixers | TE3 has ~4 standard FixExpressions; PBI Fixer has 19 |
| 5 | **Vertipaq Analyzer** | ✅ Memory Analyzer tab | DataFrame subtabs, model dropdown, read_stats_from_data toggle |
| 6 | **Perspective Editor** | ✅ Full create/edit/delete | Tri-state checkboxes, same functionality |
| 7 | **Metadata Translation Editor** | ✅ Translations tab | + auto-translate via Azure AI Translator (SynapseML) — TE3 doesn't have auto-translate |
| 8 | **Hierarchical Object Tree (TOM Explorer)** | ✅ Model Explorer tree | Tables, columns, measures, hierarchies, calc groups, relationships |
| 9 | **Diagram View** (read-only) | ✅ Model Diagram tab | SVG auto-layout with nearest-edge connections. TE3 diagram is also an editor — see "Missing" |
| 10 | **Table Data Preview** | ✅ TOPN preview in properties panel | TE3 uses Pivot Grid for this; PBI Fixer uses inline DAX query |
| 11 | **Save to Service (XMLA)** | ✅ SM via XMLA, reports via PBIR connect_report | Both support connected write-back |
| 12 | **Download / Export** | ✅ Download .pbix / .pbip | TE3: Save As .bim/.pbit/.pbip. PBI Fixer: export to local files |
| 13 | **Object Properties Panel** | ✅ Properties for columns, measures, tables, relationships | Curated subset vs TE3's full TOM property grid |
| 14 | **Create Measures** | ✅ Create Measure form (table, name, DAX, format, folder) | |
| 15 | **Create Calculated Columns** | ✅ Create Calculated Column form | |
| 16 | **Create Calculated Tables** | ✅ Create Calculated Table form | |
| 17 | **Create Calculation Groups** | ✅ Add Units CG, Add Time Intelligence CG | Preset templates only, not freeform |
| 18 | **Delete Objects** | ✅ Delete Selected (measures, columns, tables, hierarchies, calc items, relationships) | With confirmation widget |
| 19 | **Duplicate Objects** | ✅ Duplicate visuals and pages (report side) | TE3 has copy/paste for model objects |
| 20 | **Display Folders** | ✅ Editable via properties + folder-grouped tree | |
| 21 | **Object Visibility (IsHidden)** | ✅ Editable in properties panel | |
| 22 | **Format Strings** | ✅ Editable in properties panel | |
| 23 | **Descriptions** | ✅ Editable in properties panel | + auto-generate from DAX via BPA fixer |
| 24 | **Search / Filter** | ✅ Real-time keystroke filtering on both Explorer trees | TE3 has Find & Replace — see "Missing" |
| 25 | **Supported File Formats** | ✅ .pbix, .pbip | TE3 also supports .bim, .vpax, database.json, TMDL folder |

---

## TE3 Features NOT in PBI Fixer (What You're Missing)

### 🔴 Critical / High-Value Gaps

| # | TE3 Feature | Description | Difficulty to Add |
|---|-------------|-------------|-------------------|
| 1 | **DAX Debugger** | Step-by-step DAX debugging: locals, watch, evaluation context, call tree. Debug from Pivot Grid or DAX Query. Step in/out/over with F10/F11. | 🔴 Very Hard — requires deep DAX query generation engine |
| 2 | **DAX IntelliSense / Autocomplete** | Context-sensitive suggestions, parameter info, syntax highlighting, calltips as you type | 🔴 Very Hard — ipywidgets textarea has no code editor capabilities |

| 3 | **DAX Query Editor** | Write and execute ad-hoc DAX queries, view results in grid, export to CSV/Excel | 🟡 Medium — could use `fabric.evaluate_dax()` + textarea + DataFrame output |
| 4 | **C# Scripting** | Custom C# scripts for unlimited bulk operations, access to full TOM API | 🔴 Very Hard — different runtime, no .NET scripting in Python |
| 5 | **Custom BPA Rules** | User-defined JSON rule files, community rule sets (e.g., SQLBI rules) | 🟡 Medium — could parse JSON rule files and evaluate expressions |
| 6 | **Model Deployment Wizard** | Deploy to dev/test/prod with object-level selection (skip partitions, roles, etc.) | 🟡 Medium — REST API supports this, needs UI |
| 7 | **Workspace Mode** | Simultaneous save to disk + sync to Analysis Services. Real-time collaboration. | 🔴 Very Hard — architectural difference (desktop IDE vs notebook) |

### 🟡 Medium-Value Gaps

| # | TE3 Feature | Description | Difficulty to Add |
|---|-------------|-------------|-------------------|
| 8 | **DAX Scripts** | Batch view/edit DAX for multiple measures/columns/calc items in a single document | 🟡 Medium — multi-object DAX textarea with apply logic |
| 9 | **Pivot Grid** | Interactive pivot table: drag measures, columns to rows/cols/filters. Slice-and-dice data. | 🟡 Medium — could build with ipywidgets + evaluate_dax |
| 10 | **DAX Optimizer Integration** | Connect to DAX Optimizer for performance recommendations | 🟢 Easy — API integration if license available |
| 11 | **Diagram View as Editor** | Visual relationship creation/modification by dragging columns between tables | 🔴 Very Hard — SVG interaction limits in ipywidgets |
| 12 | **Import Tables** | Create new tables from data sources (SQL, OData, etc.), M expression editing | 🟡 Medium — M expressions are outside DAX scope |
| 13 | **M Expression / Partition Editing** | Edit Power Query M, manage partitions, change data source | 🟡 Medium — TOM exposes partitions, but M editing needs a code editor |
| 14 | **Find & Replace Across Model** | Search and replace across all DAX expressions, names, descriptions | 🟢 Easy — iterate all TOM objects, string match/replace |
| 15 | **Undo / Redo** | Ctrl+Z/Ctrl+Y for all property and expression changes | 🟡 Medium — needs change history stack |
| 16 | **TMDL Support / Save to Folder** | Serialize model metadata to human-readable TMDL folder structure | 🟡 Medium — SLL may have TMDL support |
| 17 | **Code Actions** | Automated DAX refactoring suggestions (extract variable, simplify expressions) | 🔴 Very Hard — requires DAX AST parsing |
| 18 | **RLS / OLS Editor** | View and edit Row-Level Security roles, Object-Level Security | 🟡 Medium — TOM exposes roles, needs UI |

### 🟢 Lower-Value Gaps

| # | TE3 Feature | Description | Difficulty to Add |
|---|-------------|-------------|-------------------|
| 19 | **DAX Package Manager** | Install/manage reusable DAX packages (measures, calc groups) from a registry | 🟡 Medium — community feature, would need package registry |
| 20 | **C# Macros** | Record and replay C# scripts for repetitive tasks | 🔴 Very Hard — C# runtime dependent |
| 21 | **Peek Definition / Go To Definition** | Alt+F12 to peek at referenced measure definition inline | 🟡 Medium — could show referenced measure DAX in a popup |
| 22 | **DAX Refactoring (Ctrl+R)** | Rename variables/extension columns across all references | 🟡 Medium — needs DAX expression parsing |
| 23 | **Table Groups** | Organize tables into logical groups in the tree (beyond display folders) | 🟢 Easy — UI grouping in tree |
| 24 | **Semantic Bridge (Databricks)** | Cross-platform model translation for Databricks | 🔴 Very Hard — specialized connector |
| 25 | **Metric View Validation** | Validate metric views in Semantic Bridge | 🔴 Very Hard — specialized |
| 26 | **Command Line Interface** | CLI for CI/CD automation (deploy, BPA scan, format) | 🟡 Medium — Python CLI wrapper around existing functions |
| 27 | **Copy/Paste Objects Across Models** | Drag measures/tables between two open model instances | 🟡 Medium — would need multi-model connection |
| 28 | **Multi-Monitor / Dockable Windows** | Desktop IDE with dockable panels, multiple monitors | 🔴 Impossible — ipywidgets constraint |
| 29 | **Dark Mode / Configurable Themes** | IDE-level dark/light theme switching | 🟡 Medium — CSS-based theming in ipywidgets |
| 30 | **Data Refresh Management** | Trigger and monitor dataset refreshes from within the tool | 🟢 Easy — REST API `POST /refreshes` |
| 31 | **Configurable Keyboard Shortcuts** | User-defined key bindings for all operations | 🔴 Very Hard — ipywidgets has limited keyboard event support |
| 32 | **Export DAX Query to CSV/Excel** | Save query results to CSV or Excel files | 🟢 Easy — DataFrame.to_csv() / to_excel() |

---

## Summary: What's Already Covered vs. What's Missing

| Category | TE3 Features | In PBI Fixer | Missing |
|----------|-------------|-------------|---------|
| DAX Editing | 6 features | 2 (editor + formatting) | 4 (debugger, IntelliSense, queries, scripts) |
| Scripting & Automation | 4 features | 0 | 4 (C# scripts, macros, library, helpers) |
| Model Analysis | 2 features | 2 (BPA + Vertipaq) | 0 (+ DAX Optimizer if desired) |
| Data Exploration | 3 features | 1 (table preview) | 2 (pivot grid, import tables) |
| Advanced Modelling | 2 features | 2 (translations + perspectives) | 0 |
| Model Organization | 2 features | 1 (tree) | 1 (table groups) |
| Deployment & Files | 5 features | 2 (save + download) | 3 (deployment wizard, workspace mode, TMDL) |
| CLI | 1 feature | 0 | 1 (CLI) |
| Semantic Bridge | 2 features | 0 | 2 (Databricks specific) |
| **Total** | **27 features** | **10** | **17** |

---

## Recommended Priorities to Close the Gap

### Quick Wins (could implement soon)
1. **Find & Replace across model** — iterate TOM objects, match/replace strings
2. **Data Refresh trigger** — REST API `POST /refreshes` with status polling
3. **Export scan results to CSV/Excel** — already have DataFrames
4. **Table Groups** — UI-only grouping in tree

### High-Impact Additions
5. **DAX Query Editor** — textarea + `evaluate_dax()` + DataFrame grid
6. **Custom BPA rules** — parse JSON rule files (compatible with TE3 format)
7. **DAX Scripts** — multi-object DAX editing in single textarea
8. **Peek Definition** — show referenced measure DAX in popup on click
9. **RLS Editor** — view/edit roles via TOM

### Aspirational (hard but differentiating)
10. **Pivot Grid** — interactive drag-and-drop data exploration
11. **Deployment Wizard** — REST API deploy with object selection
12. **Undo/Redo** — change history stack for all edits

### Likely Out of Scope (architectural constraints)
- DAX Debugger (requires deep DAX query generation)
- DAX IntelliSense (ipywidgets has no code editor)
- C# Scripting (different runtime)
- Workspace Mode (desktop IDE concept)
- Multi-monitor / dockable windows
- Configurable keyboard shortcuts
