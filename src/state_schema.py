from typing import TypedDict, Any, List, Optional,Annotated
import operator

class MaintenanceState(TypedDict, total=False):
    #request
    vehicle_id: str
    user_request: str

    #vehicle data
    telemetry: dict
    history: dict

    #RAG
    rag_evidence: List[dict]

    #ML
    ml_failure_probability: float
    ml_prediction_label: str

    #diagnosis
    diagnosis: dict
    diagnosis_status : bool

    #risk agent
    risk_decision: dict

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
