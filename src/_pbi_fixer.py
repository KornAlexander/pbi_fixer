# Interactive PBI Report Fixer UI (ipywidgets)
# Orchestrates report visual fixers and semantic model fixers via a single notebook widget.

__version__ = "1.0.3"

import ipywidgets as widgets
import io
from contextlib import redirect_stdout
from typing import Optional
from uuid import UUID

from sempy_labs.report._Fix_UpgradeToPbir import fix_upgrade_to_pbir
from sempy_labs.report._Fix_PieChart import fix_piecharts
from sempy_labs.report._Fix_BarChart import fix_barcharts
from sempy_labs.report._Fix_ColumnChart import fix_columncharts
from sempy_labs.report._Fix_PageSize import fix_page_size
from sempy_labs.report._Fix_HideVisualFilters import fix_hide_visual_filters
from sempy_labs.semantic_model._Add_CalculatedTable_Calendar import add_calculated_calendar
from sempy_labs.semantic_model._Fix_DiscourageImplicitMeasures import fix_discourage_implicit_measures
from sempy_labs.semantic_model._Fix_DefaultDataSourceVersion import fix_default_datasource_version
from sempy_labs.semantic_model._Add_Table_LastRefresh import add_last_refresh_table
from sempy_labs.semantic_model._Add_CalcGroup_Units import add_calc_group_units
from sempy_labs.semantic_model._Add_CalcGroup_TimeIntelligence import add_calc_group_time_intelligence
from sempy_labs.semantic_model._Add_CalculatedTable_MeasureTable import add_measure_table


def pbi_fixer(
    workspace: Optional[str | UUID] = None,
    report: Optional[str | UUID] = None,
    page_name: Optional[str] = None,
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
        Name or ID of the report. Pre-populates the report input field.
    page_name : str, default=None
        The display name of the page. Pre-populates the page input field.
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
        value=f'<div style="font-size:20px; font-weight:600; color:{text_color}; '
        f'font-family:-apple-system,BlinkMacSystemFont,sans-serif;">Power BI Fixer</div>'
    )
    subtitle = widgets.HTML(
        value=f'<div style="font-size:13px; color:{gray_color}; '
        f'font-family:-apple-system,BlinkMacSystemFont,sans-serif; margin-top:2px;">'
        f'Select fixers to apply to your report and semantic model</div>'
    )
    header = widgets.VBox(
        [title, subtitle],
        layout=widgets.Layout(margin="0 0 16px 0"),
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
    # REPORT INPUTS
    # -----------------------------
    def _input_label(text):
        return widgets.HTML(
            value=f'<span style="font-size:13px; font-weight:500; color:{text_color}; '
            f'font-family:-apple-system,BlinkMacSystemFont,sans-serif; '
            f'min-width:90px; display:inline-block;">{text}</span>'
        )

    report_input = widgets.Text(
        value=str(report) if report else "",
        placeholder="Report name or ID",
        layout=widgets.Layout(width="300px"),
    )
    page_input = widgets.Text(
        value=page_name if page_name else "",
        placeholder="Leave empty for all pages",
        layout=widgets.Layout(width="300px"),
    )
    workspace_input = widgets.Text(
        value=str(workspace) if workspace else "",
        placeholder="Leave empty for notebook workspace",
        layout=widgets.Layout(width="300px"),
    )

    inputs_box = widgets.VBox(
        [
            widgets.HBox(
                [_input_label("Workspace"), workspace_input],
                layout=widgets.Layout(align_items="center", gap="8px"),
            ),
            widgets.HBox(
                [_input_label("Report"), report_input],
                layout=widgets.Layout(align_items="center", gap="8px"),
            ),
            widgets.HBox(
                [_input_label("Page (opt.)"), page_input],
                layout=widgets.Layout(align_items="center", gap="8px"),
            ),
        ],
        layout=widgets.Layout(
            gap="8px",
            padding="12px",
            margin="0 0 16px 0",
            border=f"1px solid {border_color}",
            border_radius="8px",
        ),
    )

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
    cb_upgrade_pbir = widgets.Checkbox(value=False, indent=False, layout=widgets.Layout(width="22px"))
    cb_pie = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_bar = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_col = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_page_size = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_hide_filters = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))

    upgrade_pbir_row = widgets.HBox(
        [cb_upgrade_pbir, _fixer_label("Upgrade to PBIR", "converts PBIRLegacy → PBIR (required for .pbix uploads)")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )
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

    report_fixers_box = widgets.VBox(
        [_section_heading("Report — Visuals"), upgrade_pbir_row, pie_row, bar_row, col_row, page_size_row, hide_filters_row],
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
    cb_datasource_version = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_calendar = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_discourage = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_last_refresh = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_units = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_time_intel = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))
    cb_measure_tbl = widgets.Checkbox(value=True, indent=False, layout=widgets.Layout(width="22px"))

    datasource_version_row = widgets.HBox(
        [cb_datasource_version, _fixer_label("Set DataSource Version V3", "sets DefaultPowerBIDataSourceVersion to PowerBI_V3 (required for XMLA writes)")],
        layout=widgets.Layout(align_items="center", gap="6px"),
    )
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
    _sm_checkboxes = [cb_datasource_version, cb_calendar, cb_discourage, cb_last_refresh, cb_units, cb_time_intel, cb_measure_tbl]

    def _on_sm_cb_change(change=None):
        any_checked = any(cb.value for cb in _sm_checkboxes)
        writes = mode_toggle.value != "Scan"
        sm_warning_confirm.layout.display = "flex" if (any_checked and writes) else "none"
        if not any_checked or not writes:
            cb_sm_confirm.value = False

    for _cb in _sm_checkboxes:
        _cb.observe(_on_sm_cb_change, names="value")
    _on_sm_cb_change()  # evaluate initial state so warning shows if checkboxes start checked

    semantic_model_box = widgets.VBox(
        [_section_heading("Semantic Model"), datasource_version_row, discourage_row, calendar_row, last_refresh_row, measure_tbl_row, units_row, time_intel_row, sm_warning_confirm],
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

    button_row = widgets.HBox(
        [run_btn],
        layout=widgets.Layout(justify_content="flex-end", gap="8px", margin="0 0 8px 0"),
    )

    # -----------------------------
    # RUN HANDLER
    # -----------------------------
    report_fixers = [
        (cb_upgrade_pbir, "Upgrade to PBIR", lambda r, p, w, s: fix_upgrade_to_pbir(report=r, page_name=p, workspace=w, scan_only=s)),
        (cb_pie, "Fix Pie Charts",    lambda r, p, w, s: fix_piecharts(report=r, page_name=p, workspace=w, scan_only=s)),
        (cb_bar, "Fix Bar Charts",    lambda r, p, w, s: fix_barcharts(report=r, page_name=p, workspace=w, scan_only=s)),
        (cb_col, "Fix Column Charts", lambda r, p, w, s: fix_columncharts(report=r, page_name=p, workspace=w, scan_only=s)),
        (cb_page_size, "Fix Page Size", lambda r, p, w, s: fix_page_size(report=r, page_name=p, workspace=w, scan_only=s)),
        (cb_hide_filters, "Hide Visual Filters", lambda r, p, w, s: fix_hide_visual_filters(report=r, page_name=p, workspace=w, scan_only=s)),
    ]

    sm_fixers = [
        (cb_datasource_version, "Set DataSource Version V3", lambda r, w, s: fix_default_datasource_version(report=r, workspace=w, scan_only=s)),
        (cb_discourage, "Discourage Implicit Measures", lambda r, w, s: fix_discourage_implicit_measures(report=r, workspace=w, scan_only=s)),
        (cb_calendar, "Add Calendar Table", lambda r, w, s: add_calculated_calendar(report=r, workspace=w, scan_only=s)),
        (cb_measure_tbl, "Add Measure Table", lambda r, w, s: add_measure_table(report=r, workspace=w, scan_only=s)),
        (cb_last_refresh, "Add Last Refresh Table", lambda r, w, s: add_last_refresh_table(report=r, workspace=w, scan_only=s)),
        (cb_units, "Add Units Calc Group", lambda r, w, s: add_calc_group_units(report=r, workspace=w, scan_only=s)),
        (cb_time_intel, "Add Time Intelligence Calc Group", lambda r, w, s: add_calc_group_time_intelligence(report=r, workspace=w, scan_only=s)),
    ]

    def on_run(_):
        ws = workspace_input.value.strip() or None
        report = report_input.value.strip()
        page = page_input.value.strip() or None
        mode = mode_toggle.value

        if not report:
            show_status("Please enter a report name or ID.", "#ff3b30")
            return

        status.value = ""
        run_btn.disabled = True
        run_btn.description = "Running…"

        rpt_selected = [(cb, label, fn) for cb, label, fn in report_fixers if cb.value]
        sm_selected  = [(cb, label, fn) for cb, label, fn in sm_fixers if cb.value]
        total = len(rpt_selected) + len(sm_selected)

        if total == 0:
            show_status("Please select at least one fixer.", "#ff3b30")
            run_btn.disabled = False
            run_btn.description = "Run"
            return

        # Require confirmation when SM fixers are selected in a mode that writes
        if sm_selected and mode != "Scan" and not cb_sm_confirm.value:
            show_status(
                "⚠️  Please tick the XMLA confirmation checkbox before running semantic model fixers.",
                "#ff9500",
            )
            run_btn.disabled = False
            run_btn.description = "Run"
            return

        def _do_work():
            """Runs all selected fixers sequentially."""
            try:
                _progress_lines.clear()
                progress.layout.display = ""

                def _log(text=""):
                    _progress_lines.append(text)
                    progress.value = (
                        '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif; '
                        'font-size:13px; margin:0; padding:10px; '
                        'max-height:540px; overflow-y:auto; white-space:pre-wrap;">'
                        + "\n".join(_progress_lines)
                        + "</div>"
                    )

                _log(f"{total} Fixers Selected - Starting Now  [Mode: {mode}]")
                _log()
                _log(f"  Workspace: {ws or 'Notebook workspace'}")
                _log(f"  Report:    {report}")
                _log(f"  Page:      {page or 'All'}")
                _log()

                idx = 0
                errors = 0

                def _run_report_fixers(scan: bool):
                    nonlocal idx, errors
                    prefix = "🔍" if scan else "▶"
                    pbir_upgrade_failed = False
                    for cb, label, fn in rpt_selected:
                        idx += 1

                        # If PBIR upgrade failed, skip remaining report fixers
                        # (they all require PBIR format and would show redundant errors)
                        if pbir_upgrade_failed and cb is not cb_upgrade_pbir:
                            _log(f"{prefix} [{idx}/{total}] {label}...")
                            _log(f"   ⏭️ Skipped — PBIR upgrade did not complete.")
                            _log()
                            continue

                        _log(f"{prefix} [{idx}/{total}] {'Scanning' if scan else ''} {label}...")
                        try:
                            buf = io.StringIO()
                            with redirect_stdout(buf):
                                result = fn(report, page, ws, scan)
                            captured = buf.getvalue().rstrip()
                            if captured:
                                for line in captured.splitlines():
                                    _log(f"   {line}")

                            # Check if PBIR upgrade fixer failed (returned False in fix mode)
                            if cb is cb_upgrade_pbir and not scan and result is False:
                                pbir_upgrade_failed = True
                        except Exception as e:
                            errors += 1
                            _log(f"   ❌ Error: {e}")
                            if cb is cb_upgrade_pbir and not scan:
                                pbir_upgrade_failed = True
                        _log()

                def _run_sm_fixers(scan: bool):
                    nonlocal idx, errors
                    prefix = "🔍" if scan else "▶"
                    for _, label, fn in sm_selected:
                        idx += 1
                        _log(f"{prefix} [{idx}/{total}] {'Scanning' if scan else ''} {label}...")
                        try:
                            buf = io.StringIO()
                            with redirect_stdout(buf):
                                fn(report, ws, scan)
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

                if errors > 0:
                    show_status(
                        f"⚠️  Completed with {errors} error(s) out of {total} fixer(s). See progress log above.",
                        "#ff9500",
                    )
                elif mode == "Scan":
                    show_status(f"✓  Scan complete for {total} fixer(s).", "#007aff")
                elif mode == "Fix":
                    show_status(f"✓  All {total} fixer(s) completed successfully.", "#34c759")
                else:
                    show_status(f"✓  Scan + Fix complete for {total} fixer(s).", "#34c759")

            except Exception as e:
                show_status(f"Error: {e}", "#ff3b30")

            finally:
                run_btn.disabled = False
                run_btn.description = "Run"

        _do_work()

    run_btn.on_click(on_run)

    # -----------------------------
    # ASSEMBLE & DISPLAY
    # -----------------------------
    version_footer = widgets.HTML(
        value=f'<div style="text-align:right; font-size:10px; color:{gray_color}; '
        f'font-family:-apple-system,BlinkMacSystemFont,sans-serif; '
        f'margin-top:8px;">Version: {__version__}</div>'
    )

    container = widgets.VBox(
        [
            header,
            mode_row,
            inputs_box,
            report_fixers_box,
            semantic_model_box,
            button_row,
            progress,
            status,
            version_footer,
        ],
        layout=widgets.Layout(
            width="800px",
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
# pbi_fixer(workspace="Your Workspace Name", report="My Report", page_name="Overview")
