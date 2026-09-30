import json
import os
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langgraph.types import Command

from workflow import build_workflow

load_dotenv()

DATA_DIR = Path("../data")
MODEL_PATH = Path("../models/failure_model.joblib")
VECTORSTORE_PATH = Path("../vectorstore/faiss_index")
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
    if not TEST_CASES_PATH.exists():
        return []
    with open(TEST_CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


def check_prerequisites():
    issues = []
    if not os.getenv("GOOGLE_API_KEY"):
        issues.append("GOOGLE_API_KEY is not set in `.env`")
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


def main():
    st.set_page_config(
        page_title="Vehicle Predictive Maintenance",
        page_icon="🚗",
        layout="wide",
    )

    init_session_state()
    render_sidebar()

    st.title("Vehicle Predictive Maintenance")
    st.markdown(
        "Analyze vehicle telemetry, maintenance history, RAG evidence, and ML "
        "predictions through a multi-agent LangGraph workflow."
    )

    if st.session_state.pending_interrupt is not None:
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
