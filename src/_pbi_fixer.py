# Interactive PBI Report Fixer UI (ipywidgets)
# Orchestrates report visual fixers and semantic model fixers via a single notebook widget.

__version__ = "1.2.111"

import ipywidgets as widgets
import io
import time
from contextlib import redirect_stdout
from typing import Optional
from uuid import UUID
import warnings as _warnings

def _lazy_import(module_path, name):
    """Import a symbol from a module, returning None + warning on failure."""
    try:
        mod = __import__(module_path, fromlist=[name])
        return getattr(mod, name)
    except Exception as _e:
        _warnings.warn(f"PBI Fixer: could not load {module_path}.{name}: {type(_e).__name__}: {_e}")
        return None

# add_measures_from_columns and add_py_measures are imported lazily inside pbi_fixer()

# sm_explorer_tab, report_explorer_tab, perspective_editor_tab
# are imported lazily inside pbi_fixer()


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
        # Model Summary: render as vertical key-value table
        if tab_name == "Model Summary" and df is not None and len(df) > 0:
            r = df.iloc[0]
            html = f'<table style="border-collapse:collapse; font-size:13px; font-family:{FONT_FAMILY}; width:100%;">'
            for col in df.columns:
                val = _fmt_val(r.get(col, ""), col)
                html += f'<tr><td style="padding:6px 12px; font-weight:600; color:#555; border-bottom:1px solid #f0f0f0; white-space:nowrap; width:200px;">{col}</td>'
                html += f'<td style="padding:6px 12px; border-bottom:1px solid #f0f0f0;">{val}</td></tr>'
            html += '</table>'
            df_html.value = html
            return
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
    # Model selector dropdown for multi-model switching
    model_dropdown = widgets.Dropdown(
        options=["(no models loaded)"],
        value="(no models loaded)",
        layout=widgets.Layout(width="300px"),
    )

    def on_model_change(change):
        m = change.get("new", "")
        if m and m != "(no models loaded)" and m in _vp_data:
            _current_model[0] = m
            _render_subtab()

    model_dropdown.observe(on_model_change, names="value")

    right_panel = widgets.VBox([model_dropdown, subtab_selector, df_container, detail_label, detail_container], layout=widgets.Layout(flex="1", gap="4px"))
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

    # BPA fix functions — imported from standalone files (with inline fallbacks)
    def _make_bpa_fixer(module_path, func_name, inline_fn):
        """Try to import standalone fixer; fall back to inline function."""
        fn = _lazy_import(module_path, func_name)
        return fn if fn is not None else inline_fn

    def _fix_floating_point_inline(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            col = tom.model.Tables[table].Columns[obj]
            import Microsoft.AnalysisServices.Tabular as TOM
            col.DataType = TOM.DataType.Decimal
            tom.model.SaveChanges()
        return f"Changed '{table}'[{obj}] from Double to Decimal"

    def _fix_isavailableinmdx_inline(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            col = tom.model.Tables[table].Columns[obj]
            col.IsAvailableInMDX = False
            tom.model.SaveChanges()
        return f"Set IsAvailableInMDX=False on '{table}'[{obj}]"

    def _fix_description_measure_inline(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            m = tom.model.Tables[table].Measures[obj]
            m.Description = str(m.Expression) if m.Expression else ""
            tom.model.SaveChanges()
        return f"Set description of [{obj}] to its DAX expression"

    def _fix_date_format_inline(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            col = tom.model.Tables[table].Columns[obj]
            col.FormatString = "mm/dd/yyyy"
            tom.model.SaveChanges()
        return f"Set format of '{table}'[{obj}] to mm/dd/yyyy"

    def _fix_month_format_inline(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            col = tom.model.Tables[table].Columns[obj]
            col.FormatString = "MMMM yyyy"
            tom.model.SaveChanges()
        return f"Set format of '{table}'[{obj}] to MMMM yyyy"

    def _fix_integer_format_inline(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            m = tom.model.Tables[table].Measures[obj]
            m.FormatString = "#,0"
            tom.model.SaveChanges()
        return f"Set format of [{obj}] to #,0"

    def _fix_hide_foreign_key_inline(ds, ws, table, obj):
        from sempy_labs.tom import connect_semantic_model
        with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tom:
            col = tom.model.Tables[table].Columns[obj]
            col.IsHidden = True
            tom.model.SaveChanges()
        return f"Hidden '{table}'[{obj}]"

    # Use standalone files when available, with inline fallbacks
    _fix_floating_point = _fix_floating_point_inline
    _fix_isavailableinmdx = _fix_isavailableinmdx_inline
    _fix_description_measure = _fix_description_measure_inline
    _fix_date_format = _fix_date_format_inline
    _fix_month_format = _fix_month_format_inline
    _fix_integer_format = _fix_integer_format_inline
    _fix_hide_foreign_key = _fix_hide_foreign_key_inline

    # Map BPA Rule Names to fix functions (lowercase keys for fuzzy matching)
    _fix_map_raw = {
        "Do not use floating point data types": _fix_floating_point,
        "Do not use floating point data type": _fix_floating_point,
        "Set IsAvailableInMdx to false on non-attribute columns": _fix_isavailableinmdx,
        "Provide format string for 'Date' columns": _fix_date_format,
        "Provide format string for 'Month' columns": _fix_month_format,
        "Provide format string for measures": _fix_integer_format,
        "Hide foreign keys": _fix_hide_foreign_key,
    }
    _fix_map = {k.lower().strip(): v for k, v in _fix_map_raw.items()}
    _desc_fix_rule = "visible objects with no description"

    def _parse_table_object(obj_name, obj_type):
        """Parse table and object from BPA Object Name. Columns are 'Table'[Col], measures are just Name."""
        import re
        m = re.match(r"'([^']+)'\[([^\]]+)\]", obj_name)
        if m:
            return m.group(1), m.group(2)
        # Measure or table — just the name
        return "", obj_name

    def _is_fixable(rule_name, obj_type):
        key = rule_name.lower().strip()
        return key in _fix_map or (key == _desc_fix_rule and obj_type == "Measure")

    def _apply_fix(ds, ws, rule_name, obj_type, obj_name):
        """Apply a single BPA fix. Returns message or raises."""
        table_name, item_name = _parse_table_object(obj_name, obj_type)
        key = rule_name.lower().strip()
        if key in _fix_map:
            return _fix_map[key](ds, ws, table_name, item_name)
        if key == _desc_fix_rule and obj_type == "Measure":
            return _fix_description_measure(ds, ws, table_name, item_name)
        return None

    load_btn = widgets.Button(description="Run BPA", button_style="primary", layout=widgets.Layout(width="120px"))
    fix_all_btn = widgets.Button(description="\u26a1 Fix All", button_style="danger", layout=widgets.Layout(width="100px"))
    show_full_btn = widgets.Button(description="\U0001F4CB Show Full BPA", layout=widgets.Layout(width="150px"))
    conn_status = status_html()
    nav_row = widgets.HBox(
        [load_btn, fix_all_btn, show_full_btn, conn_status],
        layout=widgets.Layout(align_items="center", gap="8px", margin="0 0 8px 0"),
    )

    # Fix by rule dropdown
    rule_dropdown = widgets.Dropdown(options=["(no findings)"], value="(no findings)", layout=widgets.Layout(width="320px"))
    fix_rule_btn = widgets.Button(description="\u26a1 Fix Rule", button_style="warning", layout=widgets.Layout(width="100px"))
    # Fix single row
    row_input = widgets.IntText(value=1, layout=widgets.Layout(width="60px"))
    fix_row_btn = widgets.Button(description="Fix Row", button_style="warning", layout=widgets.Layout(width="80px"))
    row_label = widgets.HTML(value=f'<span style="font-size:11px; color:#555; font-family:{FONT_FAMILY};">Row #:</span>')
    fix_row = widgets.HBox(
        [rule_dropdown, fix_rule_btn, row_label, row_input, fix_row_btn],
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

    _all_findings = []  # [(ds, rule_name, category, obj_name, obj_type, severity), ...]

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
                        rule_name = str(row.get("Rule Name", ""))
                        category = str(row.get("Category", ""))
                        obj_name = str(row.get("Object Name", ""))
                        obj_type = str(row.get("Object Type", ""))
                        severity = str(row.get("Severity", ""))
                        _all_findings.append((ds, rule_name, category, obj_name, obj_type, severity))
            except Exception as e:
                _all_findings.append((ds, f"ERROR: {e}", "Error", "", "", "3"))

        _build_results(ws)
        _update_rule_dropdown()
        n = len([f for f in _all_findings if not f[1].startswith("ERROR")])
        set_status(conn_status, f"\u2713 BPA: {n} finding(s) across {len(items)} model(s).", "#34c759" if n == 0 else "#ff9500")
        load_btn.disabled = False
        load_btn.description = "Run BPA"

    def _update_rule_dropdown():
        """Populate rule dropdown with fixable rules + counts."""
        from collections import Counter
        fixable = [(f[1], f[4]) for f in _all_findings if _is_fixable(f[1], f[4])]
        counts = Counter(r for r, _ in fixable)
        if counts:
            opts = [f"{name} ({count})" for name, count in sorted(counts.items())]
            rule_dropdown.options = opts
            rule_dropdown.value = opts[0]
        else:
            rule_dropdown.options = ["(no fixable rules)"]
            rule_dropdown.value = "(no fixable rules)"

    def _build_results(ws):
        if not _all_findings:
            results_box.children = [widgets.HTML(
                value=f'<div style="color:#34c759; font-size:14px; font-weight:600;">\u2713 No violations found.</div>'
            )]
            return

        # Group findings by category (native BPA style with tabs)
        from collections import OrderedDict
        cats = OrderedDict()
        for ds, rule_name, category, obj_name, obj_type, severity in _all_findings:
            if rule_name.startswith("ERROR"):
                cats.setdefault("Errors", []).append((ds, rule_name, category, obj_name, obj_type, severity))
                continue
            cats.setdefault(category, []).append((ds, rule_name, category, obj_name, obj_type, severity))

        # Use unique IDs to avoid JS collision with other tabs
        import random as _rnd
        uid = _rnd.randint(1000, 9999)

        # CSS + JS (scoped with uid)
        styles = f'''<style>
        .bpa-tab-{uid} {{ overflow:hidden; border:1px solid #ccc; background:#f1f1f1; display:flex; flex-wrap:wrap; }}
        .bpa-tab-{uid} button {{ background:inherit; border:none; outline:none; cursor:pointer; padding:8px 12px; transition:0.3s; font-size:11px; }}
        .bpa-tab-{uid} button:hover {{ background:#ddd; }}
        .bpa-tab-{uid} button.active {{ background:#ccc; font-weight:bold; }}
        .bpa-tc-{uid} {{ display:none; padding:4px 8px; border:1px solid #ccc; border-top:none; max-height:350px; overflow-y:auto; }}
        .bpa-tc-{uid}.active {{ display:block; }}
        .bpa-tt {{ position:relative; display:inline-block; }}
        .bpa-tt .bpa-ttp {{ visibility:hidden; width:280px; background:#555; color:#fff; text-align:center; border-radius:6px; padding:5px; position:absolute; z-index:1; bottom:125%; left:50%; margin-left:-140px; opacity:0; transition:opacity 0.3s; font-size:11px; }}
        .bpa-tt:hover .bpa-ttp {{ visibility:visible; opacity:1; }}
        </style>'''

        script = f'''<script>
        function bpaTab{uid}(evt, tabId) {{
            var tc = document.querySelectorAll('.bpa-tc-{uid}');
            for (var i=0; i<tc.length; i++) tc[i].style.display='none';
            var btns = document.querySelectorAll('.bpa-tab-{uid} button');
            for (var i=0; i<btns.length; i++) btns[i].className = btns[i].className.replace(' active','');
            document.getElementById(tabId).style.display='block';
            evt.currentTarget.className += ' active';
        }}
        </script>'''

        tab_html = f'<div class="bpa-tab-{uid}">'
        content_html = ""
        n_fixable = 0

        for cat_idx, (cat_name, findings) in enumerate(cats.items()):
            tab_id = f"bpa{uid}_{cat_idx}"
            active = " active" if cat_idx == 0 else ""
            # Severity summary
            sev_counts = {}
            for _, _, _, _, _, sev in findings:
                sev_counts[sev] = sev_counts.get(sev, 0) + 1
            summary = " + ".join(f"{v} (Sev {k})" for k, v in sorted(sev_counts.items()))
            tab_html += f'<button class="{active}" onclick="bpaTab{uid}(event,\'{tab_id}\')">{cat_name}<br><span style="font-size:10px;color:#888;">{summary}</span></button>'

            content_html += f'<div id="{tab_id}" class="bpa-tc-{uid}{active}">'
            content_html += '<table style="border-collapse:collapse; width:100%; font-size:11px; font-family:monospace;">'
            content_html += '<tr style="background:#f5f5f5;"><th style="padding:3px 6px; text-align:left;">Model</th><th style="padding:3px 6px; text-align:left;">Rule</th><th style="padding:3px 6px; text-align:left;">Type</th><th style="padding:3px 6px; text-align:left;">Object</th><th style="padding:3px 6px; text-align:center;">Sev</th><th style="padding:3px 6px; text-align:center;">Fix</th></tr>'
            for ds, rule_name, category, obj_name, obj_type, severity in findings:
                if rule_name.startswith("ERROR"):
                    content_html += f'<tr><td colspan="6" style="color:#ff3b30; padding:2px 6px;">\u274c {ds}: {rule_name}</td></tr>'
                    continue
                sev_color = "#ff3b30" if severity in ("3",) else "#ff9500" if severity in ("2",) else "#888"
                has_fix = _is_fixable(rule_name, obj_type)
                if has_fix:
                    n_fixable += 1
                fix_icon = '<span style="color:#34c759;">\u2713</span>' if has_fix else '\u2014'
                content_html += f'<tr><td style="padding:2px 6px; border-bottom:1px solid #f0f0f0;" title="{ds}">{ds[:16]}</td>'
                content_html += f'<td style="padding:2px 6px; border-bottom:1px solid #f0f0f0; color:{ICON_ACCENT};" title="{rule_name}">{rule_name[:40]}</td>'
                content_html += f'<td style="padding:2px 6px; border-bottom:1px solid #f0f0f0; color:#888;">{obj_type[:10]}</td>'
                content_html += f'<td style="padding:2px 6px; border-bottom:1px solid #f0f0f0;" title="{obj_name}">{obj_name[:40]}</td>'
                content_html += f'<td style="padding:2px 6px; border-bottom:1px solid #f0f0f0; text-align:center; color:{sev_color}; font-weight:600;">{severity}</td>'
                content_html += f'<td style="padding:2px 6px; border-bottom:1px solid #f0f0f0; text-align:center;">{fix_icon}</td></tr>'
            content_html += '</table></div>'
        tab_html += '</div>'

        full_html = styles + tab_html + content_html + script

        summary = widgets.HTML(
            value=f'<div style="font-size:12px; font-family:{FONT_FAMILY}; color:#555; margin:8px 0 4px 0;">'
            f'{len(_all_findings)} finding(s), <b>{n_fixable}</b> auto-fixable</div>'
        )
        results_box.children = [widgets.HTML(value=full_html), summary]

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
        for ds, rule_name, category, obj_name, obj_type, severity in _all_findings:
            if rule_name.startswith("ERROR"):
                continue
            try:
                result = _apply_fix(ds, ws, rule_name, obj_type, obj_name)
                if result:
                    fixed += 1
            except Exception:
                errors += 1
        set_status(conn_status, f"\u2713 Fixed {fixed}, {errors} error(s).", "#34c759" if errors == 0 else "#ff9500")
        fix_all_btn.disabled = False
        fix_all_btn.description = "\u26a1 Fix All"

    def on_fix_rule(_):
        """Fix all violations of the selected rule."""
        selected = rule_dropdown.value
        if not selected or selected.startswith("("):
            return
        # Extract rule name (strip count suffix)
        import re
        m = re.match(r"(.+)\s+\(\d+\)$", selected)
        target_rule = m.group(1) if m else selected
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        fix_rule_btn.disabled = True
        fix_rule_btn.description = "Fixing\u2026"
        fixed = 0
        errors = 0
        for ds, rule_name, category, obj_name, obj_type, severity in _all_findings:
            if rule_name != target_rule:
                continue
            try:
                result = _apply_fix(ds, ws, rule_name, obj_type, obj_name)
                if result:
                    fixed += 1
            except Exception:
                errors += 1
        set_status(conn_status, f"\u2713 '{target_rule}': fixed {fixed}, {errors} error(s).", "#34c759" if errors == 0 else "#ff9500")
        fix_rule_btn.disabled = False
        fix_rule_btn.description = "\u26a1 Fix Rule"

    def on_fix_row(_):
        """Fix a single violation by row number."""
        idx = row_input.value - 1  # 1-based to 0-based
        if idx < 0 or idx >= len(_all_findings):
            set_status(conn_status, f"Row {idx+1} out of range (1-{len(_all_findings)}).", "#ff3b30")
            return
        ds, rule_name, category, obj_name, obj_type, severity = _all_findings[idx]
        if rule_name.startswith("ERROR"):
            set_status(conn_status, "Cannot fix error row.", "#ff3b30")
            return
        if not _is_fixable(rule_name, obj_type):
            set_status(conn_status, f"Row {idx+1} has no auto-fix for '{rule_name}'.", "#ff9500")
            return
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        try:
            msg = _apply_fix(ds, ws, rule_name, obj_type, obj_name)
            set_status(conn_status, f"\u2713 Row {idx+1}: {msg}", "#34c759")
        except Exception as e:
            set_status(conn_status, f"Error row {idx+1}: {e}", "#ff3b30")

    load_btn.on_click(on_load)
    fix_all_btn.on_click(on_fix_all)
    fix_rule_btn.on_click(on_fix_rule)
    fix_row_btn.on_click(on_fix_row)

    # Output area for the native BPA HTML (rendered below the widget)
    bpa_output = widgets.Output()

    def on_show_full(_):
        """Run run_model_bpa and capture its HTML output into the Output widget."""
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        ds_input = report_input.value.strip() if report_input else ""
        items = [x.strip() for x in ds_input.split(",") if x.strip()] if ds_input else []
        if not items:
            set_status(conn_status, "Enter a semantic model name.", "#ff3b30")
            return
        show_full_btn.disabled = True
        show_full_btn.description = "Loading\u2026"
        bpa_output.clear_output(wait=True)

        # Capture HTML by intercepting display calls
        captured_html = []
        import IPython.display as _ipd
        import IPython.core.display_functions as _idf
        _orig1 = _ipd.display
        _orig2 = getattr(_idf, 'display', None)

        def _capture(*args, **kwargs):
            for a in args:
                if hasattr(a, 'data') and isinstance(a.data, str):
                    captured_html.append(a.data)
                elif hasattr(a, '_repr_html_'):
                    captured_html.append(a._repr_html_())

        _ipd.display = _capture
        if _orig2:
            _idf.display = _capture

        import io as _io
        from contextlib import redirect_stdout as _redirect
        try:
            for ds in items:
                try:
                    buf = _io.StringIO()
                    # Also patch the display in _model_bpa module
                    try:
                        import sempy_labs._model_bpa as _bpa_mod
                        _orig_bpa = getattr(_bpa_mod, 'display', None)
                        _bpa_mod.display = _capture
                    except Exception:
                        _bpa_mod = None
                        _orig_bpa = None
                    try:
                        with _redirect(buf):
                            from sempy_labs import run_model_bpa
                            run_model_bpa(dataset=ds, workspace=ws)
                    finally:
                        if _bpa_mod and _orig_bpa:
                            _bpa_mod.display = _orig_bpa
                except Exception as e:
                    captured_html.append(f'<div style="color:red;">Error for {ds}: {e}</div>')
        finally:
            _ipd.display = _orig1
            if _orig2:
                _idf.display = _orig2

        # Render captured HTML inside the Output widget
        with bpa_output:
            from IPython.display import display as _real_display, HTML as _HTML
            if captured_html:
                _real_display(_HTML("\n".join(captured_html)))
            else:
                _real_display(_HTML('<div style="color:#888;">No output captured.</div>'))

        show_full_btn.disabled = False
        show_full_btn.description = "\U0001F4CB Show Full BPA"

    show_full_btn.on_click(on_show_full)

    widget = widgets.VBox([nav_row, fix_row, header_label, results_box, bpa_output], layout=widgets.Layout(padding="12px", gap="4px"))
    return widget


# ---------------------------------------------------------------------------
# Report BPA tab (inline)
# ---------------------------------------------------------------------------
def _report_bpa_tab(workspace_input=None, report_input=None):
    """Build the Report BPA tab — runs run_report_bpa and shows results."""
    from sempy_labs._ui_components import (
        FONT_FAMILY, BORDER_COLOR, GRAY_COLOR, ICON_ACCENT, SECTION_BG,
        status_html, set_status,
    )

    load_btn = widgets.Button(description="Run Report BPA", button_style="primary", layout=widgets.Layout(width="140px"))
    show_full_btn = widgets.Button(description="\U0001F4CB Show Native", layout=widgets.Layout(width="130px"))
    conn_status = status_html()
    nav_row = widgets.HBox(
        [load_btn, show_full_btn, conn_status],
        layout=widgets.Layout(align_items="center", gap="8px", margin="0 0 8px 0"),
    )
    header_label = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Report Best Practice Analyzer</div>'
        f'<div style="font-size:11px; color:#888; font-family:{FONT_FAMILY}; font-style:italic; margin-bottom:4px;">'
        f'\u2139\ufe0f Requires PBIR format. Auto-converts PBIRLegacy if needed.</div>'
    )
    results_box = widgets.VBox(layout=widgets.Layout(
        max_height="400px", overflow_y="auto",
        border=f"1px solid {BORDER_COLOR}", border_radius="8px",
        padding="8px", background_color=SECTION_BG,
    ))
    results_box.children = [widgets.HTML(
        value=f'<div style="padding:12px; color:{GRAY_COLOR}; font-size:13px; font-family:{FONT_FAMILY}; font-style:italic;">Click Run Report BPA to scan.</div>'
    )]
    native_output = widgets.Output()

    _all_findings = []

    def on_load(_):
        nonlocal _all_findings
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        rpt_input = report_input.value.strip() if report_input else ""
        items = [x.strip() for x in rpt_input.split(",") if x.strip()] if rpt_input else []
        if not items:
            set_status(conn_status, "Enter a report name.", "#ff3b30")
            return
        load_btn.disabled = True
        load_btn.description = "Scanning\u2026"
        import io as _io
        from contextlib import redirect_stdout as _redirect
        import IPython.display as _ipd
        _orig_display = _ipd.display

        _all_findings = []

        for i, rpt in enumerate(items):
            set_status(conn_status, f"Report BPA {i+1}/{len(items)}: '{rpt}'\u2026", GRAY_COLOR)
            try:
                buf = _io.StringIO()
                _ipd.display = lambda *a, **kw: None
                try:
                    with _redirect(buf):
                        from sempy_labs.report import run_report_bpa
                        df = run_report_bpa(report=rpt, workspace=ws, return_dataframe=True)
                finally:
                    _ipd.display = _orig_display
                if df is not None and len(df) > 0:
                    for _, row in df.iterrows():
                        _all_findings.append((
                            rpt,
                            str(row.get("Rule Name", "")),
                            str(row.get("Category", "")),
                            str(row.get("Object Name", "")),
                            str(row.get("Object Type", "")),
                            str(row.get("Severity", "")),
                        ))
            except Exception as e:
                err_msg = str(e)
                if "PBIR format" in err_msg or "ReportWrapper" in err_msg:
                    set_status(conn_status, f"\u26a0\ufe0f '{rpt}' is PBIRLegacy \u2014 converting\u2026", "#ff9500")
                    try:
                        import sempy_labs.report as _rep
                        _rep.upgrade_to_pbir(report=rpt, workspace=ws)
                        set_status(conn_status, f"\u2713 Converted. Retrying scan\u2026", "#34c759")
                        buf = _io.StringIO()
                        _ipd.display = lambda *a, **kw: None
                        try:
                            with _redirect(buf):
                                from sempy_labs.report import run_report_bpa
                                df = run_report_bpa(report=rpt, workspace=ws, return_dataframe=True)
                        finally:
                            _ipd.display = _orig_display
                        if df is not None and len(df) > 0:
                            for _, row in df.iterrows():
                                _all_findings.append((
                                    rpt,
                                    str(row.get("Rule Name", "")),
                                    str(row.get("Category", "")),
                                    str(row.get("Object Name", "")),
                                    str(row.get("Object Type", "")),
                                    str(row.get("Severity", "")),
                                ))
                    except Exception as e2:
                        _all_findings.append((rpt, f"ERROR: {e2}", "Error", "", "", "3"))
                else:
                    _all_findings.append((rpt, f"ERROR: {e}", "Error", "", "", "3"))

        _build_results()
        n = len([f for f in _all_findings if not f[1].startswith("ERROR")])
        set_status(conn_status, f"\u2713 Report BPA: {n} finding(s) across {len(items)} report(s).", "#34c759" if n == 0 else "#ff9500")
        load_btn.disabled = False
        load_btn.description = "Run Report BPA"

    def _build_results():
        if not _all_findings:
            results_box.children = [widgets.HTML(
                value=f'<div style="color:#34c759; font-size:14px; font-weight:600;">\u2713 No violations found.</div>'
            )]
            return
        html = '<div style="overflow-x:auto;"><table style="border-collapse:collapse; min-width:100%; font-size:11px; font-family:monospace;">'
        html += '<tr style="background:#f5f5f5; position:sticky; top:0; z-index:1;">'
        for hdr in ["#", "Report", "Rule", "Type", "Object", "Sev"]:
            html += f'<th style="text-align:left; padding:4px 8px; border-bottom:2px solid {BORDER_COLOR}; white-space:nowrap;">{hdr}</th>'
        html += '</tr>'
        for idx, (rpt, rule_name, category, obj_name, obj_type, severity) in enumerate(_all_findings):
            if rule_name.startswith("ERROR"):
                html += f'<tr><td colspan="6" style="color:#ff3b30; padding:3px 8px;">\u274c {rpt}: {rule_name}</td></tr>'
                continue
            sev_color = "#ff3b30" if severity in ("3",) else "#ff9500" if severity in ("2",) else "#888"
            html += '<tr>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; color:#888;">{idx+1}</td>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; white-space:nowrap;" title="{rpt}">{rpt[:16]}</td>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; color:{ICON_ACCENT}; white-space:nowrap;" title="{rule_name}">{rule_name[:40]}</td>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; color:#888;">{obj_type[:12]}</td>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; white-space:nowrap;" title="{obj_name}">{obj_name[:40]}</td>'
            html += f'<td style="padding:3px 8px; border-bottom:1px solid #f0f0f0; color:{sev_color}; font-weight:600;">{severity}</td>'
            html += '</tr>'
        html += '</table></div>'
        summary = widgets.HTML(
            value=f'<div style="font-size:12px; font-family:{FONT_FAMILY}; color:#555; margin:8px 0 4px 0;">'
            f'{len(_all_findings)} finding(s)</div>'
        )
        results_box.children = [widgets.HTML(value=html), summary]

    def on_show_native(_):
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        rpt_input = report_input.value.strip() if report_input else ""
        items = [x.strip() for x in rpt_input.split(",") if x.strip()] if rpt_input else []
        if not items:
            set_status(conn_status, "Enter a report name.", "#ff3b30")
            return
        show_full_btn.disabled = True
        show_full_btn.description = "Loading\u2026"
        native_output.clear_output()
        with native_output:
            for rpt in items:
                try:
                    from sempy_labs.report import run_report_bpa
                    run_report_bpa(report=rpt, workspace=ws)
                except Exception as e:
                    from IPython.display import display, HTML
                    display(HTML(f'<div style="color:red;">Error for {rpt}: {e}</div>'))
        show_full_btn.disabled = False
        show_full_btn.description = "\U0001F4CB Show Native"

    load_btn.on_click(on_load)
    show_full_btn.on_click(on_show_native)

    widget = widgets.VBox([nav_row, header_label, results_box, native_output], layout=widgets.Layout(padding="12px", gap="4px"))
    return widget


# ---------------------------------------------------------------------------
# Delta Analyzer tab (inline)
# ---------------------------------------------------------------------------
def _delta_analyzer_tab(workspace_input=None, report_input=None):
    """Build the Delta Analyzer tab with full DataFrame subtabs."""
    from sempy_labs._ui_components import (
        FONT_FAMILY, BORDER_COLOR, GRAY_COLOR, ICON_ACCENT, SECTION_BG,
        status_html, set_status,
    )

    _da_data = {}  # dict of DataFrames from delta_analyzer

    table_input = widgets.Text(placeholder="Delta table name", layout=widgets.Layout(width="200px"))
    lakehouse_input = widgets.Text(placeholder="Lakehouse (optional)", layout=widgets.Layout(width="180px"))
    schema_input = widgets.Text(placeholder="Schema (optional)", layout=widgets.Layout(width="130px"))
    col_stats_cb = widgets.Checkbox(value=True, description="Column stats", indent=False, layout=widgets.Layout(width="120px"))
    cardinality_cb = widgets.Checkbox(value=False, description="Cardinality", indent=False, layout=widgets.Layout(width="110px"))
    load_btn = widgets.Button(description="Analyze", button_style="primary", layout=widgets.Layout(width="100px"))
    show_native_btn = widgets.Button(description="\U0001F4CB Show Native", layout=widgets.Layout(width="130px"))
    conn_status = status_html()

    input_row = widgets.HBox(
        [table_input, lakehouse_input, schema_input, col_stats_cb, cardinality_cb],
        layout=widgets.Layout(align_items="center", gap="6px", margin="0 0 4px 0"),
    )
    nav_row = widgets.HBox(
        [load_btn, show_native_btn, conn_status],
        layout=widgets.Layout(align_items="center", gap="8px", margin="0 0 8px 0"),
    )

    _DF_TABS = ["Summary", "Parquet Files", "Row Groups", "Column Chunks", "Columns"]
    subtab_selector = widgets.ToggleButtons(
        options=_DF_TABS,
        value="Summary",
        layout=widgets.Layout(width="100%"),
        style={"button_width": "auto", "font_weight": "bold"},
    )
    df_html = widgets.HTML(
        value=f'<div style="padding:12px; color:{GRAY_COLOR}; font-size:13px; font-family:{FONT_FAMILY}; font-style:italic;">Enter a delta table name and click Analyze.</div>',
    )
    df_container = widgets.VBox(
        [df_html],
        layout=widgets.Layout(
            max_height="450px", overflow_y="auto", overflow_x="auto",
            border=f"1px solid {BORDER_COLOR}", border_radius="8px",
            padding="8px", background_color=SECTION_BG,
        ),
    )
    native_output = widgets.Output()

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

    def _fmt_val(val, col_name):
        if val is None or (isinstance(val, float) and val != val):
            return "\u2014"
        if "Size" in col_name or "Bytes" in col_name:
            return _fmt_bytes(val)
        if isinstance(val, (int, float)):
            if isinstance(val, float) and val == int(val):
                try:
                    return f"{int(val):,}"
                except (TypeError, ValueError):
                    return str(val)
            if isinstance(val, float):
                return f"{val:,.1f}"
            return f"{val:,}"
        return str(val)

    def _df_to_html(df, sort_by=None):
        if df is None or len(df) == 0:
            return f'<div style="color:{GRAY_COLOR}; font-size:13px;">No data available.</div>'
        if sort_by and sort_by in df.columns:
            df = df.sort_values(sort_by, ascending=False)
        html = '<div style="overflow-x:auto;"><table style="border-collapse:collapse; min-width:100%; font-size:11px; font-family:monospace;">'
        html += '<tr style="background:#f5f5f5; position:sticky; top:0; z-index:1;">'
        for col in df.columns:
            align = "right" if any(k in col for k in ("Size", "Count", "Bytes", "Rows", "%", "Cardinality", "Min", "Max", "Avg")) else "left"
            html += f'<th style="text-align:{align}; padding:4px 8px; border-bottom:2px solid {BORDER_COLOR}; white-space:nowrap;">{col}</th>'
        html += '</tr>'
        for _, row in df.iterrows():
            html += '<tr>'
            for col in df.columns:
                val = row.get(col, "")
                align = "right" if any(k in col for k in ("Size", "Count", "Bytes", "Rows", "%", "Cardinality", "Min", "Max", "Avg")) else "left"
                html += f'<td style="text-align:{align}; padding:3px 8px; border-bottom:1px solid #f0f0f0; white-space:nowrap;">{_fmt_val(val, col)}</td>'
            html += '</tr>'
        html += '</table></div>'
        return html

    def _render_subtab(tab_name=None):
        tab_name = tab_name or subtab_selector.value
        df = _da_data.get(tab_name)
        # Summary is single-row — render vertically
        if tab_name == "Summary" and df is not None and len(df) > 0:
            r = df.iloc[0]
            html = f'<table style="border-collapse:collapse; font-size:13px; font-family:{FONT_FAMILY}; width:100%;">'
            for col in df.columns:
                val = _fmt_val(r.get(col, ""), col)
                html += f'<tr><td style="padding:6px 12px; font-weight:600; color:#555; border-bottom:1px solid #f0f0f0; width:250px;">{col}</td>'
                html += f'<td style="padding:6px 12px; border-bottom:1px solid #f0f0f0;">{val}</td></tr>'
            html += '</table>'
            df_html.value = html
            return
        sort_by = None
        if df is not None:
            for c in ["Compressed Size", "Total Size", "Size", "Uncompressed Size"]:
                if c in df.columns:
                    sort_by = c
                    break
        df_html.value = _df_to_html(df, sort_by=sort_by)

    def on_subtab_change(change):
        _render_subtab(change.get("new"))

    subtab_selector.observe(on_subtab_change, names="value")

    def on_load(_):
        nonlocal _da_data
        t_name = table_input.value.strip()
        if not t_name:
            set_status(conn_status, "Enter a delta table name.", "#ff3b30")
            return
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        lh = lakehouse_input.value.strip() or None
        sch = schema_input.value.strip() or None
        load_btn.disabled = True
        load_btn.description = "Analyzing\u2026"
        set_status(conn_status, f"Analyzing '{t_name}'\u2026", GRAY_COLOR)
        try:
            import io as _io
            from contextlib import redirect_stdout as _redirect
            import IPython.display as _ipd
            _orig_display = _ipd.display
            _ipd.display = lambda *a, **kw: None
            try:
                buf = _io.StringIO()
                with _redirect(buf):
                    from sempy_labs import delta_analyzer as _da_fn
                    result = _da_fn(
                        table_name=t_name,
                        lakehouse=lh,
                        workspace=ws,
                        column_stats=col_stats_cb.value,
                        skip_cardinality=not cardinality_cb.value,
                        schema=sch,
                        visualize=False,
                    )
            finally:
                _ipd.display = _orig_display
            _da_data = result
            _render_subtab()
            n_keys = len(result)
            set_status(conn_status, f"\u2713 Delta Analyzer: {n_keys} views loaded for '{t_name}'.", "#34c759")
        except Exception as e:
            set_status(conn_status, f"Error: {e}", "#ff3b30")
        finally:
            load_btn.disabled = False
            load_btn.description = "Analyze"

    def on_show_native(_):
        """Run delta_analyzer with visualize=True and show the native HTML output below."""
        t_name = table_input.value.strip()
        if not t_name:
            set_status(conn_status, "Enter a delta table name.", "#ff3b30")
            return
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        lh = lakehouse_input.value.strip() or None
        sch = schema_input.value.strip() or None
        show_native_btn.disabled = True
        show_native_btn.description = "Loading\u2026"
        native_output.clear_output()
        with native_output:
            try:
                from sempy_labs import delta_analyzer as _da_fn
                _da_fn(
                    table_name=t_name,
                    lakehouse=lh,
                    workspace=ws,
                    column_stats=col_stats_cb.value,
                    skip_cardinality=not cardinality_cb.value,
                    schema=sch,
                    visualize=True,
                )
            except Exception as e:
                from IPython.display import display, HTML
                display(HTML(f'<div style="color:red;">Error: {e}</div>'))
        show_native_btn.disabled = False
        show_native_btn.description = "\U0001F4CB Show Native"

    load_btn.on_click(on_load)
    show_native_btn.on_click(on_show_native)

    header_label = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Delta Analyzer</div>'
        f'<div style="font-size:11px; color:#888; font-family:{FONT_FAMILY}; font-style:italic; margin-bottom:4px;">'
        f'Analyzes delta table structure: parquet files, row groups, column chunks, and column statistics.</div>'
    )

    tab_widget = widgets.VBox([input_row, nav_row, header_label, subtab_selector, df_container, native_output], layout=widgets.Layout(padding="12px", gap="4px"))
    return tab_widget

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

    # ---------------------------------------------------------------------------
    # Lazy imports — deferred to function call time to avoid circular imports.
    # Each fixer is optional; the UI degrades gracefully if not available.
    # ---------------------------------------------------------------------------
    fix_piecharts = _lazy_import("sempy_labs.report._Fix_PieChart", "fix_piecharts")
    fix_barcharts = _lazy_import("sempy_labs.report._Fix_BarChart", "fix_barcharts")
    fix_columncharts = _lazy_import("sempy_labs.report._Fix_ColumnChart", "fix_columncharts")
    fix_page_size = _lazy_import("sempy_labs.report._Fix_PageSize", "fix_page_size")
    fix_hide_visual_filters = _lazy_import("sempy_labs.report._Fix_HideVisualFilters", "fix_hide_visual_filters")
    fix_upgrade_to_pbir = _lazy_import("sempy_labs.report._Fix_UpgradeToPbir", "fix_upgrade_to_pbir")
    add_calculated_calendar = _lazy_import("sempy_labs.semantic_model._Add_CalculatedTable_Calendar", "add_calculated_calendar")
    fix_discourage_implicit_measures = _lazy_import("sempy_labs.semantic_model._Fix_DiscourageImplicitMeasures", "fix_discourage_implicit_measures")
    add_last_refresh_table = _lazy_import("sempy_labs.semantic_model._Add_Table_LastRefresh", "add_last_refresh_table")
    add_calc_group_units = _lazy_import("sempy_labs.semantic_model._Add_CalcGroup_Units", "add_calc_group_units")
    add_calc_group_time_intelligence = _lazy_import("sempy_labs.semantic_model._Add_CalcGroup_TimeIntelligence", "add_calc_group_time_intelligence")
    add_measure_table = _lazy_import("sempy_labs.semantic_model._Add_CalculatedTable_MeasureTable", "add_measure_table")
    add_measures_from_columns = _lazy_import("sempy_labs.semantic_model._Add_MeasuresFromColumns", "add_measures_from_columns")
    add_py_measures = _lazy_import("sempy_labs.semantic_model._Add_PYMeasures", "add_py_measures")

    # Inline fallbacks for MeasuresFromColumns and PYMeasures
    if add_measures_from_columns is None:
        def add_measures_from_columns(dataset, workspace=None, target_table=None, scan_only=False, **kw):
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
                        dest_tbl = tom.model.Tables[dest_name]
                        if dest_tbl.Measures.Find(col.Name) is not None:
                            continue
                        if scan_only:
                            print(f"  Would create: [{col.Name}] = {dax_expr}")
                            created += 1
                            continue
                        tom.add_measure(table_name=dest_name, measure_name=col.Name, expression=dax_expr, format_string="0.0", display_folder=table.Name)
                        col.IsHidden = True
                        created += 1
                        print(f"  Created [{col.Name}] = {dax_expr}")
                if not scan_only and created > 0:
                    tom.model.SaveChanges()
            print(f"  {'Would create' if scan_only else 'Created'} {created} measure(s) from columns.")
            return created

    if add_py_measures is None:
        def add_py_measures(dataset, workspace=None, measures=None, calendar_table=None, date_column=None, target_table=None, scan_only=False, **kw):
            from sempy_labs.tom import connect_semantic_model
            created = 0
            with connect_semantic_model(dataset=dataset, readonly=scan_only, workspace=workspace) as tom:
                cal = None
                if calendar_table:
                    cal = tom.model.Tables.Find(calendar_table)
                else:
                    for t in tom.model.Tables:
                        if str(getattr(t, "DataCategory", "")) == "Time":
                            cal = t; break
                if cal is None:
                    print("  No calendar table found."); return 0
                dt_col = date_column
                if not dt_col:
                    for c in cal.Columns:
                        if getattr(c, "IsKey", False): dt_col = c.Name; break
                    if not dt_col:
                        for c in cal.Columns:
                            if "date" in c.Name.lower(): dt_col = c.Name; break
                if not dt_col:
                    print(f"  No date column found in '{cal.Name}'."); return 0
                dest_tbl = tom.model.Tables.Find(target_table) if target_table else None
                src = [m for table in tom.model.Tables for m in table.Measures if measures is None or m.Name in measures]
                if not src:
                    print("  No measures found."); return 0
                for m in src:
                    n, fmt = m.Name, str(m.FormatString) if m.FormatString else ""
                    folder = str(m.DisplayFolder) if m.DisplayFolder else ""
                    py_folder = f"{folder}\\\\PY" if folder else "PY"
                    dest = dest_tbl or m.Table
                    for v_name, v_expr in [
                        (f"{n} PY", f"CALCULATE([{n}], SAMEPERIODLASTYEAR('{cal.Name}'[{dt_col}]))"),
                        (f"{n} \u0394 PY", f"[{n}] - [{n} PY]"),
                        (f"{n} \u0394 PY %", f"DIVIDE([{n}] - [{n} PY], [{n}])"),
                        (f"{n} Max Green PY", f"IF([{n} \u0394 PY] > 0, MAX([{n}], [{n} PY]))"),
                        (f"{n} Max Red AC", f"IF([{n} \u0394 PY] < 0, MAX([{n}], [{n} PY]))"),
                    ]:
                        if dest.Measures.Find(v_name) is not None: continue
                        if scan_only: print(f"  Would create: [{v_name}]"); created += 1; continue
                        tom.add_measure(table_name=dest.Name, measure_name=v_name, expression=v_expr, format_string=fmt, display_folder=py_folder)
                        created += 1
                if not scan_only and created > 0:
                    tom.model.SaveChanges()
            print(f"  {'Would create' if scan_only else 'Created'} {created} PY measure(s).")
            return created

    # Tab modules (deferred)
    sm_explorer_tab = _lazy_import("sempy_labs._sm_explorer", "sm_explorer_tab")
    report_explorer_tab = _lazy_import("sempy_labs._report_explorer", "report_explorer_tab")
    perspective_editor_tab = _lazy_import("sempy_labs._perspective_editor", "perspective_editor_tab")

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
    report_input = widgets.Combobox(
        value=str(report) if report else "",
        placeholder="Type, select, or comma-separate (blank = all)",
        options=[],
        ensure_option=False,
        layout=widgets.Layout(width="400px"),
    )
    page_input = widgets.Text(
        value=page_name if page_name else "",
        placeholder="Leave empty for all pages",
        layout=widgets.Layout(width="300px"),
    )

    list_items_btn = widgets.Button(
        description="\U0001F4CB List Items",
        layout=widgets.Layout(width="110px"),
    )
    list_items_status = widgets.HTML(value="")

    def _on_list_items(_):
        """Fetch all reports + datasets in the workspace and populate the Combobox options."""
        ws = workspace_input.value.strip() or None
        list_items_btn.disabled = True
        list_items_btn.description = "Listing\u2026"
        list_items_status.value = ""
        try:
            from sempy_labs._helper_functions import resolve_workspace_name_and_id, _base_api
            _, ws_id = resolve_workspace_name_and_id(ws)

            # Fetch reports
            rpt_url = f"/v1.0/myorg/groups/{ws_id}/reports"
            rpt_resp = _base_api(request=rpt_url, client="fabric_sp")
            rpt_names = [r.get("name") for r in rpt_resp.json().get("value", []) if r.get("name")]

            # Fetch datasets
            ds_url = f"/v1.0/myorg/groups/{ws_id}/datasets"
            ds_resp = _base_api(request=ds_url, client="fabric_sp")
            ds_names = [d.get("name") for d in ds_resp.json().get("value", []) if d.get("name")]

            # Deduplicate: if a name appears in both, show once; otherwise prefix with icon
            shared = set(n.lower() for n in rpt_names) & set(n.lower() for n in ds_names)
            combined = []
            seen_lower = set()
            for name in sorted(set(rpt_names + ds_names), key=str.lower):
                nl = name.lower()
                if nl in seen_lower:
                    continue
                seen_lower.add(nl)
                if nl in shared:
                    combined.append(name)
                elif name in rpt_names:
                    combined.append(f"\U0001F4C4 {name}")
                else:
                    combined.append(f"\U0001F4CA {name}")

            report_input.options = combined
            list_items_status.value = (
                f'<span style="font-size:12px; color:#34c759;">'
                f'{len(rpt_names)} report(s), {len(ds_names)} model(s)</span>'
            )
        except Exception as e:
            list_items_status.value = (
                f'<span style="font-size:12px; color:#ff3b30;">Error: {str(e)[:60]}</span>'
            )
        finally:
            list_items_btn.disabled = False
            list_items_btn.description = "\U0001F4CB List Items"

    list_items_btn.on_click(_on_list_items)

    def _strip_item_prefix(name):
        """Strip icon prefixes (📄 / 📊) from dropdown selections."""
        for prefix in ("\U0001F4C4 ", "\U0001F4CA "):
            if name.startswith(prefix):
                return name[len(prefix):]
        return name

    shared_inputs_box = widgets.VBox(
        [
            widgets.HBox(
                [_input_label("Workspace"), workspace_input],
                layout=widgets.Layout(align_items="center", gap="8px"),
            ),
            widgets.HBox(
                [_input_label("Report"), report_input, list_items_btn, list_items_status],
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
    # DOWNLOAD BUTTONS
    # -----------------------------
    download_pbix_btn = widgets.Button(description="\u2B07 Download .pbix", layout=widgets.Layout(width="140px"))
    download_pbip_btn = widgets.Button(description="\u2B07 Download .pbip", layout=widgets.Layout(width="140px"))
    download_status = widgets.HTML(value="")

    def _on_download_pbix(_):
        rpt = report_input.value.strip()
        ws = workspace_input.value.strip() or None
        if not rpt:
            download_status.value = f'<span style="color:#ff3b30; font-size:12px;">Enter a report name.</span>'
            return
        rpt = rpt.split(",")[0].strip()
        download_pbix_btn.disabled = True
        download_pbix_btn.description = "Downloading\u2026"
        download_status.value = f'<span style="color:#999; font-size:12px;">Downloading .pbix\u2026</span>'
        try:
            from sempy_labs.report import download_report
            download_report(report=rpt, workspace=ws)
            download_status.value = f'<span style="color:#34c759; font-size:12px;">\u2713 .pbix saved to lakehouse Files.</span>'
        except Exception as e:
            download_status.value = f'<span style="color:#ff3b30; font-size:12px;">Error: {str(e)[:80]}</span>'
        download_pbix_btn.disabled = False
        download_pbix_btn.description = "\u2B07 Download .pbix"

    def _on_download_pbip(_):
        rpt = report_input.value.strip()
        ws = workspace_input.value.strip() or None
        if not rpt:
            download_status.value = f'<span style="color:#ff3b30; font-size:12px;">Enter a report name.</span>'
            return
        rpt = rpt.split(",")[0].strip()
        download_pbip_btn.disabled = True
        download_pbip_btn.description = "Downloading\u2026"
        download_status.value = f'<span style="color:#999; font-size:12px;">Saving .pbip\u2026</span>'
        try:
            from sempy_labs.report import save_report_as_pbip
            save_report_as_pbip(report=rpt, workspace=ws)
            download_status.value = f'<span style="color:#34c759; font-size:12px;">\u2713 .pbip saved to lakehouse Files.</span>'
        except Exception as e:
            download_status.value = f'<span style="color:#ff3b30; font-size:12px;">Error: {str(e)[:80]}</span>'
        download_pbip_btn.disabled = False
        download_pbip_btn.description = "\u2B07 Download .pbip"

    download_pbix_btn.on_click(_on_download_pbix)
    download_pbip_btn.on_click(_on_download_pbip)

    # -----------------------------
    # CLONE BUTTONS (next to downloads)
    # -----------------------------
    clone_both_btn = widgets.Button(description="\U0001F4CB Clone Both", layout=widgets.Layout(width="120px"))
    clone_rpt_btn = widgets.Button(description="\U0001F4CB Clone Report", layout=widgets.Layout(width="130px"))
    clone_model_btn = widgets.Button(description="\U0001F4CB Clone Model", layout=widgets.Layout(width="130px"))

    def _resolve_report_model_name(rpt_name, ws):
        """Resolve the semantic model name backing a report."""
        try:
            from sempy_labs._helper_functions import resolve_workspace_name_and_id, _base_api
            _, ws_id = resolve_workspace_name_and_id(ws)
            url = f"/v1.0/myorg/groups/{ws_id}/reports"
            resp = _base_api(request=url, client="fabric_sp")
            for r in resp.json().get("value", []):
                if r.get("name") == rpt_name:
                    ds_id = r.get("datasetId", "")
                    if ds_id:
                        ds_url = f"/v1.0/myorg/groups/{ws_id}/datasets/{ds_id}"
                        ds_resp = _base_api(request=ds_url, client="fabric_sp")
                        return ds_resp.json().get("name", "")
        except Exception:
            pass
        return ""

    def _on_clone_report(_):
        rpt = _strip_item_prefix(report_input.value.strip())
        ws = workspace_input.value.strip() or None
        if not rpt:
            download_status.value = '<span style="color:#ff3b30; font-size:12px;">Enter a report name.</span>'
            return
        rpt = rpt.split(",")[0].strip()
        clone_rpt_btn.disabled = True
        download_status.value = f'<span style="color:#999; font-size:12px;">Cloning report\u2026</span>'
        try:
            from sempy_labs.report._report_functions import clone_report as _clone_rpt
            cloned = f"{rpt}_copy"
            _clone_rpt(report=rpt, cloned_report=cloned, workspace=ws)
            download_status.value = f'<span style="color:#34c759; font-size:12px;">\u2713 Report cloned as \'{cloned}\'.</span>'
        except Exception as e:
            download_status.value = f'<span style="color:#ff3b30; font-size:12px;">Error: {str(e)[:80]}</span>'
        clone_rpt_btn.disabled = False

    def _on_clone_model(_):
        rpt = _strip_item_prefix(report_input.value.strip())
        ws = workspace_input.value.strip() or None
        if not rpt:
            download_status.value = '<span style="color:#ff3b30; font-size:12px;">Enter a model name.</span>'
            return
        ds = rpt.split(",")[0].strip()
        clone_model_btn.disabled = True
        download_status.value = f'<span style="color:#999; font-size:12px;">Cloning model\u2026</span>'
        try:
            _clone_semantic_model_impl(ds, ws)
            download_status.value = f'<span style="color:#34c759; font-size:12px;">\u2713 Model cloned as \'{ds}_copy\'.</span>'
        except Exception as e:
            download_status.value = f'<span style="color:#ff3b30; font-size:12px;">Error: {str(e)[:80]}</span>'
        clone_model_btn.disabled = False

    def _clone_semantic_model_impl(ds, ws):
        """Clone a semantic model by name."""
        from sempy_labs._helper_functions import resolve_workspace_name_and_id, _base_api
        from sempy_labs._generate_semantic_model import create_semantic_model_from_bim
        import json, base64
        _, ws_id = resolve_workspace_name_and_id(ws)
        import sempy.fabric as fabric
        df = fabric.list_datasets(workspace=ws_id, mode="rest")
        df_filt = df[df["Dataset Name"] == ds]
        if df_filt.empty:
            raise ValueError(f"Model '{ds}' not found.")
        ds_id = str(df_filt.iloc[0]["Dataset Id"])
        url = f"v1/workspaces/{ws_id}/semanticModels/{ds_id}/getDefinition"
        resp = _base_api(request=url, method="post", lro_return_status_code=True, status_codes=[200, 202])
        if resp.status_code == 202:
            import time as _t
            loc = resp.headers.get("Location", "")
            retry = int(resp.headers.get("Retry-After", "5"))
            _t.sleep(retry + 2)
            resp = _base_api(request=f"{loc}/result", method="get")
        result = resp.json()
        bim_part = None
        for part in result.get("definition", {}).get("parts", []):
            if part.get("path", "").endswith("model.bim"):
                bim_part = json.loads(base64.b64decode(part["payload"]).decode("utf-8"))
                break
        if bim_part is None:
            raise ValueError("Could not extract model.bim.")
        create_semantic_model_from_bim(dataset=f"{ds}_copy", bim_file=bim_part, workspace=ws)

    def _on_clone_both(_):
        rpt = _strip_item_prefix(report_input.value.strip())
        ws = workspace_input.value.strip() or None
        if not rpt:
            download_status.value = '<span style="color:#ff3b30; font-size:12px;">Enter a report name.</span>'
            return
        rpt = rpt.split(",")[0].strip()
        clone_both_btn.disabled = True

        # Resolve the model name backing this report
        model_name = _resolve_report_model_name(rpt, ws)

        # Name mismatch warning
        if model_name and model_name != rpt:
            download_status.value = (
                f'<span style="color:#ff9500; font-size:12px;">'
                f'\u26a0\ufe0f Report \'{rpt}\' uses model \'{model_name}\'. '
                f'Cloning both\u2026</span>'
            )
        else:
            download_status.value = f'<span style="color:#999; font-size:12px;">Cloning model + report\u2026</span>'

        ds = model_name or rpt
        try:
            # 1. Clone model
            download_status.value = f'<span style="color:#999; font-size:12px;">Cloning model \'{ds}\'\u2026</span>'
            _clone_semantic_model_impl(ds, ws)
            # 2. Clone report, rebound to new model
            download_status.value = f'<span style="color:#999; font-size:12px;">Cloning report \'{rpt}\'\u2026</span>'
            from sempy_labs.report._report_functions import clone_report as _clone_rpt
            _clone_rpt(report=rpt, cloned_report=f"{rpt}_copy", workspace=ws, target_dataset=f"{ds}_copy")
            download_status.value = (
                f'<span style="color:#34c759; font-size:12px;">'
                f'\u2713 Cloned \'{rpt}_copy\' + \'{ds}_copy\'.</span>'
            )
        except Exception as e:
            download_status.value = f'<span style="color:#ff3b30; font-size:12px;">Error: {str(e)[:80]}</span>'
        clone_both_btn.disabled = False

    clone_both_btn.on_click(_on_clone_both)
    clone_rpt_btn.on_click(_on_clone_report)
    clone_model_btn.on_click(_on_clone_model)

    download_row = widgets.HBox(
        [download_pbix_btn, download_pbip_btn, clone_both_btn, clone_rpt_btn, clone_model_btn, download_status],
        layout=widgets.Layout(align_items="center", gap="8px", margin="0 0 8px 0", flex_wrap="wrap"),
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
    _tab_options.append("\U0001F4C4 Report BPA")
    _tab_options.append("\U0001F4D0 Delta Analyzer")
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
        items = [_strip_item_prefix(x.strip()) for x in report_val.split(",") if x.strip()] if report_val else []

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

    # BPA standalone fixers — also available as SM Explorer actions
    _bpa_fix_floating = _lazy_import("sempy_labs.semantic_model._Fix_FloatingPointDataType", "fix_floating_point_datatype")
    _bpa_fix_mdx = _lazy_import("sempy_labs.semantic_model._Fix_IsAvailableInMdx", "fix_isavailable_in_mdx")
    _bpa_fix_desc = _lazy_import("sempy_labs.semantic_model._Fix_MeasureDescriptions", "fix_measure_descriptions")
    _bpa_fix_date = _lazy_import("sempy_labs.semantic_model._Fix_DateColumnFormat", "fix_date_column_format")
    _bpa_fix_month = _lazy_import("sempy_labs.semantic_model._Fix_MonthColumnFormat", "fix_month_column_format")
    _bpa_fix_fmt = _lazy_import("sempy_labs.semantic_model._Fix_MeasureFormat", "fix_measure_format")
    _bpa_fix_fk = _lazy_import("sempy_labs.semantic_model._Fix_HideForeignKeys", "fix_hide_foreign_keys")

    if _bpa_fix_floating is not None:
        _sm_fixer_cbs["Fix Floating Point Types"] = lambda **kw: _bpa_fix_floating(dataset=kw.get("report", ""), workspace=kw.get("workspace"), scan_only=kw.get("scan_only", False))
    if _bpa_fix_mdx is not None:
        _sm_fixer_cbs["Fix IsAvailableInMDX"] = lambda **kw: _bpa_fix_mdx(dataset=kw.get("report", ""), workspace=kw.get("workspace"), scan_only=kw.get("scan_only", False))
    if _bpa_fix_desc is not None:
        _sm_fixer_cbs["Fix Measure Descriptions"] = lambda **kw: _bpa_fix_desc(dataset=kw.get("report", ""), workspace=kw.get("workspace"), scan_only=kw.get("scan_only", False))
    if _bpa_fix_fk is not None:
        _sm_fixer_cbs["Hide Foreign Keys"] = lambda **kw: _bpa_fix_fk(dataset=kw.get("report", ""), workspace=kw.get("workspace"), scan_only=kw.get("scan_only", False))

    # -- Clone callbacks (for action dropdowns — reuse shared impl) --
    def _clone_report(**kw):
        """Clone the report (appends '_copy' to the name)."""
        rpt = kw.get("report", "")
        ws = kw.get("workspace")
        if not rpt:
            print("No report specified.")
            return
        cloned_name = f"{rpt}_copy"
        print(f"Cloning report '{rpt}' \u2192 '{cloned_name}'\u2026")
        from sempy_labs.report._report_functions import clone_report as _clone_rpt
        _clone_rpt(report=rpt, cloned_report=cloned_name, workspace=ws)
        print(f"\u2713 Report cloned as '{cloned_name}'.")

    _rpt_fixer_cbs["\U0001F4CB Clone Report"] = lambda **kw: _clone_report(**kw)

    def _clone_semantic_model(**kw):
        """Clone the semantic model via shared impl."""
        ds = kw.get("report", "")
        ws = kw.get("workspace")
        if not ds:
            print("No model specified.")
            return
        print(f"Cloning model '{ds}' \u2192 '{ds}_copy'\u2026")
        _clone_semantic_model_impl(ds, ws)
        print(f"\u2713 Semantic model cloned as '{ds}_copy'.")

    _sm_fixer_cbs["\U0001F4CB Clone Model"] = lambda **kw: _clone_semantic_model(**kw)

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

    # Report BPA tab
    rpt_bpa_content = _report_bpa_tab(
        workspace_input=workspace_input, report_input=report_input
    )
    tab_panels.append(rpt_bpa_content)

    # Delta Analyzer tab
    da_content = _delta_analyzer_tab(
        workspace_input=workspace_input, report_input=report_input
    )
    tab_panels.append(da_content)

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
        [header, shared_inputs_box, download_row, tab_selector] + tab_panels + [version_footer],
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
