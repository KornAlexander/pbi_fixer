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


def _build_tree(report_data, expanded_pages, scan_results=None):
    """Build tree items, optionally annotating with scan violation counts."""
    scan_results = scan_results or {}
    items = []
    reports = report_data.get("reports", {})
    if reports:
        for r_name in sorted(reports):
            r = reports[r_name]
            is_rpt_expanded = r_name in expanded_pages
            marker = EXPANDED if is_rpt_expanded else COLLAPSED
            fmt = r.get("format", "")
            fmt_str = f" ({fmt})" if fmt else ""
            p_count = len(r.get("pages", {}))
            # Count total violations for this report
            rpt_violations = sum(v for k, v in scan_results.items() if k.startswith(f"report:{r_name}") or k.startswith(f"page:{r_name}\x1f") or k.startswith(f"visual:{r_name}\x1f"))
            badge = f" \u26a0\ufe0f{rpt_violations}" if rpt_violations > 0 else ""
            items.append((0, "page", f"{marker} {r_name}{fmt_str}  [{p_count} pages]{badge}", f"report:{r_name}"))
            if not is_rpt_expanded:
                continue
            for p_name in r["pages"]:
                p = r["pages"][p_name]
                full_key = f"{r_name}\x1f{p_name}"
                is_expanded = full_key in expanded_pages
                p_marker = EXPANDED if is_expanded else COLLAPSED
                hidden_suffix = " (hidden)" if p["hidden"] else ""
                v_count = len(p["visuals"])
                page_violations = scan_results.get(f"page:{full_key}", 0)
                badge = f" \u26a0\ufe0f{page_violations}" if page_violations > 0 else ""
                items.append((1, "page", f"{p_marker} {p['display_name']}{hidden_suffix}  [{v_count} visuals]{badge}", f"page:{full_key}"))
                if not is_expanded:
                    continue
                for v_name in sorted(p["visuals"]):
                    v = p["visuals"][v_name]
                    label = v["display_type"] or v["type"]
                    if v["title"]:
                        label = f"{label}: {v['title']}"
                    if v["hidden"]:
                        label += " (hidden)"
                    v_key = f"visual:{r_name}\x1f{p_name}:{v_name}"
                    if v_key in scan_results:
                        label += f" \u26a0\ufe0f{scan_results[v_key]}"
                    items.append((2, "visual", label, v_key))
    else:
        for p_name in report_data.get("pages", {}):
            p = report_data["pages"][p_name]
            is_expanded = p_name in expanded_pages
            marker = EXPANDED if is_expanded else COLLAPSED
            hidden_suffix = " (hidden)" if p["hidden"] else ""
            v_count = len(p["visuals"])
            page_violations = scan_results.get(f"page:{p_name}", 0)
            badge = f" \u26a0\ufe0f{page_violations}" if page_violations > 0 else ""
            items.append(
                (0, "page", f"{marker} {p['display_name']}{hidden_suffix}  [{v_count} visuals]{badge}", f"page:{p_name}")
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
                v_key = f"visual:{p_name}:{v_name}"
                if v_key in scan_results:
                    label += f" \u26a0\ufe0f{scan_results[v_key]}"
                items.append((1, "visual", label, v_key))
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


def _resolve_page(report_data, page_key):
    """Resolve a page key to its data dict. Handles both single and multi-report keys."""
    if "\x1f" in page_key:
        r_name, p_name = page_key.split("\x1f", 1)
        return report_data.get("reports", {}).get(r_name, {}).get("pages", {}).get(p_name)
    return report_data.get("pages", {}).get(page_key)


def _get_properties_html(report_data, key):
    """Return combined properties HTML (stats + metadata)."""
    parts = key.split(":", 2)
    node_type = parts[0]

    if node_type == "report":
        return ""

    if node_type == "page":
        p = _resolve_page(report_data, parts[1]) or {}
        display_name = parts[1].split("\x1f")[-1] if "\x1f" in parts[1] else parts[1]
        rows = _prop_row("Display Name", p.get("display_name", display_name))
        rows += _prop_row("Internal Name", display_name)
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
        p_key = parts[1]  # may contain \x1f for multi-report
        v_name = parts[2] if len(parts) > 2 else ""
        p = _resolve_page(report_data, p_key) or {}
        v = p.get("visuals", {}).get(v_name, {})
        rows = _prop_row("Type", v.get("type", ""))
        rows += _prop_row("Display Type", v.get("display_type", ""))
        if v.get("title"):
            rows += _prop_row("Title", v["title"])
        rows += _prop_row("Internal Name", v_name)
        p_display = p_key.split("\x1f")[-1] if "\x1f" in p_key else p_key
        rows += _prop_row("Page", p.get("display_name", p_display))
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
    _scan_results = {}  # key -> count (for tree badges)
    _scan_details = {}  # key -> [(fixer_name, description), ...]

    load_btn = widgets.Button(description="Load Report", button_style="primary", layout=widgets.Layout(width="110px"))
    expand_btn = widgets.Button(description="Expand All", layout=widgets.Layout(width="100px"))
    collapse_btn = widgets.Button(description="Collapse All", layout=widgets.Layout(width="100px"))
    scan_btn = widgets.Button(description="\U0001F50D Scan", layout=widgets.Layout(width="100px"))

    fixer_callbacks = fixer_callbacks or {}
    fixer_dropdown = widgets.Dropdown(
        options=["Select action..."] + list(fixer_callbacks.keys()),
        value="Select action...",
        layout=widgets.Layout(width="250px"),
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

    tree = widgets.SelectMultiple(options=[], rows=28, layout=widgets.Layout(width="400px", height="500px", font_family="monospace"))

    def _refresh_tree():
        nonlocal _key_map
        options, _key_map = _build_tree(_report_data, _expanded, _scan_results)
        tree.unobserve(on_select, names="value")
        tree.options = options
        tree.value = ()
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
    # Violations panel (shown below properties when scan results exist)
    violations_box = widgets.VBox(layout=widgets.Layout(display="none", gap="4px"))
    props_box = panel_box([props_label, props_html, violations_box], flex="0 0 auto", min_height="150px")

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

        load_btn.disabled = True
        load_btn.description = "Loading\u2026"
        set_status(conn_status, f"Loading {len(items)} report(s)\u2026", GRAY_COLOR)

        start_time = time.time()
        loaded = 0
        errors = 0

        try:
            if len(items) == 1:
                # Single report: load into flat structure
                _report_data = _load_report_data(report=items[0], workspace=ws)
                loaded = 1
            else:
                # Multi-report: load each into grouped structure
                merged = {"pages": {}, "reports": {}, "report_id": "", "workspace_id": ""}
                for i, rpt in enumerate(items):
                    if time.time() - start_time > _LOAD_TIMEOUT:
                        set_status(conn_status, f"\u23f1\ufe0f Timeout after {loaded}/{len(items)}.", "#ff9500")
                        break
                    set_status(conn_status, f"Report {i+1}/{len(items)}: loading '{rpt}'\u2026", GRAY_COLOR)
                    try:
                        data = _load_report_data(report=rpt, workspace=ws)
                        merged["reports"][rpt] = data
                        if not merged["report_id"]:
                            merged["report_id"] = data.get("report_id", "")
                            merged["workspace_id"] = data.get("workspace_id", "")
                        loaded += 1
                    except Exception:
                        errors += 1
                        set_status(conn_status, f"Report {i+1}/{len(items)}: '{rpt}' failed", "#ff9500")
                _report_data = merged

            # Auto-expand all items after load
            if _report_data.get("reports"):
                for r_name, r_data in _report_data["reports"].items():
                    _expanded.add(r_name)
                    for p_name in r_data.get("pages", {}):
                        _expanded.add(f"{r_name}\x1f{p_name}")
            else:
                _expanded.update(_report_data.get("pages", {}).keys())

            _refresh_tree()

            # Compute stats
            total_pages = 0
            total_visuals = 0
            if _report_data.get("reports"):
                for r in _report_data["reports"].values():
                    total_pages += len(r.get("pages", {}))
                    total_visuals += sum(len(p["visuals"]) for p in r.get("pages", {}).values())
            else:
                total_pages = len(_report_data.get("pages", {}))
                total_visuals = sum(len(p["visuals"]) for p in _report_data.get("pages", {}).values())

            elapsed = int(time.time() - start_time)
            err_str = f", {errors} error(s)" if errors else ""
            set_status(conn_status, f"Loaded {loaded}/{len(items)}: {total_pages} pages, {total_visuals} visuals ({elapsed}s{err_str})", "#34c759")

            # Initialize preview for first report
            report_id = _report_data.get("report_id", "")
            workspace_id = _report_data.get("workspace_id", "")
            if not report_id and _report_data.get("reports"):
                first = next(iter(_report_data["reports"].values()), {})
                report_id = first.get("report_id", "")
                workspace_id = first.get("workspace_id", "")
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
            if key.startswith("report:"):
                r_name = key.split(":", 1)[1]
                if r_name in _expanded:
                    _expanded.discard(r_name)
                else:
                    _expanded.add(r_name)
                _refresh_tree()
                return
            if key.startswith("page:"):
                p_name = key.split(":", 1)[1]
                if p_name in _expanded:
                    _expanded.discard(p_name)
                else:
                    _expanded.add(p_name)
                _refresh_tree()
        # Update properties + preview navigation
        props_html.value = _get_properties_html(_report_data, key)

        # Show violation details with Fix buttons if scan results exist
        details = _scan_details.get(key, [])
        if details:
            violation_widgets = []
            violation_widgets.append(widgets.HTML(
                value=f'<div style="font-size:12px; font-weight:600; color:#ff3b30; font-family:{FONT_FAMILY}; '
                f'text-transform:uppercase; letter-spacing:0.5px; margin:8px 0 4px 0;">'
                f'\u26a0\ufe0f {len(details)} Violation(s)</div>'
            ))
            for fixer_name, desc in details:
                fix_btn = widgets.Button(
                    description=f"Fix: {fixer_name}",
                    button_style="warning",
                    layout=widgets.Layout(width="auto"),
                )
                fix_label = widgets.HTML(
                    value=f'<span style="font-size:12px; color:#555; font-family:{FONT_FAMILY};">{desc}</span>'
                )
                # Capture fixer_name for closure
                def _make_fix_handler(fn, k):
                    def _handler(_):
                        ws = workspace_input.value.strip() if workspace_input else None
                        ws = ws or None
                        # Extract report + page from key
                        rpt = ""
                        page = None
                        if k.startswith("visual:"):
                            v_raw = k.split(":")[1]
                            if "\x1f" in v_raw:
                                rpt, page = v_raw.split("\x1f", 1)
                            else:
                                rpt = report_input.value.strip() if report_input else ""
                                page = v_raw
                        elif k.startswith("page:"):
                            p_raw = k.split(":", 1)[1]
                            if "\x1f" in p_raw:
                                rpt, page = p_raw.split("\x1f", 1)
                            else:
                                rpt = report_input.value.strip() if report_input else ""
                                page = p_raw
                        if not rpt:
                            rpt = report_input.value.strip() if report_input else ""
                        if rpt and fn in fixer_callbacks:
                            set_status(conn_status, f"Fixing: {fn}\u2026", GRAY_COLOR)
                            try:
                                import io as _io
                                from contextlib import redirect_stdout as _redirect
                                buf = _io.StringIO()
                                with _redirect(buf):
                                    fixer_callbacks[fn](report=rpt, page_name=page, workspace=ws, scan_only=False)
                                set_status(conn_status, f"\u2713 {fn} applied.", "#34c759")
                            except Exception as e:
                                set_status(conn_status, f"Error: {e}", "#ff3b30")
                    return _handler
                fix_btn.on_click(_make_fix_handler(fixer_name, key))
                violation_widgets.append(widgets.HBox(
                    [fix_btn, fix_label],
                    layout=widgets.Layout(align_items="center", gap="8px"),
                ))
            violations_box.children = violation_widgets
            violations_box.layout.display = ""
        else:
            violations_box.children = []
            violations_box.layout.display = "none"
        # Page navigation via powerbiclient (if widget loaded)
        if _report_widget[0] is not None and key.startswith("page:"):
            p_raw = key.split(":", 1)[1]
            if "\x1f" in p_raw:
                r_name, p_name = p_raw.split("\x1f", 1)
                p = _report_data.get("reports", {}).get(r_name, {}).get("pages", {}).get(p_name, {})
                r_data = _report_data["reports"].get(r_name, {})
                rid = r_data.get("report_id", "")
                wid = r_data.get("workspace_id", "")
                if rid and wid:
                    try:
                        from powerbiclient import Report as PBIReport
                        rpt_widget = PBIReport(group_id=wid, report_id=rid)
                        rpt_widget.layout = widgets.Layout(width="100%", height="400px")
                        _report_widget[0] = rpt_widget
                        preview_content.children = [rpt_widget]
                    except Exception:
                        pass
            else:
                p = _report_data.get("pages", {}).get(p_raw, {})
            page_display = p.get("display_name", p_raw.split("\x1f")[-1] if "\x1f" in p_raw else p_raw)
            try:
                _report_widget[0].set_active_page(page_display)
            except Exception:
                pass

    def on_expand_all(_):
        if _report_data:
            reports = _report_data.get("reports", {})
            if reports:
                for r_name, r_data in reports.items():
                    _expanded.add(r_name)
                    for p_name in r_data.get("pages", {}):
                        _expanded.add(f"{r_name}\x1f{p_name}")
            else:
                _expanded.update(_report_data.get("pages", {}).keys())
            _refresh_tree()

    def on_collapse_all(_):
        _expanded.clear()
        if _report_data:
            _refresh_tree()

    def on_run_action(_):
        """Run the action selected in the dropdown."""
        action = fixer_dropdown.value
        if action == "Select action..." or action not in fixer_callbacks:
            set_status(conn_status, "Select an action from the dropdown first.", "#ff9500")
            return
        ws = workspace_input.value.strip() if workspace_input else None
        ws = ws or None
        # Collect unique (report, page) pairs from all selected items
        targets = []
        for opt in tree.value:
            if opt not in _key_map:
                continue
            key = _key_map[opt]
            rpt = ""
            page = None
            if key.startswith("report:"):
                rpt = key.split(":", 1)[1]
            elif key.startswith("page:"):
                p_raw = key.split(":", 1)[1]
                if "\x1f" in p_raw:
                    rpt, page = p_raw.split("\x1f", 1)
                else:
                    rpt = report_input.value.strip() if report_input else ""
                    page = p_raw
            elif key.startswith("visual:"):
                v_raw = key.split(":")[1]
                if "\x1f" in v_raw:
                    rpt, page = v_raw.split("\x1f", 1)
                else:
                    rpt = report_input.value.strip() if report_input else ""
                    page = v_raw
            if rpt:
                targets.append((rpt, page))
        # Deduplicate
        seen = set()
        unique = []
        for t in targets:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        if not unique:
            rpt = report_input.value.strip() if report_input else ""
            if rpt:
                unique = [(rpt, None)]
        if not unique:
            set_status(conn_status, "No report selected.", "#ff3b30")
            return
        set_status(conn_status, f"Running {action} on {len(unique)} target(s)\u2026", GRAY_COLOR)
        import io as _io
        from contextlib import redirect_stdout as _redirect
        errors = 0
        all_output = []
        for rpt, page in unique:
            try:
                buf = _io.StringIO()
                with _redirect(buf):
                    fixer_callbacks[action](report=rpt, page_name=page, workspace=ws, scan_only=False)
                captured = buf.getvalue().rstrip()
                if captured:
                    all_output.append(captured)
            except Exception:
                errors += 1
        summary = f"\u2713 {action} on {len(unique)} target(s)."
        if errors:
            summary = f"\u26a0\ufe0f {action}: {len(unique) - errors} OK, {errors} error(s)."
        if all_output:
            first_line = all_output[0].splitlines()[0][:80]
            summary += f" {first_line}"
        set_status(conn_status, summary, "#34c759" if not errors else "#ff9500")

    def on_scan(_):
        """Fast local scan — checks loaded visual types for fixable issues without API calls."""
        if not _report_data or (not _report_data.get("pages") and not _report_data.get("reports")):
            set_status(conn_status, "No report loaded. Load first.", "#ff3b30")
            return
        scan_btn.disabled = True
        scan_btn.description = "Scanning\u2026"
        _scan_results.clear()
        _scan_details.clear()

        # Fixer rules: visual type patterns that each fixer would flag
        fixer_rules = {
            "Fix Pie Charts": (lambda v: v.get("type", "").lower() in ("piechart",) or v.get("display_type", "").lower() in ("pie chart", "donut chart"), "Replace pie chart \u2192 bar chart"),
            "Fix Bar Charts": (lambda v: v.get("type", "").lower() in ("barchart",) or "bar chart" in v.get("display_type", "").lower(), "Apply formatting best practices"),
            "Fix Column Charts": (lambda v: v.get("type", "").lower() in ("columnchart",) or "column chart" in v.get("display_type", "").lower(), "Apply formatting best practices"),
            "Hide Visual Filters": (lambda v: True, "Hide visual-level filters from filter pane"),
        }

        # Only use rules for fixers that are actually available
        active_rules = {k: v for k, v in fixer_rules.items() if k in fixer_callbacks}

        total_violations = 0

        def _scan_pages(pages, report_prefix=""):
            nonlocal total_violations
            for p_name, p in pages.items():
                page_key = f"page:{report_prefix}{p_name}" if report_prefix else f"page:{p_name}"
                page_count = 0
                for v_name, v in p.get("visuals", {}).items():
                    v_key = f"visual:{report_prefix}{p_name}:{v_name}" if report_prefix else f"visual:{p_name}:{v_name}"
                    v_violations = []
                    for rule_name, (rule_fn, rule_desc) in active_rules.items():
                        try:
                            if rule_fn(v):
                                v_violations.append((rule_name, rule_desc))
                        except Exception:
                            pass
                    if v_violations:
                        _scan_results[v_key] = len(v_violations)
                        _scan_details[v_key] = v_violations
                        page_count += len(v_violations)
                        total_violations += len(v_violations)
                if page_count > 0:
                    _scan_results[page_key] = page_count

        if _report_data.get("reports"):
            for r_name, r_data in _report_data["reports"].items():
                prefix = f"{r_name}\x1f"
                _scan_pages(r_data.get("pages", {}), report_prefix=prefix)
                # Aggregate to report level
                rpt_total = sum(v for k, v in _scan_results.items() if k.startswith(f"page:{prefix}"))
                if rpt_total > 0:
                    _scan_results[f"report:{r_name}"] = rpt_total
        else:
            _scan_pages(_report_data.get("pages", {}))

        _refresh_tree()
        scan_btn.disabled = False
        scan_btn.description = "\U0001F50D Scan"
        if total_violations > 0:
            n_reports = len(_report_data.get("reports", {})) or 1
            set_status(conn_status, f"\U0001F50D Scan complete: {total_violations} finding(s) across {n_reports} report(s).", "#ff9500")
        else:
            set_status(conn_status, f"\u2713 Scan complete: no issues found.", "#34c759")

    load_btn.on_click(on_load)
    tree.observe(on_select, names="value")
    expand_btn.on_click(on_expand_all)
    collapse_btn.on_click(on_collapse_all)
    scan_btn.on_click(on_scan)
    run_action_btn.on_click(on_run_action)

    widget = widgets.VBox([nav_row, action_row, tree_header, panels], layout=widgets.Layout(padding="12px", gap="4px"))
    return widget, on_load