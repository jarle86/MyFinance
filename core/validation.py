"""Validation layer for Agent A3 - Coordinates entity resolution tools."""

import logging
from typing import Optional
from uuid import UUID

from core.tools import (
    buscar_entidad,
    buscar_cuenta,
    buscar_categoria,
    resolver_moneda,
)

logger = logging.getLogger(__name__)

CAMPO_DEFAULT_THRESHOLDS = {
    "monto_total": 70,
    "monto": 70,
    "monto_impuesto": 70,
    "monto_descuento": 70,
    "monto_otros_cargos": 70,
    "origen": 70,
    "destino": 70,
    "categoria": 70,
    "moneda": 80,
    "fecha": 70,
    "concepto": 50,
    "descripcion": None,
}


class ValidationLayer:
    """Validation layer for Agent A3 - uses Tool Calling."""

    def __init__(self, user_config: Optional[dict] = None):
        """Initialize validation layer with user config.

        Args:
            user_config: User's agent configuration (from usuarios.config)
        """
        self.user_config = user_config or {}
        self.agentes_config = self.user_config.get("agentes", {})
        self.herramientas = self.user_config.get("herramientas", {})

    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled in user config.

        Args:
            tool_name: Name of the tool

        Returns:
            True if enabled, False otherwise
        """
        return self.herramientas.get(tool_name, True)

    def get_threshold(self, campo: str) -> int:
        """Get threshold for a specific field.

        Args:
            campo: Field name (monto_total, origen, etc.)

        Returns:
            Threshold value (0-100)
        """
        a3_config = self.agentes_config.get("A3", {})
        thresholds = a3_config.get("thresholds", CAMPO_DEFAULT_THRESHOLDS)
        return thresholds.get(campo, CAMPO_DEFAULT_THRESHOLDS.get(campo, 50))

    def get_requerido(self, campo: str) -> bool:
        """Check if a field is required.

        Args:
            campo: Field name

        Returns:
            True if required, False otherwise
        """
        a3_config = self.agentes_config.get("A3", {})
        requeridos = a3_config.get("requeridos", {})
        return requeridos.get(campo, False)

    def validar_campo(
        self,
        campo: str,
        valor: str,
        usuario_id: Optional[UUID] = None,
    ) -> dict:
        """Validate a field using the validation funnel.

        Args:
            campo: Field name (origen, destino, categoria, etc.)
            valor: Value to validate
            usuario_id: User UUID for account/category lookups

        Returns:
            Dict with validation result:
            - es_valido: bool
            - certeza: int (0-100)
            - valor_resuelto: resolved value (UUID or original)
            - fase: int (1=exacta, 2=vectorial, 3=fallback)
            - pregunta: str if clarification needed
        """
        threshold = self.get_threshold(campo)
        requerido = self.get_requerido(campo)

        if not self.is_tool_enabled("buscar_entidad"):
            return {
                "es_valido": requerido and bool(valor),
                "certeza": 100 if valor else 0,
                "valor_resuelto": valor,
                "fase": 0,
                "pregunta": None,
            }

        if not valor:
            if requerido:
                return {
                    "es_valido": False,
                    "certeza": 0,
                    "valor_resuelto": None,
                    "fase": 0,
                    "pregunta": self._generar_pregunta(campo),
                }
            return {
                "es_valido": True,
                "certeza": 100,
                "valor_resuelto": None,
                "fase": 0,
                "pregunta": None,
            }

        try:
            resultado = buscar_entidad(
                tipo=campo,
                token=valor,
                usuario_id=usuario_id,
                threshold=threshold / 100.0,
            )

            if resultado["status"] == "found":
                confidence_pct = int(resultado["confidence"] * 100)
                # 🚀 EL FIX: Pasamos el UUID explícitamente y dejamos valor_resuelto para la UI
                return {
                    "es_valido": confidence_pct >= threshold,
                    "certeza": confidence_pct,
                    "valor_resuelto": resultado.get("nombre") or valor,
                    "uuid": resultado.get("uuid") or resultado.get("id"),
                    "fase": resultado.get("fase", 0),
                    "pregunta": None,
                }
            else:
                opciones = resultado.get("opciones_sugeridas", [])
                return {
                    "es_valido": False,
                    "certeza": 0,
                    "valor_resuelto": valor,
                    "fase": resultado.get("fase", 0),
                    "pregunta": self._generar_pregunta_con_opciones(campo, opciones),
                }

        except Exception as e:
            logger.error(f"Error en validación de {campo}: {e}")
            return {
                "es_valido": False,
                "certeza": 0,
                "valor_resuelto": valor,
                "fase": 0,
                "pregunta": f"Error al validar {campo}. ¿Podrías ser más específico?",
            }

    def _generar_pregunta(self, campo: str) -> str:
        """Generate clarification question for a field.

        Args:
            campo: Field name

        Returns:
            Question string
        """
        from core.config_loader import ConfigLoader
        return ConfigLoader.get_pregunta_a3(campo)

    def _generar_pregunta_con_opciones(self, campo: str, opciones: list) -> str:
        """Generate clarification question with suggested options.

        Args:
            campo: Field name
            opciones: List of suggested alternatives

        Returns:
            Question string with options
        """
        pregunta_base = self._generar_pregunta(campo)
        if opciones:
            opciones_str = ", ".join(opciones[:3])
            return f"{pregunta_base}\n\n¿Quizás meantas: {opciones_str}?"
        return pregunta_base


def crear_validation_layer(user_config: Optional[dict] = None) -> ValidationLayer:
    """Factory function to create a validation layer.

    Args:
        user_config: User's agent configuration

    Returns:
        ValidationLayer instance
    """
    return ValidationLayer(user_config)
