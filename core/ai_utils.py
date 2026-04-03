"""LLM client for MyFinance using OpenAI-compatible API (Ollama proxy)."""

import logging
import os
import re
from typing import Optional, Any
from datetime import datetime

from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen2.5-coder:7b"  # Final fallback if nothing configured


class LLMClient:
    """Singleton LLM client for Ollama proxy."""

    _instance: Optional["LLMClient"] = None
    _client: Optional[OpenAI] = None

    def __new__(cls) -> "LLMClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._client is None:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize the OpenAI client."""
        base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1")
        api_key = os.getenv("OPENAI_API_KEY", "dummy")

        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key,
        )

    @property
    def client(self) -> OpenAI:
        """Get the OpenAI client."""
        if self._client is None:
            self._init_client()
        return self._client

    def generate(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt
            model: Model name (default: qwen2.5)
            temperature: Temperature setting
            max_tokens: Maximum tokens to generate
            system_prompt: Optional system prompt
            response_format: Optional format spec (e.g., {"type": "json_object"})

        Returns:
            Generated text response
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Add response_format if specified (JSON mode for Ollama)
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)

        return response.choices[0].message.content

    def generate_json(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """Generate a JSON response from the LLM with JSON Mode enabled.

        Uses robust JSON extraction to handle models that return text before/after JSON.
        Default temperature is 0.1 (precise, predictable) for structured output.

        Args:
            prompt: User prompt
            model: Model name
            temperature: Temperature setting (default 0.1 for precision)
            max_tokens: Maximum tokens to generate
            system_prompt: Optional system prompt

        Returns:
            Parsed JSON response
        """
        import json

        response_text = self.generate(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            response_format={"type": "json_object"},  # Enable JSON Mode
        )

        # Apply robust JSON extraction (same as retry logic)
        clean_text = response_text.strip()

        # Remove markdown code fences
        clean_text = re.sub(r"^```json\s*", "", clean_text, flags=re.MULTILINE)
        clean_text = re.sub(r"^```\s*", "", clean_text, flags=re.MULTILINE)
        clean_text = re.sub(r"\s*```$", "", clean_text, flags=re.MULTILINE)

        # Find valid JSON boundaries
        start_idx = clean_text.find("{")
        end_idx = clean_text.rfind("}")

        if start_idx != -1 and end_idx != -1:
            clean_text = clean_text[start_idx : end_idx + 1]

        return json.loads(clean_text)

    def generate_json_with_retry(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        schema: Any = None,
        retries: int = 2,
    ) -> dict | Any:
        """Generate JSON with automatic self-correction retries and temporal context injection.

        Automatically injects current date/time to prevent "amnesia" in agents.
        Enables JSON Mode at model level for guaranteed valid output.
        Default temperature is 0.1 (precise, predictable) for structured output.

        Args:
            prompt: Base prompt
            model: Model name
            temperature: Temperature setting (default 0.1 for precision)
            max_tokens: Maximum tokens
            system_prompt: Optional system prompt
            schema: Optional Pydantic model for validation
            retries: Number of retry attempts

        Returns:
            Parsed and validated JSON response
        """
        import json

        # --- AUTOMATIC TEMPORAL CONTEXT INJECTION ---
        now = datetime.now()
        time_context = f"[CONTEXTO TEMPORAL ACTUAL: {now.strftime('%A, %d de %B de %Y, %H:%M:%S (%z)')}]"

        # Build enriched system prompt with temporal context
        current_system_prompt = system_prompt or ""
        if "[CONTEXTO TEMPORAL" not in current_system_prompt:
            current_system_prompt = f"{time_context}\n\n{current_system_prompt}"

        current_prompt = prompt
        last_error = ""

        for i in range(retries + 1):
            try:
                response_text = self.generate(
                    prompt=current_prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=current_system_prompt,
                    response_format={"type": "json_object"},  # Enable JSON Mode
                )

                # --- ROBUST JSON EXTRACTION LOGIC ---
                clean_text = response_text.strip()

                # Remove markdown code fences aggressively
                clean_text = re.sub(r"^```json\s*", "", clean_text, flags=re.MULTILINE)
                clean_text = re.sub(r"^```\s*", "", clean_text, flags=re.MULTILINE)
                clean_text = re.sub(r"\s*```$", "", clean_text, flags=re.MULTILINE)

                # Find JSON boundaries
                start_idx = clean_text.find("{")
                end_idx = clean_text.rfind("}")

                if start_idx != -1 and end_idx != -1:
                    clean_text = clean_text[start_idx : end_idx + 1]

                data = json.loads(clean_text)

                # --- SCHEMA VALIDATION ---
                if schema:
                    if hasattr(schema, "model_validate"):
                        instance = schema.model_validate(data)
                    else:
                        instance = schema(**data)
                    return instance

                return data

            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️  Intento {i + 1} fallido: {last_error[:100]}")

                if i < retries:
                    # Provide error feedback for self-correction
                    sanitized_error = last_error.replace('"', "'").replace("\n", " ")[
                        :150
                    ]
                    current_prompt = f"{prompt}\n\nERROR EN RESPUESTA ANTERIOR: {sanitized_error}\nPOR FAVOR: Responde SOLO un objeto JSON válido."
                else:
                    logger.error(
                        f"❌ Agotados {retries} reintentos. Error final: {last_error}"
                    )
                    raise e

        return {}

    def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        model: str = DEFAULT_MODEL,
        temperature: float = 0.1,
        system_prompt: Optional[str] = None,
    ):
        """Generate a response using Tool Calling."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            temperature=temperature,
            tool_choice="auto",
        )

        return response.choices[0].message

    def generate_streaming(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ):
        """Generate a streaming response from the LLM.

        Args:
            prompt: User prompt
            model: Model name
            temperature: Temperature setting
            max_tokens: Maximum tokens to generate
            system_prompt: Optional system prompt

        Yields:
            Text chunks as they are generated
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content


# Singleton instance
llm_client = LLMClient()


def get_llm_client() -> LLMClient:
    """Get the LLM client singleton."""
    return llm_client


def generate_response(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    system_prompt: Optional[str] = None,
) -> str:
    """Generate a response from the LLM.

    Convenience function using the singleton client.
    """
    return llm_client.generate(
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
    )


def generate_json_response(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    system_prompt: Optional[str] = None,
) -> dict:
    """Generate a JSON response from the LLM.

    Convenience function using the singleton client.
    Default temperature is 0.1 for precise, deterministic JSON output.
    """
    return llm_client.generate_json(
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
    )


def generate_json_with_retry(
    prompt: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 2048,
    system_prompt: Optional[str] = None,
    schema: Any = None,
    retries: int = 2,
) -> dict | Any:
    """Generate JSON with automatic self-correction retries.

    Convenience function using the singleton client.
    """
    return llm_client.generate_json_with_retry(
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
        schema=schema,
        retries=retries,
    )


def test_llm_connection() -> bool:
    """Test LLM connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        response = llm_client.generate(
            prompt="Hello",
            max_tokens=10,
        )
        return response is not None and len(response) > 0
    except Exception:
        return False


def get_model_for_task(task_module: str) -> str:
    """Get configured model for a specific task module.

    Hierarchy:
    1. ConfigLoader (sistema_config via database)
    2. DEFAULT_MODEL fallback
    """
    from core.config_loader import ConfigLoader

    # 1. ConfigLoader reads from sistema_config
    model = ConfigLoader.get_model(task_module)
    if model:
        return model

    # 2. Default fallback
    return DEFAULT_MODEL


def get_temperature_for_task(task_module: str, default: float = 0.3) -> float:
    """Get configured temperature for a specific task module.

    Allows fine-tuning LLM behavior per task from database without code changes.

    Hierarchy:
    1. Database (sistema_config)
    2. Environment (.env)
    3. Default parameter

    Args:
        task_module: Module name (e.g., "classification", "parsing", "evaluation")
        default: Default temperature if not configured

    Returns:
        Temperature value (0.0-1.0)
    """
    import os
    from database import get_config_value

    key = f"TEMPERATURA_{task_module.upper()}"

    # 1. Database
    try:
        temp = get_config_value(key)
        if temp is not None:
            return float(temp)
    except Exception:
        pass

    # 2. Environment
    temp = os.getenv(key)
    if temp:
        try:
            return float(temp)
        except ValueError:
            pass

    # 3. Default
    return default


def get_local_models() -> list[str]:
    """Get list of available models from local Ollama API.

    Returns:
        List of model names available in local Ollama
    """
    import requests

    base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1")
    api_url = base_url.replace("/v1", "")

    try:
        response = requests.get(f"{api_url}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        pass
    return []


def get_cloud_models() -> list[str]:
    """Get list of available models from Ollama Cloud API.

    Returns:
        List of model names available in Ollama Cloud
    """
    import requests

    api_key = os.getenv("OLLAMA_CLOUD_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        return []

    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(
            "https://ollama.com/api/tags", headers=headers, timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        pass
    return []


def get_available_models(source: str = "all") -> list[dict]:
    """Get list of available models from Ollama.

    Args:
        source: "local", "cloud", or "all" (default: "all")

    Returns:
        List of dicts with model name and source ("local" or "cloud")
    """
    models = []

    if source in ("local", "all"):
        local_models = get_local_models()
        for model in local_models:
            models.append({"name": model, "source": "local"})

    if source in ("cloud", "all"):
        cloud_models = get_cloud_models()
        for model in cloud_models:
            if model not in [m["name"] for m in models]:
                models.append({"name": model, "source": "cloud"})

    return models
