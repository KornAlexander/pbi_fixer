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

    model_data = {"tables": {}}

    # -- Fast DataFrame reads (REST API, no TOM connection needed) --
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
                try:
                    for p in table.Partitions:
                        if "Calculated" in str(p.SourceType):
                            t_info["type"] = "CalculatedTable"
                        break
                except Exception:
                    pass
                for h in table.Hierarchies:
                    t_info["hierarchies"][h.Name] = {"levels": [str(lvl.Name) for lvl in h.Levels]}
    except Exception:
        pass

    return model_data


def _load_model_data_tom(dataset, workspace):
    """Fallback: load everything via TOM (slower but complete)."""
    from sempy_labs.tom import connect_semantic_model

    model_data = {"tables": {}}
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
                try:
                    for p in table.Partitions:
                        if "Calculated" in str(p.SourceType):
                            t_info["type"] = "CalculatedTable"
                        break
                except Exception:
                    pass
            for col in table.Columns:
                t_info["columns"][col.Name] = {
                    "data_type": str(col.DataType) if hasattr(col, "DataType") else "",
                    "is_hidden": bool(col.IsHidden),
                    "expression": str(col.Expression) if hasattr(col, "Expression") and col.Expression else None,
                    "type": str(col.Type) if hasattr(col, "Type") else "",
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
    return model_data


def _table_summary(t):
    """Return total child count for a table."""
    return str(len(t.get("columns", {})) + len(t.get("measures", {})) + len(t.get("hierarchies", {})) + len(t.get("calc_items", {})))


def _build_tree(model_data, expanded_tables):
    items = []
    models = model_data.get("models", {})
    if models:
        # Multi-model: show model-level grouping
        for m_name in sorted(models):
            m_tables = models[m_name]
            is_model_expanded = m_name in expanded_tables
            marker = EXPANDED if is_model_expanded else COLLAPSED
            t_count = len(m_tables)
            items.append((0, "calc_group", f"{marker} {m_name}  [{t_count} tables]", f"model:{m_name}"))
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
                    items.append((2, "measure", mn, f"measure:{full_key}:{mn}"))
                for cn in sorted(t["columns"]):
                    c = t["columns"][cn]
                    hidden = " (hidden)" if c["is_hidden"] else ""
                    items.append((2, "column", f"{cn} [{c['data_type']}]{hidden}", f"column:{full_key}:{cn}"))
                for hn in sorted(t["hierarchies"]):
                    lvl_str = " \u2192 ".join(t["hierarchies"][hn]["levels"])
                    items.append((2, "hierarchy", f"{hn}  ({lvl_str})", f"hierarchy:{full_key}:{hn}"))
                for ci_name in sorted(t.get("calc_items", {}), key=lambda n: t["calc_items"][n]["ordinal"]):
                    items.append((2, "calc_item", ci_name, f"calc_item:{full_key}:{ci_name}"))
    else:
        # Single model: flat table list (original behavior)
        for t_name in sorted(model_data["tables"]):
            t = model_data["tables"][t_name]
            icon = "calc_group" if t["type"] == "CalculationGroup" else "table"
            is_expanded = t_name in expanded_tables
            marker = EXPANDED if is_expanded else COLLAPSED
            suffix = " (hidden)" if t["is_hidden"] else ""
            summary = _table_summary(t)
            items.append((0, icon, f"{marker} {t_name}{suffix}  [{summary}]", f"table:{t_name}"))
            if not is_expanded:
                continue
            for mn in sorted(t["measures"]):
                items.append((1, "measure", mn, f"measure:{t_name}:{mn}"))
            for cn in sorted(t["columns"]):
                c = t["columns"][cn]
                hidden = " (hidden)" if c["is_hidden"] else ""
                items.append((1, "column", f"{cn} [{c['data_type']}]{hidden}", f"column:{t_name}:{cn}"))
            for hn in sorted(t["hierarchies"]):
                lvl_str = " \u2192 ".join(t["hierarchies"][hn]["levels"])
                items.append((1, "hierarchy", f"{hn}  ({lvl_str})", f"hierarchy:{t_name}:{hn}"))
            for ci_name in sorted(t.get("calc_items", {}), key=lambda n: t["calc_items"][n]["ordinal"]):
                items.append((1, "calc_item", ci_name, f"calc_item:{t_name}:{ci_name}"))
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
    if node_type in ("model",):
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

    load_btn = widgets.Button(description="Load Model", button_style="primary", layout=widgets.Layout(width="110px"))
    expand_btn = widgets.Button(description="Expand All", layout=widgets.Layout(width="100px"))
    collapse_btn = widgets.Button(description="Collapse All", layout=widgets.Layout(width="100px"))

    fixer_callbacks = fixer_callbacks or {}
    fixer_dropdown = widgets.Dropdown(
        options=["Actions..."] + list(fixer_callbacks.keys()),
        value="Actions...",
        layout=widgets.Layout(width="200px"),
    )

    conn_status = status_html()
    load_row = widgets.HBox(
        [load_btn, expand_btn, collapse_btn, fixer_dropdown, conn_status],
        layout=widgets.Layout(align_items="center", gap="8px", margin="0 0 8px 0"),
    )

    tree = widgets.SelectMultiple(options=[], rows=28, layout=widgets.Layout(width="400px", height="500px", font_family="monospace"))

    def _refresh_tree(preserve_selection=None):
        nonlocal _key_map
        options, _key_map = _build_tree(_model_data, _expanded)
        tree.unobserve(on_select, names="value")
        tree.options = options
        if preserve_selection:
            if isinstance(preserve_selection, str):
                preserve_selection = (preserve_selection,)
            tree.value = tuple(v for v in preserve_selection if v in options)
        else:
            tree.value = ()
        tree.observe(on_select, names="value")

    # -- expression panel --
    preview = widgets.Textarea(value="Select a measure to view its DAX expression.", layout=widgets.Layout(width="100%", height="240px", font_family="monospace"))
    save_expr_btn = widgets.Button(description="Save Expression", button_style="warning", disabled=True, layout=widgets.Layout(width="140px"))
    save_status = status_html()
    preview_label = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Expression</div>'
    )
    save_row = widgets.HBox([save_expr_btn, save_status], layout=widgets.Layout(align_items="center", gap="8px"))
    preview_box = panel_box([preview_label, preview, save_row], flex="1")

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

    save_props_btn = widgets.Button(description="Save Properties", button_style="warning", disabled=True, layout=widgets.Layout(width="140px"))
    props_save_status = status_html()
    props_save_row = widgets.HBox([save_props_btn, props_save_status], layout=widgets.Layout(align_items="center", gap="8px"))

    props_container = widgets.VBox(
        [prop_name_row, prop_table_row, prop_type_row, prop_format_row, prop_folder_row, prop_desc_row, props_save_row],
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
        save_props_btn.disabled = False
        props_save_status.value = ""
        prop_format_row.layout.display = ""
        prop_folder_row.layout.display = ""

        if node_type == "measure":
            m = _model_data["tables"][parts[1]]["measures"].get(parts[2], {})
            prop_name.value, prop_table.value, prop_obj_type.value = parts[2], parts[1], "Measure"
            prop_format_str.value = m.get("format_string", "")
            prop_display_folder.value = m.get("display_folder", "")
            prop_description.value = m.get("description", "")
        elif node_type == "column":
            c = _model_data["tables"][parts[1]]["columns"].get(parts[2], {})
            prop_name.value, prop_table.value = parts[2], parts[1]
            prop_obj_type.value = c.get("type", "Column")
            prop_format_str.value, prop_display_folder.value, prop_description.value = "", "", ""
            prop_format_row.layout.display = "none"
            prop_folder_row.layout.display = "none"
        elif node_type == "table":
            t = _model_data["tables"].get(parts[1], {})
            prop_name.value, prop_table.value = parts[1], ""
            prop_obj_type.value = t.get("type", "Table")
            prop_format_str.value, prop_display_folder.value = "", ""
            prop_format_row.layout.display = "none"
            prop_folder_row.layout.display = "none"
            prop_description.value = t.get("description", "")
        elif node_type == "calc_item":
            prop_name.value, prop_table.value = parts[2], parts[1]
            prop_obj_type.value = "Calculation Item"
            prop_format_str.value, prop_display_folder.value, prop_description.value = "", "", ""
            prop_format_row.layout.display = "none"
            prop_folder_row.layout.display = "none"
        elif node_type == "hierarchy":
            prop_name.value = parts[2] if len(parts) > 2 else ""
            prop_table.value, prop_obj_type.value = parts[1], "Hierarchy"
            prop_format_str.value, prop_display_folder.value, prop_description.value = "", "", ""
            prop_format_row.layout.display = "none"
            prop_folder_row.layout.display = "none"
            save_props_btn.disabled = True
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
        merged_data = {"tables": {}, "models": {}}
        loaded = 0
        errors = 0

        try:
            for ds in items:
                if time.time() - start_time > _LOAD_TIMEOUT:
                    set_status(conn_status, f"\u23f1\ufe0f Timeout after {loaded}/{len(items)} models.", "#ff9500")
                    break
                try:
                    data = _load_model_data_fast(dataset=ds, workspace=ws)
                    if len(items) > 1:
                        # Store per-model for grouped tree
                        merged_data["models"][ds] = data["tables"]
                    else:
                        merged_data["tables"].update(data["tables"])
                    loaded += 1
                except Exception as e:
                    errors += 1

            _model_data = merged_data
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
        # Use the last selected item for properties/expand-collapse
        last = selected[-1]
        if last not in _key_map:
            return
        key = _key_map[last]
        _current_key[0] = key
        # Expand/collapse model or table
        if key.startswith("model:"):
            m_name = key.split(":", 1)[1]
            if m_name in _expanded:
                _expanded.discard(m_name)
            else:
                _expanded.add(m_name)
            _refresh_tree(preserve_selection=selected)
            preview.value = ""
            return
        if key.startswith("table:"):
            t_name = key.split(":", 1)[1]
            if t_name in _expanded:
                _expanded.discard(t_name)
            else:
                _expanded.add(t_name)
            _refresh_tree(preserve_selection=selected)
        preview.value = _get_preview_text(_model_data, key)
        _populate_props(key)
        save_expr_btn.disabled = key.split(":")[0] not in ("measure", "calc_item")
        save_status.value = ""

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
                _expanded.update(_model_data.get("tables", {}).keys())
            _refresh_tree()

    def on_collapse_all(_):
        _expanded.clear()
        if _model_data:
            _refresh_tree()

    def on_save_expr(_):
        key = _current_key[0]
        if not key:
            return
        parts = key.split(":", 2)
        node_type = parts[0]
        new_expr = preview.value
        if node_type not in ("measure", "calc_item"):
            set_status(save_status, "Only measures and calc items can be saved.", "#ff9500")
            return
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        ds = report_input.value.strip() if report_input else ""
        if not ds:
            set_status(save_status, "No model loaded.", "#ff3b30")
            return
        save_expr_btn.disabled = True
        save_expr_btn.description = "Saving\u2026"
        set_status(save_status, "Writing via XMLA\u2026", GRAY_COLOR)
        try:
            from sempy_labs.tom import connect_semantic_model
            with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tm:
                if node_type == "measure":
                    tm.model.Tables[parts[1]].Measures[parts[2]].Expression = new_expr
                    _model_data["tables"][parts[1]]["measures"][parts[2]]["expression"] = new_expr
                elif node_type == "calc_item":
                    tm.model.Tables[parts[1]].CalculationGroup.CalculationItems[parts[2]].Expression = new_expr
                    _model_data["tables"][parts[1]]["calc_items"][parts[2]]["expression"] = new_expr
                tm.model.SaveChanges()
            set_status(save_status, "\u2713 Saved.", "#34c759")
        except Exception as e:
            set_status(save_status, f"Error: {e}", "#ff3b30")
        finally:
            save_expr_btn.disabled = False
            save_expr_btn.description = "Save Expression"

    def on_save_props(_):
        key = _current_key[0]
        if not key:
            return
        parts = key.split(":", 2)
        node_type = parts[0]
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        ds = report_input.value.strip() if report_input else ""
        if not ds:
            set_status(props_save_status, "No model loaded.", "#ff3b30")
            return
        save_props_btn.disabled = True
        save_props_btn.description = "Saving\u2026"
        set_status(props_save_status, "Writing via XMLA\u2026", GRAY_COLOR)
        try:
            from sempy_labs.tom import connect_semantic_model
            with connect_semantic_model(dataset=ds, readonly=False, workspace=ws) as tm:
                if node_type == "measure":
                    m_obj = tm.model.Tables[parts[1]].Measures[parts[2]]
                    m_obj.Name = prop_name.value
                    m_obj.FormatString = prop_format_str.value
                    m_obj.DisplayFolder = prop_display_folder.value
                    m_obj.Description = prop_description.value
                    old_name = parts[2]
                    m_data = _model_data["tables"][parts[1]]["measures"]
                    entry = m_data.pop(old_name)
                    entry["format_string"] = prop_format_str.value
                    entry["display_folder"] = prop_display_folder.value
                    entry["description"] = prop_description.value
                    m_data[prop_name.value] = entry
                elif node_type == "table":
                    tm.model.Tables[parts[1]].Description = prop_description.value
                    _model_data["tables"][parts[1]]["description"] = prop_description.value
                tm.model.SaveChanges()
            set_status(props_save_status, "\u2713 Saved.", "#34c759")
            if node_type == "measure" and prop_name.value != parts[2]:
                _current_key[0] = f"measure:{parts[1]}:{prop_name.value}"
                _refresh_tree()
        except Exception as e:
            set_status(props_save_status, f"Error: {e}", "#ff3b30")
        finally:
            save_props_btn.disabled = False
            save_props_btn.description = "Save Properties"

    load_btn.on_click(on_load)
    tree.observe(on_select, names="value")
    expand_btn.on_click(on_expand_all)
    collapse_btn.on_click(on_collapse_all)
    save_expr_btn.on_click(on_save_expr)
    save_props_btn.on_click(on_save_props)

    def on_fixer_action(change):
        action = change.get("new")
        if action == "Actions..." or action not in fixer_callbacks:
            return
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        ds = report_input.value.strip() if report_input else ""
        if not ds:
            set_status(conn_status, "No model loaded.", "#ff3b30")
            fixer_dropdown.value = "Actions..."
            return
        set_status(conn_status, f"Running {action}\u2026", GRAY_COLOR)
        try:
            import io as _io
            from contextlib import redirect_stdout as _redirect
            buf = _io.StringIO()
            with _redirect(buf):
                fixer_callbacks[action](report=ds, workspace=ws, scan_only=False)
            captured = buf.getvalue().rstrip()
            msg = f"\u2713 {action} complete."
            if captured:
                # Show first line of output in status
                first_line = captured.splitlines()[0][:80]
                msg += f" {first_line}"
            set_status(conn_status, msg, "#34c759")
        except Exception as e:
            set_status(conn_status, f"Error: {e}", "#ff3b30")
        fixer_dropdown.value = "Actions..."

    fixer_dropdown.observe(on_fixer_action, names="value")

    widget = widgets.VBox([load_row, tree_header, panels], layout=widgets.Layout(padding="12px", gap="4px"))
    return widget, on_load