# Fix / Set DefaultPowerBIDataSourceVersion on a Semantic Model
# Ensures the model has DefaultPowerBIDataSourceVersion = PowerBI_V3,
# which is required for XMLA write operations on Fabric/Premium capacities.

from uuid import UUID
from typing import Optional
from sempy._utils._log import log
import sempy_labs._icons as icons
from sempy_labs._helper_functions import (
    resolve_workspace_name_and_id,
    resolve_dataset_from_report,
)
from sempy_labs.tom import connect_semantic_model


@log
def fix_default_datasource_version(
    report: str | UUID,
    workspace: Optional[str | UUID] = None,
    scan_only: bool = False,
) -> None:
    """
    Checks the DefaultPowerBIDataSourceVersion property on the semantic model
    that backs the given report.  If the property is not set to 'PowerBI_V3',
    it will be updated (unless running in scan-only mode).

    This property must be 'PowerBI_V3' for XMLA write operations to succeed
    on Fabric / Premium capacities.  Models uploaded from .pbix files often
    lack this setting, causing other semantic model fixers to fail with:
    "The operation is only supported on model with property
    'DefaultPowerBIDataSourceVersion' set to 'PowerBI_V3'."

    Parameters
    ----------
    report : str | uuid.UUID
        Name or ID of the Power BI report whose semantic model will be checked.
    workspace : str | uuid.UUID, default=None
        The Fabric workspace name or ID.
        Defaults to None which resolves to the workspace of the attached lakehouse
        or if no lakehouse attached, resolves to the workspace of the notebook.
    scan_only : bool, default=False
        If True, only reports the current state without making any changes.

    Returns
    -------
    None
    """

    workspace_name, workspace_id = resolve_workspace_name_and_id(workspace)

    dataset_id, dataset_name, dataset_workspace_id, dataset_workspace_name = (
        resolve_dataset_from_report(report=report, workspace=workspace_id)
    )

    with connect_semantic_model(
        dataset=dataset_id,
        readonly=scan_only,
        workspace=dataset_workspace_id,
    ) as tom:

        current_value = str(tom.model.DefaultPowerBIDataSourceVersion)

        if current_value == "PowerBI_V3":
            print(
                f"{icons.green_dot} DefaultPowerBIDataSourceVersion is already "
                f"'PowerBI_V3' on '{dataset_name}' — no action needed."
            )
            return

        # Property is not PowerBI_V3
        if scan_only:
            print(
                f"{icons.yellow_dot} DefaultPowerBIDataSourceVersion is "
                f"'{current_value}' on '{dataset_name}'. "
                f"It would be set to 'PowerBI_V3'."
            )
            return

        # Fix mode
        print(
            f"{icons.in_progress} Setting DefaultPowerBIDataSourceVersion to "
            f"'PowerBI_V3' on '{dataset_name}'..."
        )

        # The TOM property expects the enum value from the AMO library
        # Microsoft.AnalysisServices.Compatibility.DefaultPowerBIDataSourceVersion
        import Microsoft.AnalysisServices.Tabular as TOM

        tom.model.DefaultPowerBIDataSourceVersion = (
            TOM.DefaultPowerBIDataSourceVersion.PowerBI_V3
        )

        print(
            f"{icons.green_dot} DefaultPowerBIDataSourceVersion has been set to "
            f"'PowerBI_V3' on '{dataset_name}'."
        )


# Sample usage:
# fix_default_datasource_version(report="My Report")
# fix_default_datasource_version(report="My Report", workspace="My Workspace")
# fix_default_datasource_version(report="My Report", scan_only=True)
