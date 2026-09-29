#!/usr/bin/env python3
"""
Debug script to verify LangSmith tracing is working correctly.
Tests configuration, environment setup, and actual trace creation.
"""
import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

print("\n" + "=" * 70)
print("LANGSMITH TRACING DEBUG")
print("=" * 70)

# 1. Check environment variables
print("\n[1] Checking Environment Variables")
print("-" * 70)

checks = {
    "LANGSMITH_TRACING": os.getenv("LANGSMITH_TRACING"),
    "LANGSMITH_API_KEY": "***" + os.getenv("LANGSMITH_API_KEY", "")[-4:] if os.getenv("LANGSMITH_API_KEY") else "NOT SET",
    "LANGSMITH_PROJECT": os.getenv("LANGSMITH_PROJECT"),
    "LANGSMITH_ENDPOINT": os.getenv("LANGSMITH_ENDPOINT"),
    "LANGCHAIN_TRACING_V2": os.getenv("LANGCHAIN_TRACING_V2"),
    "LANGCHAIN_API_KEY": "***" + os.getenv("LANGCHAIN_API_KEY", "")[-4:] if os.getenv("LANGCHAIN_API_KEY") else "NOT SET",
    "LANGCHAIN_PROJECT": os.getenv("LANGCHAIN_PROJECT"),
}

for key, value in checks.items():
    status = "✓" if value and value != "NOT SET" else "✗"
    print(f"{status} {key:30} = {value}")

# 2. Check config module
print("\n[2] Checking Config Module")
print("-" * 70)

try:
    from config import (
        LANGSMITH_ENABLED,
        LANGSMITH_PROJECT,
        LANGSMITH_API_KEY,
        LANGSMITH_ENDPOINT,
        print_config_status
    )

    print(f"✓ Config imported successfully")
    print(f"  - LANGSMITH_ENABLED: {LANGSMITH_ENABLED}")
    print(f"  - LANGSMITH_PROJECT: {LANGSMITH_PROJECT}")
    print(f"  - LANGSMITH_ENDPOINT: {LANGSMITH_ENDPOINT}")
    print(f"  - API Key set: {bool(LANGSMITH_API_KEY)}")

    print("\nFull config status:")
    print_config_status()

except Exception as e:
    print(f"✗ Config import failed: {e}")
    sys.exit(1)

# 3. Check LangSmith SDK
print("\n[3] Checking LangSmith SDK")
print("-" * 70)

try:
    from langsmith import Client
    print(f"✓ LangSmith Client imported successfully")

    if LANGSMITH_ENABLED:
        try:
            client = Client(
                api_key=LANGSMITH_API_KEY,
                api_url=LANGSMITH_ENDPOINT
            )
            print(f"✓ LangSmith Client initialized")

            # Try to get project
            try:
                project = client.get_project(project_name=LANGSMITH_PROJECT)
                print(f"✓ Successfully connected to project: {LANGSMITH_PROJECT}")
                print(f"  - Project ID: {project.id}")
                print(f"  - Project Name: {project.name}")
            except Exception as e:
                print(f"⚠️  Could not get project '{LANGSMITH_PROJECT}': {e}")

        except Exception as e:
            print(f"✗ LangSmith Client initialization failed: {e}")
    else:
        print(f"⚠️  LANGSMITH not enabled - skipping client test")

except ImportError:
    print(f"✗ LangSmith SDK not installed. Install with: pip install langsmith")
    sys.exit(1)

# 4. Check workflow tracing
print("\n[4] Checking Workflow Tracing")
print("-" * 70)

try:
    from workflow import LANGSMITH_AVAILABLE
    print(f"✓ Workflow module imported")
    print(f"  - LANGSMITH_AVAILABLE: {LANGSMITH_AVAILABLE}")

    if LANGSMITH_AVAILABLE:
        print(f"✓ LangSmith decorator available in workflow")
    else:
        print(f"⚠️  LangSmith decorator not available (using dummy)")

except Exception as e:
    print(f"✗ Workflow import failed: {e}")

# 5. Check hooks and guardrails
print("\n[5] Checking Hooks and Guardrails")
print("-" * 70)

try:
    from hooks_and_guardrails import (
        InputGuardrail,
        OutputGuardrail,
        pre_hook,
        post_hook
    )
    print(f"✓ Hooks and guardrails imported successfully")
    print(f"  - InputGuardrail: {InputGuardrail.__name__}")
    print(f"  - OutputGuardrail: {OutputGuardrail.__name__}")
    print(f"  - pre_hook: {pre_hook.__name__}")
    print(f"  - post_hook: {post_hook.__name__}")

except Exception as e:
    print(f"✗ Hooks import failed: {e}")

# 6. Test validation
print("\n[6] Testing Input Validation")
print("-" * 70)

try:
    from state_schema import MaintenanceState

    # Create test state
    test_state = {
        "vehicle_id": "VH-1001",
        "user_request": "Test request",
        "telemetry": {
            "timestamp": "2026-09-29T10:00:00",
            "engine_rpm": 2500,
            "coolant_temperature": 92,
            "oil_pressure": 3.2,
            "battery_voltage": 13.5,
            "vibration": 2.5,
            "vehicle_speed": 60,
        },
        "history": {
            "maintenance": [],
            "previous_faults": []
        },
        "audit_log": []
    }

    guardrail = InputGuardrail()
    is_valid, msg = guardrail.validate(test_state, "telemetry")

    if is_valid:
        print(f"✓ Test state validation passed")
    else:
        print(f"✗ Test state validation failed: {msg}")

except Exception as e:
    print(f"✗ Validation test failed: {e}")

# 7. Summary and recommendations
print("\n[7] Summary and Recommendations")
print("=" * 70)

if LANGSMITH_ENABLED and LANGSMITH_API_KEY:
    print("\n✓ LANGSMITH IS PROPERLY CONFIGURED")
    print("\nTo verify traces are being captured:")
    print("  1. Run: streamlit run src/app.py")
    print("  2. Navigate to 'LangSmith Traces' page")
    print("  3. Run an analysis")
    print("  4. Check the traces list for recent runs")
    print(f"\nDashboard: https://smith.langchain.com/projects")
    print(f"Project: {LANGSMITH_PROJECT}")
else:
    print("\n✗ LANGSMITH IS NOT PROPERLY CONFIGURED")
    print("\nTo enable LangSmith tracing:")
    print("  1. Check your .env file has:")
    print("     LANGSMITH_TRACING=true")
    print("     LANGSMITH_API_KEY=lsv2_pt_...")
    print("     LANGSMITH_PROJECT=Demo")
    print("     LANGSMITH_ENDPOINT=https://apac.api.smith.langchain.com")
    print("\n  2. Restart your Streamlit app")
    print("\n  3. Run debug_langsmith.py again to verify")

print("\n" + "=" * 70)
