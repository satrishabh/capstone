import json
import os
import sys
import uuid
from pathlib import Path

# Ensure src/ is on the Python path for Streamlit Cloud
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from workflow import build_workflow
from config import LANGSMITH_ENABLED, LANGSMITH_PROJECT, LANGSMITH_ENDPOINT
from snowflake_utils import (
    load_test_cases_from_snowflake,
    get_reports_from_snowflake,
    get_telemetry_from_snowflake,
    test_connection,
    list_stage_reports,
    download_stage_report,
)

load_dotenv()

SRC_DIR = Path(__file__).resolve().parent
DATA_DIR = SRC_DIR / ".." / "data"
MODEL_PATH = SRC_DIR / ".." / "models" / "failure_model.joblib"
VECTORSTORE_PATH = SRC_DIR / ".." / "vectorstore" / "faiss_index"
TEST_CASES_PATH = DATA_DIR / "test_cases.json"

RISK_COLORS = {
    "CRITICAL": "#dc3545",
    "HIGH": "#fd7e14",
    "MEDIUM": "#ffc107",
    "LOW": "#28a745",
}


@st.cache_resource
def get_workflow():
    return build_workflow(for_web=True)


@st.cache_data
def load_test_cases():
    try:
        cases = load_test_cases_from_snowflake()
        if cases:
            return cases
    except Exception:
        pass
    if not TEST_CASES_PATH.exists():
        return []
    with open(TEST_CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


def check_prerequisites():
    issues = []
    if not MODEL_PATH.exists():
        issues.append(
            f"ML model missing at `{MODEL_PATH}`. Run `python train_failure_model.py`."
        )
    if not VECTORSTORE_PATH.exists():
        issues.append(
            f"FAISS index missing at `{VECTORSTORE_PATH}`. Run `python build_rag.py`."
        )
    return issues


def get_interrupt_payload(app, config):
    snapshot = app.get_state(config)
    if not snapshot.next:
        return None

    for task in snapshot.tasks or []:
        for intr in task.interrupts or []:
            return intr.value

    return snapshot.values


def run_until_complete(app, initial_state, config):
    result = app.invoke(initial_state, config)
    snapshot = app.get_state(config)

    while snapshot.next:
        interrupt_payload = get_interrupt_payload(app, config)
        if interrupt_payload is not None:
            return None, interrupt_payload, snapshot.values

        result = app.invoke(None, config)
        snapshot = app.get_state(config)

    return result, None, None


def resume_workflow(app, decision, feedback, config):
    resume_payload = {"decision": decision, "feedback": feedback}
    result = app.invoke(Command(resume=resume_payload), config)
    snapshot = app.get_state(config)

    while snapshot.next:
        interrupt_payload = get_interrupt_payload(app, config)
        if interrupt_payload is not None:
            return None, interrupt_payload, snapshot.values

        result = app.invoke(None, config)
        snapshot = app.get_state(config)

    return result, None, None


def init_session_state():
    defaults = {
        "workflow_result": None,
        "pending_interrupt": None,
        "partial_state": None,
        "run_config": None,
        "analysis_running": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def apply_test_case(test_case):
    latest_telemetry = test_case["telemetry"][-1]
    st.session_state["vehicle_id"] = test_case["vehicle_id"]
    st.session_state["user_request"] = (
        f"Generate predictive maintenance report — {test_case['description']}"
    )
    st.session_state["timestamp"] = latest_telemetry.get(
        "timestamp", "2026-09-09T09:00:00"
    )
    st.session_state["engine_rpm"] = float(latest_telemetry["engine_rpm"])
    st.session_state["coolant_temperature"] = float(
        latest_telemetry["coolant_temperature"]
    )
    st.session_state["oil_pressure"] = float(latest_telemetry["oil_pressure"])
    st.session_state["battery_voltage"] = float(latest_telemetry["battery_voltage"])
    st.session_state["vibration"] = float(latest_telemetry["vibration"])
    st.session_state["vehicle_speed"] = float(latest_telemetry["vehicle_speed"])
    st.session_state["maintenance"] = "\n".join(
        test_case["history"].get("maintenance", [])
    )
    st.session_state["previous_faults"] = "\n".join(
        test_case["history"].get("previous_faults", [])
    )


def build_initial_state():
    maintenance = [
        line.strip()
        for line in st.session_state.get("maintenance", "").splitlines()
        if line.strip()
    ]
    previous_faults = [
        line.strip()
        for line in st.session_state.get("previous_faults", "").splitlines()
        if line.strip()
    ]

    return {
        "vehicle_id": st.session_state.get("vehicle_id", "VH-1001"),
        "user_request": st.session_state.get(
            "user_request", "Generate predictive maintenance report"
        ),
        "telemetry": {
            "timestamp": st.session_state.get("timestamp", "2026-09-09T09:00:00"),
            "engine_rpm": st.session_state.get("engine_rpm", 1800.0),
            "coolant_temperature": st.session_state.get("coolant_temperature", 94.0),
            "oil_pressure": st.session_state.get("oil_pressure", 2.8),
            "battery_voltage": st.session_state.get("battery_voltage", 13.8),
            "vibration": st.session_state.get("vibration", 2.8),
            "vehicle_speed": st.session_state.get("vehicle_speed", 60.0),
        },
        "history": {
            "maintenance": maintenance,
            "previous_faults": previous_faults,
        },
        "audit_log": [],
    }


def render_risk_badge(risk_level):
    color = RISK_COLORS.get(risk_level, "#6c757d")
    st.markdown(
        f"<span style='color:{color}; font-weight:bold; font-size:1.1em;'>"
        f"{risk_level}</span>",
        unsafe_allow_html=True,
    )


def render_overview(result):
    risk = result.get("risk_decision", {})
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Risk Score", f"{risk.get('risk_score', '—')}/100")
    with col2:
        st.write("Risk Level")
        render_risk_badge(risk.get("risk_level", "UNKNOWN"))
    with col3:
        prob = result.get("ml_failure_probability")
        if prob is not None:
            st.metric("ML Failure Probability", f"{prob:.1%}")
        else:
            st.metric("ML Failure Probability", "—")
    with col4:
        st.metric("ML Label", result.get("ml_prediction_label", "—"))

    if risk.get("reason"):
        st.info(risk["reason"])


def render_telemetry(result):
    telemetry = result.get("telemetry", {})
    raw = telemetry.get("raw", {})
    abnormalities = telemetry.get("abnormalities", [])

    st.subheader("Raw Readings")
    if raw:
        st.json(raw)
    else:
        st.write("No telemetry data.")

    st.subheader("Abnormalities")
    if not abnormalities:
        st.success("No abnormal parameters detected.")
        return

    for item in abnormalities:
        severity = item.get("severity", "UNKNOWN")
        color = RISK_COLORS.get(severity, "#6c757d")
        st.markdown(
            f"**{item.get('parameter', 'unknown')}** — "
            f"<span style='color:{color}; font-weight:bold;'>{severity}</span>: "
            f"{item.get('value')} — {item.get('reason', '')}",
            unsafe_allow_html=True,
        )


def render_diagnosis(result):
    diagnosis = result.get("diagnosis", {})
    assessment = diagnosis.get("assessment")
    if assessment:
        st.markdown(assessment)
    else:
        st.write("No diagnosis generated.")

    if diagnosis.get("human_feedback"):
        st.warning(f"Human feedback: {diagnosis['human_feedback']}")


def render_rag_evidence(result):
    evidence = result.get("rag_evidence", [])
    if not evidence:
        st.write("No RAG evidence retrieved.")
        return

    for idx, item in enumerate(evidence, start=1):
        with st.expander(f"Document {idx}: {item.get('source', 'unknown')}"):
            st.markdown(item.get("content", ""))


def render_service_plan(result):
    service_plan = result.get("service_plan", {})
    plan = service_plan.get("plan")
    if plan:
        if isinstance(plan, list):
            text = "\n".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in plan
            )
            st.markdown(text or str(plan))
        else:
            st.markdown(str(plan))
    else:
        human_decision = result.get("human_decision")
        if human_decision == "REJECT":
            st.info("Service plan skipped — human rejected the maintenance action.")
        else:
            st.write("No service plan generated.")


def render_final_report(result):
    report = result.get("final_report")
    if report:
        st.markdown(report)
    else:
        st.write("No final report generated.")


def render_audit_log(result):
    audit_log = result.get("audit_log", [])
    if not audit_log:
        st.write("No audit entries.")
        return

    for entry in audit_log:
        st.markdown(
            f"**{entry.get('timestamp', '')}** — "
            f"`{entry.get('node', '')}`: {entry.get('message', '')}"
        )


def render_results(result):
    st.header("Analysis Results")
    tabs = st.tabs(
        [
            "Overview",
            "Telemetry",
            "Diagnosis",
            "RAG Evidence",
            "Service Plan",
            "Final Report",
            "Audit Log",
        ]
    )

    with tabs[0]:
        render_overview(result)
    with tabs[1]:
        render_telemetry(result)
    with tabs[2]:
        render_diagnosis(result)
    with tabs[3]:
        render_rag_evidence(result)
    with tabs[4]:
        render_service_plan(result)
    with tabs[5]:
        render_final_report(result)
    with tabs[6]:
        render_audit_log(result)


def render_approval_panel(interrupt_payload, partial_state):
    st.warning("Human approval required — critical risk detected.")

    payload = interrupt_payload or {}
    risk_score = payload.get("risk_score")
    risk_level = payload.get("risk_level", "CRITICAL")
    vehicle_id = payload.get("vehicle_id", partial_state.get("vehicle_id", ""))

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Vehicle", vehicle_id)
        st.metric("Risk Score", f"{risk_score}/100" if risk_score is not None else "—")
    with col2:
        st.write("Risk Level")
        render_risk_badge(risk_level)

    diagnosis = payload.get("diagnosis", partial_state.get("diagnosis", {}))
    assessment = diagnosis.get("assessment") if isinstance(diagnosis, dict) else None
    if assessment:
        st.subheader("Diagnostic Assessment")
        st.markdown(assessment)

    if partial_state:
        with st.expander("Partial analysis state"):
            render_overview(partial_state)
            render_telemetry(partial_state)

    with st.form("approval_form"):
        decision = st.radio("Decision", ["APPROVE", "REJECT"], horizontal=True)
        feedback = st.text_area("Optional feedback")
        submitted = st.form_submit_button("Submit decision", type="primary")

    if submitted:
        app = get_workflow()
        config = st.session_state.run_config
        with st.spinner("Resuming workflow..."):
            result, interrupt_payload, partial_state = resume_workflow(
                app, decision, feedback, config
            )

        if interrupt_payload is not None:
            st.session_state.pending_interrupt = interrupt_payload
            st.session_state.partial_state = partial_state
        else:
            st.session_state.workflow_result = result
            st.session_state.pending_interrupt = None
            st.session_state.partial_state = None

        st.rerun()


def render_input_form():
    st.header("Vehicle Input")

    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Vehicle ID", key="vehicle_id")
    with col2:
        st.text_input("User Request", key="user_request")

    st.subheader("Telemetry")
    tcol1, tcol2, tcol3 = st.columns(3)
    with tcol1:
        st.text_input("Timestamp", key="timestamp")
        st.number_input("Engine RPM", key="engine_rpm", min_value=0.0, step=50.0)
        st.number_input("Coolant Temperature (°C)", key="coolant_temperature", step=1.0)
    with tcol2:
        st.number_input("Oil Pressure (bar)", key="oil_pressure", min_value=0.0, step=0.1)
        st.number_input("Battery Voltage (V)", key="battery_voltage", step=0.1)
    with tcol3:
        st.number_input("Vibration", key="vibration", min_value=0.0, step=0.1)
        st.number_input("Vehicle Speed", key="vehicle_speed", min_value=0.0, step=1.0)

    st.subheader("History")
    st.text_area("Maintenance records (one per line)", key="maintenance", height=120)
    st.text_area("Previous faults (one per line)", key="previous_faults", height=80)

    if st.button("Run Analysis", type="primary"):
        prerequisites = check_prerequisites()
        if prerequisites:
            for issue in prerequisites:
                st.error(issue)
            return

        app = get_workflow()
        initial_state = build_initial_state()
        thread_id = f"{initial_state['vehicle_id']}-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        st.session_state.run_config = config
        st.session_state.workflow_result = None
        st.session_state.pending_interrupt = None
        st.session_state.partial_state = None

        with st.spinner("Running predictive maintenance workflow..."):
            result, interrupt_payload, partial_state = run_until_complete(
                app, initial_state, config
            )

        if interrupt_payload is not None:
            st.session_state.pending_interrupt = interrupt_payload
            st.session_state.partial_state = partial_state or result
        else:
            st.session_state.workflow_result = result

        st.rerun()


def render_sidebar():
    st.sidebar.title("Predictive Maintenance")
    st.sidebar.caption("Agentic AI workflow powered by LangGraph")

    prerequisites = check_prerequisites()
    if prerequisites:
        st.sidebar.error("Setup incomplete")
        for issue in prerequisites:
            st.sidebar.write(f"- {issue}")
    else:
        st.sidebar.success("All prerequisites ready")

    test_cases = load_test_cases()
    if test_cases:
        options = {
            f"{tc['id']} — {tc['description']}": tc for tc in test_cases
        }
        selected = st.sidebar.selectbox("Load test case", ["—"] + list(options.keys()))
        if selected != "—" and st.sidebar.button("Apply test case"):
            apply_test_case(options[selected])
            st.rerun()

    if st.sidebar.button("New Analysis"):
        st.session_state.workflow_result = None
        st.session_state.pending_interrupt = None
        st.session_state.partial_state = None
        st.session_state.run_config = None
        st.rerun()

    st.sidebar.divider()

    # Secrets Status
    st.sidebar.subheader("🔐 Secrets Status")
    try:
        import streamlit as st_secrets
        secrets_available = bool(st_secrets.secrets)
        if secrets_available:
            st.sidebar.success("✓ Secrets loaded from secrets.toml")
            with st.sidebar.expander("View loaded secrets"):
                # Show redacted secrets (last 4 chars only)
                redacted = {}
                for key in st_secrets.secrets:
                    val = st_secrets.secrets[key]
                    if isinstance(val, str) and len(val) > 4:
                        redacted[key] = "***" + val[-4:]
                    else:
                        redacted[key] = "***"
                st.json(redacted)
        else:
            st.sidebar.info("ℹ Using .env fallback")
    except Exception:
        st.sidebar.info("ℹ Using .env fallback")

    st.sidebar.divider()

    # LangSmith Tracing Status
    st.sidebar.subheader("🔍 LangSmith Tracing")
    tracing_status = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    api_key_set = bool(os.getenv("LANGSMITH_API_KEY", ""))

    if tracing_status and api_key_set:
        st.sidebar.success("✓ Tracing enabled")
        st.sidebar.caption(f"Project: {LANGSMITH_PROJECT}")
        langsmith_url = "https://smith.langchain.com/projects"
        st.sidebar.markdown(f"[View dashboard →]({langsmith_url})", unsafe_allow_html=True)
    elif tracing_status:
        st.sidebar.warning("⚠ LANGSMITH_API_KEY not set")
        st.sidebar.caption("Tracing disabled — add key to .env")
    else:
        st.sidebar.info("ℹ Tracing disabled")
        st.sidebar.caption("Set LANGSMITH_TRACING=true to enable")

    st.sidebar.divider()
    if st.sidebar.button("Test Snowflake Connection"):
        with st.sidebar:
            info = test_connection()
            if info["status"] == "OK":
                st.success(f"Connected as {info['connected_user']} ({info['connected_role']})")
            else:
                st.error(f"Connection failed")
                st.code(f"Account: {info['account']}\n"
                        f"User: {info['user']}\n"
                        f"Password set: {info['password_set']} (len={info['password_len']})\n"
                        f"Error: {info.get('error', 'unknown')}")

    if st.sidebar.button("Load Latest Telemetry"):
        try:
            from snowflake_utils import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT vehicle_id, timestamp, engine_rpm, coolant_temperature, "
                "oil_pressure, battery_voltage, vibration, vehicle_speed "
                "FROM VEHICLE_TELEMETRY ORDER BY timestamp DESC LIMIT 1"
            )
            row = cur.fetchone()
            conn.close()
            if row:
                st.session_state["vehicle_id"] = row[0]
                st.session_state["timestamp"] = str(row[1])
                st.session_state["engine_rpm"] = float(row[2])
                st.session_state["coolant_temperature"] = float(row[3])
                st.session_state["oil_pressure"] = float(row[4])
                st.session_state["battery_voltage"] = float(row[5])
                st.session_state["vibration"] = float(row[6])
                st.session_state["vehicle_speed"] = float(row[7])
                st.sidebar.success(f"Loaded latest reading for {row[0]}")
                st.rerun()
            else:
                st.sidebar.warning("No telemetry data found")
        except Exception as e:
            st.sidebar.error(f"Failed: {e}")


def render_snowflake_history():
    st.header("Snowflake Reports History")
    try:
        reports = get_reports_from_snowflake(limit=20)
        if not reports:
            st.info("No reports saved to Snowflake yet. Run an analysis to generate one.")
            return
        for rpt in reports:
            risk_level = rpt.get("RISK_LEVEL", "UNKNOWN")
            color = RISK_COLORS.get(risk_level, "#6c757d")
            with st.expander(
                f"{rpt.get('VEHICLE_ID', '?')} | "
                f"{risk_level} (Score: {rpt.get('RISK_SCORE', '?')}) | "
                f"{rpt.get('CREATED_AT', '')}"
            ):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Risk Score", f"{rpt.get('RISK_SCORE', '—')}/100")
                with col2:
                    st.write("Risk Level")
                    st.markdown(
                        f"<span style='color:{color}; font-weight:bold;'>{risk_level}</span>",
                        unsafe_allow_html=True,
                    )
                with col3:
                    prob = rpt.get("ML_FAILURE_PROBABILITY")
                    if prob is not None:
                        st.metric("ML Failure Prob", f"{prob:.1%}")
                if rpt.get("DIAGNOSIS"):
                    st.subheader("Diagnosis")
                    st.markdown(rpt["DIAGNOSIS"])
                if rpt.get("FINAL_REPORT"):
                    st.subheader("Final Report")
                    st.markdown(rpt["FINAL_REPORT"])
    except Exception as e:
        st.error(f"Could not load Snowflake reports: {e}")


def render_snowflake_telemetry():
    st.header("Snowflake Telemetry Data")
    try:
        import pandas as pd
        data = get_telemetry_from_snowflake()
        if not data:
            st.info("No telemetry data in Snowflake.")
            return
        df = pd.DataFrame(data)
        display_cols = [c for c in df.columns if c not in ("ID", "LOADED_AT")]
        st.dataframe(df[display_cols], use_container_width=True)
    except Exception as e:
        st.error(f"Could not load telemetry: {e}")


def render_stage_reports():
    st.header("Report Files (Snowflake Stage)")
    try:
        files = list_stage_reports()
        if not files:
            st.info("No report files in stage yet. Run an analysis to generate one.")
            return
        st.write(f"**{len(files)} report file(s) stored in `@REPORT_FILES`**")
        for f in files:
            name = f.get("name", "")
            size = f.get("size", 0)
            modified = f.get("last_modified", "")
            with st.expander(f"{name} ({size} bytes) — {modified}"):
                if st.button(f"View report", key=f"view_{name}"):
                    stage_path = f"@{name}" if not name.startswith("@") else name
                    content = download_stage_report(stage_path)
                    if content:
                        st.markdown(content)
                    else:
                        st.warning("Could not download report content.")
    except Exception as e:
        st.error(f"Could not list stage reports: {e}")


def render_langsmith_traces():
    st.header("🔍 LangSmith Traces")

    if not LANGSMITH_ENABLED:
        st.warning("LangSmith tracing is not enabled. Set LANGSMITH_API_KEY in .env to enable.")
        st.code("""LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_api_key_here
LANGSMITH_PROJECT=Demo""")
        return

    st.success(f"✓ Tracing enabled — Project: **{LANGSMITH_PROJECT}**")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"[📊 Open LangSmith Dashboard](https://smith.langchain.com/projects)",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"[📖 View Docs](https://docs.smith.langchain.com/)",
            unsafe_allow_html=True,
        )

    st.divider()

    try:
        from langsmith import Client

        client = Client(api_key=LANGSMITH_API_KEY, api_url=LANGSMITH_ENDPOINT)

        st.subheader("Recent Traces")
        limit = st.slider("Number of traces to show", 1, 50, 10)

        if st.button("Refresh traces", type="primary"):
            st.session_state['refresh_traces'] = True

        traces = []
        try:
            for trace in client.list_runs(
                project_name=LANGSMITH_PROJECT,
                limit=limit,
            ):
                traces.append(trace)
        except Exception as e:
            st.error(f"Could not fetch traces: {e}")
            return

        if not traces:
            st.info(f"No traces found in project '{LANGSMITH_PROJECT}'. Run an analysis to generate traces.")
            return

        st.write(f"**{len(traces)} trace(s) found**")

        for trace in traces:
            trace_id = trace.id
            trace_name = trace.name or "unknown"
            trace_status = "✓" if trace.error is None else "✗"
            duration = trace.end_time - trace.start_time if trace.end_time else None
            duration_str = f"{duration.total_seconds():.2f}s" if duration else "—"

            with st.expander(f"{trace_status} {trace_name} | {duration_str} | {trace.start_time}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Trace ID", str(trace_id)[:16] + "...")
                with col2:
                    st.metric("Status", "Success" if trace.error is None else "Error")
                with col3:
                    st.metric("Duration", duration_str)

                if trace.error:
                    st.error(f"Error: {trace.error}")

                if trace.inputs:
                    st.subheader("Inputs")
                    st.json(trace.inputs)

                if trace.outputs:
                    st.subheader("Outputs")
                    st.json(trace.outputs)

                st.markdown(
                    f"[View in LangSmith →](https://smith.langchain.com/projects/p/{client.get_project(project_name=LANGSMITH_PROJECT).id}/r/{trace_id})",
                    unsafe_allow_html=True,
                )

    except ImportError:
        st.error("LangSmith client not installed. Install with: `pip install langsmith`")
    except Exception as e:
        st.error(f"Error loading traces: {e}")


def main():
    st.set_page_config(
        page_title="Vehicle Predictive Maintenance",
        page_icon="🚗",
        layout="wide",
    )

    init_session_state()
    render_sidebar()

    page = st.sidebar.radio(
        "Navigate",
        ["Run Analysis", "Reports History", "Report Files", "Telemetry Data", "LangSmith Traces"],
        index=0,
    )

    st.title("Vehicle Predictive Maintenance")
    st.markdown(
        "Analyze vehicle telemetry, maintenance history, RAG evidence, and ML "
        "predictions through a multi-agent LangGraph workflow."
    )

    if page == "Reports History":
        render_snowflake_history()
    elif page == "Report Files":
        render_stage_reports()
    elif page == "Telemetry Data":
        render_snowflake_telemetry()
    elif page == "LangSmith Traces":
        render_langsmith_traces()
    elif st.session_state.pending_interrupt is not None:
        render_approval_panel(
            st.session_state.pending_interrupt,
            st.session_state.partial_state,
        )
    else:
        render_input_form()
        if st.session_state.workflow_result is not None:
            render_results(st.session_state.workflow_result)


if __name__ == "__main__":
    main()
