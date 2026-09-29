# LangSmith Integration Guide

This project now has comprehensive LangSmith tracing integrated to debug, monitor, and analyze your predictive maintenance workflows.

## 🎯 What's Traced

Every agent node is instrumented with `@traceable` decorators:

- ✅ **supervisor_agent** — Workflow initialization
- ✅ **telemetry_agent** — Sensor data analysis
- ✅ **history_agent** — Maintenance history retrieval
- ✅ **rag_agent** — Document retrieval & ranking
- ✅ **ml_agent** — Failure probability prediction
- ✅ **diagnostic_agent** — LLM-powered diagnosis
- ✅ **risk_agent** — Risk scoring & decision
- ✅ **human_approval_agent** — Human-in-the-loop approval
- ✅ **reanalyze_agent** — Feedback incorporation
- ✅ **service_plan_agent** — Service plan generation
- ✅ **report_agent** — Final report compilation

## 🚀 Environment Setup

LangSmith is configured in your `.env` file:

```env
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://apac.api.smith.langchain.com
LANGSMITH_API_KEY=lsv2_pt_your_langsmith_api_key_here
LANGSMITH_PROJECT=Demo
```

## 📊 Viewing Traces

### Option 1: LangSmith Dashboard (Recommended)

1. Open: https://smith.langchain.com/projects
2. Select project: **"Demo"**
3. Run an analysis in the Streamlit app
4. Traces appear in real-time

### Option 2: Streamlit App

In the sidebar, under "🔍 LangSmith Tracing":
- View tracing status (enabled/disabled)
- Click link to go directly to dashboard

### Option 3: LangSmith CLI

```bash
# List recent traces
langsmith trace list --project Demo --limit 10 --api-key $LANGSMITH_API_KEY

# Get specific trace details
langsmith trace get <trace-id> --api-key $LANGSMITH_API_KEY

# Export traces
langsmith trace export ./traces --limit 20 --api-key $LANGSMITH_API_KEY
```

## 🔍 Trace Structure

Each workflow run creates a trace tree:

```
trace_id
├── supervisor_agent
├── telemetry_agent
├── history_agent
├── rag_agent
├── ml_agent
├── diagnostic_agent
├── risk_agent
├── [human_approval_agent - if risk=CRITICAL]
│   └── reanalyze_agent (if rejected)
├── service_plan_agent
└── report_agent
```

## 📈 Key Metrics Captured

Per trace, LangSmith records:

- **Latency** — Total workflow time + per-agent time
- **Tokens** — LLM token usage (input/output)
- **Cost** — Estimated API costs
- **Inputs/Outputs** — Agent inputs and results
- **Errors** — Exceptions and failures
- **Metadata** — Custom tags and attributes

## 💡 Common Use Cases

### Debug a Failed Agent

```bash
# Find failed traces
langsmith trace list --project Demo --error --last-n-minutes 60

# Inspect the trace
langsmith trace get <trace-id>
```

### Analyze Performance

```bash
# Find slow traces (>5 seconds)
langsmith trace list --min-latency 5.0 --project Demo

# With metadata (tokens, costs)
langsmith trace list --include-metadata --project Demo
```

### Export for Analysis

```bash
# Export with full inputs/outputs
langsmith trace export ./traces --full --limit 50

# Combine all traces into one file
cat ./traces/*.jsonl > all_traces.jsonl
```

## 🛠️ Customizing Traces

To add custom metadata or tags to a trace:

```python
from langsmith import traceable, RunTree

@traceable(name="custom_agent", tags=["production", "v1"])
def my_agent(state):
    # Your code here
    return state
```

## 🔗 Useful Links

- Dashboard: https://smith.langchain.com/projects
- API Docs: https://api.smith.langchain.com/docs
- CLI Docs: https://docs.smith.langchain.com/reference/cli
- LangSmith SDK: https://python.langsmith.langchain.com

## 📝 Notes

- Traces are automatically sent to LangSmith when `LANGSMITH_TRACING=true`
- No code changes needed — tracing works out of the box
- API key must be valid for traces to be recorded
- All sensitive data (PII, credentials) should be excluded from traces
