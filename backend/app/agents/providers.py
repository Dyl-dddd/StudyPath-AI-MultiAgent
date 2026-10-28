from dataclasses import dataclass

from app.core.config import get_settings
from app.rag.pipeline import _client


@dataclass(frozen=True)
class ProviderStatus:
    name: str
    status: str
    model_configured: bool


class DeepSeekCompatibleProvider:
    """Uses the application's existing server-side OpenAI-compatible settings."""

    @staticmethod
    def status() -> ProviderStatus:
        settings = get_settings()
        configured = bool(settings.llm_base_url.strip() and settings.llm_api_key.strip() and settings.llm_model.strip())
        return ProviderStatus("openai_compatible", "configured" if configured else "not_configured", configured)

    @staticmethod
    async def complete(messages: list[dict], *, max_tokens: int = 1200, temperature: float = 0.2) -> str:
        settings = get_settings()
        if not (settings.llm_base_url.strip() and settings.llm_api_key.strip() and settings.llm_model.strip()):
            raise RuntimeError("model_not_configured")
        response = await _client().chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise RuntimeError("empty_model_response")
        return content.strip()


class AgentHarnessAdapter:
    """Status-only boundary until the configured AgentHarness contract is identified."""

    @staticmethod
    def status() -> ProviderStatus:
        configured = bool(get_settings().agentharness_api.strip())
        return ProviderStatus("agentharness", "configured_unverified" if configured else "not_configured", configured)

    @staticmethod
    async def execute(_task: dict) -> dict:
        raise RuntimeError("agentharness_contract_unverified")
