from typing import TypedDict, Any, List, Optional,Annotated
import operator

class MaintenanceState(TypedDict, total=False):
    #request
    vehicle_id: str
    user_request: str

    #vehicle data
    telemetry: dict
    history: dict
    vehicle_model: str
    vehicle_year: int

    #RAG
    rag_evidence: List[dict]
    rag_version: str
    rag_doc_ids: List[str]

    #ML
    ml_failure_probability: float
    ml_prediction_label: str

    #diagnosis
    diagnosis: dict
    diagnosis_status : bool
    tool_results: List[dict]

    #risk agent
    risk_decision: dict
    approval_notification: dict

    #human approval
    human_decision: bool
    human_feedback: Optional[str]

    #service
    service_plan: dict
    reanalysis: dict

    #final report
    final_report: str

    #audit
    #audit_log: List[dict]
    audit_log: Annotated[list, operator.add]
