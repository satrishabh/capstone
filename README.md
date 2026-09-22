# Vehicle Predictive Maintenance — Agentic AI Capstone

This package is a synthetic, educational implementation blueprint for:

User/API
 -> Supervisor
 -> Telemetry + History + RAG
 -> Diagnostic
 -> ML Failure Probability + Risk Decision
 -> Human Approval for critical cases
 -> Service Plan / Re-analysis
 -> Final Report

## Important
All RAG documents and test data are synthetic. They are not OEM documentation and must not be used for real vehicle repair decisions.

## Suggested stack
- Python
- LangGraph for orchestration
- LangChain for model/tool abstractions
- scikit-learn for failure-probability model
- Chroma/FAISS/Vertex AI Vector Search for RAG
- FastAPI for API
- BigQuery/Cloud SQL for history
- Pub/Sub for telemetry streaming
- Cloud Run or GKE for deployment

## End-to-end execution

1. Receive vehicle_id + request.
2. Supervisor creates tasks.
3. Telemetry agent validates readings, thresholds and trends.
4. History agent retrieves maintenance/fault history.
5. RAG agent retrieves relevant synthetic service guidance.
6. ML model produces failure probability.
7. Diagnostic agent combines telemetry + history + RAG + ML probability.
8. Risk engine calculates risk score.
9. If critical: pause for human approval.
10. Approve -> service plan.
11. Reject -> capture reason and re-analysis.
12. Normal -> report directly.
13. Final report contains evidence, probability, risk, recommendation, approval state and limitations.

## RAG ingestion

Example:
    pip install langchain langchain-community chromadb sentence-transformers

Then load every file in rag_docs/ into a vector database, split into chunks,
create embeddings, and store metadata:
    source
    document_type
    section
    vehicle_family
    version

## ML warning

The included model is intentionally tiny and synthetic so the workflow can be demonstrated.
It is not a valid predictive model for real vehicles. A real system requires a large,
representative, time-aware labeled dataset, leakage prevention, calibration,
validation by vehicle/platform, drift monitoring, and domain validation.

## Recommended production state

Use a shared LangGraph state such as:
    vehicle_id
    user_request
    telemetry_result
    history_result
    rag_evidence
    ml_prediction
    diagnosis
    risk_decision
    human_decision
    service_plan
    final_report
    audit_log
