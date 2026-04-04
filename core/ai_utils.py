"""LLM client for MyFinance using OpenAI-compatible API (Ollama proxy)."""

import logging
import os
import re
from typing import Optional, Any
from datetime import datetime

from openai import OpenAI
from ollama import Client as OllamaClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen2.5-coder:7b"  # Final fallback if nothing configured


class LLMClient:
    """Singleton LLM client with dynamic routing (Local, Cloud, Gemini)."""

    _instance: Optional["LLMClient"] = None
    _clients: dict[str, OpenAI | OllamaClient] = {}

    def __new__(cls) -> "LLMClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_client_and_model(self, model: str) -> tuple[OpenAI | OllamaClient, str]:
        """Determine provider and return the appropriate client and cleaned model name."""
        from core.config_loader import ConfigLoader
        
        target_model = model
        model_lower = model.lower()
        
        # 1. ESCENARIO: GEMINI (Google Cloud)
        if "gemini" in model_lower:
            provider = "gemini"
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            api_key = ConfigLoader.get_gemini_key()
            if not api_key or api_key == "dummy":
                logger.warning("GEMINI_API_KEY no configurada. Intentando fallback local.")
                provider = "local"
        
        # 2. ESCENARIO: OLLAMA CLOUD (ollama.com)
        elif "cloud" in model_lower or "qwen3" in model_lower:
            provider = "cloud"
            # Si el modelo trae el prefijo 'cloud:', lo limpiamos
            target_model = model[6:] if model_lower.startswith("cloud:") else model
            base_url = "https://ollama.com/v1"
            api_key = os.environ.get("OLLAMA_API_KEY") or ConfigLoader.get_ollama_cloud_key()
            
            if not api_key or api_key == "dummy":
                logger.warning(f"OLLAMA_API_KEY no configurada para modelo de nube '{model}'. Intentando fallback local.")
                provider = "local"
                target_model = model
        
        # 3. ESCENARIO: OLLAMA LOCAL (localhost)
        else:
            provider = "local"
            base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
            api_key = "ollama"

        # Mantener caché de clientes para evitar reinicializaciones costosas
        cache_key = f"{provider}_{base_url}"
        if cache_key not in self._clients:
            logger.info(f"[AI ROUTER] Conectando a {provider.upper()} en {base_url} (Timeout: 120s)")
            
            if provider == "cloud":
                # Cliente NATIVO de Ollama para la nube
                self._clients[cache_key] = OllamaClient(
                    host="https://ollama.com",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=120.0
                )
            else:
                # Cliente OpenAI para Local y Gemini
                self._clients[cache_key] = OpenAI(
                    base_url=base_url,
                    api_key=api_key,
                    timeout=120.0,
                )
            
        return self._clients[cache_key], target_model

    def generate(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> str:
        """Generate a response using the appropriate provider."""
        client, target_model = self._get_client_and_model(model)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        logger.debug(f"[AI ROUTER] Generando con {target_model} via {client.__class__.__name__}")
        
        if isinstance(client, OllamaClient):
            # Llamada nativa de Ollama
            response = client.chat(
                model=target_model,
                messages=messages,
                options={
                    'temperature': temperature,
                    'num_predict': max_tokens
                }
            )
            return response['message']['content']
        else:
            # Llamada estándar de OpenAI (Local/Gemini)
            response = client.chat.completions.create(**kwargs)
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

    def _parse_json_from_text(self, text: str) -> str:
        """Helper to extract clean JSON from LLM response text."""
        clean_text = text.strip()

        # Remove markdown code fences aggressively
        clean_text = re.sub(r"^```json\s*", "", clean_text, flags=re.MULTILINE)
        clean_text = re.sub(r"^```\s*", "", clean_text, flags=re.MULTILINE)
        clean_text = re.sub(r"\s*```$", "", clean_text, flags=re.MULTILINE)

        # Find JSON boundaries
        start_idx = clean_text.find("{")
        end_idx = clean_text.rfind("}")

        if start_idx != -1 and end_idx != -1:
            clean_text = clean_text[start_idx : end_idx + 1]
            
        return clean_text

    def generate_json_with_retry(
        self,
        prompt: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        schema: Any = None,
        retries: int = 2,
        custom_format: Optional[dict] = None,
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
        client, target_model = self._get_client_and_model(model)

        for i in range(retries + 1):
            response_text = ""
            try:
                # Determinar si usar response_format (algunos modelos de nube no lo soportan bien)
                use_json_mode = "gemini" not in model.lower() # Bypass para Gemini si falla frecuentemente
                
                messages = []
                if current_system_prompt:
                    messages.append({"role": "system", "content": current_system_prompt})
                messages.append({"role": "user", "content": current_prompt})

                if isinstance(client, OllamaClient):
                    # Preparar argumentos para Ollama Nativo
                    ollama_kwargs = {
                        "model": target_model,
                        "messages": messages,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens
                        }
                    }
                    # 🚀 INYECTAR LA JAULA EN OLLAMA
                    if custom_format:
                        ollama_kwargs["format"] = custom_format
                    elif use_json_mode:
                        ollama_kwargs["format"] = "json"
                        
                    response = client.chat(**ollama_kwargs)
                    response_text = response['message']['content']
                else:
                    # Preparar argumentos para OpenAI Compatible
                    kwargs = {
                        "model": target_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if custom_format:
                        kwargs["response_format"] = custom_format
                    elif use_json_mode:
                        kwargs["response_format"] = {"type": "json_object"}
                        
                    response_text = client.chat.completions.create(**kwargs).choices[0].message.content

                if not response_text or len(response_text.strip()) == 0:
                    logger.error(f"❌ El modelo {target_model} devolvió una respuesta VACÍA. Posible bloqueo de seguridad o timeout.")
                    raise ValueError(f"Respuesta vacía del proveedor para el modelo {target_model}")

                # --- ROBUST JSON EXTRACTION LOGIC ---
                clean_text = self._parse_json_from_text(response_text)
                
                try:
                    data = json.loads(clean_text)
                except json.JSONDecodeError as je:
                    logger.error(f"❌ Error de parseo JSON. RAW: {response_text[:300]}...")
                    raise je

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
                logger.warning(f"⚠️  Intento {i + 1} fallido para {model}: {last_error[:100]}")

                if i < retries:
                    # Provide error feedback for self-correction
                    sanitized_error = last_error.replace('"', "'").replace("\n", " ")[
                        :150
                    ]
                    current_prompt = f"{prompt}\n\nERROR EN RESPUESTA ANTERIOR: {sanitized_error}\nPOR FAVOR: Responde SOLO un objeto JSON válido."
                else:
                    logger.error(
                        f"❌ Agotados {retries} reintentos en {model}. Error final: {last_error}"
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
        client, target_model = self._get_client_and_model(model)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=target_model,
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
        """Generate a streaming response using the appropriate provider."""
        client, target_model = self._get_client_and_model(model)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=target_model,
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
    custom_format: Optional[dict] = None,
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
        custom_format=custom_format,
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
