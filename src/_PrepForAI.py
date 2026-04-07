# Prep for AI — Read/Write CustomInstructions on a Semantic Model
# Uses the same private applyChange path the Power BI portal uses.
# Based on work by Lukasz Obst (update_prep_for_ai_via_apply_change.py).

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional
from uuid import UUID

import sempy_labs._icons as icons
from sempy_labs._helper_functions import (
    resolve_workspace_name_and_id,
    resolve_dataset_from_report,
)


FEATURE_TAG = "CopilotTooling"
READBACK_TIMEOUT_SECONDS = 60
READBACK_INTERVAL_SECONDS = 2


def _get_pbi_token() -> str:
    """Get a Power BI bearer token from the Fabric notebook environment."""
    import notebookutils

    return notebookutils.credentials.getToken("pbi")


def _pbi_headers() -> dict:
    """Standard headers for the private modeling endpoints."""
    return {
        "Accept": "application/json, text/plain, */*",
        "activityid": str(uuid.uuid4()),
        "requestid": str(uuid.uuid4()),
        "x-powerbi-hostenv": "Power BI Web App",
    }


def _discover_cluster_uri(workspace_id: str, item_id: str, token: str) -> str:
    """Discover the semantic model home cluster from the Power BI dataset API."""
    import requests

    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{item_id}"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    response.raise_for_status()

    home_cluster = response.headers.get("home-cluster-uri")
    if home_cluster:
        return home_cluster.rstrip("/")

    body = response.json() if response.text.strip() else {}
    odata_context = str(body.get("@odata.context", "")).strip()
    if odata_context.startswith("https://"):
        parts = odata_context.split("/", 3)
        if len(parts) >= 3:
            return "/".join(parts[:3])

    raise RuntimeError(
        "Could not discover the home cluster for this semantic model."
    )


def _get_baseline_version(
    cluster_uri: str, item_id: str, culture: str, token: str
) -> str:
    """GET /modeling/getModel/{itemId} to retrieve the current baselineVersion."""
    import requests

    url = f"{cluster_uri}/modeling/getModel/{item_id}?languageLocale={culture}"
    headers = {"Authorization": f"Bearer {token}", **_pbi_headers()}
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    model = resp.json()
    for key in ("baselineVersion", "version", "Version"):
        if key in model:
            return str(model[key])
    raise RuntimeError("Could not find baselineVersion in getModel response.")


def _get_linguistic_schema(
    cluster_uri: str,
    workspace_id: str,
    item_id: str,
    token: str,
) -> tuple[dict[str, Any], bool]:
    """Read the linguistic schema (LSDL document) from the Copilot Tooling endpoint."""
    import requests

    url = (
        f"{cluster_uri}/explore/nl2nl/copilotTooling/workspaces/{workspace_id}"
        f"/dataset/{item_id}/linguisticSchema"
    )
    headers = {"Authorization": f"Bearer {token}", **_pbi_headers()}
    resp = requests.get(url, headers=headers, timeout=120)
    resp.raise_for_status()

    payload = resp.json()
    lsdl_document = payload.get("lsdlDocument")
    if not isinstance(lsdl_document, dict):
        raise RuntimeError(
            "The linguisticSchema endpoint did not return an lsdlDocument payload."
        )
    return lsdl_document, bool(payload.get("isLsdlDocumentStale", False))


def _submit_apply_change(
    cluster_uri: str,
    item_id: str,
    culture: str,
    body: dict[str, Any],
    token: str,
):
    """POST /modeling/applyChange/{itemId} to commit linguistic schema changes."""
    import requests

    url = (
        f"{cluster_uri}/modeling/applyChange/{item_id}"
        f"?languageLocale={culture}&updateSchemaPackageClientConfigurableOptions=1"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json;charset=UTF-8",
        **_pbi_headers(),
    }
    return requests.post(url, headers=headers, json=body, timeout=120)


# ── Public API ──────────────────────────────────────────────────────


def read_prep_for_ai(
    dataset: str | UUID,
    workspace: Optional[str | UUID] = None,
) -> dict[str, Any]:
    """
    Read the Prep for AI configuration (CustomInstructions + VerifiedAnswers)
    from a semantic model.

    Parameters
    ----------
    dataset : str | uuid.UUID
        Name or ID of the semantic model.
    workspace : str | uuid.UUID, optional
        Workspace name or ID.

    Returns
    -------
    dict
        Keys: custom_instructions (str), verified_answers (list), is_stale (bool)
    """
    workspace_name, workspace_id = resolve_workspace_name_and_id(workspace)

    # Resolve dataset name to ID
    from sempy_labs._helper_functions import resolve_item_name_and_id

    _, item_id = resolve_item_name_and_id(
        item=dataset, type="SemanticModel", workspace=workspace_id
    )
    item_id = str(item_id)

    token = _get_pbi_token()
    cluster_uri = _discover_cluster_uri(workspace_id, item_id, token)
    lsdl, is_stale = _get_linguistic_schema(cluster_uri, workspace_id, item_id, token)

    return {
        "custom_instructions": str(lsdl.get("CustomInstructions", "")).strip(),
        "verified_answers": lsdl.get("VerifiedAnswers", []),
        "is_stale": is_stale,
    }


def write_prep_for_ai(
    dataset: str | UUID,
    workspace: Optional[str | UUID] = None,
    instructions: str = "",
    append: bool = False,
    culture: str = "en-US",
) -> None:
    """
    Write CustomInstructions to a semantic model's Prep for AI configuration.

    Parameters
    ----------
    dataset : str | uuid.UUID
        Name or ID of the semantic model.
    workspace : str | uuid.UUID, optional
        Workspace name or ID.
    instructions : str
        The new instructions text.
    append : bool, default=False
        If True, append to existing instructions; otherwise replace.
    culture : str, default="en-US"
        Culture/locale for the modeling endpoint.
    """
    workspace_name, workspace_id = resolve_workspace_name_and_id(workspace)

    from sempy_labs._helper_functions import resolve_item_name_and_id

    _, item_id = resolve_item_name_and_id(
        item=dataset, type="SemanticModel", workspace=workspace_id
    )
    item_id = str(item_id)

    token = _get_pbi_token()
    cluster_uri = _discover_cluster_uri(workspace_id, item_id, token)

    print(f"{icons.in_progress} Reading current linguistic schema…")
    lsdl, is_stale = _get_linguistic_schema(cluster_uri, workspace_id, item_id, token)

    baseline_version = _get_baseline_version(cluster_uri, item_id, culture, token)

    current = str(lsdl.get("CustomInstructions", "")).strip()
    if append and current:
        updated = current + "\n\n" + instructions.strip()
    else:
        updated = instructions.strip()

    lsdl["CustomInstructions"] = updated

    body = {
        "baselineVersion": baseline_version,
        "modelChange": {
            "changes": [
                {
                    "updateLinguisticMetadata": {
                        "linguisticSchemaJson": json.dumps(
                            lsdl, ensure_ascii=False, separators=(",", ":")
                        )
                    }
                },
                {
                    "SetUsedFeatureModelTraitSchemaChange": {
                        "featureTagsToAdd": [FEATURE_TAG]
                    }
                },
            ]
        },
        "validate": False,
        "allowAsyncCommit": True,
        "rollBackChanges": False,
        "clientContext": {"feature": "copilotTooling"},
    }

    print(f"{icons.in_progress} Submitting Prep for AI update…")
    resp = _submit_apply_change(cluster_uri, item_id, culture, body, token)
    resp.raise_for_status()

    # Poll for readback
    deadline = time.monotonic() + READBACK_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(READBACK_INTERVAL_SECONDS)
        lsdl_check, stale = _get_linguistic_schema(
            cluster_uri, workspace_id, item_id, token
        )
        readback = str(lsdl_check.get("CustomInstructions", "")).strip()
        if readback == updated and not stale:
            print(f"{icons.green_dot} Prep for AI instructions updated successfully.")
            return

    print(
        f"{icons.yellow_dot} Update submitted but readback not confirmed within "
        f"{READBACK_TIMEOUT_SECONDS}s. Check the model manually."
    )


def scan_prep_for_ai(
    dataset: str | UUID,
    workspace: Optional[str | UUID] = None,
    scan_only: bool = True,
) -> None:
    """
    Check if Prep for AI instructions are configured on a semantic model.
    Prints findings in the standard fixer format.

    Parameters
    ----------
    dataset : str | uuid.UUID
        Name or ID of the semantic model.
    workspace : str | uuid.UUID, optional
        Workspace name or ID.
    scan_only : bool, default=True
        Always True for this fixer (instructions require manual input).
    """
    try:
        result = read_prep_for_ai(dataset=dataset, workspace=workspace)
    except Exception as e:
        print(f"{icons.yellow_dot} Could not read Prep for AI: {e}")
        return

    instructions = result["custom_instructions"]
    verified = result["verified_answers"]

    if not instructions:
        print(
            f"{icons.yellow_dot} Prep for AI: CustomInstructions are empty. "
            f"Configure them in the Model Explorer → Prep for AI section, "
            f"or in Power BI Desktop / Service."
        )
    elif len(instructions) < 50:
        print(
            f"{icons.yellow_dot} Prep for AI: CustomInstructions are very short "
            f"({len(instructions)} chars). Consider adding more context."
        )
    else:
        print(
            f"{icons.green_dot} Prep for AI: CustomInstructions configured "
            f"({len(instructions)} chars)."
        )

    va_count = len(verified) if isinstance(verified, list) else 0
    if va_count == 0:
        print(f"{icons.info} Prep for AI: No verified answers configured.")
    else:
        print(f"{icons.green_dot} Prep for AI: {va_count} verified answer(s) configured.")
