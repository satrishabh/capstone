import json
import os
from datetime import datetime, timezone

import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

SNOWFLAKE_DATABASE = "CAPSTONE_DB"
SNOWFLAKE_SCHEMA = "PREDICTIVE_MAINTENANCE"


def _get_secret(key, default=""):
    """Read from Streamlit secrets (cloud) first, then env vars (local)."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.getenv(key, default)


def get_connection():
    account = _get_secret("SNOWFLAKE_ACCOUNT", "jk73553.ap-southeast-7.aws")
    user = _get_secret("SNOWFLAKE_USER", "RISHABDEVH")
    password = _get_secret("SNOWFLAKE_PASSWORD", "")
    warehouse = _get_secret("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")

    params = dict(
        account=account,
        user=user,
        password=password,
        warehouse=warehouse,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
    )
    if not password:
        params["authenticator"] = "externalbrowser"
    return snowflake.connector.connect(**params)


def test_connection():
    """Test Snowflake connection and return status details."""
    account = _get_secret("SNOWFLAKE_ACCOUNT", "jk73553.ap-southeast-7.aws")
    user = _get_secret("SNOWFLAKE_USER", "RISHABDEVH")
    password = _get_secret("SNOWFLAKE_PASSWORD", "")
    warehouse = _get_secret("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")

    info = {
        "account": account,
        "user": user,
        "password_set": bool(password),
        "password_len": len(password) if password else 0,
        "warehouse": warehouse,
    }
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_ACCOUNT(), CURRENT_USER(), CURRENT_ROLE()")
        row = cur.fetchone()
        conn.close()
        info["status"] = "OK"
        info["connected_account"] = row[0]
        info["connected_user"] = row[1]
        info["connected_role"] = row[2]
    except Exception as e:
        info["status"] = "FAILED"
        info["error"] = str(e)
    return info


def load_test_cases_from_snowflake():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, vehicle_id, description, expected_risk, "
            "expected_human_approval, expected_failure_prob_min, "
            "expected_failure_prob_max, telemetry_data, history_data "
            "FROM TEST_CASES ORDER BY id"
        )
        rows = cur.fetchall()
        test_cases = []
        for row in rows:
            telemetry_raw = row[7]
            history_raw = row[8]
            if isinstance(telemetry_raw, str):
                telemetry_raw = json.loads(telemetry_raw)
            if isinstance(history_raw, str):
                history_raw = json.loads(history_raw)

            test_cases.append({
                "id": row[0],
                "vehicle_id": row[1],
                "description": row[2],
                "expected_risk": row[3],
                "expected_human_approval": row[4],
                "expected_failure_probability_range": [row[5], row[6]],
                "telemetry": telemetry_raw,
                "history": history_raw,
            })
        return test_cases
    finally:
        conn.close()


def save_report_to_snowflake(report_id, state):
    conn = get_connection()
    try:
        cur = conn.cursor()
        risk = state.get("risk_decision", {})
        diagnosis = state.get("diagnosis", {})
        service_plan = state.get("service_plan", {})

        diagnosis_text = diagnosis.get("assessment", "") if isinstance(diagnosis, dict) else str(diagnosis)
        plan_text = service_plan.get("plan", "") if isinstance(service_plan, dict) else str(service_plan)
        if isinstance(plan_text, list):
            plan_text = "\n".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in plan_text
            )

        cur.execute(
            "INSERT INTO MAINTENANCE_REPORTS "
            "(report_id, vehicle_id, risk_score, risk_level, ml_failure_probability, "
            "ml_prediction_label, diagnosis, service_plan, final_report, "
            "human_decision, human_feedback, telemetry_data) "
            "SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s)",
            (
                report_id,
                state.get("vehicle_id", ""),
                risk.get("risk_score"),
                risk.get("risk_level", ""),
                state.get("ml_failure_probability"),
                state.get("ml_prediction_label", ""),
                diagnosis_text,
                plan_text,
                state.get("final_report", ""),
                state.get("human_decision", ""),
                state.get("human_feedback", ""),
                json.dumps(state.get("telemetry", {})),
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving report to Snowflake: {e}")
        return False
    finally:
        conn.close()


def save_audit_log_to_snowflake(report_id, vehicle_id, audit_log):
    conn = get_connection()
    try:
        cur = conn.cursor()
        for entry in audit_log:
            cur.execute(
                "INSERT INTO AUDIT_LOG (report_id, vehicle_id, node, message, event_timestamp) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    report_id,
                    vehicle_id,
                    entry.get("node", ""),
                    entry.get("message", ""),
                    entry.get("timestamp", ""),
                ),
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving audit log to Snowflake: {e}")
        return False
    finally:
        conn.close()


def get_reports_from_snowflake(limit=50):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT report_id, vehicle_id, risk_score, risk_level, "
            "ml_failure_probability, ml_prediction_label, diagnosis, "
            "final_report, human_decision, created_at "
            "FROM MAINTENANCE_REPORTS ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def get_telemetry_from_snowflake(vehicle_id=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        if vehicle_id:
            cur.execute(
                "SELECT * FROM VEHICLE_TELEMETRY WHERE vehicle_id = %s ORDER BY timestamp",
                (vehicle_id,),
            )
        else:
            cur.execute("SELECT * FROM VEHICLE_TELEMETRY ORDER BY vehicle_id, timestamp")
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()
