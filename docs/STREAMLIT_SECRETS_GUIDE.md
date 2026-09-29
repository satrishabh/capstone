# Streamlit Secrets Management Guide

This guide explains how to securely manage API keys and credentials in Streamlit.

## 📁 File Structure

```
capstone/
├── .streamlit/
│   └── secrets.toml          ← 🔒 Local secrets (DO NOT commit!)
├── .env                      ← Fallback env vars
├── .env.example              ← Template for public repo
└── .gitignore                ← Excludes secrets.toml
```

## 🔑 Add Secrets Locally

### Method 1: Using `secrets.toml` (Recommended)

**Create file:** `.streamlit/secrets.toml`

```toml
# API Keys
GOOGLE_API_KEY = "your-api-key-here"
LANGSMITH_API_KEY = "lsv2_pt_xxxxxx"

# Database Credentials
SNOWFLAKE_USER = "your_user"
SNOWFLAKE_PASSWORD = "your_password"

# Multi-line secrets (like private keys)
SNOWFLAKE_PRIVATE_KEY = """
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQE...
-----END PRIVATE KEY-----
"""
```

**Access in code:**

```python
import streamlit as st

api_key = st.secrets["GOOGLE_API_KEY"]
```

### Method 2: Using `.env` (Fallback)

Create `.env` file:

```bash
GOOGLE_API_KEY=your-api-key
SNOWFLAKE_USER=your_user
```

Access in code:

```python
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
```

### Method 3: Using `.streamlit/config.toml` (For Non-Secrets)

For public configuration (not secrets):

```toml
[theme]
primaryColor = "#FF4B4B"
backgroundColor = "#0E1117"

[logger]
level = "info"
```

## 🛡️ Security Best Practices

### DO ✅

- ✅ Keep `secrets.toml` in `.gitignore`
- ✅ Commit `secrets.example.toml` template instead
- ✅ Use environment-specific secrets files:
  - `.streamlit/secrets.local.toml` (dev)
  - `.streamlit/secrets.prod.toml` (production)
- ✅ Rotate API keys regularly
- ✅ Use least-privilege credentials

### DON'T ❌

- ❌ Commit `secrets.toml` to git
- ❌ Log secrets in console output
- ❌ Share secrets in code comments
- ❌ Use default/test credentials in production

## 📋 Check Current Secrets

In your app, display available secrets:

```python
import streamlit as st

# Debug: Show loaded secrets (redacted)
with st.expander("🔐 Secrets Status"):
    try:
        secrets_loaded = {
            key: "***" + value[-4:] if isinstance(value, str) else type(value).__name__
            for key, value in st.secrets.items()
        }
        st.json(secrets_loaded)
    except Exception as e:
        st.error(f"Failed to load secrets: {e}")
```

## 🚀 Deploy to Streamlit Cloud

### Step 1: Create Secrets on Cloud

1. Go to: **app.streamlit.io → Settings → Secrets**
2. Copy contents of your local `secrets.toml`
3. Paste into cloud secrets manager

Format:
```toml
GOOGLE_API_KEY = "your-key-here"
SNOWFLAKE_ACCOUNT = "your-account"
```

### Step 2: Deploy

```bash
streamlit run src/app.py
```

Streamlit Cloud automatically uses secrets from the dashboard.

## 📝 Template: `secrets.example.toml`

Create this for the public repo (with dummy values):

```toml
# Google Gemini API
GOOGLE_API_KEY = "paste-your-google-api-key-here"
GEMINI_MODEL = "gemini-1.5-flash"

# Snowflake Configuration
SNOWFLAKE_ACCOUNT = "your-account.region.cloud"
SNOWFLAKE_USER = "your_service_user"
SNOWFLAKE_WAREHOUSE = "YOUR_WH"

# LangSmith Tracing
LANGSMITH_API_KEY = "lsv2_pt_your_key_here"
LANGSMITH_PROJECT = "your-project-name"
```

## 🔗 Accessing Secrets in Code

### Single Secret

```python
import streamlit as st

api_key = st.secrets["GOOGLE_API_KEY"]
```

### Multiple Secrets

```python
import streamlit as st

config = {
    "google_key": st.secrets.get("GOOGLE_API_KEY"),
    "langsmith_key": st.secrets.get("LANGSMITH_API_KEY"),
    "snowflake_user": st.secrets.get("SNOWFLAKE_USER"),
}
```

### With Fallback to `.env`

```python
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

def get_secret(key, default=None):
    try:
        return st.secrets[key]
    except (KeyError, AttributeError):
        return os.getenv(key, default)

api_key = get_secret("GOOGLE_API_KEY")
```

## 🧪 Local Testing with Multiple Secret Files

Use different secrets files for different environments:

```bash
# Development
STREAMLIT_SECRETS_FILE=.streamlit/secrets.local.toml streamlit run src/app.py

# Production
STREAMLIT_SECRETS_FILE=.streamlit/secrets.prod.toml streamlit run src/app.py
```

## 📦 Current Project Setup

Your project already has:

✅ `.streamlit/secrets.toml` — All credentials configured  
✅ `.env` — Fallback environment variables  
✅ `snowflake_utils.py` — Smart secret loading (Streamlit → .env → default)  
✅ `config.py` — Environment configuration  

**Priority order in code:**
1. Streamlit `secrets.toml`
2. `.env` file
3. Hardcoded defaults

## 🚨 Emergency: Exposed Secrets?

If you accidentally expose a secret:

1. **Immediately rotate** the API key/credential
2. **Remove** from git history:
   ```bash
   git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch secrets.toml' --prune-empty --tag-name-filter cat -- --all
   git push origin --force
   ```
3. **Regenerate** new credentials
4. **Update** `secrets.toml` with new values

## 📚 References

- Streamlit Secrets Docs: https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app/secrets-management
- TOML Format: https://toml.io/
- Python-dotenv: https://python-dotenv.readthedocs.io/
