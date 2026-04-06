# Report Prototype Generator — standalone module.
# Generates an SVG diagram and Excalidraw JSON of all report pages with optional screenshots.

import base64
import json
import os
import uuid
from typing import Optional
from uuid import UUID


def generate_report_prototype(
    report: str,
    workspace: Optional[str | UUID] = None,
    screenshots: bool = False,
    include_hidden: bool = False,
    cols: int = 4,
    thumb_width: int = 480,
    thumb_height: int = 270,
    on_progress=None,
) -> dict:
    """
    Generates a visual prototype of a Power BI report as SVG + Excalidraw.

    Parameters
    ----------
    report : str
        Name of the Power BI report.
    workspace : str | uuid.UUID, default=None
        The Fabric workspace name or ID.
    screenshots : bool, default=False
        If True, exports each page as PNG via the Export API and embeds as images.
    include_hidden : bool, default=False
        If True, includes hidden pages in the diagram.
    cols : int, default=4
        Number of columns in the page grid layout.
    thumb_width : int, default=480
        Width of each page thumbnail in the diagram.
    thumb_height : int, default=270
        Height of each page thumbnail in the diagram.

    Returns
    -------
    dict
        A dictionary with keys:
        - "svg": str — the SVG diagram as a string
        - "excalidraw": str — the Excalidraw JSON as a string
        - "pages": list — page metadata
        - "screenshots": int — number of screenshots captured
        - "errors": list — export error messages
    """
    from sempy_labs.report import connect_report

    # Layout constants
    pad_x = 40
    pad_y = 60
    header_h = 30
    footer_h = 25

    # 1. Load page metadata + navigation edges
    pages_data = []
    nav_edges = []  # (source_page_name, target_page_name)
    with connect_report(report=report, readonly=True, workspace=workspace) as rw:
        try:
            pages_df = rw.list_pages()
        except Exception:
            # Fallback for PBIRLegacy or other issues — parse pages directly from parts
            import pandas as pd
            pages_df = pd.DataFrame(columns=["Page Name", "Page Display Name", "Width", "Height",
                                             "Hidden", "Drillthrough Target Page", "Visual Count", "Data Visual Count"])
            _fallback_rows = []
            for part in rw._report_definition.get("parts", []):
                path = part.get("path", "")
                if not path.endswith("/page.json"):
                    continue
                payload = part.get("payload")
                if not isinstance(payload, dict):
                    continue
                pg_name = payload.get("name", "")
                is_hidden = payload.get("visibility", "") == "HiddenInViewMode"
                # Check drillthrough from filterConfig
                is_dt = False
                for f in payload.get("filterConfig", {}).get("filters", []):
                    if f.get("howCreated") == "Drillthrough":
                        is_dt = True
                        break
                # Count visuals for this page
                page_prefix = path[:-9]  # strip "page.json"
                v_count = sum(1 for p in rw._report_definition.get("parts", [])
                              if p.get("path", "").startswith(page_prefix) and p.get("path", "").endswith("/visual.json"))
                _fallback_rows.append({
                    "Page Name": pg_name,
                    "Page Display Name": payload.get("displayName", pg_name),
                    "Width": payload.get("width", 1280),
                    "Height": payload.get("height", 720),
                    "Hidden": is_hidden,
                    "Drillthrough Target Page": is_dt,
                    "Visual Count": v_count,
                    "Data Visual Count": 0,
                })
            if _fallback_rows:
                pages_df = pd.DataFrame(_fallback_rows)

        for _, row in pages_df.iterrows():
            pages_data.append({
                "name": str(row.get("Page Name", "")),
                "display_name": str(row.get("Page Display Name", "")),
                "hidden": bool(row.get("Hidden", False)),
                "width": int(row.get("Width", 1280)),
                "height": int(row.get("Height", 720)),
                "drillthrough": bool(row.get("Drillthrough Target Page", False)),
                "visual_count": int(row.get("Visual Count", 0)),
                "data_visual_count": int(row.get("Data Visual Count", 0)),
            })

        # Extract page navigation from visualLink on all visuals
        # (cf. https://actionablereporting.com/2026/03/09/power-bi-report-prototyping-with-ai/)
        page_names = {p["name"] for p in pages_data}
        page_name_lookup = {}  # folder_id -> page_name (in case they differ)
        for part in rw._report_definition.get("parts", []):
            path = part.get("path", "")
            if path.endswith("/page.json"):
                payload = part.get("payload")
                if isinstance(payload, dict):
                    pg_folder = path.replace("\\", "/").split("/")
                    try:
                        pi = pg_folder.index("pages")
                        folder_id = pg_folder[pi + 1]
                        pg_name = payload.get("name", folder_id)
                        page_name_lookup[folder_id] = pg_name
                    except (ValueError, IndexError):
                        pass

        drillthrough_pages = {p["name"] for p in pages_data if p.get("drillthrough")}

        for part in rw._report_definition.get("parts", []):
            path = part.get("path", "")
            if not path.endswith("/visual.json"):
                continue
            # Derive source page from path: .../pages/<page_id>/visuals/<vid>/visual.json
            segments = path.replace("\\", "/").split("/")
            try:
                pi = segments.index("pages")
                folder_id = segments[pi + 1]
            except (ValueError, IndexError):
                continue
            source_page = page_name_lookup.get(folder_id, folder_id)
            if source_page not in page_names:
                continue
            payload = part.get("payload")
            if not isinstance(payload, dict):
                continue
            try:
                vis_links = (
                    payload.get("visual", {})
                    .get("visualContainerObjects", {})
                    .get("visualLink", [])
                )
                for link in vis_links:
                    props = link.get("properties", {})
                    show_val = (
                        props.get("show", {})
                        .get("expr", {})
                        .get("Literal", {})
                        .get("Value", "false")
                    )
                    if show_val != "true":
                        continue
                    action_type = (
                        props.get("type", {})
                        .get("expr", {})
                        .get("Literal", {})
                        .get("Value", "")
                        .strip("'")
                    )
                    target_page = (
                        props.get("navigationSection", {})
                        .get("expr", {})
                        .get("Literal", {})
                        .get("Value", "")
                        .strip("'")
                    )
                    # Resolve target page name if it's a folder ID
                    target_page = page_name_lookup.get(target_page, target_page)
                    if action_type == "PageNavigation" and target_page and target_page in page_names:
                        nav_edges.append((source_page, target_page))
            except Exception:
                continue  # skip visuals with unexpected payload structure

    if not pages_data:
        return {"svg": "", "excalidraw": "", "pages": [], "screenshots": 0, "errors": ["No pages found"]}

    # 2. Export screenshots (optional, parallel)
    page_images = {}
    export_errors = []
    if screenshots:
        from sempy_labs.report import export_report
        import sempy.fabric as fabric
        import sys
        import io as _io
        import threading

        # Pre-resolve report ID once (Win 1: avoids N×list_items calls)
        _resolved_report_id = None
        try:
            dfI = fabric.list_items(workspace=workspace)
            dfI_filt = dfI[
                (dfI["Type"] == "Report") & (dfI["Display Name"] == report)
            ]
            if not dfI_filt.empty:
                _resolved_report_id = dfI_filt["Id"].iloc[0]
        except Exception:
            pass

        target_pages = [(idx, pg) for idx, pg in enumerate(pages_data) if include_hidden or not pg["hidden"]]
        total_pages = len(target_pages)
        _lock = threading.Lock()
        _done_count = [0]

        def _export_one(idx, pg):
            # Suppress all output inside each thread
            import sys as _tsys
            import io as _tio
            _t_old_stdout = _tsys.stdout
            _tsys.stdout = _tio.StringIO()
            try:
                import IPython.display as _tipd
                _tipd_orig = _tipd.display
                _tipd.display = lambda *a, **kw: None
            except Exception:
                _tipd = None
                _tipd_orig = None
            try:
                # Win 3: get PNG bytes directly, skip file I/O
                png_bytes = export_report(
                    report=report,
                    export_format="PNG",
                    file_name=f"_prototype_{idx:02d}",
                    page_name=pg["name"],
                    workspace=workspace,
                    _report_id=_resolved_report_id,
                    _return_bytes=True,
                )
                if png_bytes:
                    with _lock:
                        page_images[pg["name"]] = base64.b64encode(png_bytes).decode("ascii")
                else:
                    with _lock:
                        export_errors.append(f"'{pg['display_name']}': empty response")
            except Exception as e:
                with _lock:
                    export_errors.append(f"'{pg['display_name']}': {str(e)[:200]}")
            finally:
                _tsys.stdout = _t_old_stdout
                if _tipd and _tipd_orig:
                    _tipd.display = _tipd_orig
                with _lock:
                    _done_count[0] += 1
                    done = _done_count[0]
                if on_progress:
                    try:
                        on_progress(done, total_pages, pg["display_name"])
                    except Exception:
                        pass

        # Redirect stdout AND suppress IPython.display to prevent notebook output overflow
        _real_stdout = sys.stdout
        sys.stdout = _io.StringIO()

        # Monkey-patch IPython display to a no-op during exports
        _ipd = None
        _ipd_orig = None
        _idf = None
        _idf_orig = None
        try:
            import IPython.display as _ipd_mod
            _ipd = _ipd_mod
            _ipd_orig = _ipd_mod.display
            _ipd_mod.display = lambda *a, **kw: None
        except Exception:
            pass
        try:
            import IPython.core.display_functions as _idf_mod
            _idf = _idf_mod
            _idf_orig = _idf_mod.display
            _idf_mod.display = lambda *a, **kw: None
        except Exception:
            pass

        try:
            if on_progress:
                on_progress(0, total_pages, "starting exports...")
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(5, total_pages)) as pool:
                pool.map(lambda args: _export_one(*args), target_pages)
        finally:
            sys.stdout = _real_stdout
            if _ipd and _ipd_orig:
                _ipd.display = _ipd_orig
            if _idf and _idf_orig:
                _idf.display = _idf_orig

    # Deduplicate navigation edges
    nav_edges = list(set(nav_edges))

    # 3. Build diagram
    svg_str, excalidraw_str = _build_diagram(
        pages_data, page_images, include_hidden,
        cols, thumb_width, thumb_height, pad_x, pad_y, header_h, footer_h,
        nav_edges,
    )

    print(f"\u2713 Prototype: {len(pages_data)} pages, {len(page_images)} screenshots, {len(nav_edges)} nav links.")
    dt_count = sum(1 for p in pages_data if p.get("drillthrough"))
    if dt_count:
        print(f"  \u2192 {dt_count} drillthrough target page(s)")
    if export_errors:
        for err in export_errors[:3]:
            print(f"  \u26a0 {err}")

    return {
        "svg": svg_str,
        "excalidraw": excalidraw_str,
        "pages": pages_data,
        "screenshots": len(page_images),
        "errors": export_errors,
        "nav_edges": nav_edges,
    }


def save_report_prototype(
    report: str,
    workspace: Optional[str | UUID] = None,
    screenshots: bool = False,
    include_hidden: bool = False,
    cols: int = 4,
):
    """
    Generates and saves a report prototype to the lakehouse.

    Saves both .excalidraw and .svg files to lakehouse Files/.

    Parameters
    ----------
    report : str
        Name of the Power BI report.
    workspace : str | uuid.UUID, default=None
        The Fabric workspace name or ID.
    screenshots : bool, default=False
        If True, exports each page as PNG via the Export API.
    include_hidden : bool, default=False
        If True, includes hidden pages.
    cols : int, default=4
        Number of columns in the grid layout.
    """
    result = generate_report_prototype(
        report=report, workspace=workspace,
        screenshots=screenshots, include_hidden=include_hidden, cols=cols,
    )

    safe_name = report.replace(" ", "_").replace("/", "_")
    from sempy_labs._helper_functions import _mount
    local_path = _mount()

    exc_path = f"{local_path}/Files/{safe_name}_prototype.excalidraw"
    with open(exc_path, "w", encoding="utf-8") as f:
        f.write(result["excalidraw"])
    print(f"\u2713 Saved {safe_name}_prototype.excalidraw")

    svg_path = f"{local_path}/Files/{safe_name}_prototype.svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(result["svg"])
    print(f"\u2713 Saved {safe_name}_prototype.svg")

    return result


def _build_diagram(pages, images, include_hidden, cols, thumb_w, thumb_h, pad_x, pad_y, header_h, footer_h, nav_edges=None):
    """Build SVG + Excalidraw JSON from page metadata and images."""
    font_family = "-apple-system,BlinkMacSystemFont,sans-serif"

    visible = [p for p in pages if include_hidden or not p["hidden"]]
    n = len(visible)
    cols = min(cols, n) if n > 0 else 1
    rows_count = (n + cols - 1) // cols

    svg_w = cols * (thumb_w + pad_x) + pad_x
    svg_h = rows_count * (thumb_h + header_h + footer_h + pad_y) + pad_y

    svg_parts = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">']
    svg_parts.append(f'<rect width="{svg_w}" height="{svg_h}" fill="#ffffff"/>')

    exc_elements = []
    exc_files = {}

    _COLORS = {
        "normal": {"bg": "#dbeafe", "stroke": "#2563eb", "text": "#1e40af"},
        "drillthrough": {"bg": "#ffedd5", "stroke": "#c2410c", "text": "#9a3412"},
        "hidden": {"bg": "#f3f4f6", "stroke": "#9ca3af", "text": "#6b7280"},
    }

    for idx, pg in enumerate(visible):
        col = idx % cols
        row = idx // cols
        x = pad_x + col * (thumb_w + pad_x)
        y = pad_y + row * (thumb_h + header_h + footer_h + pad_y)

        ptype = "hidden" if pg["hidden"] else ("drillthrough" if pg["drillthrough"] else "normal")
        colors = _COLORS[ptype]

        # Header
        svg_parts.append(f'<rect x="{x}" y="{y}" width="{thumb_w}" height="{header_h}" rx="6" ry="6" fill="{colors["bg"]}" stroke="{colors["stroke"]}" stroke-width="1.5"/>')
        label = pg["display_name"][:35]
        if pg["drillthrough"]:
            label = f"\u2192 {label}"
        if pg["hidden"]:
            label = f"[H] {label}"
        svg_parts.append(f'<text x="{x + 10}" y="{y + 20}" font-family="{font_family}" font-size="13" font-weight="600" fill="{colors["text"]}">{label}</text>')
        badge_text = f'{pg["visual_count"]}v / {pg["data_visual_count"]}d'
        svg_parts.append(f'<text x="{x + thumb_w - 10}" y="{y + 20}" font-family="{font_family}" font-size="11" fill="{colors["text"]}" text-anchor="end">{badge_text}</text>')

        img_y = y + header_h

        # Screenshot or placeholder
        if pg["name"] in images:
            b64 = images[pg["name"]]
            svg_parts.append(f'<image x="{x}" y="{img_y}" width="{thumb_w}" height="{thumb_h}" href="data:image/png;base64,{b64}" preserveAspectRatio="xMidYMid meet"/>')
            file_id = str(uuid.uuid4())
            exc_files[file_id] = {"mimeType": "image/png", "id": file_id, "dataURL": f"data:image/png;base64,{b64}"}
            exc_elements.append({
                "type": "image", "id": str(uuid.uuid4()), "x": x, "y": img_y,
                "width": thumb_w, "height": thumb_h, "fileId": file_id,
                "status": "saved", "scale": [1, 1],
            })
        else:
            svg_parts.append(f'<rect x="{x}" y="{img_y}" width="{thumb_w}" height="{thumb_h}" rx="4" fill="#f9fafb" stroke="#e5e7eb" stroke-width="1"/>')
            svg_parts.append(f'<text x="{x + thumb_w // 2}" y="{img_y + thumb_h // 2}" font-family="{font_family}" font-size="14" fill="#9ca3af" text-anchor="middle" dominant-baseline="middle">{pg["display_name"]}</text>')
            svg_parts.append(f'<text x="{x + thumb_w // 2}" y="{img_y + thumb_h // 2 + 20}" font-family="{font_family}" font-size="11" fill="#d1d5db" text-anchor="middle">(no screenshot)</text>')

        # Excalidraw header
        exc_elements.append({
            "type": "rectangle", "id": str(uuid.uuid4()), "x": x, "y": y,
            "width": thumb_w, "height": header_h,
            "backgroundColor": colors["bg"], "strokeColor": colors["stroke"],
            "fillStyle": "solid", "strokeWidth": 1, "roundness": {"type": 3},
        })
        exc_elements.append({
            "type": "text", "id": str(uuid.uuid4()), "x": x + 10, "y": y + 5,
            "width": thumb_w - 20, "height": header_h - 5,
            "text": label, "fontSize": 14, "fontFamily": 1,
            "textAlign": "left", "verticalAlign": "top", "rawText": label,
        })
        exc_elements.append({
            "type": "text", "id": str(uuid.uuid4()),
            "x": x + thumb_w - 80, "y": y + 5,
            "width": 70, "height": 20,
            "text": badge_text, "fontSize": 11, "fontFamily": 1,
            "textAlign": "right", "verticalAlign": "top", "rawText": badge_text,
        })

        # Footer
        footer_y = img_y + thumb_h + 3
        size_text = f'{pg["width"]}\u00d7{pg["height"]}'
        svg_parts.append(f'<text x="{x + 5}" y="{footer_y + 14}" font-family="{font_family}" font-size="10" fill="#9ca3af">{size_text}</text>')
        dt_label = "Drillthrough" if pg["drillthrough"] else ("Hidden" if pg["hidden"] else "")
        svg_parts.append(f'<text x="{x + thumb_w - 5}" y="{footer_y + 14}" font-family="{font_family}" font-size="10" fill="{colors["text"]}" text-anchor="end">{dt_label}</text>')

        exc_elements.append({
            "type": "text", "id": str(uuid.uuid4()),
            "x": x + 5, "y": footer_y, "width": 100, "height": 20,
            "text": size_text, "fontSize": 10, "fontFamily": 1,
            "textAlign": "left", "verticalAlign": "top",
            "strokeColor": "#9ca3af", "rawText": size_text,
        })
        if dt_label:
            exc_elements.append({
                "type": "text", "id": str(uuid.uuid4()),
                "x": x + thumb_w - 100, "y": footer_y, "width": 95, "height": 20,
                "text": dt_label, "fontSize": 10, "fontFamily": 1,
                "textAlign": "right", "verticalAlign": "top",
                "strokeColor": colors["text"], "rawText": dt_label,
            })

    # Navigation arrows — real edges from visualLink data
    if nav_edges:
        page_idx_map = {p["name"]: i for i, p in enumerate(visible)}
        seen_edges = set()
        for src_name, tgt_name in nav_edges:
            if src_name not in page_idx_map or tgt_name not in page_idx_map:
                continue
            edge_key = (src_name, tgt_name)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            si = page_idx_map[src_name]
            di = page_idx_map[tgt_name]
            src_col, src_row = si % cols, si // cols
            dst_col, dst_row = di % cols, di // cols
            x1 = pad_x + src_col * (thumb_w + pad_x) + thumb_w // 2
            y1 = pad_y + src_row * (thumb_h + header_h + footer_h + pad_y) + header_h + thumb_h + footer_h
            x2 = pad_x + dst_col * (thumb_w + pad_x) + thumb_w // 2
            y2 = pad_y + dst_row * (thumb_h + header_h + footer_h + pad_y)
            svg_parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#2563eb" stroke-width="1.5" stroke-dasharray="6,3" marker-end="url(#arrowhead-nav)"/>')

    svg_parts.insert(1, '<defs><marker id="arrowhead-nav" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#2563eb"/></marker></defs>')
    svg_parts.append('</svg>')

    # Excalidraw: add navigation map (box diagram) below the screenshot grid
    _add_nav_map(exc_elements, visible, nav_edges, svg_h + 80)

    excalidraw_json = {
        "type": "excalidraw",
        "version": 2,
        "source": "pbi_fixer",
        "elements": exc_elements,
        "files": exc_files,
    }

    return "\n".join(svg_parts), json.dumps(excalidraw_json, indent=2)


def _add_nav_map(elements, visible_pages, nav_edges, start_y):
    """Add a navigation map box diagram with colored boxes and arrows below the screenshot grid."""
    if not visible_pages:
        return

    LEVEL_COLORS = [
        {"bg": "#ccfbf1", "stroke": "#0d9488"},  # L0 Teal — Root/Landing
        {"bg": "#dbeafe", "stroke": "#2563eb"},  # L1 Blue
        {"bg": "#ede9fe", "stroke": "#7c3aed"},  # L2 Purple
        {"bg": "#ffedd5", "stroke": "#c2410c"},  # L3 Orange
        {"bg": "#fee2e2", "stroke": "#dc2626"},  # L4+ Red
    ]
    HIDDEN_COLOR = {"bg": "#f3f4f6", "stroke": "#9ca3af"}
    BOX_W, BOX_H, INDENT, V_GAP = 300, 40, 50, 12
    COL_SPACING = BOX_W + INDENT * 5 + 60

    page_map = {p["name"]: p for p in visible_pages}

    # Build adjacency from nav_edges
    children_map = {}
    has_parent = set()
    edge_set = set()
    for src, tgt in (nav_edges or []):
        if src in page_map and tgt in page_map:
            key = (src, tgt)
            if key not in edge_set:
                edge_set.add(key)
                children_map.setdefault(src, []).append(tgt)
                has_parent.add(tgt)

    # Find roots (pages with outgoing but no incoming edges)
    roots = [p["name"] for p in visible_pages
             if p["name"] not in has_parent and p["name"] in children_map]
    if not roots and children_map:
        roots = [max(children_map, key=lambda k: len(children_map[k]))]

    # BFS to build branches (one per root)
    visited = set()
    branches = []
    for root in roots:
        if root in visited:
            continue
        branch = []
        queue = [(root, 0)]
        visited.add(root)
        i = 0
        while i < len(queue):
            node, level = queue[i]
            i += 1
            branch.append((node, level))
            for child in children_map.get(node, []):
                if child not in visited:
                    visited.add(child)
                    queue.append((child, level + 1))
        branches.append(branch)

    # Standalone pages (no nav_edges)
    standalone = [p["name"] for p in visible_pages if p["name"] not in visited]
    if standalone:
        branches.append([(name, 0) for name in standalone])

    # Title
    elements.append({
        "type": "text", "id": str(uuid.uuid4()),
        "x": 0, "y": start_y, "width": 400, "height": 36,
        "text": "Navigation Map", "fontSize": 28, "fontFamily": 1,
        "textAlign": "left", "verticalAlign": "top",
        "strokeColor": "#0d9488", "roughness": 0,
        "rawText": "Navigation Map",
    })

    # Legend
    legend_y = start_y + 42
    for li, (ltxt, lcol) in enumerate([
        ("\u2192 Button Navigation", "#2563eb"),
        ("\u2192 Drillthrough Target", "#c2410c"),
        ("Hidden Page", "#9ca3af"),
    ]):
        elements.append({
            "type": "text", "id": str(uuid.uuid4()),
            "x": li * 220, "y": legend_y, "width": 210, "height": 20,
            "text": ltxt, "fontSize": 12, "fontFamily": 1,
            "textAlign": "left", "verticalAlign": "top",
            "strokeColor": lcol, "roughness": 0, "rawText": ltxt,
        })

    # Layout branches as columns, pages stacked vertically with level indentation
    map_y = legend_y + 35
    col_x = 0
    box_pos = {}
    level_map = {}

    for branch in branches:
        y = map_y
        for page_name, level in branch:
            pg = page_map[page_name]
            x = col_x + level * INDENT

            if pg["hidden"]:
                color = HIDDEN_COLOR
            else:
                color = LEVEL_COLORS[min(level, len(LEVEL_COLORS) - 1)]

            # Rectangle box
            elements.append({
                "type": "rectangle", "id": str(uuid.uuid4()),
                "x": x, "y": y, "width": BOX_W, "height": BOX_H,
                "backgroundColor": color["bg"], "strokeColor": color["stroke"],
                "fillStyle": "solid", "strokeWidth": 2, "roughness": 0,
                "roundness": {"type": 3},
            })

            # Page label
            prefix = "[H] " if pg["hidden"] else ""
            if pg["drillthrough"]:
                prefix += "\u2192 "
            label = f'{prefix}{pg["display_name"]}'
            badge = f'{pg["visual_count"]}v / {pg["data_visual_count"]}d'

            elements.append({
                "type": "text", "id": str(uuid.uuid4()),
                "x": x + 10, "y": y + 10, "width": BOX_W - 100, "height": 20,
                "text": label, "fontSize": 14, "fontFamily": 1,
                "textAlign": "left", "verticalAlign": "top",
                "strokeColor": color["stroke"], "roughness": 0, "rawText": label,
            })
            elements.append({
                "type": "text", "id": str(uuid.uuid4()),
                "x": x + BOX_W - 85, "y": y + 12, "width": 75, "height": 16,
                "text": badge, "fontSize": 11, "fontFamily": 1,
                "textAlign": "right", "verticalAlign": "top",
                "strokeColor": color["stroke"], "roughness": 0, "rawText": badge,
            })

            box_pos[page_name] = (x, y)
            level_map[page_name] = level
            y += BOX_H + V_GAP

        col_x += COL_SPACING

    # Arrows connecting pages based on nav_edges
    for src, tgt in edge_set:
        if src not in box_pos or tgt not in box_pos:
            continue
        sx, sy = box_pos[src]
        tx, ty = box_pos[tgt]

        # Arrow from bottom-center of source to top-center of target
        ax = sx + BOX_W // 2
        ay = sy + BOX_H
        dx = (tx + BOX_W // 2) - ax
        dy = ty - ay

        if abs(dx) < 2 and abs(dy) < 2:
            continue

        # Color matches target level
        tgt_lvl = level_map.get(tgt, 0)
        arrow_color = LEVEL_COLORS[min(tgt_lvl, len(LEVEL_COLORS) - 1)]["stroke"]

        elements.append({
            "type": "arrow", "id": str(uuid.uuid4()),
            "x": ax, "y": ay,
            "width": max(abs(dx), 1), "height": max(abs(dy), 1),
            "strokeColor": arrow_color, "strokeWidth": 2,
            "strokeStyle": "solid", "roughness": 0, "opacity": 100,
            "roundness": {"type": 2},
            "points": [[0, 0], [dx, dy]],
            "startBinding": None, "endBinding": None,
            "startArrowhead": None, "endArrowhead": "arrow",
        })
