# Tabular Editor 2 vs PBI Fixer — Feature Comparison

## Summary

Tabular Editor 2 (TE2) is a **full semantic model authoring tool** — a desktop IDE for TOM with scripting, deployment, and direct SSAS/Azure AS support.

PBI Fixer is a **Power BI development environment for Fabric** — a notebook-native UI for browsing, fixing, analyzing, and deploying both reports *and* semantic models. It uniquely combines report-side intelligence with model-side tooling.

They are **complementary more than competing**. TE2 dominates on deep model authoring; PBI Fixer dominates on report analysis, automated fixes, and cloud-native workflows.

---

## Where TE2 Still Wins

| Capability | TE2 | PBI Fixer |
|------------|-----|-----------|
| **Full TOM property access** | Every single TOM property exposed and editable | Curated subset of properties |
| **C# scripting** | Custom C# scripts for bulk operations, unlimited flexibility | No scripting engine (Script Runner tab disabled pending review) |
| **Custom BPA rules** | User-defined JSON rule files, community rule sets | Fixed 19 model + 4 report BPA rules, no custom rules |
| **Works without Fabric** | PBI Desktop (External Tools), SSAS, Azure AS, PBI Premium | Requires Fabric notebook environment |
| **Object creation from scratch** | Create tables, columns, measures, calc groups, hierarchies, roles, data sources — anything | Create measures, calculated columns, calculated tables, calc groups, perspectives |
| **Copy/paste across models** | Drag & drop measures, tables, calc groups between model instances | Clone entire reports/models, but no cross-model object copy |
| **Relationship editor** | Visual relationship creation, modification, cross-filtering config | View relationships + diagram, but no visual relationship editor |
| **M expression / partition editing** | Full Power Query M editing, partition management | No M expression editing |
| **Deployment wizard** | Deploy model to dev/test/prod with granular object selection | Clone to target workspace, but no incremental deployment |
| **Desktop speed** | Instant response, no kernel startup, offline capable | Notebook kernel spin-up, depends on Fabric compute |
| **Multi-model editing** | Open multiple models simultaneously, drag objects between them | Single workspace at a time, multiple items within it |
| **Git integration** | Save as folder (TMDL), native git workflows | No git integration (uses Fabric-native version control) |

---

## Where PBI Fixer Wins

| Capability | PBI Fixer | TE2 |
|------------|-----------|-----|
| **Report analysis & fixing** | Full report explorer: pages, visuals, properties, PBIR-aware fixes | Zero report capabilities |
| **15 chart fixers** | Pie→bar, column→bar, column→line, bar→column, IBCS variance, alignment, page size, visual filters, unused custom visuals, Show Items No Data, report-level measures, PBIR upgrade, all-charts unified fixer | N/A |
| **Automated chart type detection** | Detects date/non-date axes via semantic model, swaps column→line (date) or column→bar (non-date) automatically | N/A |
| **IBCS variance automation** | One-click: creates calendar, PY/ΔPY measures, applies error bars, IBCS colors, overlap layout, label backgrounds | N/A |
| **Report preview** | Embedded Power BI report via powerbiclient — live interactive preview | N/A |
| **Report prototyping** | SVG + Excalidraw export with page screenshots and navigation edge detection | N/A |
| **19 BPA auto-fixers** | 15 of these have no standard TE2 auto-fix (only 4 BPA rules have built-in FixExpression) | 4 standard auto-fixes + custom scripts |
| **Report BPA** | 4 report-level BPA rules with auto-fixers | N/A |
| **Fix All (cross-category scan)** | One-click scan across Report Fixers + Model Fixers + Model BPA + Report BPA with per-fixer progress | N/A |
| **DAX formatting** | ✅ Built-in via `tom.format_dax()` | ✅ Built-in via daxformatter.com |
| **Save back to workspace** | ✅ SM via XMLA, reports via PBIR `connect_report` | ✅ SM via XMLA |
| **No install required** | Runs in any Fabric notebook — `%pip install` and go | Desktop app requires installation |
| **Vertipaq / Memory analysis** | Integrated tab with model dropdown, DataFrame subtabs | Separate VertiPaq Analyzer tool |
| **Delta Analyzer** | Lakehouse table inspection: parquet files, row groups, column chunks | N/A |
| **Model diagram** | Auto-layout SVG relationship diagram with nearest-edge connections | N/A |
| **Translations** | Load, auto-translate (Azure AI Translator via SynapseML), preview diff, apply via XMLA | N/A |
| **Perspective editor** | Full create/edit/delete perspectives UI | ✅ (also available) |
| **PBIR format gate** | Auto-detects format, warns on PBIRLegacy, one-click conversion | N/A |
| **Clone & deploy** | Clone reports and/or semantic models within or across workspaces | N/A |
| **Download** | Export as .pbix or .pbip for local development | N/A |
| **Direct Lake cache warming** | Detect DL model → create cache warm-up perspective → generate notebook → schedule via Job Scheduler API | N/A |
| **Column display folders** | View and navigate columns grouped by display folder | ✅ (also available) |
| **Table data preview** | Inline `TOPN(...)` preview in properties panel | N/A |
| **Incremental refresh setup** | Auto-detect date columns, configure incremental refresh | N/A |

---

## Feature Parity

Both tools support these capabilities:

| Capability | Notes |
|------------|-------|
| Browse tables, columns, measures, hierarchies | Full object tree navigation |
| Edit DAX expressions | Inline editor with save |
| Edit measure properties (format string, display folder, description, hidden) | Properties panel |
| DAX formatting | Both use daxformatter.com API |
| Model BPA | Both run BPA scans with severity levels |
| Perspective editing | Create, modify, delete perspectives |
| Save changes via XMLA | Write-back to workspace |
| Vertipaq / memory analysis | Model size, column cardinality, encoding stats |

---

## When to Use Which

| Scenario | Recommended Tool |
|----------|-----------------|
| Deep model authoring (new tables, partitions, M queries) | **TE2** |
| Bulk operations via C# scripting | **TE2** |
| Working with SSAS / Azure AS (non-Fabric) | **TE2** |
| Deployment pipelines with object-level control | **TE2** |
| Report quality review & automated fixes | **PBI Fixer** |
| IBCS compliance (variance charts, chart type standardization) | **PBI Fixer** |
| Quick health scan across reports + models | **PBI Fixer** |
| Cloud-native workflow (no desktop tools, no install) | **PBI Fixer** |
| Vertipaq analysis + Delta Analyzer + Model Diagram | **PBI Fixer** |
| Translating models to multiple languages | **PBI Fixer** |
| Report prototyping (SVG / Excalidraw) | **PBI Fixer** |
| Direct Lake cache warming setup | **PBI Fixer** |

---

## The Bottom Line

**TE2** = Desktop IDE for semantic model power users who need full TOM access, C# scripting, and multi-environment deployment.

**PBI Fixer** = Cloud-native Power BI development environment that uniquely combines report intelligence with model tooling — the only tool that scans and auto-fixes both reports and semantic models in one UI. 15 of its 19 BPA auto-fixers have no equivalent in TE2's standard rules, and its entire report-side capability (15 chart fixers, report BPA, PBIR management, prototyping) is a category that TE2 simply doesn't address.
