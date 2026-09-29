# Vehicle Predictive Maintenance — Agentic AI Capstone

A LangGraph-orchestrated agent that turns vehicle telemetry into a predictive-maintenance
report: it validates sensor readings, scores failure risk with an ML model, grounds its
diagnosis in service-manual excerpts via RAG, and pauses for human approval on critical
cases before generating a final report.

> All RAG documents and test data are synthetic. They are not OEM documentation and must
> not be used for real vehicle repair decisions. The bundled ML model is a small, synthetic
> demo model — not valid for real vehicles.

## Architecture

```
User/API request
  -> Supervisor
  -> Telemetry validation + History retrieval + RAG retrieval (FAISS + BM25)
  -> ML failure-probability scoring
  -> Diagnostic agent (telemetry + history + RAG + ML probability)
  -> Risk engine
  -> Human approval interrupt (if risk is CRITICAL)
  -> Service plan / re-analysis
  -> Final report -> saved to a Snowflake internal stage + report metadata table
```

The workflow graph is defined in [src/workflow.py](src/workflow.py); the state shape is in
[src/state_schema.py](src/state_schema.py). See [langgraph_workflow.mmd](langgraph_workflow.mmd)
for the diagram source.

## Stack

- **Orchestration**: LangGraph + LangChain
- **LLM**: Google Gemini (primary, [src/llm_provider.py](src/llm_provider.py)) with
  Snowflake Cortex as fallback / embeddings provider ([src/cortex_llm.py](src/cortex_llm.py))
- **RAG**: FAISS + BM25 hybrid retrieval over [rag_docs/](rag_docs/) ([src/rag.py](src/rag.py))
- **ML**: scikit-learn failure-probability model ([src/ml_model.py](src/ml_model.py),
  trained by [src/train_failure_model.py](src/train_failure_model.py))
- **Storage**: Snowflake (telemetry, history, reports, audit logs — [src/snowflake_utils.py](src/snowflake_utils.py))
- **UI**: Streamlit ([src/app.py](src/app.py))
- **Tracing**: LangSmith (optional, enabled via `.env`)

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in your Gemini / Snowflake / LangSmith credentials.
3. Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and fill in the same
   values if running via Streamlit Cloud or `st.secrets` — see [docs/STREAMLIT_SECRETS_GUIDE.md](docs/STREAMLIT_SECRETS_GUIDE.md).
4. Build the vector store: `python scripts/build_rag.py`
5. (Optional) Seed Snowflake with mock fleet telemetry: `python scripts/mock_telemetry.py`
6. Run the app: `streamlit run src/app.py`

## Dev / diagnostic scripts

All one-off CLI utilities live in [scripts/](scripts/) (not imported by the app itself):

| Script | Purpose |
|---|---|
| `scripts/build_rag.py` | (Re)build the FAISS + BM25 vector store from `rag_docs/` |
| `scripts/mock_telemetry.py` | Seed Snowflake with simulated fleet telemetry |
| `scripts/check_agents.py` | Run each workflow node in isolation as a smoke test |
| `scripts/run_all_tests.py` | Run all 6 scenarios in `data/test_cases.json` through the full workflow |
| `scripts/test_case1.py`, `scripts/test_case2.py` | Interactive single-scenario demo runs (prompts for human approval on interrupt) |

LangSmith tracing setup is documented in [docs/LANGSMITH_GUIDE.md](docs/LANGSMITH_GUIDE.md).

## Repo layout

```
capstone/
├── src/            core application modules (Streamlit app + LangGraph workflow)
├── scripts/        standalone dev/CLI utilities
├── tests/          automated tests
├── docs/           setup guides
├── data/           sample telemetry + test scenarios
├── rag_docs/       synthetic service-manual excerpts (RAG source documents)
├── models/         trained ML artifact
├── vectorstore/    built FAISS + BM25 indexes
└── logs/           audit logs written at runtime (gitignored)
```
