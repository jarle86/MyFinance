"""Chat Agent (A6) - Humanizer and financial advice for MyFinance.

Includes interactive mode for handling pending evaluations from A3.
"""

import logging
from typing import Optional
from uuid import UUID

from core.config_loader import get_task_chat
from core.ai_utils import generate_response, get_model_for_task
from agents.evaluador_agent import EvaluacionSemantica, CampoEvaluado

logger = logging.getLogger(__name__)


class ChatAgent:
    """Agent A6: Handles chat interactions and humanizes responses."""

    def __init__(self, user_config: Optional[dict] = None):
        """Initialize the chat agent.

        Args:
            user_config: User's agent configuration from usuarios.config
        """
        self.user_config = user_config or {}

    def _get_task_prompt(self) -> str:
        """Get the chat prompt from config.

        Returns:
            Prompt from sistema_config

        Raises:
            ValueError: If TASK_CHAT not configured in database
        """
        prompt = get_task_chat()

        if not prompt:
            raise ValueError(
                "TASK_CHAT not configured in sistema_config. "
                "Add the prompt to the database before running."
            )

        return prompt

    def _get_model_config(self) -> tuple[str, float, int, int]:
        """Get model configuration from user config or defaults.

        Returns:
            Tuple of (model, temperature, max_tokens, timeout)
        """
        from core.config_loader import ConfigLoader

        model = ConfigLoader.get_model("A6") or "qwen3"
        temp = ConfigLoader.get_temp("A6")
        tokens = ConfigLoader.get_tokens("A6")
        timeout = ConfigLoader.get_timeout("A6")

        return model, temp, tokens, timeout

    def chat(self, message: str) -> str:
        """Process a chat message."""
        try:
            model, temp, tokens, _ = self._get_model_config()
            logger.info(f"[A6] INPUT: '{message[:80]}...' MODEL={model} TEMP={temp}")

            response = generate_response(
                prompt=message,
                model=model,
                temperature=temp,
                max_tokens=tokens,
                system_prompt=self._get_task_prompt(),
            )
            logger.info(f"[A6] OUTPUT: '{str(response)[:80]}...'")
            return response

        except Exception as e:
            logger.error(f"[A6] ERROR: {e}", exc_info=True)
            return f"Lo siento, tuve un problema al procesar tu mensaje. ¿Podrías intentarlo de nuevo?"

    def humanize(self, technical_output: str, output_type: str = "result") -> str:
        """Humanize technical output.

        Args:
            technical_output: Technical text to translate
            output_type: Type of output (result, error, query)

        Returns:
            Human-friendly version
        """
        prompts = {
            "result": f"Traduce el siguiente resultado a lenguaje amigable y conciso:\n\n{technical_output}",
            "error": f"Explica el siguiente error de forma amigable:\n\n{technical_output}",
            "query": f"Explica el siguiente query SQL y su resultado de forma simple:\n\n{technical_output}",
        }

        prompt = prompts.get(output_type, prompts["result"])

        try:
            model, temp, tokens, _ = self._get_model_config()

            response = generate_response(
                prompt=prompt,
                model=model,
                temperature=temp,  # Use config instead of hardcoded 0.5
                max_tokens=512,
            )
            return response

        except Exception:
            return technical_output

    def agrupar_preguntas(self, evaluacion: EvaluacionSemantica) -> str:
        """Group pending questions from A3 evaluation into one message."""
        logger.info(
            f"[A6 AGRUPAR] INPUT campos_totales={list(evaluacion.campos.keys())} "
            f"campos_pendientes={[k for k, v in evaluacion.campos.items() if v.accion == 'preguntar']}"
        )
        if evaluacion.preguntas_agrupadas:
            logger.info(
                f"[A6 AGRUPAR] OUTPUT (cache)='{evaluacion.preguntas_agrupadas[:100]}'"
            )
            return evaluacion.preguntas_agrupadas

        preguntas = []
        for nombre, campo in evaluacion.campos.items():
            if campo.accion == "preguntar" and campo.pregunta:
                preguntas.append(campo.pregunta)

        if not preguntas:
            result = "Todos los datos están completos. ¿Confirmas el registro?"
            logger.info(f"[A6 AGRUPAR] OUTPUT no_preguntas='{result}'")
            return result

        if len(preguntas) == 1:
            logger.info(f"[A6 AGRUPAR] OUTPUT 1_pregunta='{preguntas[0][:100]}'")
            return preguntas[0]

        header = "Faltan algunos datos para completar el registro:\n\n"
        items = "\n".join([f"{i + 1}. {p}" for i, p in enumerate(preguntas)])
        footer = "\n\nPor favor proporciona esta información."
        result = header + items + footer
        logger.info(f"[A6 AGRUPAR] OUTPUT {len(preguntas)}_preguntas='{result[:150]}'")
        return result

    def generar_preview(self, evaluacion: EvaluacionSemantica) -> str:
        """Generate a preview message for confirmation.

        Args:
            evaluacion: Completed evaluation from A3

        Returns:
            Formatted preview message
        """
        campos_validos = {
            nombre: campo.valor
            for nombre, campo in evaluacion.campos.items()
            if campo.valor and campo.accion == "siguiente"
        }

        if not campos_validos:
            return "No hay datos válidos para mostrar."

        preview = "📝 **Preview del Registro:**\n\n"

        if "monto_total" in campos_validos:
            monto = campos_validos["monto_total"]
            moneda = campos_validos.get("moneda", "DOP")
            preview += f"💰 **Monto:** {moneda} {monto}\n"

        if "origen" in campos_validos:
            preview += f"🏦 **Origen:** {campos_validos['origen']}\n"

        if "destino" in campos_validos:
            preview += f"🛒 **Destino:** {campos_validos['destino']}\n"

        if "categoria" in campos_validos:
            preview += f"🏷️ **Categoría:** {campos_validos['categoria']}\n"

        if "fecha" in campos_validos:
            preview += f"📅 **Fecha:** {campos_validos['fecha']}\n"

        if "concepto" in campos_validos:
            preview += f"📝 **Concepto:** {campos_validos['concepto']}\n"

        preview += "\n¿Confirmas este registro?"
        return preview

    def procesar_respuesta_interactiva(
        self,
        respuesta: str,
        evaluacion_anterior: Optional[EvaluacionSemantica] = None,
    ) -> dict:
        """Process user's response in interactive mode.

        Args:
            respuesta: User's response to pending questions
            evaluacion_anterior: Previous evaluation from A3

        Returns:
            Dict with:
            - response: Message to show to user
            - evaluacion: New evaluation (if valid)
            - accion: "continuar", "confirmar", "cancelar"
        """
        if not evaluacion_anterior:
            return {
                "response": "No hay una evaluación previa. Por favor inicia un nuevo registro.",
                "evaluacion": None,
                "accion": "cancelar",
            }

        respuesta_lower = respuesta.lower().strip()

        confirm_keywords = ["sí", "si", "confirmar", "yes", "ok", "correcto", "✅"]
        cancel_keywords = ["cancelar", "no", "cancel", "abortar", "❌"]

        if any(
            respuesta_lower == kw or respuesta_lower.startswith(kw + " ")
            for kw in confirm_keywords
        ):
            return {
                "response": self.generar_preview(evaluacion_anterior),
                "evaluacion": evaluacion_anterior,
                "accion": "confirmar",
            }

        if any(respuesta_lower == kw for kw in cancel_keywords):
            return {
                "response": "Registro cancelado. ¿En qué más puedo ayudarte?",
                "evaluacion": None,
                "accion": "cancelar",
            }

        return {
            "response": "Por favor proporciona los datos solicitados para continuar.",
            "evaluacion": evaluacion_anterior,
            "accion": "continuar",
        }

    def generar_mensaje_confirmacion(self) -> str:
        """Generate standard confirmation message.

        Returns:
            Confirmation message with options
        """
        return (
            "\n\n📌 **Opciones:**\n"
            "• Responde **'Confirmar'** para guardar\n"
            "• Responde **'Corregir'** para modificar algún dato\n"
            "• Responde **'Cancelar'** para descartar"
        )
