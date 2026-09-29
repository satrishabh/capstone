# Hooks and Guardrails Guide

## Overview

The workflow includes a comprehensive pre-hook/post-hook and guardrails system to:
- ✓ **Validate inputs** before nodes execute
- ✓ **Validate outputs** after nodes complete
- ✓ **Track execution** metadata (timing, status)
- ✓ **Handle errors** gracefully
- ✓ **Ensure data quality** throughout the pipeline

## Architecture

```
Input State
    ↓
[PRE-HOOK] InputGuardrail.validate()
    ↓
[NODE EXECUTION]
    ↓
[POST-HOOK] OutputGuardrail.validate()
    ↓
Output State + Metadata
```

## Pre-Hooks: Input Validation

Pre-hooks run **before** a node executes and validate the incoming state.

### What Gets Validated

#### 1. **Vehicle ID**
```python
# Valid
"VH-1001", "vehicle_001", "CAR123"

# Invalid
"", "VH", "x" * 100
```

- Must be 3-50 characters
- Non-empty string

#### 2. **Telemetry Data** (for telemetry, ml, diagnostic nodes)
```python
telemetry = {
    "engine_rpm": 2500,              # 0-10000
    "coolant_temperature": 92,       # -40 to 150°C
    "oil_pressure": 3.2,             # >= 0 bar
    "battery_voltage": 13.5,         # 6-16V
    "vibration": 2.5,                # >= 0
    "vehicle_speed": 60,             # >= 0
    "timestamp": "2026-09-29T10:00Z"
}
```

**Checks:**
- ✓ All required fields present
- ✓ No negative values (except temperature)
- ✓ Values within realistic ranges
- ✓ Correct data types

#### 3. **User Request** (for diagnostic, risk nodes)
```python
# Valid
"Generate predictive maintenance report"
"Analyze vehicle condition"

# Invalid
"", "hi", "x" * 1000
```

- Must be 5-500 characters

#### 4. **History Data**
```python
history = {
    "maintenance": ["Oil change - 2026-01", "Filter replacement - 2026-03"],
    "previous_faults": ["Check engine light", "Transmission warning"]
}
```

- Must be a dictionary
- Can be empty lists

### Pre-Hook Execution Flow

```python
logger.info(f"[PRE-HOOK] telemetry: Validating inputs")

# Validation runs
is_valid, msg = guardrail.validate(state, "telemetry")

if is_valid:
    logger.info(f"[PRE-HOOK] telemetry: ✓ All validations passed")
    state["execution_metadata"]["telemetry"] = {
        "started_at": "2026-09-29T10:00:00+05:30",
        "status": "running"
    }
else:
    logger.error(f"[PRE-HOOK] telemetry: ❌ Validation failed: {msg}")
    raise ValueError(f"Pre-hook validation failed: {msg}")
```

### Logs You'll See

**Success:**
```
INFO:workflow:[PRE-HOOK] telemetry: Validating inputs
INFO:workflow:[PRE-HOOK] telemetry: ✓ All validations passed
```

**Failure:**
```
INFO:workflow:[PRE-HOOK] telemetry: Validating inputs
ERROR:workflow:[PRE-HOOK] telemetry: ❌ Validation failed: Telemetry coolant_temperature out of bounds: 200°C
```

## Post-Hooks: Output Validation

Post-hooks run **after** a node executes and validate the output state.

### What Gets Validated

#### 1. **Telemetry Output**
```python
telemetry = {
    "raw": {...},
    "abnormalities": [
        {
            "parameter": "coolant_temperature",
            "severity": "HIGH",
            "value": 105,
            "reason": "Temperature above 100°C"
        }
    ]
}
```

**Checks:**
- ✓ Must be dict
- ✓ Must have `abnormalities` list

#### 2. **Diagnosis Output**
```python
diagnosis = {
    "assessment": "Possible thermostat failure...",
    "confidence": 0.85,
    "components": ["thermostat", "coolant_pump"],
    "human_feedback": None
}
```

**Checks:**
- ✓ Must be dict
- ✓ Must have `assessment` text

#### 3. **Risk Output**
```python
risk_decision = {
    "risk_score": 75,           # 0-100
    "risk_level": "HIGH",       # CRITICAL, HIGH, MEDIUM, LOW
    "human_approval_required": True,
    "reason": "High failure probability"
}
```

**Checks:**
- ✓ Must be dict
- ✓ Risk score 0-100
- ✓ Risk level in [CRITICAL, HIGH, MEDIUM, LOW]
- ✓ All required fields present

### Post-Hook Execution Flow

```python
logger.info(f"[POST-HOOK] telemetry: Validating outputs")

# Validation runs
is_valid, msg = guardrail.validate(state, "telemetry")

# Log warning if invalid (but don't fail)
if not is_valid:
    logger.warning(f"[POST-HOOK] telemetry: ⚠️  Output validation warning: {msg}")

# Record execution metadata
state["execution_metadata"]["telemetry"] = {
    "started_at": "2026-09-29T10:00:00+05:30",
    "completed_at": "2026-09-29T10:00:05+05:30",
    "status": "completed"
}

# Add to audit log
state["audit_log"].append({
    "timestamp": "2026-09-29T10:00:05+05:30",
    "node": "telemetry",
    "message": "Execution completed with 2 output updates",
    "validation_status": "passed"
})
```

### Logs You'll See

**Success:**
```
INFO:workflow:[POST-HOOK] telemetry: Validating outputs
INFO:workflow:[POST-HOOK] telemetry: ✓ Output validated
DEBUG:workflow:[POST-HOOK] telemetry: Execution metadata recorded
```

**Warning (non-fatal):**
```
INFO:workflow:[POST-HOOK] diagnostic: Validating outputs
WARNING:workflow:[POST-HOOK] diagnostic: ⚠️  Output validation warning: Missing assessment in diagnosis
```

## Execution Metadata

After each node completes, metadata is recorded:

```python
state["execution_metadata"] = {
    "telemetry": {
        "started_at": "2026-09-29T10:00:00+05:30",
        "completed_at": "2026-09-29T10:00:05+05:30",
        "status": "completed"
    },
    "diagnostic": {
        "started_at": "2026-09-29T10:00:10+05:30",
        "completed_at": "2026-09-29T10:00:15+05:30",
        "status": "completed"
    }
}
```

### View Execution Timing

You can calculate execution time:

```python
start = parse_iso(meta["telemetry"]["started_at"])
end = parse_iso(meta["telemetry"]["completed_at"])
duration = end - start
print(f"telemetry_agent took {duration.total_seconds():.2f}s")
```

## Audit Log Integration

All hook activities are recorded in the audit log:

```json
{
  "timestamp": "2026-09-29T10:00:05+05:30",
  "node": "telemetry",
  "message": "Execution completed with 2 output updates",
  "validation_status": "passed"
}
```

View in Streamlit: **Analysis Results → Audit Log**

## Error Handling

If pre-hook validation fails:
```
ValueError: Pre-hook validation failed for telemetry: 
  Telemetry coolant_temperature out of bounds: 200°C
```

The workflow stops and logs the error.

If post-hook finds issues:
```
⚠️  Output validation warning: Missing assessment in diagnosis
```

The workflow continues (warnings don't stop execution).

## LangSmith Integration

All hooks are automatically traced by LangSmith:

```
Trace: vehicle_analysis
├── pre_hook_telemetry
│   ├── Input validation
│   ├── State preparation
│   └── Metadata setup
├── telemetry_agent (node execution)
│   ├── Analyze telemetry
│   └── Detect abnormalities
└── post_hook_telemetry
    ├── Output validation
    ├── Metadata recording
    └── Audit log update
```

In LangSmith Dashboard, you can:
- See each hook execution
- View validation results
- Track timing per hook
- Debug validation failures

## Configuration

Hooks are applied automatically to all nodes. No configuration needed.

To customize validation, edit [src/hooks_and_guardrails.py](../src/hooks_and_guardrails.py):

```python
class InputGuardrail(WorkflowGuardrail):
    def validate_telemetry(self, telemetry):
        # Add custom validation here
        if telemetry["engine_rpm"] > 10000:
            return False, "Engine RPM too high"
        return True, ""
```

## Troubleshooting

### Pre-hook validation failing

**Check:**
- All required fields present in state
- Data types correct (string, float, etc.)
- Values within expected ranges

**Example:**
```python
# ❌ Wrong
state = {"vehicle_id": 123}  # Should be string

# ✓ Right
state = {"vehicle_id": "VH-1001"}
```

### Post-hook warnings

**Not critical** — workflow continues. Check the warning message and investigate the node's output.

```
⚠️  Output validation warning: Missing assessment in diagnosis
    → Check if diagnostic_agent is producing assessment
    → Check if the LLM is returning valid output
```

### Slow execution

Check `execution_metadata` timing:

```python
meta = state["execution_metadata"]["telemetry"]
start = datetime.fromisoformat(meta["started_at"])
end = datetime.fromisoformat(meta["completed_at"])
print(f"Duration: {(end - start).total_seconds():.2f}s")
```

If slower than expected:
- Check network/API latency
- Check LLM provider availability
- Review logs for errors

## Best Practices

1. **Review audit logs regularly** to catch validation issues early
2. **Monitor LangSmith traces** to see hook execution timing
3. **Set custom validation rules** for your specific domain
4. **Test with edge cases** (empty input, extreme values, etc.)
5. **Log all errors** for debugging and improvement

## See Also

- [LANGSMITH_GUIDE.md](LANGSMITH_GUIDE.md) — Viewing traces with hooks
- [FALLBACK_LOGGING_GUIDE.md](FALLBACK_LOGGING_GUIDE.md) — LLM provider logs
- [src/hooks_and_guardrails.py](../src/hooks_and_guardrails.py) — Implementation
- [src/workflow.py](../src/workflow.py) — Workflow integration
