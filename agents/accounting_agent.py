"""Accounting Agent (A4) - Parse text to accounting JSON for MyFinance."""

import logging
from difflib import SequenceMatcher

from core.ai_utils import get_model_for_task
from core.config_loader import get_task_parse, ConfigLoader
from database import get_cuentas_by_user
from database.models import AsientoContable

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = float(ConfigLoader.get("UMBRAL_FUZZY_A4", "0.7"))


class AccountingAgent:
    """Agent A4: Parses text to strict accounting JSON (Pure Parser)."""

    def __init__(self):
        pass

    def _get_parse_prompt(self) -> str:
        prompt = get_task_parse()
        if not prompt:
            raise ValueError("TASK_PARSE not configured in sistema_config.")
        return prompt

    def _fuzzy_match_value(self, value: str, candidates: list[str]) -> str:
        if not value or not candidates:
            return value
        value_lower = value.lower()
        best_match, best_ratio = value, 0.0
        for candidate in candidates:
            ratio = SequenceMatcher(None, value_lower, candidate.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = candidate
        return best_match if best_ratio >= FUZZY_THRESHOLD else value

    def _apply_fuzzy_matching(self, entidades: dict, usuario_id: str = None) -> dict:
        if not usuario_id:
            return entidades
        try:
            cuentas = get_cuentas_by_user(usuario_id)
            nombres = [c.nombre for c in cuentas]
            if not nombres:
                return entidades
            res = entidades.copy()
            if res.get("origen"):
                res["origen"] = self._fuzzy_match_value(res["origen"], nombres)
            if res.get("destino"):
                res["destino"] = self._fuzzy_match_value(res["destino"], nombres)
            return res
        except Exception as e:
            logger.warning(f"Error en matching borroso (A4): {e}")
            return entidades

    def process(self, text: str, usuario_id: str = None) -> dict:
        """A4: Mapea a esquema JSON sin cuestionarlo (Regla Agente A4)."""
        model = get_model_for_task("A4")
        temp = ConfigLoader.get_temp("A4")
        logger.info(f"[A4] INPUT: '{text[:100]}...' MODEL={model} TEMP={temp}")

        try:
            from core.ai_utils import generate_json_with_retry

            result = generate_json_with_retry(
                prompt=text,
                model=model,
                temperature=temp,
                system_prompt=self._get_parse_prompt(),
                schema=AsientoContable,
            )

            entidades = result.model_dump()
            entidades = self._apply_fuzzy_matching(entidades, usuario_id)

            logger.info(f"[A4] OUTPUT: entidades={entidades}")

            return {
                "action": "PROCESAR",
                "entidades": entidades,
                "certeza": 100,  # A4 no cuestiona, asume certeza total tras validación de A3
                "es_ambiguo": False,
            }
        except Exception as e:
            logger.error(f"Error en A4 Parser: {e}")
            return {
                "action": "ERROR",
                "response": f"Error de parseo técnico: {str(e)}",
                "entidades": {},
            }

    def merge_partial_data(
        self, partial_data: dict, user_input: str, usuario_id: str = None
    ) -> dict:
        """Merge user input into partial data during interactive slot filling.

        This method is called by processor.py when user provides a correction
        or additional data during the confirmation phase.

        Args:
            partial_data: Existing partial entities from A3 evaluation
            user_input: User's response with new/corrected data
            usuario_id: User UUID for account lookups

        Returns:
            Dict with:
            - action: "PREGUNTAR" if more data needed, "PROCESAR" if complete
            - entidades: Updated entity dictionary
            - certeza: Overall certainty score
            - es_ambiguous: Whether there are ambiguities
        """
        model = get_model_for_task("A4")
        temp = ConfigLoader.get_temp("A4")
        logger.info(
            f"[A4] MERGE INPUT: partial_data={partial_data}, user_input='{user_input[:80]}...' MODEL={model} TEMP={temp}"
        )

        try:
            from core.ai_utils import generate_json_with_retry

            merge_prompt = f"""Dados los datos parciales: {partial_data}
El usuario proporciona: {user_input}

Actualiza los datos parciales con la información del usuario.
Responde solo con JSON:
{{"entidades": {{campo: valor}}, "necesita_mas": boolean}}"""

            result = generate_json_with_retry(
                prompt=merge_prompt,
                model=get_model_for_task("A4"),
                temperature=ConfigLoader.get_temp("A4"),
                system_prompt="Eres un parser de datos financieros. Responde solo JSON.",
            )

            # Handle both Pydantic model (if schema passed) and plain dict
            if hasattr(result, "model_dump"):
                updated_entities = result.model_dump().get("entidades", {})
                necesita_mas = result.model_dump().get("necesita_mas", False)
            else:
                # Plain dict returned when no schema provided
                updated_entities = result.get("entidades", {})
                necesita_mas = result.get("necesita_mas", False)

            merged = partial_data.copy()
            for key, value in updated_entities.items():
                if value:
                    merged[key] = value

            merged = self._apply_fuzzy_matching(merged, usuario_id)

            logger.info(
                f"[A4 MERGE] OUTPUT merged={merged}, necesita_mas={necesita_mas}"
            )

            return {
                "action": "PREGUNTAR" if necesita_mas else "PROCESAR",
                "entidades": merged,
                "certeza": 80 if necesita_mas else 100,
                "es_ambiguo": necesita_mas,
            }

        except Exception as e:
            logger.error(f"Error en A4 merge: {e}")
            return {
                "action": "PREGUNTAR",
                "entidades": partial_data,
                "certeza": 50,
                "es_ambiguo": True,
            }
