# Upgrade Report to PBIR Format
# Converts PBIRLegacy reports to PBIR format using the embed-and-save approach.
# Based on: https://github.com/m-kovalsky/semantic-link-labs/blob/7393dfd/src/sempy_labs/report/_upgrade_to_pbir.py

from uuid import UUID
from typing import Optional, List
from sempy_labs._helper_functions import (
    resolve_workspace_name_and_id,
    resolve_item_name_and_id,
    _base_api,
)
from sempy._utils._log import log
import sempy_labs._icons as icons
import time

try:
    from IPython.display import HTML, display
except ImportError:  # allow import outside notebooks
    HTML = None
    display = print

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_TIME_LIMIT = 60  # seconds to poll for upgrade completion
_TIME_BETWEEN_REQUESTS = 2  # seconds between status checks


# ---------------------------------------------------------------------------
# Helper: Generate an embed token with ReadWrite permission
# ---------------------------------------------------------------------------
def _generate_embed_token(dataset_ids: list, report_ids: list) -> str:
    """Generate a Power BI embed token that includes ReadWrite on the report."""

    if not isinstance(dataset_ids, list):
        dataset_ids = [dataset_ids]
    if not isinstance(report_ids, list):
        report_ids = [report_ids]

    payload = {
        "datasets": [{"id": str(did)} for did in dataset_ids],
        "reports": [{"id": str(rid), "allowEdit": True} for rid in report_ids],
    }

    response = _base_api(
        request="/v1.0/myorg/GenerateToken",
        method="post",
        client="fabric_sp",
        payload=payload,
    )
    return response.json().get("token")


# ---------------------------------------------------------------------------
# Helper: Embed the report in edit mode (hidden) and trigger a save
# ---------------------------------------------------------------------------
def _embed_report_edit_mode(embed_url: str, access_token: str, height: int = 800):
    """
    Renders a hidden Power BI embedded report in edit mode, then
    automatically saves it.  The save triggers the PBIR format conversion
    on the server side.
    """
    html_content = f"""
    <div id="reportContainer"
         style="height:{height}px;width:100%;display:none;"></div>

    <script
      src="https://cdn.jsdelivr.net/npm/powerbi-client@2.23.1/dist/powerbi.min.js">
    </script>
    <script>
        var models = window['powerbi-client'].models;

        var embedConfig = {{
            type: 'report',
            tokenType: models.TokenType.Embed,
            accessToken: '{access_token}',
            embedUrl: '{embed_url}',
            permissions: models.Permissions.ReadWrite,
            viewMode: models.ViewMode.Edit
        }};

        var reportContainer = document.getElementById('reportContainer');
        var report = powerbi.embed(reportContainer, embedConfig);

        report.on('rendered', function() {{
            console.log("Report rendered – triggering save for PBIR upgrade...");
            report.save().then(function() {{
                console.log("Report saved – PBIR upgrade triggered.");
            }}).catch(function(error) {{
                console.error("Error saving the report:", error);
            }});
        }});

        report.on('error', function(event) {{
            console.error("Error embedding the report:", event.detail);
        }});
    </script>
    """
    if HTML is not None:
        display(HTML(html_content))
    else:
        print(html_content)


# ---------------------------------------------------------------------------
# Helper: Poll the reports API until the format flips to PBIR
# ---------------------------------------------------------------------------
def _check_upgrade_status(
    url: str, updated_report_ids: list, workspace_name: str
):
    """
    Polls ``GET /v1.0/myorg/groups/{ws}/reports`` until every report in
    *updated_report_ids* shows ``format == "PBIR"`` or the time limit is
    exceeded.
    """
    start_time = time.time()

    while time.time() - start_time < _TIME_LIMIT:
        response = _base_api(request=url, client="fabric_sp")
        verified = {}
        unverified = {}

        for rpt in response.json().get("value", []):
            rpt_id = rpt.get("id")
            rpt_name = rpt.get("name")
            rpt_format = rpt.get("format")

            if rpt_id in updated_report_ids:
                if rpt_format == "PBIR":
                    verified[rpt_id] = rpt_name
                else:
                    unverified[rpt_id] = rpt_name

        if not unverified:
            break

        time.sleep(_TIME_BETWEEN_REQUESTS)

    for rpt_id in updated_report_ids:
        if rpt_id in verified:
            print(
                f"{icons.green_dot} The '{verified[rpt_id]}' report in the "
                f"'{workspace_name}' workspace has been upgraded to PBIR format."
            )
        else:
            name = unverified.get(rpt_id, rpt_id)
            print(
                f"{icons.warning} The '{name}' report in the "
                f"'{workspace_name}' workspace could not be verified as PBIR "
                f"within {_TIME_LIMIT}s.  It may still be processing — "
                f"please check the workspace manually."
            )


# ---------------------------------------------------------------------------
# Main fixer function
# ---------------------------------------------------------------------------
@log
def fix_upgrade_to_pbir(
    report: str | UUID,
    page_name: Optional[str] = None,
    workspace: Optional[str | UUID] = None,
    scan_only: bool = False,
) -> None:
    """
    Upgrades a report from PBIRLegacy format to PBIR format.

    In scan mode the function only reports the current format of the report.
    In fix mode it embeds the report in edit mode (invisible to the user),
    triggers a save, and polls until the server confirms the upgrade.

    Parameters
    ----------
    report : str | uuid.UUID
        Name or ID of the report.
    page_name : str, default=None
        Unused — accepted for interface consistency with other report fixers.
    workspace : str | uuid.UUID, default=None
        The Fabric workspace name or ID.
        Defaults to None which resolves to the workspace of the attached lakehouse
        or if no lakehouse attached, resolves to the workspace of the notebook.
    scan_only : bool, default=False
        If True, only reports the current format without upgrading.

    Returns
    -------
    None
    """

    workspace_name, workspace_id = resolve_workspace_name_and_id(workspace)
    rpt_name, rpt_id = resolve_item_name_and_id(
        item=report, type="Report", workspace=workspace_id
    )

    # Get report metadata to check current format
    url = f"/v1.0/myorg/groups/{workspace_id}/reports"
    response = _base_api(request=url, client="fabric_sp")

    rpt_format = None
    embed_url = None
    dataset_id = None

    for rpt in response.json().get("value", []):
        if rpt.get("id") == str(rpt_id):
            rpt_format = rpt.get("format")
            embed_url = rpt.get("embedUrl")
            dataset_id = rpt.get("datasetId")
            break

    if rpt_format is None:
        print(
            f"{icons.red_dot} Could not find report '{rpt_name}' in the "
            f"'{workspace_name}' workspace."
        )
        return

    # Already PBIR
    if rpt_format == "PBIR":
        print(
            f"{icons.green_dot} Report '{rpt_name}' is already in PBIR format "
            f"— no upgrade needed."
        )
        return

    # Not PBIRLegacy — cannot upgrade
    if rpt_format != "PBIRLegacy":
        print(
            f"{icons.red_dot} Report '{rpt_name}' is in '{rpt_format}' format. "
            f"Only PBIRLegacy reports can be upgraded to PBIR."
        )
        return

    # PBIRLegacy → eligible for upgrade
    if scan_only:
        print(
            f"{icons.yellow_dot} Report '{rpt_name}' is in PBIRLegacy format "
            f"— eligible for upgrade to PBIR."
        )
        return

    # Fix mode — perform the upgrade
    print(
        f"{icons.in_progress} Upgrading '{rpt_name}' from PBIRLegacy to PBIR..."
    )

    try:
        access_token = _generate_embed_token(
            dataset_ids=[dataset_id], report_ids=[rpt_id]
        )
    except Exception as e:
        print(
            f"{icons.red_dot} Failed to generate embed token for '{rpt_name}': {e}"
        )
        return

    _embed_report_edit_mode(embed_url, access_token)

    # Poll for upgrade completion
    _check_upgrade_status(url, [str(rpt_id)], workspace_name)


# Sample usage:
# fix_upgrade_to_pbir(report="My Report")
# fix_upgrade_to_pbir(report="My Report", workspace="My Workspace", scan_only=True)
