# Report Explorer tab for PBI Fixer.
# Provides a tree view of report pages and visuals with iframe preview,
# properties, and fixer action dropdown.

import ipywidgets as widgets
import time

from sempy_labs._ui_components import (
    FONT_FAMILY,
    BORDER_COLOR,
    GRAY_COLOR,
    ICON_ACCENT,
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


def _list_workspace_reports(workspace):
    """List all report names in a workspace via REST API."""
    from sempy_labs._helper_functions import (
        resolve_workspace_name_and_id,
        _base_api,
    )
    _, ws_id = resolve_workspace_name_and_id(workspace)
    url = f"/v1.0/myorg/groups/{ws_id}/reports"
    response = _base_api(request=url, client="fabric_sp")
    return [
        (r.get("name"), r.get("format", ""))
        for r in response.json().get("value", [])
        if r.get("name")
    ]


def _load_report_data(report, workspace):
    """Load report structure via connect_report."""
    from sempy_labs.report import connect_report

    report_data = {"pages": {}, "format": "", "report_id": "", "workspace_id": ""}

    with connect_report(report=report, readonly=True, workspace=workspace) as rw:
        report_data["format"] = str(getattr(rw, "format", ""))
        report_data["report_id"] = str(getattr(rw, "_report_id", "") or "")
        report_data["workspace_id"] = str(getattr(rw, "_workspace_id", "") or "")
        pages_df = rw.list_pages()
        visuals_df = rw.list_visuals()

        for _, row in pages_df.iterrows():
            p_name = str(row.get("Page Name", row.get("Page Display Name", "")))
            display_name = str(row.get("Page Display Name", p_name))
            p_info = {
                "display_name": display_name,
                "width": int(row.get("Width", 0)) if row.get("Width") else 0,
                "height": int(row.get("Height", 0)) if row.get("Height") else 0,
                "hidden": bool(row.get("Hidden", False)),
                "visual_count": int(row.get("Visual Count", 0)) if row.get("Visual Count") else 0,
                "visuals": {},
            }
            report_data["pages"][p_name] = p_info

        for _, row in visuals_df.iterrows():
            p_name = str(row.get("Page Name", row.get("Page Display Name", "")))
            if p_name not in report_data["pages"]:
                continue
            v_name = str(row.get("Visual Name", ""))
            v_type = str(row.get("Type", ""))
            display_type = str(row.get("Display Type", v_type))
            report_data["pages"][p_name]["visuals"][v_name] = {
                "type": v_type,
                "display_type": display_type,
                "x": int(row.get("X", 0)) if row.get("X") else 0,
                "y": int(row.get("Y", 0)) if row.get("Y") else 0,
                "width": int(row.get("Width", 0)) if row.get("Width") else 0,
                "height": int(row.get("Height", 0)) if row.get("Height") else 0,
                "hidden": bool(row.get("Hidden", False)),
                "title": str(row.get("Title", "")) if row.get("Title") else "",
            }

    return report_data


def _build_tree(report_data, expanded_pages):
    items = []
    for p_name in report_data["pages"]:
        p = report_data["pages"][p_name]
        is_expanded = p_name in expanded_pages
        marker = EXPANDED if is_expanded else COLLAPSED
        hidden_suffix = " (hidden)" if p["hidden"] else ""
        v_count = len(p["visuals"])
        items.append(
            (0, "page", f"{marker} {p['display_name']}{hidden_suffix}  [{v_count} visuals]", f"page:{p_name}")
        )
        if not is_expanded:
            continue
        for v_name in sorted(p["visuals"]):
            v = p["visuals"][v_name]
            label = v["display_type"] or v["type"]
            if v["title"]:
                label = f"{label}: {v['title']}"
            if v["hidden"]:
                label += " (hidden)"
            items.append((1, "visual", label, f"visual:{p_name}:{v_name}"))
    return build_tree_items(items)


def _prop_row(label, value):
    return (
        f'<tr><td style="padding:3px 10px 3px 0; font-weight:600; color:#555; '
        f'white-space:nowrap; vertical-align:top;">{label}</td>'
        f'<td style="padding:3px 0; word-break:break-word;">{value}</td></tr>'
    )


def _props_table(rows_html):
    return (
        f'<table style="font-size:13px; font-family:{FONT_FAMILY}; '
        f'border-collapse:collapse; width:100%;">'
        f'{rows_html}</table>'
    )


def _get_properties_html(report_data, key):
    """Return combined properties HTML (stats + metadata)."""
    parts = key.split(":", 2)
    node_type = parts[0]

    if node_type == "page":
        p = report_data["pages"].get(parts[1], {})
        rows = _prop_row("Display Name", p.get("display_name", parts[1]))
        rows += _prop_row("Internal Name", parts[1])
        rows += _prop_row("Width", str(p.get("width", 0)))
        rows += _prop_row("Height", str(p.get("height", 0)))
        rows += _prop_row("Size", f"{p.get('width', 0)} \u00d7 {p.get('height', 0)}")
        rows += _prop_row("Hidden", str(p.get("hidden", False)))
        rows += _prop_row("Visual Count", str(len(p.get("visuals", {}))))
        type_counts = {}
        for v in p.get("visuals", {}).values():
            dt = v.get("display_type") or v.get("type", "unknown")
            type_counts[dt] = type_counts.get(dt, 0) + 1
        if type_counts:
            summary = ", ".join(f"{count}\u00d7 {t}" for t, count in sorted(type_counts.items(), key=lambda x: -x[1]))
            rows += _prop_row("Visual Types", summary)
        return _props_table(rows)

    if node_type == "visual":
        p_name = parts[1]
        v_name = parts[2] if len(parts) > 2 else ""
        v = report_data["pages"].get(p_name, {}).get("visuals", {}).get(v_name, {})
        rows = _prop_row("Type", v.get("type", ""))
        rows += _prop_row("Display Type", v.get("display_type", ""))
        if v.get("title"):
            rows += _prop_row("Title", v["title"])
        rows += _prop_row("Internal Name", v_name)
        rows += _prop_row("Page", report_data["pages"].get(p_name, {}).get("display_name", p_name))
        rows += _prop_row("Position", f"x={v.get('x', 0)}, y={v.get('y', 0)}")
        rows += _prop_row("Size", f"{v.get('width', 0)} \u00d7 {v.get('height', 0)}")
        rows += _prop_row("Hidden", str(v.get("hidden", False)))
        return _props_table(rows)

    return ""


def _get_embed_html(report_data, key):
    """Try to build an embed iframe for the selected page/visual."""
    return ""


def report_explorer_tab(workspace_input=None, report_input=None, fixer_callbacks=None):
    """Build the Report Explorer tab widget."""
    _report_data = {}
    _key_map = {}
    _expanded = set()
    _current_key = [None]

    load_btn = widgets.Button(description="Load Report", button_style="primary", layout=widgets.Layout(width="110px"))
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

    tree = widgets.Select(options=[], rows=28, layout=widgets.Layout(width="320px", height="500px", font_family="monospace"))

    def _refresh_tree(preserve_selection=None):
        nonlocal _key_map
        options, _key_map = _build_tree(_report_data, _expanded)
        tree.unobserve(on_select, names="value")
        tree.options = options
        tree.value = preserve_selection if (preserve_selection and preserve_selection in options) else None
        tree.observe(on_select, names="value")

    # -- preview (top-right, powerbiclient Report widget) --
    preview_label = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Preview</div>'
    )
    preview_placeholder = widgets.HTML(
        value=f'<div style="padding:16px; color:{GRAY_COLOR}; font-size:13px; font-family:{FONT_FAMILY}; font-style:italic;">Load a report to see the live preview</div>',
    )
    _report_widget = [None]  # mutable container for powerbiclient Report
    # Use a VBox as the container — we swap its children to show the Report widget
    preview_content = widgets.VBox([preview_placeholder], layout=widgets.Layout(width="100%", min_height="350px"))
    preview_box = panel_box([preview_label, preview_content], flex="1", min_height="380px")

    # -- properties (bottom-right) --
    props_label = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Properties</div>'
    )
    props_html = widgets.HTML(
        value=f'<div style="padding:12px; color:{GRAY_COLOR}; font-size:13px; font-family:{FONT_FAMILY}; font-style:italic;">Select an object to view properties</div>',
    )
    props_box = panel_box([props_label, props_html], flex="0 0 auto", min_height="150px")

    panels = create_three_panel_layout(tree, preview_box, props_box)
    tree_header = widgets.HTML(
        value=f'<div style="font-size:12px; font-weight:600; color:{ICON_ACCENT}; font-family:{FONT_FAMILY}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:2px;">Report Structure</div>'
    )

    def on_load(_):
        nonlocal _report_data, _key_map
        _expanded.clear()
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        rpt_input = report_input.value.strip() if report_input else ""

        # Parse comma-separated items, or list all if blank
        if rpt_input:
            items = [x.strip() for x in rpt_input.split(",") if x.strip()]
        else:
            load_btn.disabled = True
            load_btn.description = "Listing\u2026"
            set_status(conn_status, "Listing reports\u2026", GRAY_COLOR)
            try:
                rpt_list = _list_workspace_reports(ws)
                items = [name for name, _ in rpt_list]
            except Exception as e:
                set_status(conn_status, f"Error listing reports: {e}", "#ff3b30")
                load_btn.disabled = False
                load_btn.description = "Load Report"
                return
            if not items:
                set_status(conn_status, "No reports found in workspace.", "#ff9500")
                load_btn.disabled = False
                load_btn.description = "Load Report"
                return

        # For multiple reports, load only the first one into preview
        # (powerbiclient can only show one report at a time)
        rpt = items[0]
        load_btn.disabled = True
        load_btn.description = "Loading\u2026"
        set_status(conn_status, f"Loading '{rpt}'\u2026", GRAY_COLOR)
        try:
            _report_data = _load_report_data(report=rpt, workspace=ws)
            _refresh_tree()
            n_pages = len(_report_data["pages"])
            n_visuals = sum(len(p["visuals"]) for p in _report_data["pages"].values())
            fmt = _report_data.get("format", "")
            fmt_str = f" ({fmt})" if fmt else ""
            extra = f" (1 of {len(items)})" if len(items) > 1 else ""
            set_status(conn_status, f"Loaded: {n_pages} pages, {n_visuals} visuals{fmt_str}{extra}", "#34c759")
            # Initialize powerbiclient Report widget
            report_id = _report_data.get("report_id", "")
            workspace_id = _report_data.get("workspace_id", "")
            if report_id and workspace_id:
                try:
                    from powerbiclient import Report as PBIReport
                    rpt_widget = PBIReport(group_id=workspace_id, report_id=report_id)
                    rpt_widget.layout = widgets.Layout(width="100%", height="400px")
                    _report_widget[0] = rpt_widget
                    preview_content.children = [rpt_widget]
                except Exception as embed_err:
                    preview_content.children = [widgets.HTML(
                        value=f'<div style="padding:12px; color:{GRAY_COLOR}; font-size:13px; font-family:{FONT_FAMILY};">Preview error: {embed_err}</div>'
                    )]
        except Exception as e:
            set_status(conn_status, f"Error: {e}", "#ff3b30")
        finally:
            load_btn.disabled = False
            load_btn.description = "Load Report"

    def on_select(change):
        selected = change.get("new")
        if not selected or selected not in _key_map:
            return
        key = _key_map[selected]
        _current_key[0] = key
        if key.startswith("page:"):
            p_name = key.split(":", 1)[1]
            if p_name in _expanded:
                _expanded.discard(p_name)
            else:
                _expanded.add(p_name)
            _refresh_tree(preserve_selection=selected)
        props_html.value = _get_properties_html(_report_data, key)
        # Page navigation via powerbiclient (if widget loaded)
        if _report_widget[0] is not None and key.startswith("page:"):
            p_name = key.split(":", 1)[1]
            p = _report_data["pages"].get(p_name, {})
            page_display = p.get("display_name", p_name)
            try:
                _report_widget[0].set_active_page(page_display)
            except Exception:
                pass

    def on_expand_all(_):
        if _report_data:
            _expanded.update(_report_data["pages"].keys())
            _refresh_tree()

    def on_collapse_all(_):
        _expanded.clear()
        if _report_data:
            _refresh_tree()

    def on_fixer_action(change):
        action = change.get("new")
        if action == "Actions..." or action not in fixer_callbacks:
            return
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        rpt = report_input.value.strip() if report_input else ""
        if not rpt:
            set_status(conn_status, "No report loaded.", "#ff3b30")
            fixer_dropdown.value = "Actions..."
            return
        page = None
        key = _current_key[0]
        if key and key.startswith("page:"):
            page = key.split(":", 1)[1]
        elif key and key.startswith("visual:"):
            page = key.split(":")[1]
        set_status(conn_status, f"Running {action}\u2026", GRAY_COLOR)
        try:
            fixer_callbacks[action](report=rpt, page_name=page, workspace=ws, scan_only=False)
            set_status(conn_status, f"\u2713 {action} complete.", "#34c759")
        except Exception as e:
            set_status(conn_status, f"Error: {e}", "#ff3b30")
        fixer_dropdown.value = "Actions..."

    load_btn.on_click(on_load)
    tree.observe(on_select, names="value")
    expand_btn.on_click(on_expand_all)
    collapse_btn.on_click(on_collapse_all)
    fixer_dropdown.observe(on_fixer_action, names="value")

    return widgets.VBox([load_row, tree_header, panels], layout=widgets.Layout(padding="12px", gap="4px"))