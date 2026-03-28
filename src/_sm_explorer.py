# Semantic Model Explorer tab for PBI Fixer.
# Provides a tree view of tables, columns, measures, hierarchies and
# calculation groups with DAX expression preview and editable properties.

import ipywidgets as widgets
import time

from sempy_labs._ui_components import (
    FONT_FAMILY,
    BORDER_COLOR,
    GRAY_COLOR,
    ICON_ACCENT,
    SECTION_BG,
    ICONS,
    EXPANDED,
    COLLAPSED,
    build_tree_items,
    create_three_panel_layout,
    status_html,
    set_status,
    panel_box,
)

_LOAD_TIMEOUT = 300  # 5 minutes


def _list_workspace_datasets(workspace):
    """List all semantic model names in a workspace via REST API."""
    from sempy_labs._helper_functions import (
        resolve_workspace_name_and_id,
        _base_api,
    )
    _, ws_id = resolve_workspace_name_and_id(workspace)
    url = f"/v1.0/myorg/groups/{ws_id}/datasets"
    response = _base_api(request=url, client="fabric_sp")
    return [d.get("name") for d in response.json().get("value", []) if d.get("name")]


def _load_model_data_fast(dataset, workspace):
    """
    Load model metadata using sempy.fabric DataFrames (fast REST API).
    Falls back to TOM for hierarchies, calc groups, and table type detection.
    """
    import sempy.fabric as fabric
    from sempy_labs.tom import connect_semantic_model

    model_data = {"tables": {}, "relationships": []}
    try:
        tables_df = fabric.list_tables(dataset, workspace)
        columns_df = fabric.list_columns(dataset, workspace, extended=True)
        measures_df = fabric.list_measures(dataset, workspace)
    except Exception:
        return _load_model_data_tom(dataset, workspace)

    for _, row in tables_df.iterrows():
        t_name = str(row.get("Name", ""))
        if not t_name:
            continue
        model_data["tables"][t_name] = {
            "description": str(row.get("Description", "") or ""),
            "is_hidden": bool(row.get("Is Hidden", False)),
            "type": "Table",
            "columns": {},
            "measures": {},
            "hierarchies": {},
            "calc_items": {},
        }

    for _, row in columns_df.iterrows():
        t_name = str(row.get("Table Name", ""))
        c_name = str(row.get("Column Name", row.get("Name", "")))
        if t_name not in model_data["tables"] or not c_name:
            continue
        model_data["tables"][t_name]["columns"][c_name] = {
            "data_type": str(row.get("Data Type", "")),
            "is_hidden": bool(row.get("Is Hidden", False)),
            "expression": str(row.get("Expression", "")) if row.get("Expression") else None,
            "type": str(row.get("Column Type", row.get("Type", ""))),
            "summarize_by": str(row.get("Summarize By", "")) if row.get("Summarize By") else "",
        }

    for _, row in measures_df.iterrows():
        t_name = str(row.get("Table Name", ""))
        m_name = str(row.get("Measure Name", row.get("Name", "")))
        if t_name not in model_data["tables"] or not m_name:
            continue
        model_data["tables"][t_name]["measures"][m_name] = {
            "expression": str(row.get("Measure Expression", row.get("Expression", "")) or ""),
            "format_string": str(row.get("Measure Format String", row.get("Format String", "")) or ""),
            "description": str(row.get("Measure Description", row.get("Description", "")) or ""),
            "display_folder": str(row.get("Measure Display Folder", row.get("Display Folder", "")) or ""),
        }

    # Hierarchies, calc groups, table types require TOM (short connection)
    try:
        with connect_semantic_model(dataset=dataset, readonly=True, workspace=workspace) as tm:
            for table in tm.model.Tables:
                t_name = table.Name
                if t_name not in model_data["tables"]:
                    continue
                t_info = model_data["tables"][t_name]
                try:
                    if table.CalculationGroup is not None:
                        t_info["type"] = "CalculationGroup"
                        for ci in table.CalculationGroup.CalculationItems:
                            t_info["calc_items"][ci.Name] = {
                                "expression": str(ci.Expression) if ci.Expression else "",
                                "ordinal": int(ci.Ordinal) if hasattr(ci, "Ordinal") else 0,
                            }
                        continue
                except Exception:
                    pass
                partitions = []
                try:
                    for p in table.Partitions:
                        if "Calculated" in str(p.SourceType):
                            t_info["type"] = "CalculatedTable"
                        src_type = str(p.SourceType) if hasattr(p, "SourceType") else ""
                        expr = ""
                        try:
                            if hasattr(p, "Source") and hasattr(p.Source, "Expression"):
                                expr = str(p.Source.Expression) if p.Source.Expression else ""
                        except Exception:
                            pass
                        partitions.append({
                            "name": str(p.Name),
                            "source_type": src_type,
                            "expression": expr,
                        })
                except Exception:
                    pass
                t_info["partitions"] = partitions
                for h in table.Hierarchies:
                    t_info["hierarchies"][h.Name] = {"levels": [str(lvl.Name) for lvl in h.Levels]}

            # Load relationships
            for rel in tm.model.Relationships:
                try:
                    model_data["relationships"].append({
                        "from_table": str(rel.FromTable.Name),
                        "from_column": str(rel.FromColumn.Name),
                        "to_table": str(rel.ToTable.Name),
                        "to_column": str(rel.ToColumn.Name),
                        "cross_filter": str(rel.CrossFilteringBehavior) if hasattr(rel, "CrossFilteringBehavior") else "",
                        "is_active": bool(rel.IsActive) if hasattr(rel, "IsActive") else True,
                        "multiplicity": str(rel.FromCardinality) + " → " + str(rel.ToCardinality) if hasattr(rel, "FromCardinality") else "",
                    })
                except Exception:
                    pass

            # Load perspectives
            for p in tm.model.Perspectives:
                model_data["perspectives"].append(str(p.Name))

            # Load model properties
            model_data["model_properties"] = {
                "compatibility_level": str(tm.model.Model.Database.CompatibilityLevel) if hasattr(tm.model.Model, "Database") else "",
                "default_mode": str(tm.model.DefaultMode) if hasattr(tm.model, "DefaultMode") else "",
            }
    except Exception:
        pass

    return model_data


def _load_model_data_tom(dataset, workspace):
    """Fallback: load everything via TOM (slower but complete)."""
    from sempy_labs.tom import connect_semantic_model

    model_data = {"tables": {}, "relationships": [], "perspectives": []}
    with connect_semantic_model(dataset=dataset, readonly=True, workspace=workspace) as tm:
        for table in tm.model.Tables:
            t_name = table.Name
            t_info = {
                "description": str(table.Description or ""),
                "is_hidden": bool(table.IsHidden),
                "type": "Table",
                "columns": {},
                "measures": {},
                "hierarchies": {},
                "calc_items": {},
            }
            is_calc_group = False
            try:
                if table.CalculationGroup is not None:
                    is_calc_group = True
                    t_info["type"] = "CalculationGroup"
            except Exception:
                pass
            if not is_calc_group:
                partitions = []
                try:
                    for p in table.Partitions:
                        if "Calculated" in str(p.SourceType):
                            t_info["type"] = "CalculatedTable"
                        src_type = str(p.SourceType) if hasattr(p, "SourceType") else ""
                        expr = ""
                        try:
                            if hasattr(p, "Source") and hasattr(p.Source, "Expression"):
                                expr = str(p.Source.Expression) if p.Source.Expression else ""
                        except Exception:
                            pass
                        partitions.append({
                            "name": str(p.Name),
                            "source_type": src_type,
                            "expression": expr,
                        })
                except Exception:
                    pass
                t_info["partitions"] = partitions
            for col in table.Columns:
                t_info["columns"][col.Name] = {
                    "data_type": str(col.DataType) if hasattr(col, "DataType") else "",
                    "is_hidden": bool(col.IsHidden),
                    "expression": str(col.Expression) if hasattr(col, "Expression") and col.Expression else None,
                    "type": str(col.Type) if hasattr(col, "Type") else "",
                    "summarize_by": str(col.SummarizeBy) if hasattr(col, "SummarizeBy") else "",
                }
            for m in table.Measures:
                t_info["measures"][m.Name] = {
                    "expression": str(m.Expression) if m.Expression else "",
                    "format_string": str(m.FormatString) if m.FormatString else "",
                    "description": str(m.Description) if m.Description else "",
                    "display_folder": str(m.DisplayFolder) if m.DisplayFolder else "",
                }
            for h in table.Hierarchies:
                t_info["hierarchies"][h.Name] = {"levels": [str(lvl.Name) for lvl in h.Levels]}
            if is_calc_group:
                try:
                    for ci in table.CalculationGroup.CalculationItems:
                        t_info["calc_items"][ci.Name] = {
                            "expression": str(ci.Expression) if ci.Expression else "",
                            "ordinal": int(ci.Ordinal) if hasattr(ci, "Ordinal") else 0,
                        }
                except Exception:
                    pass
            model_data["tables"][t_name] = t_info

        # Load model properties
        model_data["model_properties"] = {
            "compatibility_level": str(tm.model.Model.Database.CompatibilityLevel) if hasattr(tm.model.Model, "Database") else "",
            "default_mode": str(tm.model.DefaultMode) if hasattr(tm.model, "DefaultMode") else "",
        }

        # Load relationships
        for rel in tm.model.Relationships:
            try:
                model_data["relationships"].append({
                    "from_table": str(rel.FromTable.Name),
                    "from_column": str(rel.FromColumn.Name),
                    "to_table": str(rel.ToTable.Name),
                    "to_column": str(rel.ToColumn.Name),
                    "cross_filter": str(rel.CrossFilteringBehavior) if hasattr(rel, "CrossFilteringBehavior") else "",
                    "is_active": bool(rel.IsActive) if hasattr(rel, "IsActive") else True,
                    "multiplicity": str(rel.FromCardinality) + " \u2192 " + str(rel.ToCardinality) if hasattr(rel, "FromCardinality") else "",
                })
            except Exception:
                pass

        # Load perspectives
        for p in tm.model.Perspectives:
            model_data["perspectives"].append(str(p.Name))
    return model_data


def _table_summary(t):
    """Return total child count for a table."""
    return str(len(t.get("columns", {})) + len(t.get("measures", {})) + len(t.get("hierarchies", {})) + len(t.get("calc_items", {})))


def _build_tree(model_data, expanded_tables, scan_results=None, pending_changes=None):
    """Build tree items, optionally annotating with scan findings."""
    scan_results = scan_results or {}
    pending_changes = pending_changes or {}
    items = []
    models = model_data.get("models", {})
    if models:
        for m_name in sorted(models):
            m_tables = models[m_name]
            is_model_expanded = m_name in expanded_tables
            marker = EXPANDED if is_model_expanded else COLLAPSED
            t_count = len(m_tables)
            model_findings = scan_results.get(f"model:{m_name}", 0)
            badge = f" \u26a0\ufe0f{model_findings}" if model_findings > 0 else ""
            items.append((0, "calc_group", f"{marker} {m_name}  [{t_count} tables]{badge}", f"model:{m_name}"))
            if not is_model_expanded:
                continue
            for t_name in sorted(m_tables):
                t = m_tables[t_name]
                icon = "calc_group" if t["type"] == "CalculationGroup" else "table"
                full_key = f"{m_name}\x1f{t_name}"
                is_expanded = full_key in expanded_tables
                t_marker = EXPANDED if is_expanded else COLLAPSED
                suffix = " (hidden)" if t["is_hidden"] else ""
                summary = _table_summary(t)
                items.append((1, icon, f"{t_marker} {t_name}{suffix}  [{summary}]", f"table:{full_key}"))
                if not is_expanded:
                    continue
                for mn in sorted(t["measures"]):
                    mk = f"measure:{full_key}:{mn}"
                    pfx = "\u270f " if mk in pending_changes else ""
                    items.append((2, "measure", f"{pfx}{mn}", mk))
                for cn in sorted(t["columns"]):
                    c = t["columns"][cn]
                    hidden = " (hidden)" if c["is_hidden"] else ""
                    ck = f"column:{full_key}:{cn}"
                    pfx = "\u270f " if ck in pending_changes else ""
                    items.append((2, "column", f"{pfx}{cn} [{c['data_type']}]{hidden}", ck))
                for hn in sorted(t["hierarchies"]):
                    lvl_str = " \u2192 ".join(t["hierarchies"][hn]["levels"])
                    items.append((2, "hierarchy", f"{hn}  ({lvl_str})", f"hierarchy:{full_key}:{hn}"))
                for ci_name in sorted(t.get("calc_items", {}), key=lambda n: t["calc_items"][n]["ordinal"]):
                    items.append((2, "calc_item", ci_name, f"calc_item:{full_key}:{ci_name}"))
                # Partitions
                for pt in t.get("partitions", []):
                    items.append((2, "partition", f"{pt['name']} ({pt['source_type']})", f"partition:{full_key}:{pt['name']}"))
            # Relationships for this model
            m_rels = model_data.get("model_relationships", {}).get(m_name, [])
            if m_rels:
                rel_key = f"rels:{m_name}"
                is_rels_exp = rel_key in expanded_tables
                r_marker = EXPANDED if is_rels_exp else COLLAPSED
                items.append((1, "relationship", f"{r_marker} Relationships  [{len(m_rels)}]", rel_key))
                if is_rels_exp:
                    for i, rel in enumerate(m_rels):
                        active = "" if rel.get("is_active", True) else " (inactive)"
                        label = f"{rel['from_table']}[{rel['from_column']}] \u2194 {rel['to_table']}[{rel['to_column']}]{active}"
                        items.append((2, "relationship", label, f"rel:{m_name}:{i}"))
            # Perspectives for this model
            m_persps = model_data.get("model_perspectives", {}).get(m_name, [])
            if m_persps:
                items.append((1, "folder", f"Perspectives  [{len(m_persps)}]", f"persps:{m_name}"))
                for pname in sorted(m_persps):
                    items.append((2, "calc_item", pname, f"persp:{m_name}:{pname}"))
    else:
        # Single model: show model node (always visible for refresh/properties)
        ds_input = model_data.get("_dataset_name", "Model")
        props = model_data.get("model_properties", {})
        compat = props.get("compatibility_level", "")
        mode = props.get("default_mode", "")
        prop_str = f" ({mode}, CL {compat})" if compat else ""
        t_count = len(model_data.get("tables", {}))
        is_model_exp = ds_input in expanded_tables
        marker = EXPANDED if is_model_exp else COLLAPSED
        items.append((0, "calc_group", f"{marker} {ds_input}{prop_str}  [{t_count} tables]", f"model:{ds_input}"))
        if not is_model_exp:
            pass  # collapsed
        else:
          for t_name in sorted(model_data["tables"]):
            t = model_data["tables"][t_name]
            icon = "calc_group" if t["type"] == "CalculationGroup" else "table"
            is_expanded = t_name in expanded_tables
            marker = EXPANDED if is_expanded else COLLAPSED
            suffix = " (hidden)" if t["is_hidden"] else ""
            summary = _table_summary(t)
            items.append((1, icon, f"{marker} {t_name}{suffix}  [{summary}]", f"table:{t_name}"))
            if not is_expanded:
                continue
            for mn in sorted(t["measures"]):
                mk = f"measure:{t_name}:{mn}"
                pfx = "\u270f " if mk in pending_changes else ""
                items.append((2, "measure", f"{pfx}{mn}", mk))
            for cn in sorted(t["columns"]):
                c = t["columns"][cn]
                hidden = " (hidden)" if c["is_hidden"] else ""
                ck = f"column:{t_name}:{cn}"
                pfx = "\u270f " if ck in pending_changes else ""
                items.append((2, "column", f"{pfx}{cn} [{c['data_type']}]{hidden}", ck))
            for hn in sorted(t["hierarchies"]):
                lvl_str = " \u2192 ".join(t["hierarchies"][hn]["levels"])
                items.append((2, "hierarchy", f"{hn}  ({lvl_str})", f"hierarchy:{t_name}:{hn}"))
            for ci_name in sorted(t.get("calc_items", {}), key=lambda n: t["calc_items"][n]["ordinal"]):
                items.append((2, "calc_item", ci_name, f"calc_item:{t_name}:{ci_name}"))
            # Partitions
            for pt in t.get("partitions", []):
                items.append((2, "partition", f"{pt['name']} ({pt['source_type']})", f"partition:{t_name}:{pt['name']}"))
          # Relationships (single model) — under model node
          rels = model_data.get("relationships", [])
          if rels:
            rel_key = "rels:_single"
            is_rels_exp = rel_key in expanded_tables
            r_marker = EXPANDED if is_rels_exp else COLLAPSED
            items.append((1, "relationship", f"{r_marker} Relationships  [{len(rels)}]", rel_key))
            if is_rels_exp:
                for i, rel in enumerate(rels):
                    active = "" if rel.get("is_active", True) else " (inactive)"
                    label = f"{rel['from_table']}[{rel['from_column']}] \u2194 {rel['to_table']}[{rel['to_column']}]{active}"
                    items.append((2, "relationship", label, f"rel:_single:{i}"))
          # Perspectives (single model) — under model node
          persps = model_data.get("perspectives", [])
          if persps:
            items.append((1, "folder", f"Perspectives  [{len(persps)}]", "persps:_single"))
            for pname in sorted(persps):
                items.append((2, "calc_item", pname, f"persp:_single:{pname}"))
    return build_tree_items(items)


def _resolve_table(model_data, table_key):
    """Resolve a table key to its data dict. Handles both single and multi-model keys."""
    if "\x1f" in table_key:
        m_name, t_name = table_key.split("\x1f", 1)
        return model_data.get("models", {}).get(m_name, {}).get(t_name)
    return model_data.get("tables", {}).get(table_key)


def _get_preview_text(model_data, key):
    parts = key.split(":", 2)
    node_type = parts[0]
    if node_type in ("rels",):
        return ""
    if node_type == "model":
        # Show model properties
        props = model_data.get("model_properties", {})
        if not props:
            for m_data in model_data.get("models", {}).values():
                break  # multi-model: can't show single model props here
        lines = []
        for k, v in props.items():
            lines.append(f"{k}: {v}")
        return "\n".join(lines) if lines else ""
    if node_type == "partition":
        # Show M script for partition
        raw_table = parts[1] if len(parts) > 1 else ""
        p_name = parts[2] if len(parts) > 2 else ""
        t = _resolve_table(model_data, raw_table)
        if t:
            for pt in t.get("partitions", []):
                if pt["name"] == p_name:
                    return pt.get("expression", "")
        return ""
    if node_type == "rel":
        # Show relationship details
        m_name = parts[1] if len(parts) > 1 else ""
        idx = int(parts[2]) if len(parts) > 2 else -1
        if m_name == "_single":
            rels = model_data.get("relationships", [])
        else:
            rels = model_data.get("model_relationships", {}).get(m_name, [])
        if 0 <= idx < len(rels):
            r = rels[idx]
            return (
                f"From: '{r['from_table']}'[{r['from_column']}]\n"
                f"To:   '{r['to_table']}'[{r['to_column']}]\n"
                f"Multiplicity: {r.get('multiplicity', '')}\n"
                f"Cross-filter: {r.get('cross_filter', '')}\n"
                f"Active: {r.get('is_active', True)}"
            )
        return ""
    if node_type == "measure":
        t = _resolve_table(model_data, parts[1])
        return t["measures"].get(parts[2], {}).get("expression", "") if t else ""
    if node_type == "column":
        t = _resolve_table(model_data, parts[1])
        return (t["columns"].get(parts[2], {}).get("expression") or "") if t else ""
    if node_type == "calc_item":
        t = _resolve_table(model_data, parts[1])
        return t["calc_items"].get(parts[2], {}).get("expression", "") if t else ""
    return ""


def sm_explorer_tab(workspace_input=None, report_input=None, fixer_callbacks=None):
    """Build the Semantic Model Explorer tab widget."""
    _model_data = {}
    _key_map = {}
    _expanded = set()
    _current_key = [None]
    _selected_keys = []  # all currently selected keys for fixer actions
    _scan_results = {}  # key -> violation count

    load_btn = widgets.Button(description="Load Model", button_style="primary", layout=widgets.Layout(width="110px"))
    expand_btn = widgets.Button(description="Expand All", layout=widgets.Layout(width="100px"))
    collapse_btn = widgets.Button(description="Collapse All", layout=widgets.Layout(width="100px"))
    scan_btn = widgets.Button(description="\U0001F50D Scan", layout=widgets.Layout(width="110px"))

    fixer_callbacks = fixer_callbacks or {}
    fixer_dropdown = widgets.Dropdown(
        options=["Select action..."] + list(fixer_callbacks.keys()),
        value="Select action...",
        layout=widgets.Layout(width="208px"),
    )
    run_action_btn = widgets.Button(
        description="\u26A1 Run",
        button_style="danger",
        layout=widgets.Layout(width="100px"),
    )

    conn_status = status_html()
    nav_row = widgets.HBox(
        [load_btn, expand_btn, collapse_btn, conn_status],
        layout=widgets.Layout(align_items="center", gap="8px", margin="0 0 4px 0"),
    )
    action_row = widgets.HBox(
        [scan_btn, fixer_dropdown, run_action_btn],
        layout=widgets.Layout(align_items="center", gap="8px", margin="0 0 8px 0"),
    )

    tree = widgets.SelectMultiple(options=[], rows=18, layout=widgets.Layout(width="400px", height="450px", font_family="monospace"))

    def _refresh_tree():
        nonlocal _key_map
        options, _key_map = _build_tree(_model_data, _expanded, _scan_results, _pending_changes)
        tree.unobserve(on_select, names="value")
        tree.options = options
        try:
            tree.value = ()
        except Exception:
            pass
        tree.observe(on_select, names="value")

    # -- expression panel --
    preview = widgets.Textarea(value="Select a measure to view its DAX expression.", disabled=True, layout=widgets.Layout(width="100%", height="160px", font_family="monospace"))
    fmt_long_btn = widgets.Button(description="Format Long", layout=widgets.Layout(width="110px"))
    fmt_short_btn = widgets.Button(description="Format Short", layout=widgets.Layout(width="110px"))

    def _do_format_dax(max_line_length, btn):
        """Format the current DAX expression via daxformatter.com API."""
        expr = preview.value.strip()
        if not expr:
            return
        btn.disabled = True
        orig = btn.description
        btn.description = "Formatting\u2026"
        try:
            from sempy_labs._daxformatter import _format_dax
            formatted = _format_dax([expr])
            # Patch MaxLineLength into the call if needed
            if max_line_length > 0:
                import requests, json
                from sempy_labs._a_lib_info import lib_name, lib_version
                payload = {
                    "Dax": [f"x :={expr}"],
                    "MaxLineLength": max_line_length,
                    "SkipSpaceAfterFunctionName": False,
                    "ListSeparator": ",",
                    "DecimalSeparator": ".",
                }
                headers = {
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Content-Type": "application/json; charset=UTF-8",
                    "Host": "daxformatter.azurewebsites.net",
                    "CallerApp": lib_name,
                    "CallerVersion": lib_version,
                }
                resp = requests.post("https://daxformatter.azurewebsites.net/api/daxformatter/daxtextformatmulti", json=payload, headers=headers)
                result = resp.json()
                if result and result[0].get("formatted"):
                    txt = result[0]["formatted"]
                    if txt.startswith("x :="):
                        txt = txt[4:]
                    if txt.startswith("\r\n"):
                        txt = txt[2:]
                    elif txt.startswith("\n"):
                        txt = txt[1:]
                    preview.value = txt
                    btn.disabled = False
                    btn.description = orig
                    return
            if formatted and formatted[0]:
                preview.value = formatted[0]
        except Exception:
            pass
        btn.disabled = False
        btn.description = orig

    def on_format_long(_):
        _do_format_dax(0, fmt_long_btn)

    def on_format_short(_):
        _do_format_dax(80, fmt_short_btn)

    fmt_long_btn.on_click(on_format_long)
    fmt_short_btn.on_click(on_format_short)
    format_row = widgets.HBox([fmt_long_btn, fmt_short_btn], layout=widgets.Layout(gap="8px"))

    preview_label = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Expression</div>'
    )
    preview_box = panel_box([preview_label, preview, format_row], flex="1")

    # -- editable properties --
    props_label = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Properties</div>'
    )
    def _prop_input(label_text, width="200px", disabled=False):
        lbl = widgets.HTML(value=f'<span style="font-size:12px; font-weight:600; color:#555; font-family:{FONT_FAMILY}; min-width:110px; display:inline-block;">{label_text}</span>')
        inp = widgets.Text(layout=widgets.Layout(width=width), disabled=disabled)
        row = widgets.HBox([lbl, inp], layout=widgets.Layout(align_items="center", gap="4px"))
        return inp, row

    prop_name, prop_name_row = _prop_input("Name")
    prop_table, prop_table_row = _prop_input("Table", disabled=True)
    prop_obj_type, prop_type_row = _prop_input("Object Type", disabled=True)
    prop_format_str, prop_format_row = _prop_input("Format String")
    prop_display_folder, prop_folder_row = _prop_input("Display Folder")
    prop_description, prop_desc_row = _prop_input("Description", width="300px")
    prop_summarize_by, prop_summarize_row = _prop_input("Summarize By", disabled=True)

    # Unified save button with dirty state + pending changes buffer
    _is_dirty = [False]
    _pending_changes = {}  # key -> {expression, name, format_string, display_folder, description}
    _suppressing_observe = [False]  # prevent observe triggers during programmatic updates
    save_btn = widgets.Button(description="\u2713 No changes", button_style="success", disabled=True, layout=widgets.Layout(width="200px"))
    save_status = status_html()
    save_row = widgets.HBox([save_btn, save_status], layout=widgets.Layout(align_items="center", gap="8px", margin="8px 0 0 0"))

    # Refresh controls
    refresh_type_dd = widgets.Dropdown(
        options=["full", "dataOnly", "calculate", "automatic"],
        value="automatic",
        layout=widgets.Layout(width="130px"),
    )
    refresh_btn = widgets.Button(description="🔄 Refresh Model", layout=widgets.Layout(width="150px"))
    refresh_status = status_html()

    def on_refresh(_):
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        ds_input = report_input.value.strip() if report_input else ""
        key = _current_key[0] or ""
        refresh_btn.disabled = True
        refresh_btn.description = "Refreshing…"
        try:
            from sempy_labs import refresh_semantic_model
            r_type = refresh_type_dd.value

            # Determine what to refresh based on selection
            if key.startswith("partition:"):
                # Refresh single partition's table
                parts = key.split(":", 2)
                raw_table = parts[1] if len(parts) > 1 else ""
                if "\x1f" in raw_table:
                    ds, table_name = raw_table.split("\x1f", 1)
                else:
                    ds = ds_input
                    table_name = raw_table
                set_status(refresh_status, f"Refreshing table '{table_name}'…", GRAY_COLOR)
                refresh_semantic_model(dataset=ds, refresh_type=r_type, workspace=ws, tables=[table_name])
                set_status(refresh_status, f"✓ Table '{table_name}' refreshed.", "#34c759")
            elif key.startswith("table:"):
                raw_table = key.split(":", 1)[1]
                if "\x1f" in raw_table:
                    ds, table_name = raw_table.split("\x1f", 1)
                else:
                    ds = ds_input
                    table_name = raw_table
                set_status(refresh_status, f"Refreshing table '{table_name}'…", GRAY_COLOR)
                refresh_semantic_model(dataset=ds, refresh_type=r_type, workspace=ws, tables=[table_name])
                set_status(refresh_status, f"✓ Table '{table_name}' refreshed.", "#34c759")
            else:
                # Model-level refresh
                if key.startswith("model:"):
                    ds = key.split(":", 1)[1]
                elif _model_data.get("_dataset_name"):
                    ds = _model_data["_dataset_name"]
                else:
                    items_list = [x.strip() for x in ds_input.split(",") if x.strip()]
                    ds = items_list[0] if items_list else ""
                if not ds:
                    set_status(refresh_status, "No model selected.", "#ff3b30")
                    return
                set_status(refresh_status, f"Refreshing '{ds}'…", GRAY_COLOR)
                refresh_semantic_model(dataset=ds, refresh_type=r_type, workspace=ws)
                set_status(refresh_status, f"✓ Model '{ds}' refreshed.", "#34c759")
        except Exception as e:
            set_status(refresh_status, f"Error: {e}", "#ff3b30")
        finally:
            refresh_btn.disabled = False
            refresh_btn.description = "🔄 Refresh Model"

    refresh_btn.on_click(on_refresh)
    refresh_row = widgets.HBox([refresh_type_dd, refresh_btn, refresh_status], layout=widgets.Layout(align_items="center", gap="8px", margin="4px 0 0 0"))

    def _capture_current():
        """Store current field values as pending changes for the current key."""
        key = _current_key[0]
        if key and not _suppressing_observe[0]:
            node_type = key.split(":")[0]
            if node_type in ("measure", "calc_item", "column", "table"):
                _pending_changes[key] = {
                    "expression": preview.value,
                    "name": prop_name.value,
                    "format_string": prop_format_str.value,
                    "display_folder": prop_display_folder.value,
                    "description": prop_description.value,
                }

    def _mark_dirty(*_):
        if _suppressing_observe[0]:
            return
        if not _is_dirty[0]:
            _is_dirty[0] = True
        # Capture changes immediately
        _capture_current()
        n = len(_pending_changes)
        save_btn.description = f"\u26a0\ufe0f {n} unsaved change(s)"
        save_btn.button_style = "danger"
        save_btn.disabled = False

    def _mark_clean():
        _is_dirty[0] = False
        _pending_changes.clear()
        save_btn.description = "\u2713 No changes"
        save_btn.button_style = "success"
        save_btn.disabled = True
        save_status.value = ""

    # Observe editable fields for changes
    preview.observe(_mark_dirty, names="value")
    prop_name.observe(_mark_dirty, names="value")
    prop_format_str.observe(_mark_dirty, names="value")
    prop_display_folder.observe(_mark_dirty, names="value")
    prop_description.observe(_mark_dirty, names="value")

    props_container = widgets.VBox(
        [prop_name_row, prop_table_row, prop_type_row, prop_format_row, prop_folder_row, prop_summarize_row, prop_desc_row],
        layout=widgets.Layout(gap="4px"),
    )
    props_placeholder = widgets.HTML(
        value=f'<div style="padding:12px; color:{GRAY_COLOR}; font-size:13px; font-family:{FONT_FAMILY}; font-style:italic;">Select an object to view properties</div>',
    )
    props_container.layout.display = "none"
    props_box = panel_box([props_label, props_placeholder, props_container], flex="0 0 auto", min_height="150px")

    panels = create_three_panel_layout(tree, preview_box, props_box)
    tree_header = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Model Objects</div>'
    )

    def _populate_props(key):
        parts = key.split(":", 2)
        node_type = parts[0]
        props_placeholder.layout.display = "none"
        props_container.layout.display = ""
        prop_format_row.layout.display = ""
        prop_folder_row.layout.display = ""
        prop_summarize_row.layout.display = "none"

        # Strip model prefix from table key for display
        raw_table = parts[1] if len(parts) > 1 else ""
        display_table = raw_table.split("\x1f")[-1] if "\x1f" in raw_table else raw_table

        if node_type == "measure":
            t = _resolve_table(_model_data, raw_table)
            m = t["measures"].get(parts[2], {}) if t else {}
            prop_name.value, prop_table.value, prop_obj_type.value = parts[2], display_table, "Measure"
            prop_format_str.value = m.get("format_string", "")
            prop_display_folder.value = m.get("display_folder", "")
            prop_description.value = m.get("description", "")
        elif node_type == "column":
            t = _resolve_table(_model_data, raw_table)
            c = t["columns"].get(parts[2], {}) if t else {}
            prop_name.value, prop_table.value = parts[2], display_table
            prop_obj_type.value = c.get("type", "Column")
            prop_summarize_by.value = c.get("summarize_by", "")
            prop_format_str.value, prop_display_folder.value, prop_description.value = "", "", ""
            prop_format_row.layout.display = "none"
            prop_folder_row.layout.display = "none"
            prop_summarize_row.layout.display = ""
        elif node_type == "table":
            t = _resolve_table(_model_data, raw_table) or {}
            prop_name.value, prop_table.value = display_table, ""
            prop_obj_type.value = t.get("type", "Table")
            prop_format_str.value, prop_display_folder.value = "", ""
            prop_format_row.layout.display = "none"
            prop_folder_row.layout.display = "none"
            prop_description.value = t.get("description", "")
        elif node_type == "calc_item":
            prop_name.value, prop_table.value = parts[2], display_table
            prop_obj_type.value = "Calculation Item"
            prop_format_str.value, prop_display_folder.value, prop_description.value = "", "", ""
            prop_format_row.layout.display = "none"
            prop_folder_row.layout.display = "none"
        elif node_type == "hierarchy":
            prop_name.value = parts[2] if len(parts) > 2 else ""
            prop_table.value, prop_obj_type.value = display_table, "Hierarchy"
            prop_format_str.value, prop_display_folder.value, prop_description.value = "", "", ""
            prop_format_row.layout.display = "none"
            prop_folder_row.layout.display = "none"
        elif node_type == "partition":
            p_name = parts[2] if len(parts) > 2 else ""
            t = _resolve_table(_model_data, raw_table)
            src_type = ""
            if t:
                for pt in t.get("partitions", []):
                    if pt["name"] == p_name:
                        src_type = pt.get("source_type", "")
                        break
            prop_name.value, prop_table.value = p_name, display_table
            prop_obj_type.value = f"Partition ({src_type})" if src_type else "Partition"
            prop_format_str.value, prop_display_folder.value, prop_description.value = "", "", ""
            prop_format_row.layout.display = "none"
            prop_folder_row.layout.display = "none"
        elif node_type == "model":
            m_name = parts[1] if len(parts) > 1 else ""
            props_data = _model_data.get("model_properties", {})
            prop_name.value = m_name
            prop_table.value = ""
            prop_obj_type.value = "Semantic Model"
            prop_format_str.value = props_data.get("compatibility_level", "")
            prop_display_folder.value = props_data.get("default_mode", "")
            prop_description.value = ""
            # Repurpose labels: Format String → Compat Level, Display Folder → Default Mode
            prop_format_row.layout.display = ""
            prop_folder_row.layout.display = ""
        else:
            props_container.layout.display = "none"
            props_placeholder.layout.display = ""

    def on_load(_):
        nonlocal _model_data, _key_map
        _expanded.clear()
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        ds_input = report_input.value.strip() if report_input else ""

        # Parse comma-separated items, or list all if blank
        if ds_input:
            items = [x.strip() for x in ds_input.split(",") if x.strip()]
        else:
            # Blank = load all semantic models in the workspace
            load_btn.disabled = True
            load_btn.description = "Listing\u2026"
            set_status(conn_status, "Listing semantic models\u2026", GRAY_COLOR)
            try:
                items = _list_workspace_datasets(ws)
            except Exception as e:
                set_status(conn_status, f"Error listing models: {e}", "#ff3b30")
                load_btn.disabled = False
                load_btn.description = "Load Model"
                return
            if not items:
                set_status(conn_status, "No semantic models found in workspace.", "#ff9500")
                load_btn.disabled = False
                load_btn.description = "Load Model"
                return

        load_btn.disabled = True
        load_btn.description = "Loading\u2026"
        set_status(conn_status, f"Loading {len(items)} model(s)\u2026", GRAY_COLOR)

        start_time = time.time()
        merged_data = {"tables": {}, "models": {}, "relationships": [], "model_relationships": {}, "perspectives": [], "model_perspectives": {}}
        loaded = 0
        errors = 0

        try:
            for i, ds in enumerate(items):
                if time.time() - start_time > _LOAD_TIMEOUT:
                    set_status(conn_status, f"\u23f1\ufe0f Timeout after {loaded}/{len(items)} models.", "#ff9500")
                    break
                set_status(conn_status, f"Model {i+1}/{len(items)}: loading '{ds}'\u2026", GRAY_COLOR)
                try:
                    data = _load_model_data_fast(dataset=ds, workspace=ws)
                    if len(items) > 1:
                        merged_data["models"][ds] = data["tables"]
                        merged_data["model_relationships"][ds] = data.get("relationships", [])
                        merged_data["model_perspectives"][ds] = data.get("perspectives", [])
                    else:
                        merged_data["tables"].update(data["tables"])
                        merged_data["relationships"] = data.get("relationships", [])
                        merged_data["perspectives"] = data.get("perspectives", [])
                        merged_data["_dataset_name"] = ds
                        merged_data["model_properties"] = data.get("model_properties", {})
                    loaded += 1
                except Exception as e:
                    errors += 1
                    set_status(conn_status, f"Model {i+1}/{len(items)}: '{ds}' failed", "#ff9500")

            _model_data = merged_data

            # Auto-expand all items after load
            models = _model_data.get("models", {})
            if models:
                for m_name, m_tables in models.items():
                    _expanded.add(m_name)
                    for t_name in m_tables:
                        _expanded.add(f"{m_name}\x1f{t_name}")
            else:
                ds_name = _model_data.get("_dataset_name", "Model")
                _expanded.add(ds_name)
                _expanded.update(_model_data.get("tables", {}).keys())

            _refresh_tree()
            # Count tables across both single and multi-model structures
            all_tables = {}
            all_tables.update(_model_data.get("tables", {}))
            for m_tables in _model_data.get("models", {}).values():
                all_tables.update(m_tables)
            n_t = len(all_tables)
            n_m = sum(len(t["measures"]) for t in all_tables.values())
            n_c = sum(len(t["columns"]) for t in all_tables.values())
            elapsed = int(time.time() - start_time)
            err_str = f", {errors} error(s)" if errors else ""
            set_status(conn_status, f"Loaded {loaded}/{len(items)} model(s): {n_t} tables, {n_c} columns, {n_m} measures ({elapsed}s{err_str})", "#34c759")
            preview.value = "Select a measure to view its DAX expression."
        except Exception as e:
            set_status(conn_status, f"Error: {e}", "#ff3b30")
        finally:
            load_btn.disabled = False
            load_btn.description = "Load Model"

    def on_select(change):
        selected = change.get("new", ())
        if not selected:
            return
        last = selected[-1]
        if last not in _key_map:
            return
        key = _key_map[last]
        _current_key[0] = key
        # Single-click on a parent node: toggle expand/collapse
        if len(selected) == 1:
            if key.startswith("model:"):
                m_name = key.split(":", 1)[1]
                if m_name in _expanded:
                    _expanded.discard(m_name)
                else:
                    _expanded.add(m_name)
                _refresh_tree()
                # Fall through to show model properties/expression
            elif key.startswith("table:"):
                t_name = key.split(":", 1)[1]
                if t_name in _expanded:
                    _expanded.discard(t_name)
                else:
                    _expanded.add(t_name)
                _refresh_tree()
            if key.startswith("rels:"):
                if key in _expanded:
                    _expanded.discard(key)
                else:
                    _expanded.add(key)
                _refresh_tree()
                return
        # Update properties/expression for last selected item
        # Restore pending changes if this item was previously edited
        _suppressing_observe[0] = True
        if key in _pending_changes:
            pending = _pending_changes[key]
            preview.value = pending.get("expression", "")
            prop_name.value = pending.get("name", "")
            prop_format_str.value = pending.get("format_string", "")
            prop_display_folder.value = pending.get("display_folder", "")
            prop_description.value = pending.get("description", "")
            preview.disabled = key.split(":")[0] not in ("measure", "calc_item", "rel")
            _populate_props(key)
            # Re-apply pending values (populate_props may overwrite)
            prop_name.value = pending.get("name", prop_name.value)
            prop_format_str.value = pending.get("format_string", prop_format_str.value)
            prop_display_folder.value = pending.get("display_folder", prop_display_folder.value)
            prop_description.value = pending.get("description", prop_description.value)
            preview.value = pending.get("expression", preview.value)
        else:
            preview.value = _get_preview_text(_model_data, key)
            preview.disabled = key.split(":")[0] not in ("measure", "calc_item", "rel")
            _populate_props(key)
        _suppressing_observe[0] = False

    def on_expand_all(_):
        if _model_data:
            # Expand all models and all tables
            models = _model_data.get("models", {})
            if models:
                for m_name, m_tables in models.items():
                    _expanded.add(m_name)
                    for t_name in m_tables:
                        _expanded.add(f"{m_name}\x1f{t_name}")
            else:
                ds_name = _model_data.get("_dataset_name", "Model")
                _expanded.add(ds_name)
                _expanded.update(_model_data.get("tables", {}).keys())
            _refresh_tree()

    def on_collapse_all(_):
        _expanded.clear()
        if _model_data:
            _refresh_tree()

    def on_save(_):
        """Save ALL pending changes across all modified items."""
        # Also capture current item's latest state
        _capture_current()
        if not _pending_changes:
            return
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        save_btn.disabled = True
        save_btn.description = "Saving\u2026"
        set_status(save_status, f"Writing {len(_pending_changes)} change(s) via XMLA\u2026", GRAY_COLOR)
        saved = 0
        errors = 0
        # Group by dataset
        by_ds = {}
        for pkey, changes in _pending_changes.items():
            parts = pkey.split(":", 2)
            raw_table = parts[1] if len(parts) > 1 else ""
            if "\x1f" in raw_table:
                ds, table_name = raw_table.split("\x1f", 1)
            else:
                ds = report_input.value.strip() if report_input else ""
                table_name = raw_table
            if ds not in by_ds:
                by_ds[ds] = []
            by_ds[ds].append((pkey, parts, table_name, changes))

        for ds, items_list in by_ds.items():
            if not ds:
                continue
            try:
                from sempy_labs.tom import connect_semantic_model
                with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tm:
                    for pkey, parts, table_name, changes in items_list:
                        node_type = parts[0]
                        try:
                            if node_type == "measure":
                                m_obj = tm.model.Tables[table_name].Measures[parts[2]]
                                m_obj.Expression = changes.get("expression", m_obj.Expression)
                                m_obj.Name = changes.get("name", m_obj.Name)
                                m_obj.FormatString = changes.get("format_string", "")
                                m_obj.DisplayFolder = changes.get("display_folder", "")
                                m_obj.Description = changes.get("description", "")
                                # Update local cache
                                raw_table = parts[1]
                                t = _resolve_table(_model_data, raw_table)
                                if t:
                                    old_name = parts[2]
                                    entry = t["measures"].pop(old_name, {})
                                    entry["expression"] = changes.get("expression", "")
                                    entry["format_string"] = changes.get("format_string", "")
                                    entry["display_folder"] = changes.get("display_folder", "")
                                    entry["description"] = changes.get("description", "")
                                    t["measures"][changes.get("name", old_name)] = entry
                                saved += 1
                            elif node_type == "calc_item":
                                tm.model.Tables[table_name].CalculationGroup.CalculationItems[parts[2]].Expression = changes.get("expression", "")
                                t = _resolve_table(_model_data, parts[1])
                                if t:
                                    t["calc_items"][parts[2]]["expression"] = changes.get("expression", "")
                                saved += 1
                            elif node_type == "table":
                                tm.model.Tables[table_name].Description = changes.get("description", "")
                                t = _resolve_table(_model_data, parts[1])
                                if t:
                                    t["description"] = changes.get("description", "")
                                saved += 1
                        except Exception:
                            errors += 1
                    tm.model.SaveChanges()
            except Exception as e:
                errors += len(items_list)
                set_status(save_status, f"Error on '{ds}': {e}", "#ff3b30")

        _mark_clean()
        if errors:
            set_status(save_status, f"\u26a0\ufe0f Saved {saved}, {errors} error(s).", "#ff9500")
        else:
            set_status(save_status, f"\u2713 Saved {saved} change(s).", "#34c759")
        _refresh_tree()

    load_btn.on_click(on_load)
    tree.observe(on_select, names="value")
    expand_btn.on_click(on_expand_all)
    collapse_btn.on_click(on_collapse_all)
    save_btn.on_click(on_save)

    def on_run_action(_):
        """Run the action selected in the dropdown."""
        action = fixer_dropdown.value
        if action == "Select action..." or action not in fixer_callbacks:
            set_status(conn_status, "Select an action from the dropdown first.", "#ff9500")
            return
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        ds = report_input.value.strip() if report_input else ""
        if not ds:
            set_status(conn_status, "No model loaded.", "#ff3b30")
            return

        # Extract selected measure and column names from tree selection
        sel_measures = []
        sel_columns = []
        for key in _selected_keys:
            parts = key.split(":", 2)
            if parts[0] == "measure" and len(parts) > 2:
                sel_measures.append(parts[2])
            elif parts[0] == "column" and len(parts) > 2:
                sel_columns.append(parts[2])

        set_status(conn_status, f"Running {action}\u2026", GRAY_COLOR)
        try:
            import io as _io
            from contextlib import redirect_stdout as _redirect
            buf = _io.StringIO()
            # Build kwargs, passing selection if action supports it
            kwargs = {"report": ds, "workspace": ws, "scan_only": False}
            if sel_measures and action in ("Add PY Measures (Y-1)",):
                kwargs["measures"] = sel_measures
            if sel_columns and action in ("Auto-Create Measures from Columns",):
                kwargs["columns"] = sel_columns
            with _redirect(buf):
                fixer_callbacks[action](**kwargs)
            captured = buf.getvalue().rstrip()
            msg = f"\u2713 {action} complete."
            if captured:
                # Show first line of output in status
                first_line = captured.splitlines()[0][:80]
                msg += f" {first_line}"
            set_status(conn_status, msg, "#34c759")
        except Exception as e:
            set_status(conn_status, f"Error: {e}", "#ff3b30")

    run_action_btn.on_click(on_run_action)

    # Scan results detail panel (below save row)
    scan_results_box = widgets.VBox(layout=widgets.Layout(display="none", gap="4px",
        max_height="400px", overflow_y="auto",
        border=f"1px solid {BORDER_COLOR}", border_radius="8px",
        padding="8px", background_color=SECTION_BG, margin="8px 0 0 0"))

    def on_scan(_):
        """Run all SM fixers in scan_only mode, collect detailed findings."""
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        ds_input = report_input.value.strip() if report_input else ""
        items = [x.strip() for x in ds_input.split(",") if x.strip()] if ds_input else []
        if not items and not _model_data.get("models") and not _model_data.get("tables"):
            set_status(conn_status, "No model loaded. Load first.", "#ff3b30")
            return
        if not items:
            items = list(_model_data.get("models", {}).keys())
            if not items:
                items = [ds_input] if ds_input else []

        scan_btn.disabled = True
        scan_btn.description = "Scanning\u2026"
        _scan_results.clear()

        import io as _io
        from contextlib import redirect_stdout as _redirect

        total_findings = 0
        all_findings = []  # [(model, fixer_name, detail_line), ...]
        # Skip these from scan (they're additive actions, not violations)
        skip_fixers = {"Auto-Create Measures from Columns", "Add PY Measures (Y-1)", "Format All DAX"}
        fixer_names = [k for k in fixer_callbacks if k not in skip_fixers and k != "Select action..."]

        for ds in items:
            set_status(conn_status, f"Scanning '{ds}'\u2026", GRAY_COLOR)
            for fixer_name in fixer_names:
                try:
                    buf = _io.StringIO()
                    with _redirect(buf):
                        fixer_callbacks[fixer_name](report=ds, workspace=ws, scan_only=True)
                    output = buf.getvalue()
                    for line in output.splitlines():
                        line = line.strip()
                        if line:
                            all_findings.append((ds, fixer_name, line))
                            total_findings += 1
                            model_key = f"model:{ds}"
                            _scan_results[model_key] = _scan_results.get(model_key, 0) + 1
                except Exception:
                    pass

        _refresh_tree()

        # Build results panel with Fix buttons
        if all_findings:
            result_widgets = []
            result_widgets.append(widgets.HTML(
                value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; '
                f'text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">'
                f'\u26a0\ufe0f {total_findings} Finding(s)</div>'
            ))
            # Table header
            result_widgets.append(widgets.HTML(
                value=f'<div style="display:grid; grid-template-columns:120px 200px 1fr 60px; font-size:11px; font-weight:600; color:#555; font-family:{FONT_FAMILY}; '
                f'padding:4px 8px; border-bottom:1px solid {BORDER_COLOR}; gap:8px;">'
                f'<span>Model</span>'
                f'<span>Check</span>'
                f'<span>Finding</span>'
                f'<span></span>'
                f'</div>'
            ))
            for ds, fixer_name, detail in all_findings:
                no_action = "no action needed" in detail.lower()
                if no_action:
                    action_widget = widgets.HTML(value='<span style="width:60px;display:inline-block;"></span>')
                else:
                    fix_btn = widgets.Button(
                        description="Fix",
                        button_style="warning",
                        layout=widgets.Layout(width="60px", height="24px"),
                    )
                    def _make_fix(fn, model):
                        def _handler(_):
                            _ws = ws
                            set_status(conn_status, f"Fixing: {fn} on '{model}'\u2026", GRAY_COLOR)
                            try:
                                buf2 = _io.StringIO()
                                with _redirect(buf2):
                                    fixer_callbacks[fn](report=model, workspace=_ws, scan_only=False)
                                set_status(conn_status, f"\u2713 {fn} applied to '{model}'.", "#34c759")
                            except Exception as e:
                                set_status(conn_status, f"Error: {e}", "#ff3b30")
                        return _handler
                    fix_btn.on_click(_make_fix(fixer_name, ds))
                    action_widget = fix_btn
                row = widgets.HBox([
                    widgets.HTML(value=f'<span style="font-size:11px; font-family:{FONT_FAMILY}; color:#333; width:120px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{ds}</span>',
                        layout=widgets.Layout(width="120px")),
                    widgets.HTML(value=f'<span style="font-size:11px; font-family:{FONT_FAMILY}; color:{ICON_ACCENT}; width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">{fixer_name}</span>',
                        layout=widgets.Layout(width="200px")),
                    widgets.HTML(value=f'<span style="font-size:11px; font-family:{FONT_FAMILY}; color:#555;">{detail[:120]}</span>',
                        layout=widgets.Layout(flex="1")),
                    action_widget,
                ], layout=widgets.Layout(align_items="center", gap="8px", padding="2px 8px",
                    border_bottom=f"1px solid #f0f0f0"))
                result_widgets.append(row)
            scan_results_box.children = result_widgets
            scan_results_box.layout.display = ""
        else:
            scan_results_box.children = []
            scan_results_box.layout.display = "none"

        scan_btn.disabled = False
        scan_btn.description = "\U0001F50D Scan"
        if total_findings > 0:
            set_status(conn_status, f"\U0001F50D Scan: {total_findings} finding(s) across {len(items)} model(s).", "#ff9500")
        else:
            set_status(conn_status, f"\u2713 Scan complete: no issues found.", "#34c759")

    scan_btn.on_click(on_scan)

    widget = widgets.VBox([nav_row, action_row, tree_header, panels, save_row, refresh_row, scan_results_box], layout=widgets.Layout(padding="12px", gap="4px"))
    return widget, on_load