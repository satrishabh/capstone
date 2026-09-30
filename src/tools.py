"""Synthetic maintenance-system tools exposed to the diagnostic LLM.

These adapters intentionally return deterministic demo data. Replace their
implementations with authenticated service clients before using them in
production, especially for tools that create external side effects.
"""

from datetime import datetime, timezone
from typing import Any

from langchain_core.tools import tool


def _receipt(action: str, **details: Any) -> dict[str, Any]:
    return {
        "status": "simulated",
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **details,
    }


@tool
def get_additional_telemetry(
    vehicle_id: str, parameter: str, time_range: str
) -> dict[str, Any]:
    """Pull finer-grained sensor history for a vehicle and parameter."""
    return {
        "vehicle_id": vehicle_id,
        "parameter": parameter,
        "time_range": time_range,
        "readings": [],
        "note": "No secondary telemetry source is configured in this demo.",
    }


@tool
def lookup_dtc_code(code: str) -> dict[str, Any]:
    """Decode an OBD-II or manufacturer trouble code."""
    normalized_code = code.strip().upper()
    known_codes = {
        "P0524": "Engine oil pressure too low",
        "P0217": "Engine coolant over-temperature condition",
        "P0562": "System voltage low",
    }
    return {
        "code": normalized_code,
        "description": known_codes.get(
            normalized_code, "Unknown code; consult the manufacturer service manual."
        ),
        "source": "synthetic demo lookup",
    }


@tool
def get_similar_fleet_cases(symptom_pattern: str) -> dict[str, Any]:
    """Find similar synthetic fleet cases and their reported root causes."""
    return {
        "symptom_pattern": symptom_pattern,
        "matches": [],
        "note": "Fleet case history is not connected in this demo.",
    }


@tool
def check_recalls_and_tsbs(model: str, year: int) -> dict[str, Any]:
    """Cross-reference synthetic recalls and technical service bulletins."""
    return {
        "model": model,
        "year": year,
        "recalls": [],
        "tsbs": [],
        "note": "OEM recall and TSB data is not connected in this demo.",
    }


@tool
def check_parts_inventory(part_name: str, location: str) -> dict[str, Any]:
    """Check synthetic parts availability at a service-center location."""
    return {
        "part_name": part_name,
        "location": location,
        "in_stock": False,
        "quantity": 0,
        "note": "Live service-center inventory is not connected in this demo.",
    }


@tool
def check_warranty_status(vehicle_id: str) -> dict[str, Any]:
    """Check synthetic warranty coverage for a vehicle."""
    return {
        "vehicle_id": vehicle_id,
        "covered": None,
        "note": "Warranty data is not connected in this demo.",
    }


@tool
def estimate_repair_cost(service_plan: str) -> dict[str, Any]:
    """Estimate repair cost from a service plan using a synthetic placeholder."""
    return {
        "service_plan": service_plan,
        "currency": "USD",
        "parts_estimate": None,
        "labor_estimate": None,
        "total_estimate": None,
        "note": "Pricing data is not connected in this demo.",
    }


@tool
def schedule_service_appointment(vehicle_id: str, date: str) -> dict[str, Any]:
    """Create a simulated service appointment request after approval."""
    return _receipt(
        "schedule_service_appointment", vehicle_id=vehicle_id, date=date
    )


@tool
def order_replacement_parts(part_list: str) -> dict[str, Any]:
    """Create a simulated replacement-parts order after approval."""
    return _receipt("order_replacement_parts", part_list=part_list)


@tool
def send_approval_request(channel: str = "email") -> dict[str, Any]:
    """Create a simulated approval notification for a technician."""
    if channel not in {"slack", "sms", "email"}:
        return {"status": "rejected", "reason": "Unsupported approval channel."}
    return _receipt("send_approval_request", channel=channel)


@tool
def create_work_order(system: str = "ServiceNow") -> dict[str, Any]:
    """Create a simulated work order in a supported maintenance system."""
    if system not in {"ServiceNow", "Jira"}:
        return {"status": "rejected", "reason": "Unsupported work-order system."}
    return _receipt("create_work_order", system=system)


@tool
def notify_driver(vehicle_id: str, message: str) -> dict[str, Any]:
    """Create a simulated driver notification."""
    return _receipt("notify_driver", vehicle_id=vehicle_id, message=message)


@tool
def send_report(channel: str, recipient: str) -> dict[str, Any]:
    """Create a simulated report delivery receipt."""
    return _receipt("send_report", channel=channel, recipient=recipient)


@tool
def upload_to_dashboard(report: str) -> dict[str, Any]:
    """Create a simulated dashboard upload receipt."""
    return _receipt("upload_to_dashboard", report=report[:200])


MAINTENANCE_TOOLS = [
    get_additional_telemetry,
    lookup_dtc_code,
    get_similar_fleet_cases,
    check_recalls_and_tsbs,
    check_parts_inventory,
    check_warranty_status,
    estimate_repair_cost,
    schedule_service_appointment,
    order_replacement_parts,
    send_approval_request,
    create_work_order,
    notify_driver,
    send_report,
    upload_to_dashboard,
]

MAINTENANCE_TOOL_MAP = {item.name: item for item in MAINTENANCE_TOOLS}