#!/usr/bin/env python3
"""Test script to demonstrate LLM provider fallback logging."""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

# Set up detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from llm_provider import get_llm_provider, init_llm_provider

print("=" * 70)
print("LLM PROVIDER FALLBACK LOGGING TEST")
print("=" * 70)

# Initialize the LLM provider
print("\n📋 Initializing LLM provider...\n")
provider = init_llm_provider()

# Show provider configuration
print("\n" + "=" * 70)
print("PROVIDER CONFIGURATION")
print("=" * 70)
print(f"Provider Type: {provider.__class__.__name__}")

if hasattr(provider, 'provider_usage'):
    print(f"Fallback Enabled: Yes")
    print(f"Primary: {provider.primary.__class__.__name__}")
    print(f"Secondary: {provider.secondary.__class__.__name__}")
    print(f"Max Retries: {provider.max_retries}")
else:
    print(f"Fallback Enabled: No (single provider)")
    print(f"Provider: {provider.__class__.__name__}")

print("\n" + "=" * 70)
print("TEST: Sending a completion request")
print("=" * 70)
print("\nNote: Detailed logs below show provider selection and fallback behavior:\n")

try:
    test_prompt = "Write a single sentence about vehicle maintenance."
    result = provider.complete(test_prompt)

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print(f"\n✓ Completion successful!")
    print(f"\nResponse preview: {result[:100]}...")

    if hasattr(provider, 'get_usage_stats'):
        stats = provider.get_usage_stats()
        print(f"\nProvider Usage Statistics:")
        print(f"  - Primary: {stats['primary']} calls")
        print(f"  - Secondary: {stats['secondary']} calls")
        print(f"  - Failed: {stats['failed']} calls")

except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "=" * 70)
