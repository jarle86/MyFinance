"""Accounting Agent (A4) - Parse text to accounting JSON for MyFinance."""

import logging
from difflib import SequenceMatcher

from core.ai_utils import get_model_for_task
from core.config_loader import get_task_parse 
from database import get_cuentas_by_user
from database.models import AsientoContable

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 0.7

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
        try:
            from core.ai_utils import generate_json_with_retry
            
            result = generate_json_with_retry(
                prompt=text,
                model=get_model_for_task("A4"),
                temperature=0.0,
                system_prompt=self._get_parse_prompt(),
                schema=AsientoContable
            )
            
            entidades = result.model_dump()
            entidades = self._apply_fuzzy_matching(entidades, usuario_id)
            
            return {
                "action": "PROCESAR",
                "entidades": entidades,
                "certeza": 100, # A4 no cuestiona, asume certeza total tras validación de A3
                "es_ambiguo": False
            }
        except Exception as e:
            logger.error(f"Error en A4 Parser: {e}")
            return {
                "action": "ERROR", 
                "response": f"Error de parseo técnico: {str(e)}", 
                "entidades": {}
            }