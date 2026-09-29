"""Run all 6 test cases through the workflow and show diverse risk results."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
from workflow import build_workflow

DATA_DIR = Path(__file__).resolve().parent / ".." / "data"
TEST_CASES_PATH = DATA_DIR / "test_cases.json"

with open(TEST_CASES_PATH, encoding="utf-8") as f:
    test_cases = json.load(f)

app = build_workflow(for_web=True)

print("\n" + "=" * 70)
print("RUNNING ALL 6 TEST CASES")
print("=" * 70)

results = []
for tc in test_cases:
    tc_id = tc["id"]
    vehicle_id = tc["vehicle_id"]
    description = tc["description"]
    expected_risk = tc["expected_risk"]
    latest = tc["telemetry"][-1]

    print(f"\n{'-' * 60}")
    print(f"TEST CASE: {tc_id} -- {description}")
    print(f"Vehicle: {vehicle_id} | Expected risk: {expected_risk}")
    print(f"Telemetry: oil={latest['oil_pressure']}, coolant={latest['coolant_temperature']}, vibration={latest['vibration']}, battery={latest['battery_voltage']}")
    print(f"{'-' * 60}")

    initial_state = {
        "vehicle_id": vehicle_id,
        "user_request": f"Predictive maintenance - {description}",
        "telemetry": latest,
        "history": tc["history"],
        "audit_log": [],
    }
    config = {"configurable": {"thread_id": f"{vehicle_id}-batch-{tc_id}"}}

    try:
        result = app.invoke(initial_state, config)
        # Check if interrupted (CRITICAL cases need human approval)
        snapshot = app.get_state(config)
        if snapshot.next:
            # Auto-approve for batch testing
            from langgraph.types import Command
            resume_payload = {"decision": "APPROVE", "feedback": "Auto-approved for batch test"}
            result = app.invoke(Command(resume=resume_payload), config)

        risk = result.get("risk_decision", {})
        ml_prob = result.get("ml_failure_probability", 0)
        risk_score = risk.get("risk_score", "?")
        risk_level = risk.get("risk_level", "?")

        results.append({
            "tc": tc_id,
            "vehicle": vehicle_id,
            "expected": expected_risk,
            "actual": risk_level,
            "score": risk_score,
            "ml_prob": f"{ml_prob:.1%}",
            "match": "OK" if expected_risk == risk_level else "MISMATCH",
        })
        print(f"\n  -> Risk: {risk_level} (score={risk_score}), ML={ml_prob:.1%}")

    except Exception as e:
        results.append({
            "tc": tc_id, "vehicle": vehicle_id,
            "expected": expected_risk, "actual": "ERROR",
            "score": "-", "ml_prob": "-", "match": "ERROR",
        })
        print(f"\n  -> ERROR: {e}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"{'TC':<6} {'Vehicle':<10} {'Expected':<10} {'Actual':<10} {'Score':<6} {'ML Prob':<8} {'Match'}")
print("-" * 70)
for r in results:
    print(f"{r['tc']:<6} {r['vehicle']:<10} {r['expected']:<10} {r['actual']:<10} {r['score']:<6} {r['ml_prob']:<8} {r['match']}")
