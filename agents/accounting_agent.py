"""Accounting Agent (A4) - Pure Transformer for MyFinance 4.0.
Transforms validated entities into final accounting JSON (AsientoContable).
"""

import logging
from difflib import SequenceMatcher
from typing import Optional

from core.ai_utils import get_model_for_task
from core.config_loader import get_task_parse, ConfigLoader
from database import get_cuentas_by_user
from database.models import AsientoContable

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = float(ConfigLoader.get("UMBRAL_FUZZY_A4", "0.7"))


class AccountingAgent:
    """Agent A4: Final Transformer (Pure Mapper)."""

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

    def process(self, data_json: str, usuario_id: str = None) -> dict:
        """
        A4: Transforma un JSON de campos validados a la estructura AsientoContable final.
        Este agente ya no decide si falta información, solo mapea lo recibido.
        """
        model = get_model_for_task("A4")
        temp = ConfigLoader.get_temp("A4")
        logger.info(f"[A4] TRANSFORMING: input_len={len(data_json)} MODEL={model}")

        try:
            import json
            from core.ai_utils import generate_json_with_retry
            from database import get_categoria_by_nombre

            # 1. Enriquecer data_json con el tipo de la categoría (Ingreso vs Gasto)
            try:
                parsed_data = json.loads(data_json)
                ents = parsed_data.get("entidades", parsed_data)
                cat_val = ents.get("categoria")
                if cat_val and cat_val != "No Identificado":
                    cat = get_categoria_by_nombre(cat_val, usuario_id)
                    if cat and cat.tipo:
                        contexto = f"CONTEXTO VITAL: La categoría '{cat.nombre}' es de TIPO: '{cat.tipo}'. Aplica las reglas de Partida Doble en base a esto."
                        parsed_data["contexto_sistema"] = contexto
                        data_json = json.dumps(parsed_data)
            except Exception as e:
                logger.warning(f"[A4] Error inyectando contexto de categoría: {e}")

            # 2. Quitamos schema=AsientoContable para que Pydantic no borre los datos anidados
            result = generate_json_with_retry(
                prompt=data_json,
                model=model,
                temperature=temp,
                system_prompt=self._get_parse_prompt(),
                schema=None,  # <-- FIJAMOS EN NONE
            )

            # 2. Extraemos el bloque 'entidades' que pedimos en el prompt
            if isinstance(result, dict):
                entidades = result.get("entidades", result)  # Fallback por si lo manda plano
            else:
                logger.error("[A4] El LLM no devolvió un diccionario JSON válido.")
                raise ValueError("Formato JSON inválido")

            # 3. Aplicamos lógica de matching borroso
            entidades = self._apply_fuzzy_matching(entidades, usuario_id)

            logger.info(f"[A4] OUTPUT: {entidades}")

            return {
                "action": "PROCESAR",
                "entidades": entidades,
                "certeza": 100,
                "es_ambiguo": False,
            }
        except Exception as e:
            logger.error(f"Error en A4 Parser: {e}")
            return {
                "action": "ERROR",
                "response": f"Error de transformación técnica: {str(e)}",
                "entidades": {},
            }
