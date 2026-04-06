# Unified Chart Fixer — covers bar, column, line, and combo charts.
# Each chart type has its own checks config (axis semantics differ).
# Line charts keep the Y value axis visible.
# Column↔Bar fixer: converts non-time column charts to bar charts (IBCS).

import re
from uuid import UUID
from typing import Optional
from sempy._utils._log import log
import sempy_labs._icons as icons
from sempy_labs.report._reportwrapper import connect_report
from sempy_labs._helper_functions import resolve_dataset_from_report


def _get_visual_property(visual: dict, object_name: str, property_name: str) -> str | None:
    obj_list = visual.get("visual", {}).get("objects", {}).get(object_name, [])
    if not obj_list:
        return None
    return obj_list[0].get("properties", {}).get(property_name, {}).get("expr", {}).get("Literal", {}).get("Value")


def _set_visual_property(visual: dict, object_name: str, property_name: str, value: str) -> None:
    objects = visual.setdefault("visual", {}).setdefault("objects", {})
    if object_name not in objects or not objects[object_name]:
        objects[object_name] = [{"properties": {}}]
    obj = objects[object_name][0]
    if "properties" not in obj:
        obj["properties"] = {}
    obj["properties"][property_name] = {"expr": {"Literal": {"Value": value}}}


# --- Per-type check configs ---
# Bar charts: value axis = horizontal (X), category axis = vertical (Y)
_BAR_CHECKS = [
    ("valueAxis",    "showAxisTitle", "false", "X axis title"),
    ("valueAxis",    "show",          "false", "X axis values"),
    ("categoryAxis", "showAxisTitle", "false", "Y axis title"),
    ("labels",       "show",          "true",  "Data labels"),
    ("valueAxis",    "gridlineShow",  "false", "Gridlines"),
]

# Column charts: category axis = horizontal (X), value axis = vertical (Y)
_COLUMN_CHECKS = [
    ("categoryAxis", "showAxisTitle", "false", "X axis title"),
    ("valueAxis",    "showAxisTitle", "false", "Y axis title"),
    ("valueAxis",    "show",          "false", "Y axis values"),
    ("labels",       "show",          "true",  "Data labels"),
    ("categoryAxis", "gridlineShow",  "false", "Gridlines"),
]

# Line charts: same layout as column but KEEP Y value axis visible
_LINE_CHECKS = [
    ("categoryAxis", "showAxisTitle", "false", "X axis title"),
    ("valueAxis",    "showAxisTitle", "false", "Y axis title"),
    ("labels",       "show",          "true",  "Data labels"),
    ("categoryAxis", "gridlineShow",  "false", "Gridlines"),
]

_TYPE_CHECKS = {
    "barChart":                        _BAR_CHECKS,
    "clusteredBarChart":               _BAR_CHECKS,
    "columnChart":                     _COLUMN_CHECKS,
    "clusteredColumnChart":            _COLUMN_CHECKS,
    "lineChart":                       _LINE_CHECKS,
    "lineClusteredColumnComboChart":   _LINE_CHECKS,
}

_ALL_CHART_TYPES = set(_TYPE_CHECKS.keys())

_TYPE_LABELS = {
    "barChart":                        "bar chart",
    "clusteredBarChart":               "clustered bar chart",
    "columnChart":                     "column chart",
    "clusteredColumnChart":            "clustered column chart",
    "lineChart":                       "line chart",
    "lineClusteredColumnComboChart":   "line/column combo chart",
}


@log
def fix_charts(
    report: str | UUID,
    page_name: Optional[str] = None,
    workspace: Optional[str | UUID] = None,
    scan_only: bool = False,
    chart_types: Optional[set[str]] = None,
) -> None:
    """
    Fixes chart visuals in a report by applying best-practice formatting.

    Covers bar, column, line, and combo chart types. Applies per-type rules:
    - Bar/Column: remove axis titles, remove value axis labels, add data labels, remove gridlines
    - Line/Combo: same but keeps the Y value axis visible

    Parameters
    ----------
    report : str | uuid.UUID
        Name or ID of the report.
    page_name : str, default=None
        The display name of the page to apply changes to.
        Defaults to None which applies changes to all pages.
    workspace : str | uuid.UUID, default=None
        The Fabric workspace name or ID.
        Defaults to None which resolves to the workspace of the attached lakehouse
        or if no lakehouse attached, resolves to the workspace of the notebook.
    scan_only : bool, default=False
        If True, only scans and reports issues without applying fixes.
    chart_types : set[str], default=None
        Subset of visual types to process. Defaults to all supported types.
    """

    target_types = (chart_types or _ALL_CHART_TYPES) & _ALL_CHART_TYPES

    with connect_report(report=report, workspace=workspace, readonly=scan_only, show_diffs=False) as rw:
        if rw.format != "PBIR":
            print(
                f"{icons.red_dot} Report '{rw._report_name}' is in '{rw.format}' format, not PBIR. "
                f"Run 'Upgrade to PBIR' first."
            )
            return

        paths_df = rw.list_paths()
        charts_found = 0
        charts_fixed = 0
        charts_need_fixing = 0

        page_id = rw.resolve_page_name(page_name) if page_name else None

        for file_path in paths_df["Path"]:
            if not file_path.endswith("/visual.json"):
                continue
            if page_id and f"/{page_id}/" not in file_path:
                continue

            visual = rw.get(file_path=file_path)
            vtype = visual.get("visual", {}).get("visualType")

            if vtype not in target_types:
                continue

            charts_found += 1
            checks = _TYPE_CHECKS[vtype]

            issues = [
                label
                for obj, prop, val, label in checks
                if _get_visual_property(visual, obj, prop) != val
            ]

            if not issues:
                if scan_only:
                    print(f"{icons.green_dot} {file_path} — {_TYPE_LABELS[vtype]} OK")
                continue

            charts_need_fixing += 1
            type_label = _TYPE_LABELS[vtype]

            if scan_only:
                print(f"{icons.yellow_dot} {file_path} — {type_label} needs fixing: {', '.join(issues)}")
                continue

            for obj, prop, val, _ in checks:
                _set_visual_property(visual, obj, prop, val)

            rw.update(file_path=file_path, payload=visual)
            charts_fixed += 1
            print(f"{icons.green_dot} Fixed {type_label} in {file_path}")

        type_desc = "chart" if len(target_types) > 2 else "/".join(sorted({_TYPE_LABELS[t] for t in target_types}))

        if charts_found == 0:
            print(f"{icons.info} No {type_desc}s found in the '{rw._report_name}' report.")
        elif scan_only:
            if charts_need_fixing == 0:
                print(f"\n{icons.green_dot} Scanned {charts_found} {type_desc}(s) — all have correct settings.")
            else:
                print(f"\n{icons.yellow_dot} Scanned {charts_found} {type_desc}(s) — {charts_need_fixing} need fixing.")
        elif charts_fixed == 0:
            print(f"{icons.info} Found {charts_found} {type_desc}(s) — all already have correct settings.")
        else:
            print(f"{icons.green_dot} Successfully fixed {charts_fixed} of {charts_found} {type_desc}(s).")


# Convenience wrappers for backward compatibility
def fix_barcharts(
    report: str | UUID,
    page_name: Optional[str] = None,
    workspace: Optional[str | UUID] = None,
    scan_only: bool = False,
) -> None:
    """Fixes bar chart visuals. Wrapper around fix_charts(chart_types=bar types)."""
    fix_charts(report=report, page_name=page_name, workspace=workspace, scan_only=scan_only,
               chart_types={"barChart", "clusteredBarChart"})


def fix_columncharts(
    report: str | UUID,
    page_name: Optional[str] = None,
    workspace: Optional[str | UUID] = None,
    scan_only: bool = False,
) -> None:
    """Fixes column chart visuals. Wrapper around fix_charts(chart_types=column types)."""
    fix_charts(report=report, page_name=page_name, workspace=workspace, scan_only=scan_only,
               chart_types={"columnChart", "clusteredColumnChart"})


def fix_linecharts(
    report: str | UUID,
    page_name: Optional[str] = None,
    workspace: Optional[str | UUID] = None,
    scan_only: bool = False,
) -> None:
    """Fixes line chart visuals. Keeps Y value axis visible. Wrapper around fix_charts(chart_types=line types)."""
    fix_charts(report=report, page_name=page_name, workspace=workspace, scan_only=scan_only,
               chart_types={"lineChart", "lineClusteredColumnComboChart"})


# ---------------------------------------------------------------------------
# Column↔Bar by Category Type (IBCS)
# ---------------------------------------------------------------------------

_COLUMN_CHART_TYPES = {"columnChart", "clusteredColumnChart"}
_DATE_DATA_TYPES = {"DateTime", "DateTimeOffset"}
_TIME_NAME_PATTERN = re.compile(
    r"(date|month|year|quarter|period|week|day|fiscal|calendar)",
    re.IGNORECASE,
)

# Standalone mapping: preserve stacked/clustered
_COL_TO_BAR = {
    "columnChart": "barChart",
    "clusteredColumnChart": "clusteredBarChart",
}


def _get_category_fields(visual: dict) -> list[tuple[str, str]]:
    """Return [(table, column), ...] from the Category axis projections."""
    projections = (
        visual.get("visual", {})
        .get("query", {})
        .get("queryState", {})
        .get("Category", {})
        .get("projections", [])
    )
    result = []
    for proj in projections:
        field = proj.get("field", {})
        col = field.get("Column", {})
        if not col:
            continue
        prop = col.get("Property")
        entity = col.get("Expression", {}).get("SourceRef", {}).get("Entity")
        if prop and entity:
            result.append((entity, prop))
    return result


def _is_time_field(table: str, column: str, date_columns: set) -> bool:
    """Check if a field is time-based by DataType or name pattern."""
    if (table, column) in date_columns:
        return True
    if _TIME_NAME_PATTERN.search(column):
        return True
    return False


@log
def fix_column_to_bar(
    report: str | UUID,
    page_name: Optional[str] = None,
    workspace: Optional[str | UUID] = None,
    scan_only: bool = False,
    force_clustered: bool = False,
) -> None:
    """
    Converts column charts to bar charts when the category axis is NOT time-based (IBCS).

    IBCS rule: time series use vertical columns (left→right), structural
    comparisons use horizontal bars (top→bottom). This fixer detects column
    charts whose category axis does not contain date/time fields and converts
    them to bar charts.

    Parameters
    ----------
    report : str | uuid.UUID
        Name or ID of the report.
    page_name : str, default=None
        Page to apply changes to. None = all pages.
    workspace : str | uuid.UUID, default=None
        The Fabric workspace name or ID.
    scan_only : bool, default=False
        If True, only scans without applying fixes.
    force_clustered : bool, default=False
        If True, always convert to clusteredBarChart regardless of source type.
        Used when called from the IBCS variance fixer.
    """

    with connect_report(report=report, workspace=workspace, readonly=scan_only, show_diffs=False) as rw:
        if rw.format != "PBIR":
            print(
                f"{icons.red_dot} Report '{rw._report_name}' is in '{rw.format}' format, not PBIR. "
                f"Run 'Upgrade to PBIR' first."
            )
            return

        # Build set of Date/DateTime columns from the semantic model
        dataset_id, _, dataset_workspace_id, _ = resolve_dataset_from_report(
            report=rw._report_id, workspace=rw._workspace_id
        )
        import sempy.fabric as fabric

        df_cols = fabric.list_columns(dataset=dataset_id, workspace=dataset_workspace_id)
        date_columns = set()
        for _, row in df_cols.iterrows():
            if row.get("Data Type") in _DATE_DATA_TYPES:
                date_columns.add((row["Table Name"], row["Column Name"]))

        paths_df = rw.list_paths()
        charts_found = 0
        charts_converted = 0
        charts_need_fixing = 0

        page_id = rw.resolve_page_name(page_name) if page_name else None

        for file_path in paths_df["Path"]:
            if not file_path.endswith("/visual.json"):
                continue
            if page_id and f"/{page_id}/" not in file_path:
                continue

            visual = rw.get(file_path=file_path)
            vtype = visual.get("visual", {}).get("visualType")

            if vtype not in _COLUMN_CHART_TYPES:
                continue

            charts_found += 1
            category_fields = _get_category_fields(visual)

            # If any category field is time-based, keep as column chart
            is_time = any(_is_time_field(t, c, date_columns) for t, c in category_fields)

            if is_time:
                if scan_only:
                    cols = ", ".join(f"{t}.{c}" for t, c in category_fields) or "(no fields)"
                    print(f"{icons.green_dot} {file_path} — {vtype} with time axis [{cols}] — keep as column")
                continue

            charts_need_fixing += 1
            cols_str = ", ".join(f"{t}.{c}" for t, c in category_fields) or "(no fields)"
            target_type = "clusteredBarChart" if force_clustered else _COL_TO_BAR[vtype]

            if scan_only:
                print(f"{icons.yellow_dot} {file_path} — {vtype} [{cols_str}] → should be {target_type}")
                continue

            visual["visual"]["visualType"] = target_type
            rw.update(file_path=file_path, payload=visual)
            charts_converted += 1
            print(f"{icons.green_dot} Changed {vtype} → {target_type}: {file_path} [{cols_str}]")

        if charts_found == 0:
            print(f"{icons.info} No column charts found in '{rw._report_name}'.")
        elif scan_only:
            if charts_need_fixing == 0:
                print(f"\n{icons.green_dot} Scanned {charts_found} column chart(s) — all have time-based axes.")
            else:
                print(f"\n{icons.yellow_dot} Scanned {charts_found} column chart(s) — {charts_need_fixing} should be bar charts.")
        elif charts_converted == 0:
            print(f"{icons.info} Found {charts_found} column chart(s) — all have time-based axes.")
        else:
            print(f"{icons.green_dot} Converted {charts_converted} of {charts_found} column chart(s) to bar charts.")
