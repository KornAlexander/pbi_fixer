# Interactive PBI Report Fixer UI (ipywidgets)
# Orchestrates report visual fixers and semantic model fixers via a single notebook widget.

__version__ = "1.2.77"

import ipywidgets as widgets
import io
import time
from contextlib import redirect_stdout
from typing import Optional
from uuid import UUID

# ---------------------------------------------------------------------------
# Lazy imports — each fixer is optional so the UI degrades gracefully
# if individual fixer PRs haven't been merged yet.
# ---------------------------------------------------------------------------
try:
    from sempy_labs.report._Fix_PieChart import fix_piecharts
except ImportError:
    fix_piecharts = None

try:
    from sempy_labs.report._Fix_BarChart import fix_barcharts
except ImportError:
    fix_barcharts = None

try:
    from sempy_labs.report._Fix_ColumnChart import fix_columncharts
except ImportError:
    fix_columncharts = None

try:
    from sempy_labs.report._Fix_PageSize import fix_page_size
except ImportError:
    fix_page_size = None

try:
    from sempy_labs.report._Fix_HideVisualFilters import fix_hide_visual_filters
except ImportError:
    fix_hide_visual_filters = None

try:
    from sempy_labs.report._Fix_UpgradeToPbir import fix_upgrade_to_pbir
except ImportError:
    fix_upgrade_to_pbir = None

try:
    from sempy_labs.semantic_model._Add_CalculatedTable_Calendar import add_calculated_calendar
except ImportError:
    add_calculated_calendar = None

try:
    from sempy_labs.semantic_model._Fix_DiscourageImplicitMeasures import fix_discourage_implicit_measures
except ImportError:
    fix_discourage_implicit_measures = None

try:
    from sempy_labs.semantic_model._Add_Table_LastRefresh import add_last_refresh_table
except ImportError:
    add_last_refresh_table = None

try:
    from sempy_labs.semantic_model._Add_CalcGroup_Units import add_calc_group_units
except ImportError:
    add_calc_group_units = None

try:
    from sempy_labs.semantic_model._Add_CalcGroup_TimeIntelligence import add_calc_group_time_intelligence
except ImportError:
    add_calc_group_time_intelligence = None

try:
    from sempy_labs.semantic_model._Add_CalculatedTable_MeasureTable import add_measure_table
except ImportError:
    add_measure_table = None

try:
    from sempy_labs.semantic_model._Add_MeasuresFromColumns import add_measures_from_columns
except Exception:
    # Inline fallback if separate file not deployed
    def add_measures_from_columns(dataset, workspace=None, target_table=None, scan_only=False, **kw):
        """Creates measures from columns based on SummarizeBy property."""
        from sempy_labs.tom import connect_semantic_model
        created = 0
        with connect_semantic_model(dataset=dataset, readonly=scan_only, workspace=workspace) as tom:
            for table in tom.model.Tables:
                dest_name = target_table or table.Name
                for col in table.Columns:
                    summarize_by = str(col.SummarizeBy) if hasattr(col, "SummarizeBy") else "None"
                    if summarize_by in ("None", "Default"):
                        continue
                    agg_fn = summarize_by.upper()
                    dax_expr = f"{agg_fn}('{table.Name}'[{col.Name}])"
                    # Check if measure already exists
                    dest_tbl = tom.model.Tables[dest_name]
                    if dest_tbl.Measures.Find(col.Name) is not None:
                        continue
                    if scan_only:
                        print(f"  Would create: [{col.Name}] = {dax_expr}")
                        created += 1
                        continue
                    tom.add_measure(
                        table_name=dest_name,
                        measure_name=col.Name,
                        expression=dax_expr,
                        format_string="0.0",
                        display_folder=table.Name,
                    )
                    col.IsHidden = True
                    created += 1
                    print(f"  Created [{col.Name}] = {dax_expr}")
            if not scan_only and created > 0:
                tom.model.SaveChanges()
        print(f"  {'Would create' if scan_only else 'Created'} {created} measure(s) from columns.")
        return created

try:
    from sempy_labs.semantic_model._Add_PYMeasures import add_py_measures
except Exception:
    # Inline fallback if separate file not deployed
    def add_py_measures(dataset, workspace=None, measures=None, calendar_table=None, date_column=None, target_table=None, scan_only=False, **kw):
        """Creates PY time intelligence measures (PY, Δ PY, Δ PY %, Max Green, Max Red)."""
        from sempy_labs.tom import connect_semantic_model
        created = 0
        with connect_semantic_model(dataset=dataset, readonly=scan_only, workspace=workspace) as tom:
            cal = None
            if calendar_table:
                cal = tom.model.Tables.Find(calendar_table)
            else:
                for t in tom.model.Tables:
                    if str(getattr(t, "DataCategory", "")) == "Time":
                        cal = t
                        break
            if cal is None:
                print("  No calendar table found.")
                return 0
            dt_col = date_column
            if not dt_col:
                for c in cal.Columns:
                    if getattr(c, "IsKey", False):
                        dt_col = c.Name
                        break
                if not dt_col:
                    for c in cal.Columns:
                        if "date" in c.Name.lower():
                            dt_col = c.Name
                            break
            if not dt_col:
                print(f"  No date column found in '{cal.Name}'.")
                return 0
            print(f"  Calendar: '{cal.Name}'[{dt_col}]")
            dest_tbl = tom.model.Tables.Find(target_table) if target_table else None
            src = []
            for table in tom.model.Tables:
                for m in table.Measures:
                    if measures is None or m.Name in measures:
                        src.append(m)
            if not src:
                print("  No measures found.")
                return 0
            for m in src:
                n = m.Name
                fmt = str(m.FormatString) if m.FormatString else ""
                folder = str(m.DisplayFolder) if m.DisplayFolder else ""
                py_folder = f"{folder}\\\\PY" if folder else "PY"
                dest = dest_tbl or m.Table
                variants = [
                    (f"{n} PY", f"CALCULATE([{n}], SAMEPERIODLASTYEAR('{cal.Name}'[{dt_col}]))"),
                    (f"{n} \\u0394 PY", f"[{n}] - [{n} PY]"),
                    (f"{n} \\u0394 PY %", f"DIVIDE([{n}] - [{n} PY], [{n}])"),
                    (f"{n} Max Green PY", f"IF([{n} \\u0394 PY] > 0, MAX([{n}], [{n} PY]))"),
                    (f"{n} Max Red AC", f"IF([{n} \\u0394 PY] < 0, MAX([{n}], [{n} PY]))"),
                ]
                for v_name, v_expr in variants:
                    if dest.Measures.Find(v_name) is not None:
                        continue
                    if scan_only:
                        print(f"  Would create: [{v_name}]")
                        created += 1
                        continue
                    tom.add_measure(
                        table_name=dest.Name,
                        measure_name=v_name,
                        expression=v_expr,
                        format_string=fmt,
                        display_folder=py_folder,
                    )
                    created += 1
                if not scan_only:
                    print(f"  Created PY variants for [{n}]")
            if not scan_only and created > 0:
                tom.model.SaveChanges()
        print(f"  {'Would create' if scan_only else 'Created'} {created} PY measure(s).")
        return created

try:
    from sempy_labs._sm_explorer import sm_explorer_tab
except ImportError:
    sm_explorer_tab = None

try:
    from sempy_labs._report_explorer import report_explorer_tab
except ImportError:
    report_explorer_tab = None

try:
    from sempy_labs._perspective_editor import perspective_editor_tab
except ImportError:
    perspective_editor_tab = None


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Vertipaq Analyzer tab (inline — no external file dependency)
# ---------------------------------------------------------------------------
def _vertipaq_tab(workspace_input=None, report_input=None):
    """Build the Vertipaq Analyzer tab with full DataFrame subtabs."""
    from sempy_labs._ui_components import (
        FONT_FAMILY, BORDER_COLOR, GRAY_COLOR, ICON_ACCENT, SECTION_BG,
        ICONS, EXPANDED, COLLAPSED, build_tree_items, status_html, set_status, panel_box,
    )

    _vp_data = {}  # {model_name: dict_of_dataframes}
    _key_map = {}
    _expanded = set()
    _current_key = [None]
    _current_model = [None]  # track which model is selected for subtabs

    load_btn = widgets.Button(description="Load Memory", button_style="primary", layout=widgets.Layout(width="120px"))
    expand_btn = widgets.Button(description="Expand All", layout=widgets.Layout(width="100px"))
    collapse_btn = widgets.Button(description="Collapse All", layout=widgets.Layout(width="100px"))
    conn_status = status_html()

    nav_row = widgets.HBox(
        [load_btn, expand_btn, collapse_btn, conn_status],
        layout=widgets.Layout(align_items="center", gap="8px", margin="0 0 8px 0"),
    )

    tree = widgets.SelectMultiple(options=[], rows=18, layout=widgets.Layout(width="350px", height="450px", font_family="monospace"))

    def _fmt_bytes(n):
        try:
            if n is None or (isinstance(n, float) and n != n):
                return "\u2014"
            n = int(n)
        except (TypeError, ValueError):
            return "\u2014"
        if n < 1024:
            return f"{n} B"
        if n < 1024 * 1024:
            return f"{n / 1024:.1f} KB"
        if n < 1024 * 1024 * 1024:
            return f"{n / (1024 * 1024):.1f} MB"
        return f"{n / (1024 * 1024 * 1024):.2f} GB"

    def _fmt_int(n):
        try:
            if n is None or (isinstance(n, float) and n != n):
                return "\u2014"
            return f"{int(n):,}"
        except (TypeError, ValueError):
            return "\u2014"

    def _fmt_val(val, col_name):
        """Format a cell value based on column name."""
        if val is None or (isinstance(val, float) and val != val):
            return "\u2014"
        if "Size" in col_name:
            return _fmt_bytes(val)
        if "%" in col_name:
            try:
                return f"{float(val):.1f}%"
            except (TypeError, ValueError):
                return "\u2014"
        if isinstance(val, (int, float)):
            if isinstance(val, float) and val == int(val):
                return _fmt_int(int(val))
            if isinstance(val, float):
                return f"{val:,.1f}"
            return _fmt_int(val)
        return str(val)

    def _build_tree():
        nonlocal _key_map
        items = []
        for m_name in sorted(_vp_data):
            dfs = _vp_data[m_name]
            tables_df = dfs.get("Tables")
            is_model_exp = m_name in _expanded
            marker = EXPANDED if is_model_exp else COLLAPSED
            model_df = dfs.get("Model")
            total_size = ""
            if model_df is not None and "Total Size" in model_df.columns and len(model_df) > 0:
                total_size = f" ({_fmt_bytes(model_df.iloc[0].get('Total Size', 0))})"
            t_count = len(tables_df) if tables_df is not None else 0
            items.append((0, "calc_group", f"{marker} {m_name}{total_size}  [{t_count} tables]", f"model:{m_name}"))
            if not is_model_exp or tables_df is None:
                continue
            for _, row in tables_df.sort_values("Total Size", ascending=False).iterrows():
                t_name = row.get("Table Name", "")
                t_size = _fmt_bytes(row.get("Total Size", 0))
                t_rows = _fmt_int(row.get("Row Count", 0))
                t_pct = f"{row.get('% DB', 0):.1f}%" if row.get("% DB") else ""
                full_key = f"{m_name}\x1f{t_name}"
                is_t_exp = full_key in _expanded
                t_marker = EXPANDED if is_t_exp else COLLAPSED
                items.append((1, "table", f"{t_marker} {t_name}  [{t_size}, {t_rows} rows, {t_pct}]", f"table:{full_key}"))
                if not is_t_exp:
                    continue
                cols_df = dfs.get("Columns")
                if cols_df is not None:
                    t_cols = cols_df[cols_df["Table Name"] == t_name].sort_values("Total Size", ascending=False)
                    for _, crow in t_cols.iterrows():
                        c_name = crow.get("Column Name", "")
                        c_size = _fmt_bytes(crow.get("Total Size", 0))
                        c_card = _fmt_int(crow.get("Cardinality", 0))
                        c_enc = crow.get("Encoding", "")
                        items.append((2, "column", f"{c_name}  [{c_size}, card {c_card}, {c_enc}]", f"col:{full_key}:{c_name}"))
        options, _key_map = build_tree_items(items)
        tree.unobserve(on_select, names="value")
        tree.options = options
        tree.value = ()
        tree.observe(on_select, names="value")

    # -- DataFrame subtabs --
    _DF_TABS = ["Model Summary", "Tables", "Partitions", "Columns", "Relationships", "Hierarchies"]
    _DF_KEY_MAP = {
        "Model Summary": "Model",
        "Tables": "Tables",
        "Partitions": "Partitions",
        "Columns": "Columns",
        "Relationships": "Relationships",
        "Hierarchies": "Hierarchies",
    }

    subtab_selector = widgets.ToggleButtons(
        options=_DF_TABS,
        value="Model Summary",
        layout=widgets.Layout(width="100%"),
        style={"button_width": "auto", "font_weight": "bold"},
    )
    df_html = widgets.HTML(
        value=f'<div style="padding:12px; color:{GRAY_COLOR}; font-size:13px; font-family:{FONT_FAMILY}; font-style:italic;">Click Load Memory to analyze model sizes.</div>',
    )
    df_container = widgets.VBox(
        [df_html],
        layout=widgets.Layout(
            max_height="420px", overflow_y="auto", overflow_x="auto",
            border=f"1px solid {BORDER_COLOR}", border_radius="8px",
            padding="8px", background_color=SECTION_BG,
        ),
    )

    # Detail panel for tree clicks
    detail_label = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Details</div>'
    )
    detail_html = widgets.HTML(
        value=f'<div style="padding:8px; color:{GRAY_COLOR}; font-size:13px; font-family:{FONT_FAMILY}; font-style:italic;">Select a tree item for details</div>',
    )
    detail_container = widgets.VBox(
        [detail_html],
        layout=widgets.Layout(
            max_height="300px", overflow_y="auto",
            border=f"1px solid {BORDER_COLOR}", border_radius="8px",
            padding="8px", background_color=SECTION_BG,
        ),
    )

    def _df_to_html(df, highlight_col=None, highlight_val=None, sort_by=None):
        """Convert a DataFrame to a styled HTML table."""
        if df is None or len(df) == 0:
            return f'<div style="color:{GRAY_COLOR}; font-size:13px;">No data available.</div>'
        if sort_by and sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=False)
        html = '<div style="overflow-x:auto;"><table style="border-collapse:collapse; min-width:100%; font-size:11px; font-family:monospace;">'
        html += '<tr style="background:#f5f5f5; position:sticky; top:0; z-index:1;">'
        for col in df.columns:
            align = "right" if any(k in col for k in ("Size", "Count", "%", "Cardinality", "Rows", "Temperature", "Segment", "Max", "Missing")) else "left"
            html += f'<th style="text-align:{align}; padding:4px 8px; border-bottom:2px solid {BORDER_COLOR}; white-space:nowrap;">{col}</th>'
        html += '</tr>'
        for _, row in df.iterrows():
            is_hl = highlight_col and highlight_val and str(row.get(highlight_col, "")) == str(highlight_val)
            bg = "background:#fff3cd;" if is_hl else ""
            html += f'<tr style="{bg}">'
            for col in df.columns:
                val = row.get(col, "")
                align = "right" if any(k in col for k in ("Size", "Count", "%", "Cardinality", "Rows", "Temperature", "Segment", "Max", "Missing")) else "left"
                formatted = _fmt_val(val, col)
                extra = ""
                if "% DB" in col or "% Table" in col:
                    try:
                        pct_val = float(val) if val == val else 0
                        bar_color = "#ff3b30" if pct_val > 30 else "#ff9500" if pct_val > 10 else "#34c759"
                        extra = f'<div style="height:3px; width:{min(pct_val * 2, 100):.0f}%; background:{bar_color}; border-radius:1px; margin-top:1px;"></div>'
                    except (TypeError, ValueError):
                        pass
                html += f'<td style="text-align:{align}; padding:3px 8px; border-bottom:1px solid #f0f0f0; white-space:nowrap;">{formatted}{extra}</td>'
            html += '</tr>'
        html += '</table></div>'
        return html

    def _render_subtab(tab_name=None, highlight_col=None, highlight_val=None):
        """Render the selected DataFrame subtab."""
        tab_name = tab_name or subtab_selector.value
        m_name = _current_model[0]
        if not m_name and _vp_data:
            m_name = next(iter(_vp_data))
        if not m_name or m_name not in _vp_data:
            df_html.value = f'<div style="color:{GRAY_COLOR};">No data loaded.</div>'
            return
        dfs = _vp_data[m_name]
        df_key = _DF_KEY_MAP.get(tab_name, tab_name)
        df = dfs.get(df_key)
        sort_by = "Total Size" if df is not None and "Total Size" in df.columns else None
        df_html.value = _df_to_html(df, highlight_col=highlight_col, highlight_val=highlight_val, sort_by=sort_by)

    def on_subtab_change(change):
        _render_subtab(change.get("new"))

    subtab_selector.observe(on_subtab_change, names="value")

    def _prop_row(label, value):
        return f'<tr><td style="padding:2px 10px 2px 0; font-weight:600; color:#555; white-space:nowrap;">{label}</td><td style="padding:2px 0;">{value}</td></tr>'

    def _show_detail(key):
        """Show detail for a tree item + switch subtab + highlight."""
        parts = key.split(":", 2)
        node_type = parts[0]
        if node_type == "model":
            m_name = parts[1]
            _current_model[0] = m_name
            dfs = _vp_data.get(m_name, {})
            model_df = dfs.get("Model")
            if model_df is not None and len(model_df) > 0:
                r = model_df.iloc[0]
                rows = ""
                for col in model_df.columns:
                    rows += _prop_row(col, _fmt_val(r.get(col, ""), col))
                detail_html.value = f'<table style="font-size:13px; font-family:{FONT_FAMILY}; border-collapse:collapse; width:100%;">{rows}</table>'
            subtab_selector.value = "Model Summary"
            _render_subtab("Model Summary")
        elif node_type == "table":
            raw = parts[1]
            m_name, t_name = raw.split("\x1f", 1) if "\x1f" in raw else (raw, "")
            _current_model[0] = m_name
            dfs = _vp_data.get(m_name, {})
            tables_df = dfs.get("Tables")
            if tables_df is not None:
                t_row = tables_df[tables_df["Table Name"] == t_name]
                if len(t_row) > 0:
                    r = t_row.iloc[0]
                    rows = ""
                    for col in tables_df.columns:
                        rows += _prop_row(col, _fmt_val(r.get(col, ""), col))
                    detail_html.value = f'<table style="font-size:13px; font-family:{FONT_FAMILY}; border-collapse:collapse; width:100%;">{rows}</table>'
            subtab_selector.value = "Tables"
            _render_subtab("Tables", highlight_col="Table Name", highlight_val=t_name)
        elif node_type == "col":
            raw_table = parts[1]
            c_name = parts[2] if len(parts) > 2 else ""
            m_name, t_name = raw_table.split("\x1f", 1) if "\x1f" in raw_table else (raw_table, "")
            _current_model[0] = m_name
            dfs = _vp_data.get(m_name, {})
            cols_df = dfs.get("Columns")
            if cols_df is not None:
                c_row = cols_df[(cols_df["Table Name"] == t_name) & (cols_df["Column Name"] == c_name)]
                if len(c_row) > 0:
                    r = c_row.iloc[0]
                    rows = ""
                    for col in cols_df.columns:
                        rows += _prop_row(col, _fmt_val(r.get(col, ""), col))
                    detail_html.value = f'<table style="font-size:13px; font-family:{FONT_FAMILY}; border-collapse:collapse; width:100%;">{rows}</table>'
            subtab_selector.value = "Columns"
            _render_subtab("Columns", highlight_col="Column Name", highlight_val=c_name)

    def on_select(change):
        selected = change.get("new", ())
        if not selected:
            return
        last = selected[-1]
        if last not in _key_map:
            return
        key = _key_map[last]
        _current_key[0] = key
        if len(selected) == 1:
            if key.startswith("model:"):
                m_name = key.split(":", 1)[1]
                if m_name in _expanded:
                    _expanded.discard(m_name)
                else:
                    _expanded.add(m_name)
                _build_tree()
            if key.startswith("table:"):
                t_name = key.split(":", 1)[1]
                if t_name in _expanded:
                    _expanded.discard(t_name)
                else:
                    _expanded.add(t_name)
                _build_tree()
        _show_detail(key)

    def on_load(_):
        nonlocal _vp_data
        _expanded.clear()
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        ds_input = report_input.value.strip() if report_input else ""
        items = [x.strip() for x in ds_input.split(",") if x.strip()] if ds_input else []
        if not items:
            set_status(conn_status, "Enter a semantic model name.", "#ff3b30")
            return
        load_btn.disabled = True
        load_btn.description = "Loading\u2026"
        _vp_data = {}
        import io as _io
        from contextlib import redirect_stdout as _redirect
        for i, ds in enumerate(items):
            set_status(conn_status, f"Memory Analyzer {i+1}/{len(items)}: '{ds}'\u2026", GRAY_COLOR)
            try:
                buf = _io.StringIO()
                # Suppress ALL display paths: module-level, core, and vertipaq's own imported display
                import IPython.display as _ipd
                _orig_display = _ipd.display
                _ipd.display = lambda *a, **kw: None
                try:
                    import IPython.core.display_functions as _idf
                    _orig_display2 = _idf.display
                    _idf.display = lambda *a, **kw: None
                except Exception:
                    _idf = None
                    _orig_display2 = None
                # Patch the display imported directly in _vertipaq module
                import sempy_labs._vertipaq as _vp_mod
                _orig_vp_display = getattr(_vp_mod, 'display', None)
                _vp_mod.display = lambda *a, **kw: None
                try:
                    with _redirect(buf):
                        from sempy_labs import vertipaq_analyzer
                        result = vertipaq_analyzer(dataset=ds, workspace=ws)
                finally:
                    _ipd.display = _orig_display
                    if _idf is not None and _orig_display2 is not None:
                        _idf.display = _orig_display2
                    if _orig_vp_display is not None:
                        _vp_mod.display = _orig_vp_display
                _vp_data[ds] = result
                _expanded.add(ds)
                _current_model[0] = ds
            except Exception as e:
                set_status(conn_status, f"Error loading '{ds}': {e}", "#ff3b30")
        _build_tree()
        _render_subtab()
        total_models = len(_vp_data)
        set_status(conn_status, f"\u2713 Loaded memory stats for {total_models} model(s).", "#34c759")
        load_btn.disabled = False
        load_btn.description = "Load Memory"

    def on_expand_all(_):
        for m_name, dfs in _vp_data.items():
            _expanded.add(m_name)
            tables_df = dfs.get("Tables")
            if tables_df is not None:
                for t_name in tables_df["Table Name"]:
                    _expanded.add(f"{m_name}\x1f{t_name}")
        _build_tree()

    def on_collapse_all(_):
        _expanded.clear()
        _build_tree()

    load_btn.on_click(on_load)
    tree.observe(on_select, names="value")
    expand_btn.on_click(on_expand_all)
    collapse_btn.on_click(on_collapse_all)

    tree_header = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Tables &amp; Columns by Size</div>'
    )
    right_panel = widgets.VBox([subtab_selector, df_container, detail_label, detail_container], layout=widgets.Layout(flex="1", gap="4px"))
    panels = widgets.HBox([tree, right_panel], layout=widgets.Layout(width="100%", gap="8px"))

    widget = widgets.VBox([nav_row, tree_header, panels], layout=widgets.Layout(padding="12px", gap="4px"))
    return widget


# ---------------------------------------------------------------------------
# Best Practice Analyzer tab (inline)
# ---------------------------------------------------------------------------
def _bpa_tab(workspace_input=None, report_input=None):
    """Build the BPA tab with fix buttons per violation."""
    from sempy_labs._ui_components import (
        FONT_FAMILY, BORDER_COLOR, GRAY_COLOR, ICON_ACCENT, SECTION_BG,
        status_html, set_status,
    )

    # BPA fix functions — each takes (dataset, workspace, table_name, object_name)
    def _fix_floating_point(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            col = tom.model.Tables[table].Columns[obj]
            import Microsoft.AnalysisServices.Tabular as TOM
            col.DataType = TOM.DataType.Decimal
            tom.model.SaveChanges()
        return f"Changed '{table}'[{obj}] from Double to Decimal"

    def _fix_isavailableinmdx(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            col = tom.model.Tables[table].Columns[obj]
            col.IsAvailableInMDX = False
            tom.model.SaveChanges()
        return f"Set IsAvailableInMDX=False on '{table}'[{obj}]"

    def _fix_description_measure(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            m = tom.model.Tables[table].Measures[obj]
            m.Description = str(m.Expression) if m.Expression else ""
            tom.model.SaveChanges()
        return f"Set description of [{obj}] to its DAX expression"

    def _fix_date_format(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            col = tom.model.Tables[table].Columns[obj]
            col.FormatString = "mm/dd/yyyy"
            tom.model.SaveChanges()
        return f"Set format of '{table}'[{obj}] to mm/dd/yyyy"

    def _fix_month_format(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            col = tom.model.Tables[table].Columns[obj]
            col.FormatString = "MMMM yyyy"
            tom.model.SaveChanges()
        return f"Set format of '{table}'[{obj}] to MMMM yyyy"

    def _fix_integer_format(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            m = tom.model.Tables[table].Measures[obj]
            m.FormatString = "#,0"
            tom.model.SaveChanges()
        return f"Set format of [{obj}] to #,0"

    def _fix_hide_foreign_key(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            col = tom.model.Tables[table].Columns[obj]
            col.IsHidden = True
            tom.model.SaveChanges()
        return f"Hidden '{table}'[{obj}]"

    # Map BPA rule IDs to fix functions
    _fix_map = {
        "AVOID_FLOATING_POINT_DATA_TYPES": _fix_floating_point,
        "ISAVAILABLEINMDX_FALSE_NONATTRIBUTE_COLUMNS": _fix_isavailableinmdx,
        "DATECOLUMN_FORMATSTRING": _fix_date_format,
        "MONTHCOLUMN_FORMATSTRING": _fix_month_format,
        "INTEGER_FORMATTING": _fix_integer_format,
        "HIDE_FOREIGN_KEYS": _fix_hide_foreign_key,
    }
    # Special: description fix only for measures
    _desc_fix_rule = "OBJECTS_WITH_NO_DESCRIPTION"

    load_btn = widgets.Button(description="Run BPA", button_style="primary", layout=widgets.Layout(width="120px"))
    fix_all_btn = widgets.Button(description="\u26a1 Fix All", button_style="danger", layout=widgets.Layout(width="100px"))
    conn_status = status_html()
    nav_row = widgets.HBox(
        [load_btn, fix_all_btn, conn_status],
        layout=widgets.Layout(align_items="center", gap="8px", margin="0 0 8px 0"),
    )

    header_label = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Best Practice Analyzer</div>'
    )
    results_box = widgets.VBox(layout=widgets.Layout(
        max_height="400px", overflow_y="auto",
        border=f"1px solid {BORDER_COLOR}", border_radius="8px",
        padding="8px", background_color=SECTION_BG,
    ))
    results_box.children = [widgets.HTML(
        value=f'<div style="padding:12px; color:{GRAY_COLOR}; font-size:13px; font-family:{FONT_FAMILY}; font-style:italic;">Click Run BPA to scan.</div>'
    )]

    _all_findings = []  # [(ds, rule_id, rule_name, category, obj_name, obj_type, severity, table_name), ...]

    def on_load(_):
        nonlocal _all_findings
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        ds_input = report_input.value.strip() if report_input else ""
        items = [x.strip() for x in ds_input.split(",") if x.strip()] if ds_input else []
        if not items:
            set_status(conn_status, "Enter a semantic model name.", "#ff3b30")
            return
        load_btn.disabled = True
        load_btn.description = "Scanning\u2026"
        import io as _io
        from contextlib import redirect_stdout as _redirect
        import IPython.display as _ipd
        _orig_display = _ipd.display

        _all_findings = []

        for i, ds in enumerate(items):
            set_status(conn_status, f"BPA {i+1}/{len(items)}: '{ds}'\u2026", GRAY_COLOR)
            try:
                buf = _io.StringIO()
                _ipd.display = lambda *a, **kw: None
                try:
                    with _redirect(buf):
                        from sempy_labs import run_model_bpa
                        df = run_model_bpa(dataset=ds, workspace=ws, return_dataframe=True)
                finally:
                    _ipd.display = _orig_display

                if df is not None and len(df) > 0:
                    for _, row in df.iterrows():
                        rule_id = str(row.get("Rule ID", row.get("ID", "")))
                        rule_name = str(row.get("Rule Name", ""))
                        category = str(row.get("Category", ""))
                        obj_name = str(row.get("Object Name", ""))
                        obj_type = str(row.get("Object Type", ""))
                        severity = str(row.get("Severity", ""))
                        table_name = str(row.get("Table Name", ""))
                        _all_findings.append((ds, rule_id, rule_name, category, obj_name, obj_type, severity, table_name))
            except Exception as e:
                _all_findings.append((ds, "ERROR", str(e), "Error", "", "", "3", ""))

        _build_results(ws)
        n = len([f for f in _all_findings if f[1] != "ERROR"])
        set_status(conn_status, f"\u2713 BPA: {n} finding(s) across {len(items)} model(s).", "#34c759" if n == 0 else "#ff9500")
        load_btn.disabled = False
        load_btn.description = "Run BPA"

    def _build_results(ws):
        if not _all_findings:
            results_box.children = [widgets.HTML(
                value=f'<div style="color:#34c759; font-size:14px; font-weight:600;">\u2713 No violations found.</div>'
            )]
            return

        # Build a single HTML table for all findings
        html = '<div style="overflow-x:auto;"><table style="border-collapse:collapse; min-width:100%; font-size:11px; font-family:monospace;">'
        html += '<tr style="background:#f5f5f5; position:sticky; top:0; z-index:1;">'
        for hdr in ["#", "Model", "Rule", "Type", "Object", "Sev", "Fixable"]:
            html += f'<th style="text-align:left; padding:4px 8px; border-bottom:2px solid {BORDER_COLOR}; white-space:nowrap;">{hdr}</th>'
        html += '</tr>'

        fixable_indices = []
        for idx, (ds, rule_id, rule_name, category, obj_name, obj_type, severity, table_name) in enumerate(_all_findings):
            if rule_id == "ERROR":
                html += f'<tr><td colspan="7" style="color:#ff3b30; padding:3px 8px;">\u274c {ds}: {rule_name}</td></tr>'
                continue
            sev_color = "#ff3b30" if severity in ("3",) else "#ff9500" if severity in ("2",) else "#888"
            has_fix = rule_id in _fix_map or (rule_id == _desc_fix_rule and obj_type == "Measure")
            if has_fix:
                fixable_indices.append(idx)
            fix_icon = f'<span style="color:#34c759;">\u2713</span>' if has_fix else '\u2014'
            html += f'<tr>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; color:#888;">{idx+1}</td>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; white-space:nowrap;" title="{ds}">{ds[:16]}</td>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; color:{ICON_ACCENT}; white-space:nowrap;" title="{rule_name}">{rule_name[:35]}</td>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; color:#888;">{obj_type[:10]}</td>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; white-space:nowrap;" title="{table_name}.{obj_name}">{obj_name[:35]}</td>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; color:{sev_color}; font-weight:600;">{severity}</td>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; text-align:center;">{fix_icon}</td>'
            html += '</tr>'
        html += '</table></div>'

        table_html = widgets.HTML(value=html)

        # Summary line
        n_fixable = len(fixable_indices)
        summary = widgets.HTML(
            value=f'<div style="font-size:12px; font-family:{FONT_FAMILY}; color:#555; margin:8px 0 4px 0;">'
            f'{len(_all_findings)} finding(s), <b>{n_fixable}</b> auto-fixable</div>'
        )

        results_box.children = [table_html, summary]

    def on_fix_all(_):
        """Fix all fixable violations."""
        if not _all_findings:
            return
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        fix_all_btn.disabled = True
        fix_all_btn.description = "Fixing\u2026"
        fixed = 0
        errors = 0
        for ds, rule_id, rule_name, category, obj_name, obj_type, severity, table_name in _all_findings:
            if rule_id == "ERROR":
                continue
            try:
                if rule_id in _fix_map:
                    _fix_map[rule_id](ds, ws, table_name, obj_name)
                    fixed += 1
                elif rule_id == _desc_fix_rule and obj_type == "Measure":
                    _fix_description_measure(ds, ws, table_name, obj_name)
                    fixed += 1
            except Exception:
                errors += 1
        set_status(conn_status, f"\u2713 Fixed {fixed}, {errors} error(s).", "#34c759" if errors == 0 else "#ff9500")
        fix_all_btn.disabled = False
        fix_all_btn.description = "\u26a1 Fix All"

    load_btn.on_click(on_load)
    fix_all_btn.on_click(on_fix_all)

    widget = widgets.VBox([nav_row, header_label, results_box], layout=widgets.Layout(padding="12px", gap="4px"))
    return widget

# ---------------------------------------------------------------------------
# Timeout constants
# ---------------------------------------------------------------------------
_TOTAL_TIMEOUT = 300  # 5 minutes hard wall-clock limit


def _check_report_format(report_name, workspace):
    """
    Check report format via Fabric REST API.
    Returns 'PBIR', 'PBIRLegacy', etc., or None on error.
    """
    try:
        from sempy_labs._helper_functions import (
            resolve_workspace_name_and_id,
            resolve_item_name_and_id,
            _base_api,
        )
        _, ws_id = resolve_workspace_name_and_id(workspace)
        _, rpt_id = resolve_item_name_and_id(
            item=report_name, type="Report", workspace=ws_id
        )
        url = f"/v1.0/myorg/groups/{ws_id}/reports"
        response = _base_api(request=url, client="fabric_sp")
        for rpt in response.json().get("value", []):
            if rpt.get("id") == str(rpt_id):
                return rpt.get("format")
    except Exception:
        pass
    return None


def pbi_fixer(
    workspace: Optional[str | UUID] = None,
    report: Optional[str | UUID] = None,
    page_name: Optional[str] = None,
    show_fixer_tab: bool = False,
):
    """
    Launches an interactive UI for scanning and fixing Power BI report visuals.

    Parameters
    ----------
    workspace : str | uuid.UUID, default=None
        The Fabric workspace name or ID.
        Defaults to None which resolves to the workspace of the attached lakehouse
        or if no lakehouse attached, resolves to the workspace of the notebook.
    report : str | uuid.UUID, default=None
        Name(s) or ID(s) of the report(s). Supports comma-separated values.
        Pre-populates the report input field.
    page_name : str, default=None
        The display name of the page. Pre-populates the page input field.
    show_fixer_tab : bool, default=False
        If True, shows the Fixer tab. By default hidden since all fixers
        are accessible via action dropdowns in the Report and SM tabs.
    """

    # -----------------------------
    # COLOR THEME (matches perspective_editor)
    # -----------------------------
    text_color = "inherit"
    border_color = "#e0e0e0"
    icon_accent = "#FF9500"
    gray_color = "#999"
    section_bg = "#fafafa"

    # -----------------------------
    # STATUS + PROGRESS
    # -----------------------------
    status = widgets.HTML(value="")
    progress = widgets.HTML(
        value="",
        layout=widgets.Layout(
            display="none",
            border=f"1px solid {border_color}",
            border_radius="8px",
            margin="4px 0 0 0",
        ),
    )
    _progress_lines = []  # mutable list to accumulate lines

    def show_status(msg, color):
        status.value = (
            f'<div style="padding:8px 12px; border-radius:8px; '
            f"background:{color}1a; color:{color}; font-size:14px; "
            f'font-family:-apple-system,BlinkMacSystemFont,sans-serif;">{msg}</div>'
        )

    # -----------------------------
    # HEADER
    # -----------------------------
    title = widgets.HTML(
        value=f'<div style="font-size:22px; font-weight:700; color:{icon_accent}; '
        f'font-family:-apple-system,BlinkMacSystemFont,sans-serif;">'
        f'Power BI Fixer</div>'
    )
    subtitle = widgets.HTML(
        value=f'<div style="font-size:13px; color:{gray_color}; '
        f'font-family:-apple-system,BlinkMacSystemFont,sans-serif; margin-top:2px;">'
        f'Scan, fix, and explore your Power BI reports and semantic models</div>'
    )
    header = widgets.VBox(
        [title, subtitle],
        layout=widgets.Layout(margin="0 0 12px 0", padding="0 0 8px 0",
                              border_bottom=f"2px solid {icon_accent}"),
    )

    # -----------------------------
    # MODE SELECTOR (Fix | Scan | Scan + Fix)
    # Scan modes are placeholders for future implementation
    # -----------------------------
    mode_label = widgets.HTML(
        value=f'<span style="font-size:13px; font-weight:500; color:{text_color}; '
        f'font-family:-apple-system,BlinkMacSystemFont,sans-serif;">Mode</span>'
    )
    mode_toggle = widgets.ToggleButtons(
        options=["Fix", "Scan", "Scan + Fix"],
        value="Fix",
        layout=widgets.Layout(margin="0"),
    )
    mode_toggle.style.button_width = "100px"

    def on_mode_change(change):
        status.value = ""
        _on_sm_cb_change()

    mode_toggle.observe(on_mode_change, names="value")

    mode_row = widgets.HBox(
        [mode_label, mode_toggle],
        layout=widgets.Layout(align_items="center", gap="12px", margin="0 0 16px 0"),
    )

    # -----------------------------
    # SHARED INPUTS (top-level, used by all tabs)
    # -----------------------------
    def _input_label(text):
        return widgets.HTML(
            value=f'<span style="font-size:13px; font-weight:500; color:{text_color}; '
            f'font-family:-apple-system,BlinkMacSystemFont,sans-serif; '
            f'min-width:90px; display:inline-block;">{text}</span>'
        )

    workspace_input = widgets.Text(
        value=str(workspace) if workspace else "",
        placeholder="Leave empty for notebook workspace",
        layout=widgets.Layout(width="400px"),
    )
    report_input = widgets.Text(
        value=str(report) if report else "",
        placeholder="Comma-separated names or IDs (blank = all)",
        layout=widgets.Layout(width="400px"),
    )
    page_input = widgets.Text(
        value=page_name if page_name else "",
        placeholder="Leave empty for all pages",
        layout=widgets.Layout(width="300px"),
    )

    shared_inputs_box = widgets.VBox(
        [
            widgets.HBox(
                [_input_label("Workspace"), workspace_input],
                layout=widgets.Layout(align_items="center", gap="8px"),
            ),
            widgets.HBox(
                [_input_label("Report"), report_input],
                layout=widgets.Layout(align_items="center", gap="8px"),
            ),
        ],
        layout=widgets.Layout(
            gap="8px",
            padding="12px",
            margin="0 0 12px 0",
            border=f"1px solid {border_color}",
            border_radius="8px",
            background_color="#fafafa",
        ),
    )

    # -----------------------------
    # TAB SELECTOR (ToggleButtons — more reliable than widgets.Tab in Fabric)
    # -----------------------------
    _fixer_visible = show_fixer_tab
    _tab_options = []
    if sm_explorer_tab is not None:
        _tab_options.append("\U0001F4CA Semantic Model")
    if report_explorer_tab is not None:
        _tab_options.append("\U0001F4C4 Report")
    if _fixer_visible:
        _tab_options.append("\u26A1 Fixer")
    if perspective_editor_tab is not None:
        _tab_options.append("\U0001F441 Perspectives")
    _tab_options.append("\U0001F4BE Memory Analyzer")
    _tab_options.append("\U0001F4CB BPA")
    _tab_options.append("\u2139\ufe0f About")
    if not _tab_options:
        _tab_options = ["\u26A1 Fixer"]
        _fixer_visible = True

    tab_selector = widgets.ToggleButtons(
        options=_tab_options,
        value=_tab_options[0],
        layout=widgets.Layout(margin="0 0 12px 0"),
    )
    tab_selector.style.button_width = "155px"

    # -----------------------------
    # SECTION HEADING HELPER
    # -----------------------------
    def _section_heading(text):
        return widgets.HTML(
            value=f'<div style="font-size:13px; font-weight:600; color:{icon_accent}; '
            f'font-family:-apple-system,BlinkMacSystemFont,sans-serif; '
            f'text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;">'
            f'{text}</div>'
        )

    def _fixer_label(title, description):
        return widgets.HTML(
            value=f'<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;">'
            f'<span style="font-size:14px; font-weight:500; color:{text_color};">{title}</span>'
            f'<span style="font-size:12px; color:{gray_color}; margin-left:8px;">{description}</span>'
            f'</div>'
        )

    # -----------------------------
    # REPORT FIXERS — VISUALS
    # -----------------------------
    cb_pie = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_bar = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_col = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_page_size = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_hide_filters = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))

    pie_row = widgets.HBox(
        [cb_pie, _fixer_label("Fix Pie Charts", "replaces all pie charts → Clustered Bar Chart (default)")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )
    bar_row = widgets.HBox(
        [cb_bar, _fixer_label("Fix Bar Charts", "remove axis titles/values · add data labels · remove gridlines")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )
    col_row = widgets.HBox(
        [cb_col, _fixer_label("Fix Column Charts", "remove axis titles/values · add data labels · remove gridlines")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )
    page_size_row = widgets.HBox(
        [cb_page_size, _fixer_label("Fix Page Size", "changes default 720×1280 pages to 1080×1920 (Full HD)")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )
    hide_filters_row = widgets.HBox(
        [cb_hide_filters, _fixer_label("Hide Visual Filters", "sets isHiddenInViewMode on all visual-level filters")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )

    cb_upgrade = widgets.Checkbox(value=False, indent=False, layout=widgets.Layout(width="22px"))
    upgrade_row = widgets.HBox(
        [cb_upgrade, _fixer_label("Upgrade to PBIR", "converts PBIRLegacy \u2192 PBIR via REST round-trip (runs first)")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )

    # Only show rows for available fixers
    _report_fixer_rows = [_section_heading("Report — Visuals")]
    if fix_upgrade_to_pbir is not None:
        _report_fixer_rows.append(upgrade_row)
    if fix_piecharts is not None:
        _report_fixer_rows.append(pie_row)
    if fix_barcharts is not None:
        _report_fixer_rows.append(bar_row)
    if fix_columncharts is not None:
        _report_fixer_rows.append(col_row)
    if fix_page_size is not None:
        _report_fixer_rows.append(page_size_row)
    if fix_hide_visual_filters is not None:
        _report_fixer_rows.append(hide_filters_row)

    report_fixers_box = widgets.VBox(
        _report_fixer_rows,
        layout=widgets.Layout(
            gap="6px",
            padding="12px",
            margin="0 0 16px 0",
            border=f"1px solid {border_color}",
            border_radius="8px",
            background_color=section_bg,
        ),
    )

    # -----------------------------
    # SEMANTIC MODEL FIXERS
    # -----------------------------
    cb_calendar = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_discourage = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_last_refresh = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_units = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_time_intel = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_measure_tbl = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))

    # datasource_version_row removed — requires Large SM storage format enabled first
    calendar_row = widgets.HBox(
        [cb_calendar, _fixer_label("Add Calendar Table", "adds \"CalcCalendar\" calculated table if no table has been \"marked\" as a date table")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )
    discourage_row = widgets.HBox(
        [cb_discourage, _fixer_label("Discourage Implicit Measures", "sets DiscourageImplicitMeasures to True (recommended &amp; required for calc groups)")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )
    last_refresh_row = widgets.HBox(
        [cb_last_refresh, _fixer_label("Add Last Refresh Table", "adds a \"Last Refresh\" table with M partition &amp; measure showing refresh timestamp")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )
    units_row = widgets.HBox(
        [cb_units, _fixer_label("Add Units Calc Group", "Thousand &amp; Million items · skips % / ratio measures · ⚡ can impact report performance")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )
    time_intel_row = widgets.HBox(
        [cb_time_intel, _fixer_label("Add Time Intelligence Calc Group", "AC · Y-1/Y-2/Y-3 · YTD · abs/rel/achiev. variances · requires calendar table")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )
    measure_tbl_row = widgets.HBox(
        [cb_measure_tbl, _fixer_label("Add Measure Table", "adds an empty \"Measure\" calculated table to centralise measures")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )

    # XMLA warning + confirmation — shown only when ≥1 SM fixer is checked
    cb_sm_confirm = widgets.Checkbox(
        value=False, indent=False, layout=widgets.Layout(width="22px"),
    )
    sm_warning_text = widgets.HTML(
        value=f'<span style="font-size:12px; color:#856404; '
        f'font-family:-apple-system,BlinkMacSystemFont,sans-serif;">'
        f'⚠️ <b>XMLA write</b> — Semantic model fixers use the XMLA endpoint. '
        f'Once modified, the model can no longer be downloaded as a .pbix with embedded data. '
        f'This is irreversible. <b>Tick to confirm.</b></span>'
    )
    sm_warning_confirm = widgets.HBox(
        [cb_sm_confirm, sm_warning_text],
        layout=widgets.Layout(
            align_items="center", gap="8px",
            padding="6px 10px",
            border="1px solid #ffc107", border_radius="6px",
            display="none",
        ),
    )
    sm_warning_confirm.add_class("sm-xmla-warning")

    # Show/hide warning when any SM fixer checkbox changes
    _sm_checkboxes = [cb_calendar, cb_discourage, cb_last_refresh, cb_units, cb_time_intel, cb_measure_tbl]

    def _on_sm_cb_change(change=None):
        any_checked = any(cb.value for cb in _sm_checkboxes)
        writes = mode_toggle.value != "Scan"
        sm_warning_confirm.layout.display = "flex" if (any_checked and writes) else "none"
        if not any_checked or not writes:
            cb_sm_confirm.value = False

    for _cb in _sm_checkboxes:
        _cb.observe(_on_sm_cb_change, names="value")
    _on_sm_cb_change()  # evaluate initial state so warning shows if checkboxes start checked

    # Only show rows for available fixers
    _sm_fixer_rows = [_section_heading("Semantic Model")]
    if fix_discourage_implicit_measures is not None:
        _sm_fixer_rows.append(discourage_row)
    if add_calculated_calendar is not None:
        _sm_fixer_rows.append(calendar_row)
    if add_last_refresh_table is not None:
        _sm_fixer_rows.append(last_refresh_row)
    if add_measure_table is not None:
        _sm_fixer_rows.append(measure_tbl_row)
    if add_calc_group_units is not None:
        _sm_fixer_rows.append(units_row)
    if add_calc_group_time_intelligence is not None:
        _sm_fixer_rows.append(time_intel_row)
    _sm_fixer_rows.append(sm_warning_confirm)

    semantic_model_box = widgets.VBox(
        _sm_fixer_rows,
        layout=widgets.Layout(
            gap="6px",
            padding="12px",
            margin="0 0 16px 0",
            border=f"1px solid {border_color}",
            border_radius="8px",
            background_color=section_bg,
        ),
    )

    # -----------------------------
    # RUN BUTTON
    # -----------------------------
    run_btn = widgets.Button(
        description="Run",
        button_style="primary",
        layout=widgets.Layout(width="100px"),
    )

    god_btn = widgets.Button(
        description="\u26A1 Fix Everything",
        button_style="danger",
        layout=widgets.Layout(width="160px"),
    )

    button_row = widgets.HBox(
        [god_btn, run_btn],
        layout=widgets.Layout(justify_content="flex-end", gap="8px", margin="0 0 8px 0"),
    )

    # -----------------------------
    # RUN HANDLER
    # -----------------------------
    report_fixers = [
        # (checkbox, label, callable) — Upgrade to PBIR runs first
        x for x in [
            (cb_upgrade, "Upgrade to PBIR", lambda r, p, w, s: fix_upgrade_to_pbir(report=r, page_name=p, workspace=w, scan_only=s)) if fix_upgrade_to_pbir else None,
            (cb_pie, "Fix Pie Charts", lambda r, p, w, s: fix_piecharts(report=r, page_name=p, workspace=w, scan_only=s)) if fix_piecharts else None,
            (cb_bar, "Fix Bar Charts", lambda r, p, w, s: fix_barcharts(report=r, page_name=p, workspace=w, scan_only=s)) if fix_barcharts else None,
            (cb_col, "Fix Column Charts", lambda r, p, w, s: fix_columncharts(report=r, page_name=p, workspace=w, scan_only=s)) if fix_columncharts else None,
            (cb_page_size, "Fix Page Size", lambda r, p, w, s: fix_page_size(report=r, page_name=p, workspace=w, scan_only=s)) if fix_page_size else None,
            (cb_hide_filters, "Hide Visual Filters", lambda r, p, w, s: fix_hide_visual_filters(report=r, page_name=p, workspace=w, scan_only=s)) if fix_hide_visual_filters else None,
        ] if x is not None
    ]

    sm_fixers = [
        x for x in [
            (cb_discourage, "Discourage Implicit Measures", lambda r, w, s: fix_discourage_implicit_measures(report=r, workspace=w, scan_only=s)) if fix_discourage_implicit_measures else None,
            (cb_calendar, "Add Calendar Table", lambda r, w, s: add_calculated_calendar(report=r, workspace=w, scan_only=s)) if add_calculated_calendar else None,
            (cb_measure_tbl, "Add Measure Table", lambda r, w, s: add_measure_table(report=r, workspace=w, scan_only=s)) if add_measure_table else None,
            (cb_last_refresh, "Add Last Refresh Table", lambda r, w, s: add_last_refresh_table(report=r, workspace=w, scan_only=s)) if add_last_refresh_table else None,
            (cb_units, "Add Units Calc Group", lambda r, w, s: add_calc_group_units(report=r, workspace=w, scan_only=s)) if add_calc_group_units else None,
            (cb_time_intel, "Add Time Intelligence Calc Group", lambda r, w, s: add_calc_group_time_intelligence(report=r, workspace=w, scan_only=s)) if add_calc_group_time_intelligence else None,
        ] if x is not None
    ]

    def on_run(_):
        ws = workspace_input.value.strip() or None
        report_val = report_input.value.strip()
        page = page_input.value.strip() or None
        mode = mode_toggle.value

        # Parse comma-separated items
        items = [x.strip() for x in report_val.split(",") if x.strip()] if report_val else []

        if not items:
            show_status("Please enter at least one report / SM name or ID.", "#ff3b30")
            return

        status.value = ""
        run_btn.disabled = True
        god_btn.disabled = True
        run_btn.description = "Running…"

        rpt_selected = [(cb, label, fn) for cb, label, fn in report_fixers if cb.value]
        sm_selected  = [(cb, label, fn) for cb, label, fn in sm_fixers if cb.value]
        total_fixers = len(rpt_selected) + len(sm_selected)

        if total_fixers == 0:
            show_status("Please select at least one fixer.", "#ff3b30")
            run_btn.disabled = False
            god_btn.disabled = False
            run_btn.description = "Run"
            return

        # Require confirmation when SM fixers are selected in a mode that writes
        if sm_selected and mode != "Scan" and not cb_sm_confirm.value:
            show_status(
                "⚠️  Please tick the XMLA confirmation checkbox before running semantic model fixers.",
                "#ff9500",
            )
            run_btn.disabled = False
            god_btn.disabled = False
            run_btn.description = "Run"
            return

        def _do_work():
            """Runs selected fixers on each item, with timeout and PBIR gate."""
            start_time = time.time()
            try:
                _progress_lines.clear()
                progress.layout.display = ""
                total = total_fixers * len(items)

                def _log(text=""):
                    _progress_lines.append(text)
                    progress.value = (
                        '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif; '
                        'font-size:13px; margin:0; padding:10px; '
                        'max-height:540px; overflow-y:auto; white-space:pre-wrap;">'
                        + "\n".join(_progress_lines)
                        + "</div>"
                    )

                _log(f"{total_fixers} Fixer(s) × {len(items)} Item(s) = {total} total  [Mode: {mode}]")
                _log()
                _log(f"  Workspace: {ws or 'Notebook workspace'}")
                _log(f"  Items:     {', '.join(items)}")
                _log(f"  Page:      {page or 'All'}")
                _log()

                idx = 0
                errors = 0
                timed_out = False

                def _check_timeout():
                    nonlocal timed_out
                    if time.time() - start_time > _TOTAL_TIMEOUT:
                        _log(f"⏱️  5-minute timeout reached ({int(time.time() - start_time)}s). Aborting.")
                        timed_out = True
                        return True
                    return False

                # PBIR gate state
                upgrade_selected = any(label == "Upgrade to PBIR" for _, label, _ in rpt_selected)
                non_upgrade_rpt = [x for x in rpt_selected if x[1] != "Upgrade to PBIR"]

                def _run_report_fixers(scan: bool):
                    nonlocal idx, errors
                    prefix = "🔍" if scan else "▶"
                    for item in items:
                        if _check_timeout():
                            return
                        # PBIR gate (fix mode only)
                        if not scan and non_upgrade_rpt:
                            fmt = _check_report_format(item, ws)
                            if fmt == "PBIRLegacy" and not upgrade_selected:
                                _log(f"⚠️  '{item}' is in PBIRLegacy format — skipping report fixers.")
                                _log(f"    → Enable 'Upgrade to PBIR' to convert automatically.")
                                _log()
                                idx += len(rpt_selected)
                                errors += len(rpt_selected)
                                continue
                        for cb, label, fn in rpt_selected:
                            if _check_timeout():
                                return
                            idx += 1
                            suffix = f" on '{item}'" if len(items) > 1 else ""
                            _log(f"{prefix} [{idx}/{total}] {'Scanning ' if scan else ''}{label}{suffix}...")
                            try:
                                buf = io.StringIO()
                                with redirect_stdout(buf):
                                    fn(item, page, ws, scan)
                                captured = buf.getvalue().rstrip()
                                if captured:
                                    for line in captured.splitlines():
                                        _log(f"   {line}")
                            except Exception as e:
                                errors += 1
                                _log(f"   ❌ Error: {e}")
                            _log()

                def _run_sm_fixers(scan: bool):
                    nonlocal idx, errors
                    prefix = "🔍" if scan else "▶"
                    for item in items:
                        if _check_timeout():
                            return
                        for _, label, fn in sm_selected:
                            if _check_timeout():
                                return
                            idx += 1
                            suffix = f" on '{item}'" if len(items) > 1 else ""
                            _log(f"{prefix} [{idx}/{total}] {'Scanning ' if scan else ''}{label}{suffix}...")
                            try:
                                buf = io.StringIO()
                                with redirect_stdout(buf):
                                    fn(item, ws, scan)
                                captured = buf.getvalue().rstrip()
                                if captured:
                                    for line in captured.splitlines():
                                        _log(f"   {line}")
                            except Exception as e:
                                errors += 1
                                _log(f"   ❌ Error: {e}")
                            _log()

                if mode == "Scan":
                    _run_report_fixers(scan=True)
                    _run_sm_fixers(scan=True)
                elif mode == "Fix":
                    _run_report_fixers(scan=False)
                    _run_sm_fixers(scan=False)
                else:  # Scan + Fix
                    _log("─" * 40)
                    _log("PHASE 1: Scan")
                    _log()
                    _run_report_fixers(scan=True)
                    _run_sm_fixers(scan=True)
                    idx = 0
                    _log("─" * 40)
                    _log("PHASE 2: Fix")
                    _log()
                    _run_report_fixers(scan=False)
                    _run_sm_fixers(scan=False)

                elapsed = int(time.time() - start_time)
                if timed_out:
                    show_status(
                        f"⏱️  Timed out after {elapsed}s. {idx}/{total} run(s), {errors} error(s).",
                        "#ff9500",
                    )
                elif errors > 0:
                    show_status(
                        f"⚠️  Completed with {errors} error(s) out of {total} run(s) in {elapsed}s.",
                        "#ff9500",
                    )
                elif mode == "Scan":
                    show_status(f"✓  Scan complete — {total} run(s) in {elapsed}s.", "#007aff")
                elif mode == "Fix":
                    show_status(f"✓  All {total} run(s) completed in {elapsed}s.", "#34c759")
                else:
                    show_status(f"✓  Scan + Fix complete — {total} run(s) in {elapsed}s.", "#34c759")

            except Exception as e:
                show_status(f"Error: {e}", "#ff3b30")

            finally:
                run_btn.disabled = False
                god_btn.disabled = False
                run_btn.description = "Run"

        _do_work()

    run_btn.on_click(on_run)

    def on_god_btn(_):
        """Select all fixers and run."""
        all_cbs = [cb_pie, cb_bar, cb_col, cb_page_size, cb_hide_filters]
        if fix_upgrade_to_pbir is not None:
            all_cbs.append(cb_upgrade)
        for cb in all_cbs:
            cb.value = True
        for cb in _sm_checkboxes:
            cb.value = True
        cb_sm_confirm.value = True
        on_run(None)

    god_btn.on_click(on_god_btn)

    # -----------------------------
    # ASSEMBLE & DISPLAY
    # -----------------------------
    version_footer = widgets.HTML(
        value=f'<div style="text-align:right; font-size:11px; color:{gray_color}; '
        f'font-family:-apple-system,BlinkMacSystemFont,sans-serif; '
        f'margin-top:8px; padding-top:8px; border-top:1px solid {border_color};">'
        f'v{__version__} \u2022 Alexander Korn \u2022 '
        f'<a href="https://actionablereporting.com" target="_blank" '
        f'style="color:{icon_accent}; text-decoration:none;">actionablereporting.com</a></div>'
    )

    # -- Fixer tab content (existing UI, minus inputs which are now shared) --
    page_input_row = widgets.HBox(
        [_input_label("Page (opt.)"), page_input],
        layout=widgets.Layout(align_items="center", gap="8px", margin="0 0 12px 0"),
    )
    fixer_content = widgets.VBox(
        [
            mode_row,
            page_input_row,
            report_fixers_box,
            semantic_model_box,
            button_row,
            progress,
            status,
        ],
        layout=widgets.Layout(padding="4px 0"),
    )

    # -- Build fixer callbacks for Report Explorer actions dropdown --
    _rpt_fixer_cbs = {}
    if fix_upgrade_to_pbir is not None:
        _rpt_fixer_cbs["Convert to PBIR"] = lambda **kw: fix_upgrade_to_pbir(**kw)
    if fix_piecharts is not None:
        _rpt_fixer_cbs["Fix Pie Charts"] = lambda **kw: fix_piecharts(**kw)
    if fix_barcharts is not None:
        _rpt_fixer_cbs["Fix Bar Charts"] = lambda **kw: fix_barcharts(**kw)
    if fix_columncharts is not None:
        _rpt_fixer_cbs["Fix Column Charts"] = lambda **kw: fix_columncharts(**kw)
    if fix_page_size is not None:
        _rpt_fixer_cbs["Fix Page Size"] = lambda **kw: fix_page_size(**kw)
    if fix_hide_visual_filters is not None:
        _rpt_fixer_cbs["Hide Visual Filters"] = lambda **kw: fix_hide_visual_filters(**kw)

    # -- Build fixer callbacks for SM Explorer actions dropdown --
    _sm_fixer_cbs = {}
    if fix_discourage_implicit_measures is not None:
        _sm_fixer_cbs["Discourage Implicit Measures"] = lambda **kw: fix_discourage_implicit_measures(**kw)
    if add_calculated_calendar is not None:
        _sm_fixer_cbs["Add Calendar Table"] = lambda **kw: add_calculated_calendar(**kw)
    if add_last_refresh_table is not None:
        _sm_fixer_cbs["Add Last Refresh Table"] = lambda **kw: add_last_refresh_table(**kw)
    if add_measure_table is not None:
        _sm_fixer_cbs["Add Measure Table"] = lambda **kw: add_measure_table(**kw)
    if add_calc_group_units is not None:
        _sm_fixer_cbs["Add Units Calc Group"] = lambda **kw: add_calc_group_units(**kw)
    if add_calc_group_time_intelligence is not None:
        _sm_fixer_cbs["Add Time Intelligence"] = lambda **kw: add_calc_group_time_intelligence(**kw)
    if add_measures_from_columns is not None:
        _sm_fixer_cbs["Auto-Create Measures from Columns"] = lambda **kw: add_measures_from_columns(
            dataset=kw.get("report", ""), workspace=kw.get("workspace"), scan_only=kw.get("scan_only", False)
        )
    if add_py_measures is not None:
        _sm_fixer_cbs["Add PY Measures (Y-1)"] = lambda **kw: add_py_measures(
            dataset=kw.get("report", ""), workspace=kw.get("workspace"), scan_only=kw.get("scan_only", False)
        )

    def _format_all_dax(**kw):
        """Format all DAX expressions via daxformatter.com API."""
        ds = kw.get("report", "")
        ws = kw.get("workspace")
        if not ds:
            print("No model specified.")
            return
        from sempy_labs.tom import connect_semantic_model
        print(f"Formatting DAX in '{ds}'...")
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            tom.format_dax()
        print(f"\u2713 All DAX expressions formatted.")

    _sm_fixer_cbs["Format All DAX"] = lambda **kw: _format_all_dax(**kw)

    # -- Build tab panels (show/hide via layout.display) --
    tab_panels = []

    if sm_explorer_tab is not None:
        sm_result = sm_explorer_tab(
            workspace_input=workspace_input, report_input=report_input,
            fixer_callbacks=_sm_fixer_cbs,
        )
        if isinstance(sm_result, tuple):
            sm_content, _sm_load_fn = sm_result
        else:
            sm_content = sm_result
        tab_panels.append(sm_content)

    if report_explorer_tab is not None:
        def _navigate_to_sm(obj_name, table_name, obj_type):
            """Switch to SM Explorer tab (callback from Report Explorer)."""
            sm_tab_label = "\U0001F4CA Semantic Model"
            if sm_tab_label in _tab_options:
                tab_selector.value = sm_tab_label

        rpt_result = report_explorer_tab(
            workspace_input=workspace_input, report_input=report_input,
            fixer_callbacks=_rpt_fixer_cbs,
            navigate_to_sm=_navigate_to_sm if sm_explorer_tab is not None else None,
        )
        if isinstance(rpt_result, tuple):
            rpt_content, _rpt_load_fn = rpt_result
        else:
            rpt_content = rpt_result
        tab_panels.append(rpt_content)

    if _fixer_visible:
        tab_panels.append(fixer_content)

    if perspective_editor_tab is not None:
        persp_content = perspective_editor_tab(
            workspace_input=workspace_input, report_input=report_input
        )
        tab_panels.append(persp_content)

    # Memory Analyzer tab (renamed from Vertipaq)
    vp_content = _vertipaq_tab(
        workspace_input=workspace_input, report_input=report_input
    )
    tab_panels.append(vp_content)

    # BPA tab
    bpa_content = _bpa_tab(
        workspace_input=workspace_input, report_input=report_input
    )
    tab_panels.append(bpa_content)

    # About tab
    about_content = widgets.HTML(
        value=(
            f'<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif; padding:24px; max-width:600px;">'
            f'<div style="font-size:28px; font-weight:700; color:#FF9500; margin-bottom:4px;">Power BI Fixer</div>'
            f'<div style="font-size:14px; color:#666; margin-bottom:24px;">Version {__version__}</div>'
            f'<div style="margin-bottom:20px; padding:16px; background:#fafafa; border-radius:8px; border:1px solid #e0e0e0;">'
            f'<div style="font-size:20px; font-weight:600; color:#333;">Alexander Korn</div>'
            f'<div style="font-size:13px; margin-top:8px;">'
            f'<a href="https://www.linkedin.com/in/alexanderkorn/" target="_blank" style="color:#0A66C2; text-decoration:none; margin-right:12px;">LinkedIn</a>'
            f'<a href="https://github.com/KornAlexander" target="_blank" style="color:#333; text-decoration:none; margin-right:12px;">GitHub</a>'
            f'<a href="https://actionablereporting.com" target="_blank" style="color:#FF9500; text-decoration:none;">actionablereporting.com</a>'
            f'</div>'
            f'<div style="font-size:13px; color:#888; margin-top:4px;">Transform data into actionable insights</div>'
            f'</div>'
            f'<div style="margin-bottom:20px; padding:16px; background:#fafafa; border-radius:8px; border:1px solid #e0e0e0;">'
            f'<div style="font-size:16px; font-weight:600; margin-bottom:8px;">\U0001F4E6 Source</div>'
            f'<div style="font-size:13px;">'
            f'<a href="https://github.com/KornAlexander/pbi_fixer" target="_blank" style="color:#FF9500;">github.com/KornAlexander/pbi_fixer</a><br>'
            f'<a href="https://github.com/KornAlexander/semantic-link-labs" target="_blank" style="color:#FF9500;">github.com/KornAlexander/semantic-link-labs</a> (fork)<br>'
            f'<a href="https://github.com/microsoft/semantic-link-labs" target="_blank" style="color:#FF9500;">github.com/microsoft/semantic-link-labs</a> (official)'
            f'</div>'
            f'</div>'
            f'<div style="padding:16px; background:#fafafa; border-radius:8px; border:1px solid #e0e0e0;">'
            f'<div style="font-size:16px; font-weight:600; margin-bottom:8px;">\U0001F6E0\ufe0f Built with</div>'
            f'<div style="font-size:13px; color:#555; line-height:1.8;">'
            f'\u2022 <b>Semantic Link Labs</b> \u2014 TOM, connect_report, vertipaq_analyzer<br>'
            f'\u2022 <b>ipywidgets</b> \u2014 interactive UI in Fabric Notebooks<br>'
            f'\u2022 <b>powerbiclient</b> \u2014 live report preview embed<br>'
            f'\u2022 <b>DAX Formatter</b> by SQLBI \u2014 '
            f'<a href="https://www.daxformatter.com/" target="_blank" style="color:#FF9500;">daxformatter.com</a> '
            f'(<a href="https://www.sqlbi.com/blog/marco/2014/02/24/how-to-pass-a-dax-query-to-dax-formatter/" target="_blank" style="color:#FF9500;">API docs</a>)'
            f'</div>'
            f'<div style="font-size:13px; color:#888; margin-top:12px; padding-top:8px; border-top:1px solid #e0e0e0;">'
            f'The Perspective Editor is based on work by <b>Michael Kovalsky</b> '
            f'(<a href="https://github.com/m-kovalsky/semantic-link-labs" target="_blank" style="color:#FF9500;">m-kovalsky/semantic-link-labs</a>).'
            f'</div>'
            f'</div>'
            f'</div>'
        ),
        layout=widgets.Layout(padding="12px"),
    )
    tab_panels.append(about_content)

    def _switch_tab(change=None):
        idx = _tab_options.index(tab_selector.value)
        for i, panel in enumerate(tab_panels):
            panel.layout.display = "" if i == idx else "none"

    tab_selector.observe(_switch_tab, names="value")
    _switch_tab()  # set initial visibility

    container = widgets.VBox(
        [header, shared_inputs_box, tab_selector] + tab_panels + [version_footer],
        layout=widgets.Layout(
            width="100%",
            padding="20px",
            border=f"1px solid {border_color}",
            border_radius="12px",
        ),
    )

    return container


# Sample usage (must be last line of notebook cell so Jupyter renders the returned widget):
# pbi_fixer()
# pbi_fixer(workspace="Your Workspace Name")
# pbi_fixer(workspace="Your Workspace Name", report="My Report")
# pbi_fixer(workspace="Your Workspace Name", report="Report A, Report B")
