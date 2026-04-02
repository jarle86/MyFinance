"""LLM client for MyFinance using OpenAI-compatible API (Ollama proxy)."""

import os
from typing import Optional, Any

from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


DEFAULT_MODEL = "qwen2.5:3b"


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
    ) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt
            model: Model name (default: qwen2.5)
            temperature: Temperature setting
            max_tokens: Maximum tokens to generate
            system_prompt: Optional system prompt

        Returns:
            Generated text response
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
        )

        return response.choices[0].message.content

    def generate_json(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """Generate a JSON response from the LLM.

        Args:
            prompt: User prompt
            model: Model name
            temperature: Temperature setting
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
        )

        return json.loads(response_text.strip())

    def generate_json_with_retry(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        schema: Any = None,
        retries: int = 2,
    ) -> dict | Any:
        """Generate JSON with automatic self-correction retries.
        
        If parsing fails or fails validation, it sends the error back to the LLM.
        """
        import json
        
        current_prompt = prompt
        last_error = ""
        
        for i in range(retries + 1):
            try:
                response_text = self.generate(
                    prompt=current_prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                )
                
                # Cleanup JSON markdown
                clean_text = response_text.strip()
                if clean_text.startswith("```json"): clean_text = clean_text[7:]
                elif clean_text.startswith("```"): clean_text = clean_text[3:]
                if clean_text.endswith("```"): clean_text = clean_text[:-3]
                
                data = json.loads(clean_text)
                
                # If schema provided, validate (supports Pydantic)
                if schema:
                    if hasattr(schema, "model_validate"):
                        instance = schema.model_validate(data)
                        return instance
                    else:
                        instance = schema(**data)
                        return instance
                
                return data
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Intento {i+1} fallido por error JSON/Pydantic: {last_error}")
                if i < retries:
                    # Enrich prompt with error for next attempt
                    current_prompt = f"{prompt}\n\nERROR PREVIO: {last_error}\nPor favor, corrige el JSON y asegúrate de cumplir el esquema."
                else:
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
    temperature: float = 0.3,
    max_tokens: int = 2048,
    system_prompt: Optional[str] = None,
) -> dict:
    """Generate a JSON response from the LLM.

    Convenience function using the singleton client.
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
    1. Database (sistema_config)
    2. Environment (.env)
    3. DEFAULT_MODEL fallback
    """
    import os
    from database import get_config_value

    key = f"MODELO_{task_module.upper()}"
    
    # 1. Database
    model = get_config_value(key)
    if model:
        return model
        
    # 2. Environment
    model = os.getenv(key)
    if model:
        return model
        
    # 3. Default
    return DEFAULT_MODEL


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
