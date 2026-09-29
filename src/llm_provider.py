"""
Unified LLM Provider with fallback support.
Primary: Google Gemini API
Fallback: Snowflake Cortex AI
"""
import os
import time
from abc import ABC, abstractmethod
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from snowflake_utils import get_connection


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Generate a completion for the given prompt."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available."""
        pass


class GoogleGeminiProvider(LLMProvider):
    """Google Gemini API provider using LangChain."""

    def __init__(self, model: str = "gemini-1.5-flash", temperature: float = 0):
        self.model_name = model
        self.temperature = temperature
        self.llm = None
        self.api_key = os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")

        if GEMINI_AVAILABLE:
            self.llm = ChatGoogleGenerativeAI(
                model=model,
                temperature=temperature,
                google_api_key=self.api_key
            )

    def is_available(self) -> bool:
        """Check if Gemini API is available and configured."""
        return GEMINI_AVAILABLE and self.api_key is not None

    def complete(self, prompt: str) -> str:
        """Generate completion using Google Gemini."""
        if not self.is_available():
            raise RuntimeError("Google Gemini API is not available")

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            content = response.content

            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, str):
                        text_parts.append(item)
                    elif isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                return "\n".join(part for part in text_parts if part)
            else:
                return str(content)
        except Exception as e:
            print(f"Gemini API error: {str(e)}")
            raise


class SnowflakeCortexProvider(LLMProvider):
    """Snowflake Cortex AI provider."""

    CORTEX_MODEL = "llama3.1-8b"

    def __init__(self, model: str = CORTEX_MODEL):
        self.model_name = model

    def is_available(self) -> bool:
        """Check if Snowflake connection is available."""
        try:
            conn = get_connection()
            conn.close()
            return True
        except Exception:
            return False

    def complete(self, prompt: str) -> str:
        """Generate completion using Snowflake Cortex."""
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT SNOWFLAKE.CORTEX.COMPLETE(%s, %s) AS response",
                (self.model_name, prompt),
            )
            row = cur.fetchone()
            result = row[0] if row else ""

            if result:
                elapsed_note = f" [Cortex model={self.model_name}]"
                print(f"  Snowflake Cortex response received{elapsed_note}")

            return result
        except Exception as e:
            print(f"Snowflake Cortex error: {str(e)}")
            raise
        finally:
            conn.close()


class FallbackLLMProvider(LLMProvider):
    """
    LLM Provider with automatic fallback.
    Tries primary provider first, falls back to secondary on failure.
    """

    def __init__(
        self,
        primary: LLMProvider,
        secondary: LLMProvider,
        max_retries: int = 2
    ):
        self.primary = primary
        self.secondary = secondary
        self.max_retries = max_retries
        self.provider_usage = {"primary": 0, "secondary": 0, "failed": 0}

    def is_available(self) -> bool:
        """At least one provider must be available."""
        return self.primary.is_available() or self.secondary.is_available()

    def complete(self, prompt: str) -> str:
        """Try primary, fall back to secondary with retries."""

        # Try primary provider
        if self.primary.is_available():
            for attempt in range(self.max_retries):
                try:
                    print(f"[LLM] Using PRIMARY provider (attempt {attempt + 1}/{self.max_retries})")
                    result = self.primary.complete(prompt)
                    self.provider_usage["primary"] += 1
                    return result
                except Exception as e:
                    print(f"[LLM] PRIMARY provider failed: {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(1)  # Brief backoff before retry
                    continue

        # Fall back to secondary provider
        print("[LLM] Falling back to SECONDARY provider")
        if self.secondary.is_available():
            for attempt in range(self.max_retries):
                try:
                    print(f"[LLM] Using SECONDARY provider (attempt {attempt + 1}/{self.max_retries})")
                    result = self.secondary.complete(prompt)
                    self.provider_usage["secondary"] += 1
                    return result
                except Exception as e:
                    print(f"[LLM] SECONDARY provider failed: {str(e)}")
                    if attempt < self.max_retries - 1:
                        time.sleep(1)
                    continue

        # Both providers failed
        self.provider_usage["failed"] += 1
        raise RuntimeError(
            "Both primary (Gemini) and secondary (Snowflake Cortex) LLM providers failed"
        )

    def get_usage_stats(self) -> dict:
        """Return provider usage statistics."""
        return self.provider_usage.copy()


def get_llm_provider() -> LLMProvider:
    """
    Factory function to get the appropriate LLM provider.

    Returns:
        - FallbackProvider: If both Gemini and Snowflake are configured
        - GoogleGeminiProvider: If only Gemini is configured
        - SnowflakeCortexProvider: If only Snowflake is configured

    Raises:
        ValueError: If no LLM provider is configured
    """

    gemini_configured = bool(os.getenv("GOOGLE_API_KEY"))
    snowflake_configured = bool(os.getenv("SNOWFLAKE_ACCOUNT"))

    # Option 1: Both configured - use fallback
    if gemini_configured and snowflake_configured:
        print("[LLM] Initializing with PRIMARY=Gemini, SECONDARY=Snowflake Cortex")
        try:
            primary = GoogleGeminiProvider()
            secondary = SnowflakeCortexProvider()
            return FallbackLLMProvider(primary, secondary)
        except Exception as e:
            print(f"[LLM] Failed to initialize Gemini provider: {e}")
            print("[LLM] Falling back to Snowflake only")
            return SnowflakeCortexProvider()

    # Option 2: Only Gemini configured
    elif gemini_configured:
        print("[LLM] Using PRIMARY=Gemini only")
        return GoogleGeminiProvider()

    # Option 3: Only Snowflake configured
    elif snowflake_configured:
        print("[LLM] Using PRIMARY=Snowflake Cortex only")
        return SnowflakeCortexProvider()

    # Option 4: Nothing configured
    else:
        raise ValueError(
            "No LLM provider configured. "
            "Set GOOGLE_API_KEY for Gemini or SNOWFLAKE_ACCOUNT for Cortex."
        )


# Global provider instance
_llm_provider: Optional[LLMProvider] = None


def init_llm_provider() -> LLMProvider:
    """Initialize and cache the LLM provider."""
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = get_llm_provider()
    return _llm_provider


def complete(prompt: str) -> str:
    """
    Convenience function to generate LLM completions.
    Uses the cached provider instance.
    """
    provider = init_llm_provider()
    return provider.complete(prompt)
