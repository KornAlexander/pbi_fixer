# Setup Incremental Refresh — standalone fixer.
# Auto-detects the first DateTime column and configures incremental refresh.

from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta


def setup_incremental_refresh(
    dataset: str,
    table_name: str,
    workspace: Optional[str | UUID] = None,
    column_name: Optional[str] = None,
    rolling_window_years: int = 3,
    incremental_days: int = 30,
    only_refresh_complete_days: bool = False,
    scan_only: bool = False,
):
    """
    Sets up an incremental refresh policy on a table.

    Auto-detects the first DateTime column if column_name is not specified.

    Parameters
    ----------
    dataset : str
        Name of the semantic model.
    table_name : str
        Name of the table to configure.
    workspace : str | uuid.UUID, default=None
        The Fabric workspace name or ID.
    column_name : str, default=None
        The DateTime column to use. If None, auto-detects the first DateTime column.
    rolling_window_years : int, default=3
        Number of years to keep in the rolling window.
    incremental_days : int, default=30
        Number of days to refresh incrementally.
    only_refresh_complete_days : bool, default=False
        If True, only refresh complete days (offset -1).
    scan_only : bool, default=False
        If True, only reports what would be configured without making changes.
    """
    from sempy_labs.tom import connect_semantic_model

    with connect_semantic_model(dataset=dataset, readonly=scan_only, workspace=workspace) as tom:
        import Microsoft.AnalysisServices.Tabular as TOM

        t = tom.model.Tables[table_name]

        # Auto-detect date column
        date_col = column_name
        if date_col is None:
            for col in t.Columns:
                if col.DataType == TOM.DataType.DateTime:
                    date_col = col.Name
                    break
            if date_col is None:
                print(f"  No DateTime column found in '{table_name}'. Cannot set up incremental refresh.")
                return

        # Verify column type
        c = t.Columns[date_col]
        if c.DataType != TOM.DataType.DateTime:
            print(f"  Column '{date_col}' is not DateTime ({c.DataType}). Skipping.")
            return

        # Check if already has refresh policy
        try:
            if t.RefreshPolicy is not None:
                print(f"  Table '{table_name}' already has an incremental refresh policy. Skipping.")
                return
        except Exception:
            pass

        # Dates
        end_date = datetime.now().strftime("%m/%d/%Y")
        start_date = (datetime.now() - timedelta(days=rolling_window_years * 365)).strftime("%m/%d/%Y")

        if scan_only:
            print(f"  Would set up incremental refresh on '{table_name}':")
            print(f"    Column: [{date_col}]")
            print(f"    Rolling window: {rolling_window_years} year(s)")
            print(f"    Incremental refresh: {incremental_days} day(s)")
            print(f"    Only complete days: {only_refresh_complete_days}")
            print(f"    Range: {start_date} - {end_date}")
            return

        tom.add_incremental_refresh_policy(
            table_name=table_name,
            column_name=date_col,
            start_date=start_date,
            end_date=end_date,
            incremental_granularity="Day",
            incremental_periods=incremental_days,
            rolling_window_granularity="Year",
            rolling_window_periods=rolling_window_years,
            only_refresh_complete_days=only_refresh_complete_days,
        )
        print(f"  \u2713 Incremental refresh configured on '{table_name}'[{date_col}]")
        print(f"    Rolling window: {rolling_window_years} year(s), Refresh: {incremental_days} day(s)")
