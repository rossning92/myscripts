import os
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional


Provider = Literal[
    "anthropic",
    "cliproxy",
    "deepseek",
    "gemini",
    "llama_cpp",
    "openai",
    "openrouter",
]
ReasoningEffort = Literal["low", "medium", "high"]
ApiType = Literal[
    "anthropic_messages",
    "gemini_generate_content",
    "openai_chat_completions",
    "openai_images",
    "openai_responses",
]


@dataclass(frozen=True)
class Model:
    """Everything needed to route a model selection to its provider."""

    provider: Provider
    model: str
    api_type: ApiType = "openai_responses"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    reasoning_effort: Optional[ReasoningEffort] = None

    @property
    def id(self) -> str:
        return f"{self.provider}:{self.model}"


# Ranking: https://deepswe.datacurve.ai/
MODELS: List[Model] = [
    Model(
        "anthropic",
        "claude-sonnet-4-5",
        api_type="anthropic_messages",
    ),
    Model("openai", "gpt-4.1-mini"),
    Model("openai", "gpt-4.1"),
    Model("openai", "gpt-5.2-chat-latest"),
    Model("openai", "gpt-5.6-sol"),
    Model("openai", "gpt-5.6-luna"),
    Model(
        "cliproxy",
        "gpt-5.6-sol",
        base_url=os.environ.get("CLIPROXY_BASE_URL", "http://127.0.0.1:8317/v1"),
        api_key=os.environ.get("CLIPROXY_API_KEY", "myscripts-local-key"),
    ),
    Model(
        "cliproxy",
        "gpt-5.6-terra",
        base_url=os.environ.get("CLIPROXY_BASE_URL", "http://127.0.0.1:8317/v1"),
        api_key=os.environ.get("CLIPROXY_API_KEY", "myscripts-local-key"),
    ),
    Model(
        "cliproxy",
        "gpt-5.6-luna",
        base_url=os.environ.get("CLIPROXY_BASE_URL", "http://127.0.0.1:8317/v1"),
        api_key=os.environ.get("CLIPROXY_API_KEY", "myscripts-local-key"),
    ),
    Model(
        "gemini",
        "gemini-3-flash-preview",
        api_type="gemini_generate_content",
    ),
    Model(
        "gemini",
        "gemini-3-pro-image",
        api_type="gemini_generate_content",
    ),
    Model(
        "gemini",
        "gemini-3.1-flash-image",
        api_type="gemini_generate_content",
    ),
    Model(
        "gemini",
        "gemini-3.1-flash-lite-preview",
        api_type="gemini_generate_content",
    ),
    Model("openai", "gpt-image-2", api_type="openai_images"),
    Model(
        "openrouter",
        "google/gemini-3-flash-preview",
        api_type="openai_chat_completions",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    ),
    Model(
        "llama_cpp",
        os.environ.get("LLAMA_CPP_MODEL", "Qwen/Qwen3-1.7B-GGUF"),
        api_type="openai_chat_completions",
        base_url=os.environ.get(
            "LLAMA_CPP_ENDPOINT", "http://127.0.0.1:8080/v1"
        ),
        api_key=os.environ.get("LLAMA_CPP_API_KEY", "no-key"),
    ),
    Model(
        "openrouter",
        "x-ai/grok-4.5",
        api_type="openai_chat_completions",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    ),
    Model(
        "openrouter",
        "x-ai/grok-imagine-image-quality",
        api_type="openai_chat_completions",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    ),
    Model(
        "openrouter",
        "openai/gpt-image-2",
        api_type="openai_chat_completions",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    ),
    Model(
        "deepseek",
        "deepseek-v4-flash",
        api_type="openai_chat_completions",
        base_url="https://api.deepseek.com",
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
    ),
    Model(
        "deepseek",
        "deepseek/deepseek-v4-flash-0731",
        api_type="openai_chat_completions",
        base_url="https://api.deepseek.com",
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
    ),
    Model(
        "deepseek",
        "deepseek-v4-pro",
        api_type="openai_chat_completions",
        base_url="https://api.deepseek.com",
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
    ),
]

MODELS_BY_ID: Dict[str, Model] = {model.id: model for model in MODELS}
MODEL_IDS = list(MODELS_BY_ID)
DEFAULT_MODEL = "openai:gpt-5.2-chat-latest"


def get_model(model_id: Optional[str]) -> Model:
    """Resolve a model id, including legacy bare model/provider selectors."""

    model_id = model_id or DEFAULT_MODEL
    model = MODELS_BY_ID.get(model_id)
    if model:
        return model

    legacy_matches = [
        model
        for model in MODELS
        if model.model == model_id or model.provider == model_id
    ]
    if len(legacy_matches) == 1:
        return legacy_matches[0]

    return Model("openai", model_id)
