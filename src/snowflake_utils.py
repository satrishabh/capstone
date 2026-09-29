import json
import os
from datetime import datetime, timezone

import snowflake.connector
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization

load_dotenv()

SNOWFLAKE_DATABASE = "CAPSTONE_DB"
SNOWFLAKE_SCHEMA = "PREDICTIVE_MAINTENANCE"


def _get_secret(key, default=""):
    """Read from Streamlit secrets first, then .env env vars, then default.

    Priority order:
    1. Streamlit secrets.toml (local & cloud)
    2. Environment variables (.env)
    3. Default value
    """
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            try:
                return st.secrets[key]
            except (KeyError, AttributeError):
                pass
    except ImportError:
        pass
    return os.getenv(key, default)


def _load_private_key():
    """Load RSA private key from secret or env var."""
    pem_text = _get_secret("SNOWFLAKE_PRIVATE_KEY", "")
    if not pem_text:
        return None
    pem_bytes = pem_text.encode("utf-8") if isinstance(pem_text, str) else pem_text
    return serialization.load_pem_private_key(pem_bytes, password=None)


def get_connection():
    account = _get_secret("SNOWFLAKE_ACCOUNT", "jk73553.ap-southeast-7.aws")
    user = _get_secret("SNOWFLAKE_USER", "CAPSTONE_SVC_USER")
    warehouse = _get_secret("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")

    params = dict(
        account=account,
        user=user,
        warehouse=warehouse,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA,
    )

    # Try key-pair auth first, then password, then externalbrowser
    private_key = _load_private_key()
    if private_key:
        params["private_key"] = private_key
    else:
        password = _get_secret("SNOWFLAKE_PASSWORD", "")
        if password:
            params["password"] = password
        else:
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


def save_report_to_stage(report_id, vehicle_id, report_text):
    """Save a markdown report file to Snowflake internal stage."""
    import tempfile
    conn = get_connection()
    try:
        filename = f"{vehicle_id}_{report_id}_report.md"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(report_text)
            tmp_path = f.name.replace("\\", "/")

        cur = conn.cursor()
        stage_path = f"@REPORT_FILES/reports/{vehicle_id}/"
        cur.execute(f"PUT 'file://{tmp_path}' '{stage_path}' AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
        os.unlink(tmp_path.replace("/", os.sep))

        print(f"Report uploaded to stage: {stage_path}{filename}")
        return f"{stage_path}{filename}"
    except Exception as e:
        print(f"Error saving report to stage: {e}")
        return None
    finally:
        conn.close()


def list_stage_reports():
    """List all report files in the internal stage."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("LIST @REPORT_FILES/reports/")
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


def download_stage_report(stage_path):
    """Download a report file from the internal stage and return its content."""
    import tempfile
    conn = get_connection()
    try:
        cur = conn.cursor()
        tmp_dir = tempfile.mkdtemp()
        cur.execute(f"GET '{stage_path}' 'file://{tmp_dir}/'")
        # Find the downloaded file
        for fname in os.listdir(tmp_dir):
            fpath = os.path.join(tmp_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            os.unlink(fpath)
            os.rmdir(tmp_dir)
            return content
        return None
    except Exception as e:
        print(f"Error downloading from stage: {e}")
        return None
    finally:
        conn.close()
