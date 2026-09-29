warning: in the working copy of 'README.md', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/.gitignore b/.gitignore[m
[1mindex d805153..6df92b5 100644[m
[1m--- a/.gitignore[m
[1m+++ b/.gitignore[m
[36m@@ -3,11 +3,16 @@[m
 .env[m
 .cortex[m
 .claude[m
[32m+[m[32m.streamlit/secrets.toml[m
[32m+[m[32m.streamlit/secrets.local.toml[m
[32m+[m[32m.streamlit/secrets.prod.toml[m
 # Python[m
 src/__pycache__/[m
 __pycache__/[m
 *.pyc[m
[31m-*.md[m
 [m
 # logs folder[m
 logs/[m
[32m+[m
[32m+[m[32m# local reference clone for the langsmith-trace Claude Code skill (not part of the app)[m
[32m+[m[32mlangsmith-skills/[m
[1mdiff --git a/README.md b/README.md[m
[1mindex b289b24..49cc26d 100644[m
[1m--- a/README.md[m
[1m+++ b/README.md[m
[36m@@ -1,78 +1,79 @@[m
 # Vehicle Predictive Maintenance — Agentic AI Capstone[m
 [m
[31m-This package is a synthetic, educational implementation blueprint for:[m
[32m+[m[32mA LangGraph-orchestrated agent that turns vehicle telemetry into a predictive-maintenance[m
[32m+[m[32mreport: it validates sensor readings, scores failure risk with an ML model, grounds its[m
[32m+[m[32mdiagnosis in service-manual excerpts via RAG, and pauses for human approval on critical[m
[32m+[m[32mcases before generating a final report.[m
 [m
[31m-User/API[m
[31m- -> Supervisor[m
[31m- -> Telemetry + History + RAG[m
[31m- -> Diagnostic[m
[31m- -> ML Failure Probability + Risk Decision[m
[31m- -> Human Approval for critical cases[m
[31m- -> Service Plan / Re-analysis[m
[31m- -> Final Report[m
[32m+[m[32m> All RAG documents and test data are synthetic. They are not OEM documentation and must[m
[32m+[m[32m> not be used for real vehicle repair decisions. The bundled ML model is a small, synthetic[m
[32m+[m[32m> demo model — not valid for real vehicles.[m
 [m
[31m-## Important[m
[31m-All RAG documents and test data are synthetic. They are not OEM documentation and must not be used for real vehicle repair decisions.[m
[32m+[m[32m## Architecture[m
 [m
[31m-## Suggested stack[m
[31m-- Python[m
[31m-- LangGraph for orchestration[m
[31m-- LangChain for model/tool abstractions[m
[31m-- scikit-learn for failure-probability model[m
[31m-- Chroma/FAISS/Vertex AI Vector Search for RAG[m
[31m-- FastAPI for API[m
[31m-- BigQuery/Cloud SQL for history[m
[31m-- Pub/Sub for telemetry streaming[m
[31m-- Cloud Run or GKE for deployment[m
[32m+[m[32m```[m
[32m+[m[32mUser/API request[m
[32m+[m[32m  -> Supervisor[m
[32m+[m[32m  -> Telemetry validation + History retrieval + RAG retrieval (FAISS + BM25)[m
[32m+[m[32m  -> ML failure-probability scoring[m
[32m+[m[32m  -> Diagnostic agent (telemetry + history + RAG + ML probability)[m
[32m+[m[32m  -> Risk engine[m
[32m+[m[32m  -> Human approval interrupt (if risk is CRITICAL)[m
[32m+[m[32m  -> Service plan / re-analysis[m
[32m+[m[32m  -> Final report -> saved to a Snowflake internal stage + report metadata table[m
[32m+[m[32m```[m
 [m
[31m-## End-to-end execution[m
[32m+[m[32mThe workflow graph is defined in [src/workflow.py](src/workflow.py); the state shape is in[m
[32m+[m[32m[src/state_schema.py](src/state_schema.py). See [langgraph_workflow.mmd](langgraph_workflow.mmd)[m
[32m+[m[32mfor the diagram source.[m
 [m
[31m-1. Receive vehicle_id + request.[m
[31m-2. Supervisor creates tasks.[m
[31m-3. Telemetry agent validates readings, thresholds and trends.[m
[31m-4. History agent retrieves maintenance/fault history.[m
[31m-5. RAG agent retrieves relevant synthetic service guidance.[m
[31m-6. ML model produces failure probability.[m
[31m-7. Diagnostic agent combines telemetry + history + RAG + ML probability.[m
[31m-8. Risk engine calculates risk score.[m
[31m-9. If critical: pause for human approval.[m
[31m-10. Approve -> service plan.[m
[31m-11. Reject -> capture reason and re-analysis.[m
[31m-12. Normal -> report directly.[m
[31m-13. Final report contains evidence, probability, risk, recommendation, approval state and limitations.[m
[32m+[m[32m## Stack[m
 [m
[31m-## RAG ingestion[m
[32m+[m[32m- **Orchestration**: LangGraph + LangChain[m
[32m+[m[32m- **LLM**: Google Gemini (primary, [src/llm_provider.py](src/llm_provider.py)) with[m
[32m+[m[32m  Snowflake Cortex as fallback / embeddings provider ([src/cortex_llm.py](src/cortex_llm.py))[m
[32m+[m[32m- **RAG**: FAISS + BM25 hybrid retrieval over [rag_docs/](rag_docs/) ([src/rag.py](src/rag.py))[m
[32m+[m[32m- **ML**: scikit-learn failure-probability model ([src/ml_model.py](src/ml_model.py),[m
[32m+[m[32m  trained by [src/train_failure_model.py](src/train_failure_model.py))[m
[32m+[m[32m- **Storage**: Snowflake (telemetry, history, reports, audit logs — [src/snowflake_utils.py](src/snowflake_utils.py))[m
[32m+[m[32m- **UI**: Streamlit ([src/app.py](src/app.py))[m
[32m+[m[32m- **Tracing**: LangSmith (optional, enabled via `.env`)[m
 [m
[31m-Example:[m
[31m-    pip install langchain langchain-community chromadb sentence-transformers[m
[32m+[m[32m## Setup[m
 [m
[31m-Then load every file in rag_docs/ into a vector database, split into chunks,[m
[31m-create embeddings, and store metadata:[m
[31m-    source[m
[31m-    document_type[m
[31m-    section[m
[31m-    vehicle_family[m
[31m-    version[m
[32m+[m[32m1. `pip install -r requirements.txt`[m
[32m+[m[32m2. Copy `.env.example` to `.env` and fill in your Gemini / Snowflake / LangSmith credentials.[m
[32m+[m[32m3. Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and fill in the same[m
[32m+[m[32m   values if running via Streamlit Cloud or `st.secrets` — see [docs/STREAMLIT_SECRETS_GUIDE.md](docs/STREAMLIT_SECRETS_GUIDE.md).[m
[32m+[m[32m4. Build the vector store: `python scripts/build_rag.py`[m
[32m+[m[32m5. (Optional) Seed Snowflake with mock fleet telemetry: `python scripts/mock_telemetry.py`[m
[32m+[m[32m6. Run the app: `streamlit run src/app.py`[m
 [m
[31m-## ML warning[m
[32m+[m[32m## Dev / diagnostic scripts[m
 [m
[31m-The included model is intentionally tiny and synthetic so the workflow can be demonstrated.[m
[31m-It is not a valid predictive model for real vehicles. A real system requires a large,[m
[31m-representative, time-aware labeled dataset, leakage prevention, calibration,[m
[31m-validation by vehicle/platform, drift monitoring, and domain validation.[m
[32m+[m[32mAll one-off CLI utilities live in [scripts/](scripts/) (not imported by the app itself):[m
 [m
[31m-## Recommended production state[m
[32m+[m[32m| Script | Purpose |[m
[32m+[m[32m|---|---|[m
[32m+[m[32m| `scripts/build_rag.py` | (Re)build the FAISS + BM25 vector store from `rag_docs/` |[m
[32m+[m[32m| `scripts/mock_telemetry.py` | Seed Snowflake with simulated fleet telemetry |[m
[32m+[m[32m| `scripts/check_agents.py` | Run each workflow node in isolation as a smoke test |[m
[32m+[m[32m| `scripts/run_all_tests.py` | Run all 6 scenarios in `data/test_cases.json` through the full workflow |[m
[32m+[m[32m| `scripts/test_case1.py`, `scripts/test_case2.py` | Interactive single-scenario demo runs (prompts for human approval on interrupt) |[m
 [m
[31m-Use a shared LangGraph state such as:[m
[31m-    vehicle_id[m
[31m-    user_request[m
[31m-    telemetry_result[m
[31m-    history_result[m
[31m-    rag_evidence[m
[31m-    ml_prediction[m
[31m-    diagnosis[m
[31m-    risk_decision[m
[31m-    human_decision[m
[31m-    service_plan[m
[31m-    final_report[m
[31m-    audit_log[m
[32m+[m[32mLangSmith tracing setup is documented in [docs/LANGSMITH_GUIDE.md](docs/LANGSMITH_GUIDE.md).[m
[32m+[m
[32m+[m[32m## Repo layout[m
[32m+[m
[32m+[m[32m```[m
[32m+[m[32mcapstone/[m
[32m+[m[32m├── src/            core application modules (Streamlit app + LangGraph workflow)[m
[32m+[m[32m├── scripts/        standalone dev/CLI utilities[m
[32m+[m[32m├── tests/          automated tests[m
[32m+[m[32m├── docs/           setup guides[m
[32m+[m[32m├── data/           sample telemetry + test scenarios[m
[32m+[m[32m├── rag_docs/       synthetic service-manual excerpts (RAG source documents)[m
[32m+[m[32m├── models/         trained ML artifact[m
[32m+[m[32m├── vectorstore/    built FAISS + BM25 indexes[m
[32m+[m[32m└── logs/           audit logs written at runtime (gitignored)[m
[32m+[m[32m```[m
[1mdiff --git a/requirements.txt b/requirements.txt[m
[1mindex cbecfe9..23a26f5 100644[m
[1m--- a/requirements.txt[m
[1m+++ b/requirements.txt[m
[36m@@ -13,3 +13,4 @@[m [mstreamlit[m
 snowflake-connector-python[m
 cryptography[m
 tenacity[m
[32m+[m[32mlangsmith[m
[1mdiff --git a/scripts/build_rag.py b/scripts/build_rag.py[m
[1mindex e455478..2db4f2c 100644[m
[1m--- a/scripts/build_rag.py[m
[1m+++ b/scripts/build_rag.py[m
[36m@@ -1,3 +1,8 @@[m
[32m+[m[32mimport os[m
[32m+[m[32mimport sys[m
[32m+[m
[32m+[m[32msys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))[m
[32m+[m
 from rag import build_vectorstore[m
 [m
 [m
[1mdiff --git a/scripts/check_agents.py b/scripts/check_agents.py[m
[1mindex ef52617..18a0233 100644[m
[1m--- a/scripts/check_agents.py[m
[1m+++ b/scripts/check_agents.py[m
[36m@@ -1,6 +1,6 @@[m
 """Quick agent-by-agent diagnostic — runs each workflow node in isolation."""[m
 import sys, os[m
[31m-sys.path.insert(0, os.path.dirname(__file__))[m
[32m+[m[32msys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))[m
 [m
 from dotenv import load_dotenv[m
 load_dotenv()[m
[1mdiff --git a/scripts/mock_telemetry.py b/scripts/mock_telemetry.py[m
[1mindex 6e11916..7ff7b66 100644[m
[1m--- a/scripts/mock_telemetry.py[m
[1m+++ b/scripts/mock_telemetry.py[m
[36m@@ -1,6 +1,6 @@[m
 """Mock telemetry data generator — simulates a fleet of vehicles sending data to Snowflake."""[m
 import sys, os, time, random[m
[31m-sys.path.insert(0, os.path.dirname(__file__))[m
[32m+[m[32msys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))[m
 [m
 from dotenv import load_dotenv[m
 load_dotenv()[m
[1mdiff --git a/scripts/run_all_tests.py b/scripts/run_all_tests.py[m
[1mindex f530f0b..9cb6d5e 100644[m
[1m--- a/scripts/run_all_tests.py[m
[1m+++ b/scripts/run_all_tests.py[m
[36m@@ -1,6 +1,6 @@[m
 """Run all 6 test cases through the workflow and show diverse risk results."""[m
 import sys, os, json[m
[31m-sys.path.insert(0, os.path.dirname(__file__))[m
[32m+[m[32msys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))[m
 [m
 from dotenv import load_dotenv[m
 load_dotenv()[m
[1mdiff --git a/scripts/test_case1.py b/scripts/test_case1.py[m
[1mindex ee21d0a..5542a62 100644[m
[1m--- a/scripts/test_case1.py[m
[1m+++ b/scripts/test_case1.py[m
[36m@@ -1,3 +1,8 @@[m
[32m+[m[32mimport os[m
[32m+[m[32mimport sys[m
[32m+[m
[32m+[m[32msys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))[m
[32m+[m
 from workflow import build_workflow[m
 from langgraph.types import Command[m
 def main():[m
[1mdiff --git a/scripts/test_case2.py b/scripts/test_case2.py[m
[1mindex 136b761..3f7ecfd 100644[m
[1m--- a/scripts/test_case2.py[m
[1m+++ b/scripts/test_case2.py[m
[36m@@ -1,3 +1,8 @@[m
[32m+[m[32mimport os[m
[32m+[m[32mimport sys[m
[32m+[m
[32m+[m[32msys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))[m
[32m+[m
 from workflow import build_workflow[m
 def main():[m
     app = build_workflow()[m
[1mdiff --git a/src/app.py b/src/app.py[m
[1mindex 8f76ce2..1f9bf0f 100644[m
[1m--- a/src/app.py[m
[1m+++ b/src/app.py[m
[36m@@ -476,6 +476,30 @@[m [mdef render_sidebar():[m
 [m
     st.sidebar.divider()[m
 [m
[32m+[m[32m    # Secrets Status[m
[32m+[m[32m    st.sidebar.subheader("🔐 Secrets Status")[m
[32m+[m[32m    try:[m
[32m+[m[32m        import streamlit as st_secrets[m
[32m+[m[32m        secrets_available = bool(st_secrets.secrets)[m
[32m+[m[32m        if secrets_available:[m
[32m+[m[32m            st.sidebar.success("✓ Secrets loaded from secrets.toml")[m
[32m+[m[32m            with st.sidebar.expander("View loaded secrets"):[m
[32m+[m[32m                # Show redacted secrets (last 4 chars only)[m
[32m+[m[32m                redacted = {}[m
[32m+[m[32m                for key in st_secrets.secrets:[m
[32m+[m[32m                    val = st_secrets.secrets[key][m
[32m+[m[32m                    if isinstance(val, str) and len(val) > 4:[m
[32m+[m[32m                        redacted[key] = "***" + val[-4:][m
[32m+[m[32m                    else:[m
[32m+[m[32m                        redacted[key] = "***"[m
[32m+[m[32m                st.json(redacted)[m
[32m+[m[32m        else:[m
[32m+[m[32m            st.sidebar.info("ℹ Using .env fallback")[m
[32m+[m[32m    except Exception:[m
[32m+[m[32m        st.sidebar.info("ℹ Using .env fallback")[m
[32m+[m
[32m+[m[32m    st.sidebar.divider()[m
[32m+[m
     # LangSmith Tracing Status[m
     st.sidebar.subheader("🔍 LangSmith Tracing")[m
     if LANGSMITH_ENABLED:[m
[1mdiff --git a/src/snowflake_utils.py b/src/snowflake_utils.py[m
[1mindex f6c7088..610b149 100644[m
[1m--- a/src/snowflake_utils.py[m
[1m+++ b/src/snowflake_utils.py[m
[36m@@ -13,12 +13,21 @@[m [mSNOWFLAKE_SCHEMA = "PREDICTIVE_MAINTENANCE"[m
 [m
 [m
 def _get_secret(key, default=""):[m
[31m-    """Read from Streamlit secrets (cloud) first, then env vars (local)."""[m
[32m+[m[32m    """Read from Streamlit secrets first, then .env env vars, then default.[m
[32m+[m
[32m+[m[32m    Priority order:[m
[32m+[m[32m    1. Streamlit secrets.toml (local & cloud)[m
[32m+[m[32m    2. Environment variables (.env)[m
[32m+[m[32m    3. Default value[m
[32m+[m[32m    """[m
     try:[m
         import streamlit as st[m
[31m-        if hasattr(st, "secrets") and key in st.secrets:[m
[31m-            return st.secrets[key][m
[31m-    except Exception:[m
[32m+[m[32m        if hasattr(st, "secrets"):[m
[32m+[m[32m            try:[m
[32m+[m[32m                return st.secrets[key][m
[32m+[m[32m            except (KeyError, AttributeError):[m
[32m+[m[32m                pass[m
[32m+[m[32m    except ImportError:[m
         pass[m
     return os.getenv(key, default)[m
 [m
[1mdiff --git a/src/workflow.py b/src/workflow.py[m
[1mindex 4f3db88..f5f2b6d 100644[m
[1m--- a/src/workflow.py[m
[1m+++ b/src/workflow.py[m
[36m@@ -18,12 +18,8 @@[m [mfrom langsmith import traceable[m
 [m
 # Set up LangSmith tracing via LangChain env vars (automatically used by LangChain)[m
 if LANGSMITH_ENABLED:[m
[31m-    print(f"✓ LangSmith tracing enabled for project: {LANGSMITH_PROJECT}")[m
[32m+[m[32m    print(f"LangSmith tracing enabled for project: {LANGSMITH_PROJECT}")[m
 [m
[31m-try:[m
[31m-    import boto3[m
[31m-except ImportError:  # pragma: no cover[m
[31m-    boto3 = None[m
 from langgraph.graph import ([m
     StateGraph,[m
     START,[m
[36m@@ -656,51 +652,6 @@[m [mdef service_plan(state: MaintenanceState):[m
     add_audit(state,"service_plan","Service plan generated")[m
     return state[m
 [m
[31m-def save_final_report_to_s3(state: MaintenanceState):[m
[31m-    """Upload the final report text to S3 using values from .env."""[m
[31m-    bucket = os.getenv("S3_BUCKET_NAME")[m
[31m-    if not bucket:[m
[31m-        return None[m
[31m-[m
[31m-    if boto3 is None:[m
[31m-        raise ImportError([m
[31m-            "boto3 is required for S3 uploads. Install it with: pip install boto3"[m
[31m-        )[m
[31m-[m
[31m-    report_text = state.get("final_report", "")[m
[31m-    if not isinstance(report_text, str):[m
[31m-        report_text = json.dumps(report_text, indent=2)[m
[31m-[m
[31m-    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")[m
[31m-    vehicle_id = state.get("vehicle_id", "unknown_vehicle")[m
[31m-    key = f"final-reports/{vehicle_id}/{timestamp}_report.md"[m
[31m-[m
[31m-    region = os.getenv("AWS_DEFAULT_R