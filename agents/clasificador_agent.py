"""Clasificador Agent (A1/A5) - Intent classification for MyFinance.

Determines the appropriate route based on user intent and certainty level.
Controlado dinámicamente por la base de datos (sistema_config).
"""

from typing import Optional
import logging

from core.config_loader import get_task_classify, ConfigLoader
from core.ai_utils import generate_json_response, get_model_for_task

logger = logging.getLogger(__name__)


class ClasificadorAgent:
    """Agent A1: Classifies user intent to determine routing dynamically."""

    ROUTE_MAP = {
        "chat": "A",
        "registro": "D",
        "consulta": "B",
        "autorizar": "F",
        "comando_sistema": "X",
    }

    DEFAULT_INTENT = "chat"

    def _get_dynamic_config(self) -> dict:
        """Fetch dynamic parameters from DB (Streamlit Dashboard)."""
        config_db = ConfigLoader.get_agent_config("A1") or {}

        return {
            "min_certeza": config_db.get("min_certeza", 85),
            "temperature": config_db.get("temperature", 0.3),
            "max_tokens": config_db.get("max_tokens", 100),
            "modelo": config_db.get("modelo", "A1"),
        }

    def _get_task_prompt(self) -> str:
        """Get the classification prompt from config with dynamic variables."""
        prompt = get_task_classify()

        if not prompt:
            raise ValueError(
                "TASK_CLASSIFY not configured in sistema_config. "
                "Add the prompt to the database before running."
            )

        # Inyectar variables dinámicas de la DB (Regla #2)
        config = self._get_dynamic_config()
        keywords_escape = ConfigLoader.get_keywords_escape()
        
        # Usar .replace en lugar de .format para evitar conflictos con llaves de JSON en el prompt
        final_prompt = prompt.replace("{keywords_escape}", keywords_escape)
        final_prompt = final_prompt.replace("{umbral_certeza_clasificador}", str(config["min_certeza"]))
        
        return final_prompt

    def classify(self, text: str) -> str:
        """Classify user input into intent."""
        result = self._classify_json(text)
        config = self._get_dynamic_config()

        if result["es_ambiguo"]:
            logger.info(f"[A1 DECISION] '{text[:60]}' → ambiguo → fallback='{self.DEFAULT_INTENT}'")
            return self.DEFAULT_INTENT

        certeza = result.get("certeza", 0)
        min_certeza = config["min_certeza"]

        if certeza < min_certeza:
            logger.info(
                f"[A1 DECISION] '{text[:60]}' → certeza={certeza} < umbral={min_certeza} → fallback='{self.DEFAULT_INTENT}'"
            )
            return self.DEFAULT_INTENT

        logger.info(f"[A1 DECISION] '{text[:60]}' → intencion='{result.get('intencion')}' certeza={certeza}")
        return result.get("intencion", self.DEFAULT_INTENT)

    def _classify_json(self, text: str) -> dict:
        """Classify and return full JSON response using dynamic params."""
        config = self._get_dynamic_config()

        try:
            prompt = f"Mensaje: {text}"
            from core.ai_utils import generate_json_with_retry
            
            result = generate_json_with_retry(
                prompt=prompt,
                model=get_model_for_task(config["modelo"]),
                temperature=config["temperature"],
                max_tokens=config["max_tokens"],
                system_prompt=self._get_task_prompt(),
            )

            logger.info(
                f"[A1 RAW] input='{text[:60]}' → "
                f"intencion='{result.get('intencion')}' "
                f"certeza={result.get('certeza')} "
                f"es_ambiguo={result.get('es_ambiguo')}"
            )

            return {
                "intencion": result.get("intencion", self.DEFAULT_INTENT),
                "certeza": int(result.get("certeza", 50)),
                "es_ambiguo": bool(result.get("es_ambiguo", False)),
            }

        except Exception as e:
            logger.error(f"Error en ClasificadorAgent A1: {e}", exc_info=True)
            return {
                "intencion": self.DEFAULT_INTENT,
                "certeza": 0,
                "es_ambiguo": True,
            }

    def get_route(self, text: str) -> str:
        """Get the processing route for the input."""
        intent = self.classify(text)
        return self.ROUTE_MAP.get(intent, "A")

    def classify_with_details(self, text: str) -> dict:
        """Classify and return full details."""
        result = self._classify_json(text)
        intent = self.classify(text)

        return {
            **result,
            "route": self.ROUTE_MAP.get(intent, "A"),
        }
