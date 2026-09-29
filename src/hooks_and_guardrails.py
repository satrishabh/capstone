"""
Pre-hooks, post-hooks, and guardrails for the predictive maintenance workflow.
Provides input/output validation, state management, and error handling.
"""
import logging
import json
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from state_schema import MaintenanceState

logger = logging.getLogger(__name__)


class WorkflowGuardrail:
    """Base class for workflow guardrails."""

    def validate(self, state: MaintenanceState, node_name: str) -> tuple[bool, str]:
        """
        Validate state before/after node execution.
        Returns: (is_valid, error_message)
        """
        raise NotImplementedError


class InputGuardrail(WorkflowGuardrail):
    """Validates input state before node execution."""

    def validate_telemetry(self, telemetry: Dict[str, Any]) -> tuple[bool, str]:
        """Validate telemetry data."""
        required_fields = {
            "engine_rpm": float,
            "coolant_temperature": float,
            "oil_pressure": float,
            "battery_voltage": float,
            "vibration": float,
            "vehicle_speed": float,
            "timestamp": str,
        }

        for field, field_type in required_fields.items():
            if field not in telemetry:
                return False, f"Missing required telemetry field: {field}"

            try:
                if field_type == float:
                    val = float(telemetry[field])
                    if val < 0:
                        return False, f"Telemetry {field} cannot be negative: {val}"
                    if field == "engine_rpm" and val > 10000:
                        return False, f"Engine RPM unrealistic: {val}"
                    if field == "coolant_temperature" and (val < -40 or val > 150):
                        return False, f"Coolant temperature out of bounds: {val}°C"
                    if field == "battery_voltage" and (val < 6 or val > 16):
                        return False, f"Battery voltage out of bounds: {val}V"
            except (TypeError, ValueError) as e:
                return False, f"Invalid type for {field}: {str(e)}"

        return True, ""

    def validate_vehicle_id(self, vehicle_id: str) -> tuple[bool, str]:
        """Validate vehicle ID format."""
        if not vehicle_id or not isinstance(vehicle_id, str):
            return False, "Invalid vehicle_id"
        if len(vehicle_id) < 3:
            return False, "Vehicle ID too short"
        if len(vehicle_id) > 50:
            return False, "Vehicle ID too long"
        return True, ""

    def validate_user_request(self, request: str) -> tuple[bool, str]:
        """Validate user request."""
        if not request or not isinstance(request, str):
            return False, "Invalid user_request"
        if len(request) < 5:
            return False, "User request too short"
        if len(request) > 500:
            return False, "User request too long"
        return True, ""

    def validate(self, state: MaintenanceState, node_name: str) -> tuple[bool, str]:
        """Validate inputs for a specific node."""

        # All nodes need basic state
        if not state.get("vehicle_id"):
            return False, "Missing vehicle_id"

        is_valid, msg = self.validate_vehicle_id(state["vehicle_id"])
        if not is_valid:
            return False, msg

        # Telemetry node
        if node_name in ["telemetry", "ml", "diagnostic"]:
            telemetry = state.get("telemetry", {})
            is_valid, msg = self.validate_telemetry(telemetry)
            if not is_valid:
                return False, msg

        # History node
        if node_name in ["history", "diagnostic"]:
            history = state.get("history", {})
            if not isinstance(history, dict):
                return False, "Invalid history format"

        # Diagnostic and beyond
        if node_name in ["diagnostic", "risk", "service_plan"]:
            if not state.get("user_request"):
                return False, "Missing user_request"
            is_valid, msg = self.validate_user_request(state["user_request"])
            if not is_valid:
                return False, msg

        return True, ""


class OutputGuardrail(WorkflowGuardrail):
    """Validates output state after node execution."""

    def validate_telemetry_output(self, telemetry: Dict[str, Any]) -> tuple[bool, str]:
        """Validate telemetry agent output."""
        if not isinstance(telemetry, dict):
            return False, "Telemetry output must be dict"
        if "abnormalities" not in telemetry:
            return False, "Missing abnormalities in telemetry output"
        if not isinstance(telemetry["abnormalities"], list):
            return False, "Abnormalities must be list"
        return True, ""

    def validate_diagnosis_output(self, diagnosis: Dict[str, Any]) -> tuple[bool, str]:
        """Validate diagnostic agent output."""
        if not isinstance(diagnosis, dict):
            return False, "Diagnosis must be dict"
        if not diagnosis.get("assessment"):
            return False, "Missing assessment in diagnosis"
        return True, ""

    def validate_risk_output(self, risk: Dict[str, Any]) -> tuple[bool, str]:
        """Validate risk agent output."""
        if not isinstance(risk, dict):
            return False, "Risk decision must be dict"

        required = ["risk_score", "risk_level", "human_approval_required"]
        for field in required:
            if field not in risk:
                return False, f"Missing {field} in risk output"

        score = risk.get("risk_score")
        if not isinstance(score, (int, float)) or score < 0 or score > 100:
            return False, f"Risk score out of range: {score}"

        valid_levels = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        if risk.get("risk_level") not in valid_levels:
            return False, f"Invalid risk level: {risk.get('risk_level')}"

        return True, ""

    def validate(self, state: MaintenanceState, node_name: str) -> tuple[bool, str]:
        """Validate outputs for a specific node."""

        if node_name == "telemetry":
            telemetry = state.get("telemetry")
            if telemetry:
                return self.validate_telemetry_output(telemetry)

        if node_name == "diagnostic":
            diagnosis = state.get("diagnosis")
            if diagnosis:
                return self.validate_diagnosis_output(diagnosis)

        if node_name == "risk":
            risk = state.get("risk_decision")
            if risk:
                return self.validate_risk_output(risk)

        return True, ""


def pre_hook(state: MaintenanceState, node_name: str) -> Dict[str, Any]:
    """
    Execute before node runs.
    Returns updated state.
    """
    logger.info(f"[PRE-HOOK] {node_name}: Validating inputs")

    # Input validation
    guardrail = InputGuardrail()
    is_valid, msg = guardrail.validate(state, node_name)

    if not is_valid:
        logger.error(f"[PRE-HOOK] {node_name}: ❌ Validation failed: {msg}")
        raise ValueError(f"Pre-hook validation failed for {node_name}: {msg}")

    logger.info(f"[PRE-HOOK] {node_name}: ✓ All validations passed")

    # Add execution metadata
    if "execution_metadata" not in state:
        state["execution_metadata"] = {}

    state["execution_metadata"][node_name] = {
        "started_at": datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Kolkata")).isoformat(),
        "status": "running",
    }

    logger.debug(f"[PRE-HOOK] {node_name}: State prepared, ready for execution")
    return {}


def post_hook(state: MaintenanceState, node_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute after node runs.
    Returns additional state updates.
    """
    logger.info(f"[POST-HOOK] {node_name}: Validating outputs")

    # Output validation
    guardrail = OutputGuardrail()
    is_valid, msg = guardrail.validate({**state, **result}, node_name)

    if not is_valid:
        logger.warning(f"[POST-HOOK] {node_name}: ⚠️  Output validation warning: {msg}")
        # Log warning but don't fail - allow workflow to continue

    logger.info(f"[POST-HOOK] {node_name}: ✓ Output validated")

    # Update execution metadata
    if "execution_metadata" not in state:
        state["execution_metadata"] = {}

    state["execution_metadata"][node_name] = state["execution_metadata"].get(node_name, {})
    state["execution_metadata"][node_name].update({
        "completed_at": datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Kolkata")).isoformat(),
        "status": "completed",
    })

    # Add to audit log
    audit_log = state.get("audit_log", [])
    audit_log.append({
        "timestamp": datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Kolkata")).isoformat(),
        "node": node_name,
        "message": f"Execution completed with {len(result)} output updates",
        "validation_status": "passed" if is_valid else "warning",
    })
    state["audit_log"] = audit_log

    logger.debug(f"[POST-HOOK] {node_name}: Execution metadata recorded")
    return {}


class HookWrapper:
    """Wraps a node function with pre/post hooks."""

    def __init__(self, node_func, node_name: str):
        self.node_func = node_func
        self.node_name = node_name
        self.logger = logger

    def __call__(self, state: MaintenanceState) -> Dict[str, Any]:
        """Execute node with hooks."""
        self.logger.info(f"[HOOKS] {self.node_name}: Starting execution")

        try:
            # Pre-hook
            self.logger.info(f"[HOOKS] {self.node_name}: Running pre-hook")
            pre_hook(state, self.node_name)

            # Execute node
            self.logger.info(f"[HOOKS] {self.node_name}: Executing node")
            result = self.node_func(state)

            # Post-hook
            self.logger.info(f"[HOOKS] {self.node_name}: Running post-hook")
            post_hook(state, self.node_name, result)

            self.logger.info(f"[HOOKS] {self.node_name}: ✓ Execution successful")
            return result

        except Exception as e:
            self.logger.error(f"[HOOKS] {self.node_name}: ❌ Error: {str(e)}")

            # Record error in audit log
            if isinstance(state, dict):
                audit_log = state.get("audit_log", [])
                audit_log.append({
                    "timestamp": datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Kolkata")).isoformat(),
                    "node": self.node_name,
                    "message": f"ERROR: {str(e)}",
                    "error": True,
                })
                state["audit_log"] = audit_log

            raise


def wrap_node(node_func, node_name: str):
    """Wrap a node function with pre/post hooks."""
    return HookWrapper(node_func, node_name)
