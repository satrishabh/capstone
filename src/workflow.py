import os
from typing import Literal
from pathlib import Path
from datetime import datetime, timezone
import json
from zoneinfo import ZoneInfo
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None
from langgraph.graph import (
    StateGraph,
    START,
    END
)
from langgraph.types import interrupt
from langchain_google_genai import (
    ChatGoogleGenerativeAI
)
from langchain_core.messages import HumanMessage
from state_schema import MaintenanceState
from rag import retrieve_documents
from ml_model import (
    predict_failure_probability
)
from tools import analyze_telemetry


#GEMINI LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    temperature=0
)

def add_audit(state: MaintenanceState,node: str,message: str = ""):
    logs = state.get("audit_log",[])
    logs.append({"timestamp":datetime.now(timezone.utc)
            .astimezone(ZoneInfo("Asia/Kolkata"))
            .isoformat(),"node": node,"message": message})
    state["audit_log"] = logs

#write the logs to a file
def write_audit_log(state: MaintenanceState):
    audit_logs = state.get("audit_log", [])
    log_dir = Path("../logs")
    log_dir.mkdir(exist_ok=True)
    vehicle_id = state.get("vehicle_id", "unknown_vehicle")
    execution_id = state.get(
        "execution_id",
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )

    log_file = log_dir / (
        f"{vehicle_id}_{execution_id}_audit.json"
    )
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(
            audit_logs,
            f,
            indent=4,
            ensure_ascii=False
        )
    return str(log_file)


# 1. SUPERVISOR (Parallel)
def supervisor(state: MaintenanceState):
    add_audit(state,"supervisor","Workflow started")
    print("\n==============================")
    print("SUPERVISOR AGENT")
    print("Vehicle:",state["vehicle_id"])
    print("Request:",state["user_request"])
    print("==============================")
    return {
        "audit_log": [
            {
                "timestamp": datetime.now(timezone.utc)
            .astimezone(ZoneInfo("Asia/Kolkata"))
            .isoformat(),
                "node": "supervisor",
                "message": "Workflow started"
            }
        ]
    }


# 2. TELEMETRY AGENT
def telemetry_agent(state: MaintenanceState):
    print("\n>>> TELEMETRY AGENT")
    telemetry = state.get("telemetry",{})
    result = analyze_telemetry.invoke({
        "telemetry": telemetry
    })

    abnormalities = result["abnormalities"]

    return {
        "telemetry": result,
        "audit_log": [
            {
                "timestamp": datetime.now(timezone.utc)
            .astimezone(ZoneInfo("Asia/Kolkata"))
            .isoformat(),
                "node": "telemetry_agent",
                "message": (
                    f"Found {len(abnormalities)} "
                    f"abnormal parameters"
                )
            }
        ]
    }


# 3. HISTORY AGENT
def history_agent(state: MaintenanceState):
    print("\n>>> HISTORY AGENT")
    history = state.get("history",{})
    previous_faults = history.get("previous_faults",[])
    maintenance = history.get("maintenance",[])

    """
    state["history"] = {
        "maintenance":
            maintenance,
        "previous_faults":
            previous_faults,
        "trend_summary":
            "Historical information retrieved"
    }
    add_audit(state,"history_agent","Historical vehicle information retrieved")
    return state
    """
    return {
        "history": {
            "maintenance": maintenance,
            "previous_faults": previous_faults,
            "trend_summary":
                "Historical information retrieved"
        },

        "audit_log": [
            {
                "timestamp": datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Kolkata")).isoformat(),
                "node": "history_agent",
                "message":
                    "Historical vehicle information retrieved"
            }
        ]
    }


# 4. RAG AGENT
def rag_agent(state: MaintenanceState):
    print("\n>>> RAG AGENT")
    telemetry = state["telemetry"]["raw"]

    abnormalities = state["telemetry"]["abnormalities"]
    query_parts = []

    for item in abnormalities:
        query_parts.append(
            f"{item['parameter']} "
            f"{item['value']} "
            f"{item['reason']}"
        )

    query = "\n".join(query_parts)
    if not query:
        query = (
            "normal vehicle "
            "predictive maintenance"
        )
    print("FAISS Query:")
    print(query)

    documents = retrieve_documents(
        query=query,
        k=5
    )
    rag_evidence = []
    for doc in documents:
        rag_evidence.append({
            "source":doc["source"],
            "content":doc["content"]
        })

    #state["rag_evidence"] = rag_evidence
    #add_audit(state,"rag_agent",f"Retrieved {len(rag_evidence)} FAISS documents")
    return {
        "rag_evidence": rag_evidence,
        "audit_log": [
            {
                "timestamp": datetime.now(timezone.utc)
                .astimezone(
                    ZoneInfo("Asia/Kolkata")
                )
                .isoformat(),
                "node": "rag_agent",
                "message":
                    f"Retrieved {len(rag_evidence)} FAISS documents"
            }
        ]
    }


# 5. ML AGENT
def ml_agent(state: MaintenanceState):
    print("\n>>> ML FAILURE PREDICTION AGENT")
    telemetry = state["telemetry"]["raw"]
    #telemetry = state.get("telemetry", {})
    try:
        probability = (predict_failure_probability(telemetry))
    except Exception as e:
        print("ML prediction failed:",e)
        probability = 0.0
    state["ml_failure_probability"] = probability

    if probability >= 0.75:
        label = "HIGH"
    elif probability >= 0.50:
        label = "MEDIUM"
    else:
        label = "LOW"

    #state["ml_prediction_label"] = label
    print(f"Failure probability: "f"{probability:.2%}")
    print(f"Prediction level: {label}")

    #add_audit(state,"ml_agent",f"Failure probability={probability:.3f}")
    #return state
    return {
        "ml_failure_probability":probability,
        "ml_prediction_label":label,
        "audit_log": [
            {
                "timestamp":
                    datetime.now(timezone.utc)
                    .astimezone(
                        ZoneInfo("Asia/Kolkata")
                    )
                    .isoformat(),
                "node":
                    "ml_agent",
                "message":
                    f"Failure probability={probability:.3f}"
            }
        ]
    }


# 6. DIAGNOSTIC AGENT
def diagnostic_agent(state: MaintenanceState):
    print("\n>>> DIAGNOSTIC AGENT")
    telemetry = state["telemetry"]
    history = state["history"]
    rag = state.get("rag_evidence",[])
    ml_probability = state.get("ml_failure_probability",0.0)

    # Convert RAG documents to context
    rag_context = "\n\n".join(
        [
            (
                f"SOURCE: {item['source']}\n"
                f"{item['content']}"
            )
            for item in rag
        ]
    )

    prompt = f"""
    You are the Diagnostic Agent in a vehicle predictive-maintenance system.
    
    Your job is to reason over evidence.

    DO NOT claim a component has definitely failed unless the evidence proves it.
    Use:
    1. Current telemetry
    2. Historical information
    3. Internal RAG evidence
    4. ML failure probability
    
    CURRENT TELEMETRY:
    {telemetry}
    
    HISTORY:
    {history}
    
    RAG EVIDENCE:
    {rag_context}
    
    ML FAILURE PROBABILITY:
    {ml_probability:.3f}
    
    Produce a concise diagnostic assessment.
    
    Return:
    
    PRIMARY FINDING
    POSSIBLE CAUSES
    EVIDENCE
    RECOMMENDED VERIFICATION
    LIMITATIONS
    
    Remember:

    - ML probability is an estimate, not proof.
    - RAG evidence is supporting evidence, not physical proof.
    - Telemetry anomalies may be caused by sensor faults.
    - Recommend physical verification before declaring component failure.
    """

    response = llm.invoke(
        [
            HumanMessage(
                content=prompt
            )
        ]
    )

    """
    diagnosis_text = response.content
    state["diagnosis"] = {
        "assessment":
            diagnosis_text,

        "ml_failure_probability":
            ml_probability
    }
    """
    content = response.content
    if isinstance(content, str):
        diagnosis_text = content
    elif isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(
                        item.get("text", "")
                    )

        diagnosis_text = "\n".join(
            part for part in text_parts if part
        )
    else:
        diagnosis_text = str(content)
    #state["diagnosis"] = {"assessment": diagnosis_text,"ml_failure_probability": ml_probability}
    print("\nDiagnostic assessment:")
    print(diagnosis_text)
    #add_audit(state,"diagnostic_agent","Diagnostic assessment generated")
    #return state

    return {
        "diagnosis": {
            "assessment":
                diagnosis_text,
            "ml_failure_probability":
                ml_probability
        },
        "audit_log": [
            {
                "timestamp":
                    datetime.now(timezone.utc)
                    .astimezone(
                        ZoneInfo("Asia/Kolkata")
                    )
                    .isoformat(),
                "node":
                    "diagnostic_agent",
                "message":
                    "Diagnostic assessment generated"
            }
        ]
    }

# 7. RISK / DECISION AGENT
def risk_agent(state: MaintenanceState):
    print("\n>>> RISK / DECISION AGENT")
    abnormalities = state["telemetry"]["abnormalities"]
    ml_probability = state.get("ml_failure_probability",0.0)
    history = state["history"]

    # Deterministic scoring
    score = 0

    # Current telemetry
    for item in abnormalities:
        severity = item["severity"]
        if severity == "CRITICAL":
            score += 30
        elif severity == "HIGH":
            score += 20
        elif severity == "WARNING":
            score += 10

    # ML contribution
    score += int(ml_probability * 25)

    # Historical faults
    previous_faults = history.get("previous_faults",[])
    if len(previous_faults) >= 2:
        score += 15
    elif len(previous_faults) == 1:
        score += 7

    # Maximum 100
    score = min(score,100)

    # Risk category
    if score >= 81:
        risk_level = "CRITICAL"
    elif score >= 61:
        risk_level = "HIGH"
    elif score >= 31:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    human_required = (risk_level == "CRITICAL")

    state["risk_decision"] = {
        "risk_score":
            score,
        "risk_level":
            risk_level,
        "human_approval_required":
            human_required,
        "reason":
            (
                "Critical risk requires "
                "human approval."
                if human_required
                else
                "Automatic reporting permitted."
            )
    }
    print(f"Risk score: {score}/100")
    print(f"Risk level: {risk_level}")
    add_audit(state,"risk_agent",f"Risk={risk_level}, score={score}")
    return state


# 8. ROUTE AFTER RISK
def route_after_risk(state: MaintenanceState) -> Literal[
    "human_approval",
    "report"
]:

    risk_level = (state["risk_decision"]["risk_level"])
    if risk_level == "CRITICAL":
        return "human_approval"
    return "report"


# 9. HUMAN APPROVAL

"""
def human_approval(state: MaintenanceState):
    print("\n>>> HUMAN APPROVAL REQUIRED")
    risk = state["risk_decision"]
    diagnosis = state["diagnosis"]
    approval_request = {
        "message":
            "Critical vehicle maintenance "
            "decision requires human approval.",

        "vehicle_id":
            state["vehicle_id"],

        "risk_score":
            risk["risk_score"],

        "risk_level":
            risk["risk_level"],

        "diagnosis":
            diagnosis,

        "options": [
            "APPROVE",
            "REJECT"
        ]
    }

    # LangGraph interrupt
    human_response = interrupt(approval_request)

    # Expected response:
    # {
    #     "decision": "APPROVE",
    #     "feedback": "Proceed with inspection"
    # }

    if isinstance(human_response,dict):
        state["human_decision"] = human_response.get("decision")
        state["human_feedback"] = human_response.get("feedback","")
    else:
        state["human_decision"] = str(human_response)
        state["human_feedback"] = ""
    print("Human decision:",state["human_decision"])

    add_audit(state,"human_approval",f"Decision={state['human_decision']}")
    return state
    """

def human_approval(state: MaintenanceState):

    print("\n>>> HUMAN APPROVAL REQUIRED")
    risk = state["risk_decision"]
    diagnosis = state["diagnosis"]

    print("\n" + "=" * 60)
    print("HUMAN APPROVAL")
    print("=" * 60)

    print(f"Vehicle ID   : {state['vehicle_id']}")
    print(f"Risk Score   : {risk['risk_score']}/100")
    print(f"Risk Level   : {risk['risk_level']}")

    print("\nDiagnostic Assessment:")
    print(diagnosis["assessment"])

    print("\n" + "-" * 60)
    print("Available decisions:")
    print("  APPROVE - Proceed with maintenance service plan")
    print("  REJECT  - Re-analyze the vehicle condition")
    print("-" * 60)

    #Get human input from terminal
    while True:
        human_input = input(
            "\nEnter your decision (APPROVE/REJECT): "
        ).strip().upper()
        if human_input in ["APPROVE", "REJECT"]:
            break
        print("Invalid input. Please enter APPROVE or REJECT.")

    #optional feedback
    feedback = input("Enter optional feedback: ").strip()

    # Store human decision
    state["human_decision"] = human_input
    state["human_feedback"] = feedback
    print(f"\nHuman decision: {human_input}")

    if feedback:
        print(f"Human feedback: {feedback}")

    add_audit(state,"human_approval",f"Decision={human_input}, Feedback={feedback}")
    return state

# 10. ROUTE AFTER HUMAN
def route_after_human(state: MaintenanceState) -> Literal["service_plan","reanalyze"]:
    decision = (state.get("human_decision"))
    if decision == "APPROVE":
        return "service_plan"
    return "reanalyze"


# 11. RE-ANALYSIS
def reanalyze(state: MaintenanceState):
    print("\n>>> RE-ANALYSIS")
    feedback = state.get("human_feedback","")
    print("Human feedback:",feedback)

    # Add the human feedback into the
    # diagnosis context.

    state["diagnosis"]["human_feedback"] = feedback
    add_audit(state,"reanalyze","Human feedback incorporated")

    return state


# 12. SERVICE PLAN
def service_plan(state: MaintenanceState):
    print("\n>>> SERVICE PLAN AGENT")
    diagnosis = state["diagnosis"]
    rag = state.get("rag_evidence",[])
    rag_context = "\n\n".join([
            item["content"]
            for item in rag
        ]
    )

    prompt = f"""
    You are a Vehicle Service Planning Agent.
    
    Create an actionable maintenance plan based on:
    
    DIAGNOSIS:
    {diagnosis}
    
    TECHNICAL DOCUMENTATION:
    {rag_context}
    
    Generate:
    
    1. Priority
    2. Immediate checks
    3. Diagnostic checks
    4. Potential service actions
    5. Post-service validation
    
    Do not recommend replacing expensive components
    without verification.
    """

    response = llm.invoke([HumanMessage(content=prompt)])
    state["service_plan"] = {"plan":response.content}
    add_audit(state,"service_plan","Service plan generated")
    return state

def save_final_report_to_s3(state: MaintenanceState):
    """Upload the final report text to S3 using values from .env."""
    bucket = (
        os.getenv("S3_BUCKET_NAME")
        or os.getenv("AWS_S3_BUCKET")
        or os.getenv("S3_BUCKET")
    )
    if not bucket:
        print("S3 upload skipped: no bucket configured in .env (S3_BUCKET_NAME/AWS_S3_BUCKET).")
        return None

    if boto3 is None:
        raise ImportError(
            "boto3 is required for S3 uploads. Install it with: pip install boto3"
        )

    report_text = state.get("final_report", "")
    if not isinstance(report_text, str):
        report_text = json.dumps(report_text, indent=2)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    vehicle_id = state.get("vehicle_id", "unknown_vehicle")
    key = f"final-reports/{vehicle_id}/{timestamp}_report.md"

    region = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "us-east-1"
    access_key = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("S3_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("S3_SECRET_ACCESS_KEY")
    endpoint_url = (
        os.getenv("AWS_S3_ENDPOINT_URL")
        or os.getenv("S3_ENDPOINT_URL")
        or os.getenv("S3_ENDPOINT")
    )

    client_kwargs = {"region_name": region}
    if access_key and secret_key:
        client_kwargs["aws_access_key_id"] = access_key
        client_kwargs["aws_secret_access_key"] = secret_key
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url

    s3 = boto3.client("s3", **client_kwargs)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=report_text.encode("utf-8"),
        ContentType="text/markdown"
    )

    s3_uri = f"s3://{bucket}/{key}"
    print(f"Final report uploaded to S3: {s3_uri}")
    add_audit(state, "report", f"Final report saved to S3: {s3_uri}")
    return s3_uri


# 13. REPORT
def report(state: MaintenanceState):

    print("\n>>> FINAL REPORT AGENT")
    vehicle_id = state["vehicle_id"]
    telemetry = state["telemetry"]
    history = state["history"]
    diagnosis = state.get("diagnosis",{})
    risk = state.get("risk_decision",{})
    probability = state.get("ml_failure_probability",0)
    service = state.get("service_plan",{})

    human_decision = state.get("human_decision","NOT_REQUIRED")

    prompt = f"""
    Create a professional Vehicle Predictive
    Maintenance Report.
    
    Vehicle:
    {vehicle_id}
    
    Telemetry:
    {telemetry}
    
    History:
    {history}
    
    ML Failure Probability:
    {probability:.2%}
    
    Diagnosis:
    {diagnosis}
    
    Risk:
    {risk}
    
    Human Decision:
    {human_decision}
    
    Service Plan:
    {service}
    
    The report must contain:
    
    1. Executive Summary
    2. Vehicle Information
    3. Current Telemetry
    4. Abnormal Parameters
    5. Historical Trends
    6. ML Failure Probability
    7. Diagnostic Assessment
    8. RAG Evidence
    9. Risk Assessment
    10. Human Decision
    11. Recommended Service
    12. Limitations
    
    Clearly state that the ML probability is an
    estimate and that diagnosis is not certainty.
    """

    response = llm.invoke(
        [
            HumanMessage(
                content=prompt
            )
        ]
    )

    state["final_report"] = response.content
    add_audit(state,"report","Final report generated")

    try:
        save_final_report_to_s3(state)
    except Exception as exc:
        print(f"S3 upload failed: {exc}")
        add_audit(state, "report", f"S3 upload failed: {exc}")

    audit_file = write_audit_log(state)
    print("\nAudit log written to:")
    print(audit_file)
    return state


def save_workflow_graph(app):
    mermaid_code = app.get_graph().draw_mermaid()

    output_file = Path("langgraph_workflow.mmd")

    output_file.write_text(
        mermaid_code,
        encoding="utf-8"
    )
    print("\nMermaid workflow saved:")
    print(output_file.resolve())


# BUILD GRAPH
def build_workflow():

    graph = StateGraph(MaintenanceState)

    # Nodes
    #graph.add_node("supervisor",supervisor)
    graph.add_node("telemetry",telemetry_agent)
    graph.add_node("history",history_agent)
    graph.add_node("rag",rag_agent)
    graph.add_node("ml",ml_agent)
    graph.add_node("diagnostic",diagnostic_agent)
    graph.add_node("risk",risk_agent)
    graph.add_node("human_approval",human_approval)
    graph.add_node("reanalyze",reanalyze)
    graph.add_node("service_plan",service_plan)
    graph.add_node("report",report)


    # START - Parallel Execution
    graph.add_edge(START,"telemetry")
    graph.add_edge(START, "history")

    # Supervisor - Parallel execution
    #graph.add_edge("supervisor", "telemetry")
    #graph.add_edge("supervisor","history")

    graph.add_edge("telemetry", "ml")
    graph.add_edge("history", "ml")

    graph.add_edge("telemetry", "rag")
    graph.add_edge("history", "rag")

    #graph.add_edge("ml","rag")
    graph.add_edge("ml", "diagnostic")
    graph.add_edge("rag", "diagnostic")

    graph.add_edge("diagnostic","risk")

    # Risk conditional routing
    graph.add_conditional_edges("risk",route_after_risk,
        {
            "human_approval":
                "human_approval",
            "report":
                "report"
        }
    )

    # Human decision
    graph.add_conditional_edges(
        "human_approval",
        route_after_human,
        {
            "service_plan":
                "service_plan",

            "reanalyze":
                "reanalyze"
        }
    )

    # Re-analysis
    #graph.add_edge("reanalyze","diagnostic")
    graph.add_edge("reanalyze", "report")

    # Service plan
    graph.add_edge("service_plan","report")

    # Final
    graph.add_edge("report",END)
    print("The graph:",graph)
    app=graph.compile()

    #saving the graph chart to png
    save_workflow_graph(app)

    return app