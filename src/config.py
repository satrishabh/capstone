"""
Configuration for Vehicle Predictive Maintenance Capstone.
Supports both Google Gemini API (primary) and Snowflake Cortex AI (fallback).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Google Gemini API Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0"))

# Snowflake Configuration
SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT")
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER")
SNOWFLAKE_PRIVATE_KEY = os.getenv("SNOWFLAKE_PRIVATE_KEY")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "CAPSTONE_DB")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "PREDICTIVE_MAINTENANCE")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
CORTEX_MODEL = os.getenv("CORTEX_MODEL", "llama3.1-8b")

# LLM Provider Settings
LLM_PRIMARY = os.getenv("LLM_PRIMARY", "auto")  # auto, gemini, snowflake
LLM_FALLBACK = os.getenv("LLM_FALLBACK", "auto")  # auto, gemini, snowflake
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# LangSmith Tracing
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "Demo")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

# Legacy LangChain env vars (for backward compatibility)
os.environ["LANGCHAIN_TRACING_V2"] = "true" if LANGSMITH_TRACING else "false"
os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT
if LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
if LANGSMITH_ENDPOINT:
    os.environ["LANGCHAIN_ENDPOINT"] = LANGSMITH_ENDPOINT

LANGSMITH_ENABLED = LANGSMITH_TRACING and bool(LANGSMITH_API_KEY)

# Validate Configuration
def validate_config() -> list[str]:
    """Validate that required configuration is present."""
    issues = []

    gemini_available = bool(GOOGLE_API_KEY)
    snowflake_available = bool(SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER and (SNOWFLAKE_PRIVATE_KEY or SNOWFLAKE_PASSWORD))

    if not gemini_available and not snowflake_available:
        issues.append(
            "No LLM provider configured. "
            "Set GOOGLE_API_KEY (Gemini) or SNOWFLAKE_* (Cortex) in .env"
        )

    if gemini_available:
        if not GEMINI_MODEL:
            issues.append("GEMINI_MODEL not set in .env")

    if snowflake_available:
        if not CORTEX_MODEL:
            issues.append("CORTEX_MODEL not set in .env")

    return issues


def print_config_status():
    """Print current configuration status."""
    print("\n" + "=" * 60)
    print("LLM CONFIGURATION STATUS")
    print("=" * 60)

    gemini_status = "✓ Configured" if GOOGLE_API_KEY else "✗ Not configured"
    snowflake_status = "✓ Configured" if (SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER) else "✗ Not configured"

    print(f"Google Gemini API   : {gemini_status}")
    if GOOGLE_API_KEY:
        print(f"  Model: {GEMINI_MODEL}")
        print(f"  Temperature: {GEMINI_TEMPERATURE}")

    print(f"Snowflake Cortex AI : {snowflake_status}")
    if SNOWFLAKE_ACCOUNT:
        print(f"  Account: {SNOWFLAKE_ACCOUNT}")
        print(f"  Model: {CORTEX_MODEL}")

    print(f"LLM Strategy        : Primary={LLM_PRIMARY}, Fallback={LLM_FALLBACK}")
    print(f"Max Retries         : {LLM_MAX_RETRIES}")

    langsmith_status = "✓ ON" if LANGSMITH_ENABLED else "✗ OFF"
    print(f"LangSmith Tracing   : {langsmith_status}")
    if LANGSMITH_ENABLED:
        print(f"  Project: {LANGSMITH_PROJECT}")
        print(f"  Endpoint: {LANGSMITH_ENDPOINT}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    print_config_status()
    issues = validate_config()
    if issues:
        print("Configuration issues:")
        for issue in issues:
            print(f"  ⚠ {issue}")
