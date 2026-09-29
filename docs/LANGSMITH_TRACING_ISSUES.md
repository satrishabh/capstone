# LangSmith Tracing Issues & Solutions

## ✓ Current Status

Your LangSmith configuration is **properly set up**:
- ✓ `LANGSMITH_TRACING=true` 
- ✓ `LANGSMITH_API_KEY` configured
- ✓ `LANGSMITH_PROJECT=Demo` configured
- ✓ `LANGSMITH_ENDPOINT=https://apac.api.smith.langchain.com`
- ✓ Config module reading values correctly
- ✓ LangSmith SDK available
- ✓ Workflow tracing enabled
- ✓ Hooks and guardrails system working

## Issue: SSL Certificate Verification

### What's Happening

When connecting to LangSmith API, you may see:
```
SSLError(SSLCertificateVerificationError)
certificate verify failed: unable to get local issuer certificate
```

This is a **network/environment issue**, not a configuration issue. The system can't verify the SSL certificate for `apac.api.smith.langchain.com`.

### Solution 1: Update Certificate Bundle (Recommended)

Python uses a certificate bundle from `certifi`. Update it:

```bash
pip install --upgrade certifi
```

Then tell Python to use it:

```bash
# For Linux/Mac
export REQUESTS_CA_BUNDLE=$(python -c "import certifi; print(certifi.where())")
export SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")

# For Windows PowerShell
$python_path = python -c "import certifi; print(certifi.where())"
$env:REQUESTS_CA_BUNDLE = $python_path
$env:SSL_CERT_FILE = $python_path
```

### Solution 2: Disable SSL Verification (Quick Fix, Less Secure)

⚠️ **Only for local development/testing**

```python
# In src/config.py or your script
import os
os.environ['LANGSMITH_SSL_VERIFY'] = 'false'
```

Or set before running:
```bash
LANGSMITH_SSL_VERIFY=false streamlit run src/app.py
```

### Solution 3: Use US Endpoint Instead

If you're having persistent SSL issues with the APAC endpoint, try the US endpoint:

In `.env`:
```env
# Old
LANGSMITH_ENDPOINT=https://apac.api.smith.langchain.com

# New
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

## Tracing in Streamlit

Even with SSL issues, **tracing still works** because:
- The workflow has `@traceable` decorators on all nodes
- LangSmith SDK buffers traces locally before sending
- Traces are queued and sent when connection is available

### To Verify Traces Are Being Captured

1. **Run the app:**
```bash
streamlit run src/app.py
```

2. **Go to "LangSmith Traces" page** in sidebar

3. **Run an analysis** with test data

4. **Check dashboard:** https://smith.langchain.com/projects

### What You Should See

In the traces viewer:
```
Trace: vehicle_analysis_20260929_143022
├── supervisor_agent (11ms)
├── telemetry_agent (245ms)
│   ├── input_validation (2ms)
│   ├── analyze_telemetry (240ms)
│   └── output_validation (3ms)
├── history_agent (5ms)
├── rag_agent (180ms)
├── ml_agent (95ms)
├── diagnostic_agent (350ms)
├── risk_agent (10ms)
├── human_approval_agent (5000ms) [manual wait]
└── report_agent (50ms)
```

## Pre-Hooks and Post-Hooks

All nodes now have automatic pre/post hooks:

### Pre-Hook (Before Node Execution)
```
[PRE-HOOK] telemetry: Validating inputs
[PRE-HOOK] telemetry: ✓ All validations passed
```

**Checks:**
- Input data format correct
- All required fields present
- Values within acceptable ranges

### Post-Hook (After Node Execution)
```
[POST-HOOK] telemetry: Validating outputs
[POST-HOOK] telemetry: ✓ Output validated
```

**Checks:**
- Output structure valid
- Required fields present
- Data quality acceptable

### In LangSmith Traces

Each node shows:
```
telemetry_agent
├── pre_hook
│   ├── validate_vehicle_id ✓
│   ├── validate_telemetry ✓
│   └── prepare_state
├── node_execution (actual work)
│   ├── analyze_telemetry
│   └── detect_abnormalities
└── post_hook
    ├── validate_output ✓
    ├── record_metadata
    └── update_audit_log
```

## Guardrails in Action

### Input Validation (Pre-Hook)

Validates before execution:
```python
telemetry = {
    "engine_rpm": 2500,              # ✓ Between 0-10000
    "coolant_temperature": 92,       # ✓ Between -40 to 150°C
    "oil_pressure": 3.2,             # ✓ Positive
    "battery_voltage": 13.5,         # ✓ Between 6-16V
}
```

If invalid:
```
ERROR: Pre-hook validation failed for telemetry: 
  Telemetry coolant_temperature out of bounds: 200°C
```

### Output Validation (Post-Hook)

Validates after execution:
```python
risk_decision = {
    "risk_score": 75,           # ✓ 0-100
    "risk_level": "HIGH",       # ✓ Valid level
    "human_approval_required": True  # ✓ Present
}
```

If missing/invalid:
```
WARNING: Output validation warning: 
  Missing assessment in diagnosis
```

## Logs to Check

### Terminal/Console Logs

```bash
# Environment setup
[LangSmith] ✓ LangSmith SDK available
[LangSmith] ✓ Tracing enabled for project: Demo

# Pre/post hooks
[PRE-HOOK] telemetry: Validating inputs
[PRE-HOOK] telemetry: ✓ All validations passed
[POST-HOOK] telemetry: Validating outputs
[POST-HOOK] telemetry: ✓ Output validated
```

### Streamlit Logs

Check the terminal where you ran `streamlit run src/app.py`:
- Look for `[PRE-HOOK]` and `[POST-HOOK]` messages
- Look for validation failures
- Look for timing information

### LangSmith Dashboard

1. Go to https://smith.langchain.com/projects
2. Select project: **"Demo"**
3. Click on a recent trace
4. Expand nodes to see:
   - Input/output data
   - Execution time
   - Pre/post hook results
   - Validation status

## Workflow Execution Timeline

```
START
  ↓
[PRE] telemetry input validation
  ↓
telemetry_agent (analyze sensor data)
  ↓
[POST] telemetry output validation ✓
  ↓
history_agent (in parallel)
  ↓
ml_agent (predict failure)
  ↓
[PRE] diagnostic input validation
  ↓
diagnostic_agent (LLM analysis)
  ↓
[POST] diagnostic output validation ✓
  ↓
risk_agent (calculate score)
  ↓
[IF risk_level == CRITICAL]
  ├─→ human_approval_agent (wait for user)
  │   └─→ [IF approved]
  │       └─→ service_plan_agent
  │
  └─→ report_agent
  ↓
END
```

## Troubleshooting Checklist

- [ ] Updated `certifi`: `pip install --upgrade certifi`
- [ ] Environment variables set in `.env`
- [ ] Restarted Streamlit app after changing `.env`
- [ ] Ran debug script: `python scripts/debug_langsmith.py`
- [ ] Checked for SSL errors in logs
- [ ] Verified LangSmith account has valid API key
- [ ] Checked project "Demo" exists in LangSmith dashboard
- [ ] Ran an analysis and waited 30+ seconds
- [ ] Checked LangSmith dashboard for recent traces

## Debug Commands

Run the debug script to verify everything:
```bash
python scripts/debug_langsmith.py
```

Should show:
```
✓ LangSmith Client imported successfully
✓ LangSmith Client initialized
✓ Workflow module imported
  - LANGSMITH_AVAILABLE: True
✓ Hooks and guardrails imported successfully
✓ Test state validation passed

✓ LANGSMITH IS PROPERLY CONFIGURED
```

## Example: Full Trace with Hooks

```
Execution started: 2026-09-29T14:30:00+05:30

telemetry_agent
├─ [PRE-HOOK] Validating inputs
│  ├─ vehicle_id: "VH-1001" ✓
│  ├─ telemetry.engine_rpm: 2500 ✓
│  ├─ telemetry.coolant_temp: 92°C ✓
│  └─ Status: Ready
├─ Node execution
│  ├─ Analyzing telemetry data
│  ├─ Detected abnormalities:
│  │  ├─ coolant_temperature: HIGH (92°C)
│  │  └─ vibration: MEDIUM (2.8)
│  └─ Duration: 245ms
└─ [POST-HOOK] Validating outputs
   ├─ abnormalities: list ✓
   ├─ raw_data: dict ✓
   └─ Status: Valid

Audit log entry:
  timestamp: 2026-09-29T14:30:00.245+05:30
  node: telemetry_agent
  message: Execution completed with 2 output updates
  validation_status: passed
```

## Next Steps

1. **Fix SSL certificate:** Run `pip install --upgrade certifi`
2. **Test the setup:** Run `python scripts/debug_langsmith.py`
3. **Start Streamlit:** `streamlit run src/app.py`
4. **Run analysis:** Go to "LangSmith Traces" page
5. **Check dashboard:** https://smith.langchain.com/projects

## See Also

- [HOOKS_AND_GUARDRAILS_GUIDE.md](HOOKS_AND_GUARDRAILS_GUIDE.md)
- [LANGSMITH_GUIDE.md](LANGSMITH_GUIDE.md)
- [FALLBACK_LOGGING_GUIDE.md](FALLBACK_LOGGING_GUIDE.md)
