# LLM Provider Fallback Logging Guide

## Overview

The LLM provider system now includes comprehensive logging for the fallback mechanism. This helps you understand when and why the system switches from the primary provider (Google Gemini) to the secondary provider (Snowflake Cortex).

## What Gets Logged

### 1. **Provider Initialization** 

When the app starts, you'll see:

```
INFO:llm_provider:[LLM] ✓ Both Gemini and Snowflake configured - Initializing with PRIMARY=Gemini, SECONDARY=Snowflake Cortex
INFO:llm_provider:[LLM] ✓ FallbackLLMProvider initialized successfully
```

Or if only one provider is configured:

```
INFO:llm_provider:[LLM] ✓ Only Gemini configured - Using PRIMARY=Gemini
```

### 2. **Request Processing**

When you send a completion request:

```
INFO:llm_provider:[LLM] Using PRIMARY provider: GoogleGeminiProvider (attempt 1/2)
INFO:llm_provider:[Gemini] Sending request (prompt length: 245 chars)
INFO:llm_provider:[Gemini] Received response (512 chars)
INFO:llm_provider:[LLM] PRIMARY provider succeeded with 512 chars
```

### 3. **Fallback Trigger** ⚠️

If the primary provider fails, you'll see a clear warning:

```
WARNING:llm_provider:[LLM] PRIMARY provider failed: GoogleGeminiProvider - Connection timeout
WARNING:llm_provider:[LLM] Retrying in 1 second (attempt 2/2)...
WARNING:llm_provider:[LLM] PRIMARY provider failed: GoogleGeminiProvider - Connection timeout
WARNING:llm_provider:[LLM] ⚠️  PRIMARY provider exhausted - FALLING BACK to SECONDARY provider: SnowflakeCortexProvider
INFO:llm_provider:[LLM] Using SECONDARY provider: SnowflakeCortexProvider (attempt 1/2)
INFO:llm_provider:[Cortex] Sending request to model=llama3.1-8b (prompt length: 245 chars)
INFO:llm_provider:[Cortex] Received response from model=llama3.1-8b (487 chars)
INFO:llm_provider:[LLM] SECONDARY provider succeeded with 487 chars
```

### 4. **Both Providers Fail** ❌

If both providers fail:

```
ERROR:llm_provider:[LLM] ❌ Both PRIMARY and SECONDARY providers failed. Usage: {'primary': 2, 'secondary': 2, 'failed': 1}
```

## Log Levels

- **INFO** — Normal operation (provider selected, request sent/received)
- **WARNING** — Provider failed but fallback available
- **ERROR** — Both providers failed or critical error
- **DEBUG** — Detailed request/response information (set `logging.getLogger('llm_provider').setLevel(logging.DEBUG)`)

## Provider Usage Statistics

After requests complete, you can check which provider was used:

```python
from llm_provider import init_llm_provider

provider = init_llm_provider()
if hasattr(provider, 'get_usage_stats'):
    stats = provider.get_usage_stats()
    print(f"Primary calls: {stats['primary']}")
    print(f"Secondary calls: {stats['secondary']}")
    print(f"Failed: {stats['failed']}")
```

## Viewing Logs in Streamlit

Logs appear in:
1. **Terminal/Console** where you run Streamlit
2. **Browser Console** (press F12 in your browser)
3. **Streamlit logs** (check the running process output)

## Example: Testing Fallback

Run the test script to see fallback logging in action:

```bash
python test_fallback_logging.py
```

This will:
1. Initialize the LLM provider
2. Send a test completion request
3. Show all logging output
4. Display provider usage statistics

## Log Format

Each log entry includes:
- **Timestamp** — When the event occurred
- **Logger Name** — `llm_provider` (the module)
- **Level** — INFO, WARNING, ERROR, DEBUG
- **Message** — The actual log message

Example:
```
2026-09-29 19:48:01.955 INFO:llm_provider:[LLM] ✓ Both Gemini and Snowflake configured - ...
```

## Environment Variables for Logging

Control logging verbosity:

```bash
# In .env or terminal
LOGLEVEL=INFO    # Default
LOGLEVEL=DEBUG   # Verbose (includes detailed request info)
LOGLEVEL=WARNING # Only warnings and errors
```

## Troubleshooting

### "PRIMARY provider failed" repeatedly?
- Check your `GOOGLE_API_KEY` is valid
- Check your internet connection
- Check Google Gemini API status

### "FALLING BACK to SECONDARY" appears?
- This is normal — primary provider had an issue
- Check logs for the specific error message
- Verify your Snowflake connection

### "Both providers failed"?
- Check both `GOOGLE_API_KEY` and Snowflake credentials
- Verify both services are accessible
- Check network connectivity
- Review error messages in logs

## Configuration Reference

In `src/llm_provider.py`:

```python
# Max retries per provider (default: 2)
FallbackLLMProvider(primary, secondary, max_retries=2)

# Retry backoff
time.sleep(1)  # 1 second between retries
```

## See Also

- **LangSmith Integration** — [LANGSMITH_GUIDE.md](LANGSMITH_GUIDE.md)
- **Configuration** — [../src/config.py](../src/config.py)
- **LLM Provider** — [../src/llm_provider.py](../src/llm_provider.py)
