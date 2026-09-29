"""Quick agent-by-agent diagnostic — runs each workflow node in isolation."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
load_dotenv()

PASS = "PASS"
FAIL = "FAIL"
results = []

def check(name, fn):
    try:
        fn()
        results.append((name, PASS, ""))
        print(f"  [{PASS}] {name}")
    except Exception as e:
        results.append((name, FAIL, str(e)))
        print(f"  [{FAIL}] {name} -> {e}")

# --- 1. Telemetry Agent ---
def test_telemetry():
    from tools import analyze_telemetry
    out = analyze_telemetry.invoke({"telemetry": {
        "engine_rpm": 2400, "coolant_temperature": 108,
        "oil_pressure": 1.3, "battery_voltage": 13.3,
        "vibration": 8.2, "vehicle_speed": 70
    }})
    assert "abnormalities" in out, f"Unexpected output: {out}"
    assert len(out["abnormalities"]) > 0, "Expected abnormalities for bad readings"

# --- 2. ML Agent ---
def test_ml():
    from ml_model import predict_failure_probability
    prob = predict_failure_probability({
        "engine_rpm": 2400, "coolant_temperature": 108,
        "oil_pressure": 1.3, "battery_voltage": 13.3,
        "vibration": 8.2, "vehicle_speed": 70
    })
    assert 0 <= prob <= 1, f"Probability out of range: {prob}"
    print(f"    ML failure probability: {prob:.2%}")

# --- 3. RAG Agent ---
def test_rag():
    from rag import retrieve_documents
    docs = retrieve_documents("engine overheating coolant", k=3)
    assert len(docs) > 0, "No RAG documents retrieved"
    print(f"    Retrieved {len(docs)} documents")

# --- 4. LLM (Cortex AI) ---
def test_cortex_llm():
    from cortex_llm import cortex_complete
    resp = cortex_complete("Say OK if you can hear me.")
    assert resp and len(resp.strip()) > 0, "Empty Cortex response"
    print(f"    Cortex response: {resp.strip()[:80]}")

# --- 5. Risk scoring (deterministic) ---
def test_risk():
    from workflow import risk_agent
    state = {
        "vehicle_id": "VH-TEST",
        "telemetry": {"abnormalities": [
            {"parameter": "oil_pressure", "severity": "CRITICAL"},
            {"parameter": "vibration", "severity": "HIGH"},
        ]},
        "ml_failure_probability": 0.92,
        "history": {"previous_faults": ["oil pressure decline"]},
        "audit_log": [],
    }
    out = risk_agent(state)
    risk = out.get("risk_decision", {})
    assert "risk_score" in risk, f"No risk_score: {risk}"
    print(f"    Risk score: {risk['risk_score']}, level: {risk['risk_level']}")

# --- 6. Snowflake connectivity ---
def test_snowflake():
    from snowflake_utils import get_connection
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM CAPSTONE_DB.PREDICTIVE_MAINTENANCE.VEHICLE_TELEMETRY")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 18, f"Expected 18 rows, got {count}"
    print(f"    Snowflake telemetry rows: {count}")

# --- 7. Cortex Embeddings ---
def test_cortex_embed():
    from cortex_llm import cortex_embed
    emb = cortex_embed("engine oil pressure low")
    assert len(emb) == 768, f"Expected 768-dim embedding, got {len(emb)}"
    print(f"    Embedding dimension: {len(emb)}")

# --- 8. Full workflow build ---
def test_workflow_build():
    from workflow import build_workflow
    app = build_workflow(for_web=True)
    nodes = list(app.get_graph().nodes)
    print(f"    Graph nodes: {nodes}")
    assert len(nodes) >= 8, f"Expected >=8 nodes, got {len(nodes)}"

print("\n=== Agent Diagnostics (Cortex AI) ===\n")
check("1. Telemetry Agent", test_telemetry)
check("2. ML Agent", test_ml)
check("3. RAG Agent (FAISS+BM25)", test_rag)
check("4. LLM (Cortex COMPLETE)", test_cortex_llm)
check("5. Risk Agent", test_risk)
check("6. Snowflake Connectivity", test_snowflake)
check("7. Cortex Embeddings", test_cortex_embed)
check("8. Workflow Graph Build", test_workflow_build)

print(f"\n=== Summary: {sum(1 for _,s,_ in results if s==PASS)}/{len(results)} passed ===\n")
for name, status, err in results:
    if status == FAIL:
        print(f"  FAILED: {name}: {err}")
