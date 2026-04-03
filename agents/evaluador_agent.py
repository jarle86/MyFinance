"""Agente A3 - Evaluador Semántico for MyFinance.

Evaluates coherence of data before JSON parsing. Uses Tool Calling for entity resolution.
"""

import json
import logging
from typing import Optional
from uuid import UUID

from pydantic import BaseModel
from typing import Literal

from core.ai_utils import generate_json_response, get_model_for_task
from core.config_loader import get_task_evaluate
from core.validation import CAMPO_DEFAULT_THRESHOLDS

logger = logging.getLogger(__name__)


class CampoEvaluado(BaseModel):
    """Evaluated field with certainty and action."""

    nombre: str
    valor: Optional[str] = None
    certeza: int = 0
    es_requerido: bool = False
    accion: Literal["skip", "siguiente", "preguntar"] = "preguntar"
    pregunta: Optional[str] = None


class EvaluacionSemantica(BaseModel):
    """Complete semantic evaluation result."""

    _razonamiento_previo: str
    campos: dict[str, CampoEvaluado]
    estado_global: Literal["COMPLETADO", "PENDIENTE"]
    preguntas_agrupadas: Optional[str] = None


class EvaluadorAgent:
    """Agent A3: Semantic Evaluator with Tool Calling."""

    CAMPOS_EVALUACION = [
        "monto_total",
        "monto",
        "monto_impuesto",
        "monto_descuento",
        "monto_otros_cargos",
        "origen",
        "destino",
        "categoria",
        "moneda",
        "fecha",
        "concepto",
        "descripcion",
    ]

    CAMPOS_REQUERIDOS_DEFAULT = ["monto_total", "origen", "destino"]

    def __init__(
        self,
        user_config: Optional[dict] = None,
        usuario_id: Optional[UUID] = None,
    ):
        """Initialize the evaluator agent.

        Args:
            user_config: User's agent configuration from usuarios.config
            usuario_id: User UUID for entity lookups
        """
        self.user_config = user_config or {}
        self.usuario_id = usuario_id

    def _get_task_prompt(self) -> str:
        """Get the TASK_EVALUATE prompt from config."""
        prompt = get_task_evaluate()
        if not prompt:
            raise ValueError(
                "TASK_EVALUATE not configured in sistema_config. "
                "Add the prompt to the database before running."
            )
        return prompt

    def _get_model_config(self) -> tuple[str, float, int, int]:
        """Get model configuration from user config or defaults.

        Returns:
            Tuple of (model, temperature, max_tokens, timeout)
        """
        from core.config_loader import ConfigLoader
        
        model = ConfigLoader.get_model("A3") or "qwen2.5-coder:7b"
        temp = ConfigLoader.get_temp("A3")
        tokens = ConfigLoader.get_tokens("A3")
        timeout = ConfigLoader.get_timeout("A3")

        return model, temp, tokens, timeout

    def evaluar(self, texto: str) -> EvaluacionSemantica:
        """Evaluate text for registration."""
        try:
            prompt = f"Texto a evaluar:\n{texto}"
            model, temp, tokens, _ = self._get_model_config()
            logger.info("[A3 EVALUAR] Inicio de evaluación A3", extra={"texto_corto": texto[:100], "model": model})

            from core.ai_utils import generate_json_with_retry
            
            result = generate_json_with_retry(
                prompt=prompt,
                model=model,
                temperature=temp,
                max_tokens=tokens,
                system_prompt=self._get_task_prompt(),
                schema=None
            )

            logger.info(
                "[A3 EVALUAR] RAW LLM JSON keys=%s estado_global=%s entidades=%s",
                list(result.keys()),
                result.get("estado_global"),
                list(result.get("entidades", result.get("campos", {})).keys()),
            )

            evaluacion = self._procesar_resultado_llm(result, texto)
            logger.info(
                f"[A3 EVALUAR] OUTPUT estado_global='{evaluacion.estado_global}' "
                f"campos_pendientes={[k for k,v in evaluacion.campos.items() if v.accion=='preguntar']} "
                f"campos_completados={[k for k,v in evaluacion.campos.items() if v.accion=='siguiente']}"
            )
            return evaluacion

        except Exception as e:
            logger.error(f"[A3 EVALUAR] ERROR: {e}", exc_info=True)
            return self._crear_evaluacion_error(str(e))

    def _procesar_resultado_llm(
        self, result: dict, texto_original: str
    ) -> EvaluacionSemantica:
        """Process LLM response and run validation funnel.

        Args:
            result: Response from LLM with extracted fields
            texto_original: Original user text

        Returns:
            EvaluacionSemantica with validated fields
        """
        # Extract using "campos" (new prompt) or "entidades" (legacy)
        entidades_raw = result.get("campos", result.get("entidades", {}))
        razonamiento = result.get("_razonamiento_previo", "")

        campos_eval = {}
        preguntas = []

        for campo_nombre in self.CAMPOS_EVALUACION:
            # LLM now returns nested dicts per field
            # E.g. "monto_total": {"valor": 500, "certeza": 95, "accion": "siguiente"}
            datos_del_campo = entidades_raw.get(campo_nombre, {})
            
            # Extract actual value for validator
            valor_extraido = datos_del_campo.get("valor") if isinstance(datos_del_campo, dict) else datos_del_campo
            # Convert to string for consistency with CampoEvaluado model
            valor_extraido = str(valor_extraido) if valor_extraido is not None else None
            
            # Extract pre-calculated certeza from LLM to avoid redundant calls
            certeza_llm = None
            if isinstance(datos_del_campo, dict) and "certeza" in datos_del_campo:
                certeza_llm = int(datos_del_campo.get("certeza", 0))
            
            campo_eval = self._evaluar_campo(
                nombre=campo_nombre,
                valor=valor_extraido,
                texto_original=texto_original,
                certeza_precalculada=certeza_llm,
            )
            campos_eval[campo_nombre] = campo_eval

            logger.debug(
                "[A3 campo] %s => valor=%s, certeza=%s, accion=%s",
                campo_nombre,
                campo_eval.valor,
                campo_eval.certeza,
                campo_eval.accion,
            )

            if campo_eval.accion == "preguntar" and campo_eval.pregunta:
                preguntas.append(campo_eval.pregunta)

        estado = self._determinar_estado_global(campos_eval)

        logger.info(
            "[A3 resumen] estado_global=%s preguntas=%s campos_pendientes=%s",
            estado,
            preguntas,
            [k for k,v in campos_eval.items() if v.accion == "preguntar"],
        )

        preguntas_agrupadas = self._agrupar_preguntas(preguntas) if preguntas else None

        return EvaluacionSemantica(
            _razonamiento_previo=razonamiento,
            campos=campos_eval,
            estado_global=estado,
            preguntas_agrupadas=preguntas_agrupadas,
        )

    def _evaluar_campo(
        self,
        nombre: str,
        valor: Optional[str],
        texto_original: str,
        certeza_precalculada: Optional[int] = None,
    ) -> CampoEvaluado:
        """Evaluate a single field using CoT + Tool Calling.

        Args:
            nombre: Field name
            valor: Extracted value from LLM
            texto_original: Original text for context
            certeza_precalculada: Pre-calculated certainty from LLM (optimization)

        Returns:
            CampoEvaluado with evaluation results
        """
        es_requerido = self._es_campo_requerido(nombre)
        threshold = self._get_threshold(nombre)

        logger.debug(
            "[A3 _evaluar_campo] Iniciando campo=%s valor=%s requerido=%s",
            nombre,
            valor,
            es_requerido,
        )

        if not valor:
            if es_requerido:
                pregunta = self._generar_pregunta(nombre)
                logger.warning(
                    "[A3 _evaluar_campo] Campo requerido faltante %s -> preguntar",
                    nombre,
                )
                return CampoEvaluado(
                    nombre=nombre,
                    valor=None,
                    certeza=0,
                    es_requerido=True,
                    accion="preguntar",
                    pregunta=pregunta,
                )
            logger.info(
                "[A3 _evaluar_campo] Campo opcional faltante %s -> skip",
                nombre,
            )
            return CampoEvaluado(
                nombre=nombre,
                valor=None,
                certeza=100,
                es_requerido=False,
                accion="skip",
                pregunta=None,
            )

        # Use pre-calculated certainty from LLM or fallback to CoT
        if certeza_precalculada is not None:
            certeza = certeza_precalculada
            logger.debug(
                "[A3 _evaluar_campo] Usando certeza del LLM para campo=%s: %s",
                nombre,
                certeza,
            )
        else:
            logger.warning(
                "[A3 _evaluar_campo] Fallback CoT para campo=%s (no pre-calculated)",
                nombre,
            )
            certeza = self._evaluar_certeza(nombre, valor, texto_original)

        logger.debug(
            "[A3 _evaluar_campo] Campo=%s certeza=%s threshold=%s",
            nombre,
            certeza,
            threshold,
        )

        # Decision based on semantic certainty
        if certeza >= threshold:
            return CampoEvaluado(
                nombre=nombre,
                valor=valor,
                certeza=certeza,
                es_requerido=es_requerido,
                accion="siguiente",
                pregunta=None,
            )

        return CampoEvaluado(
            nombre=nombre,
            valor=valor,
            certeza=certeza,
            es_requerido=es_requerido,
            accion="preguntar",
            pregunta=self._generar_pregunta(nombre),
        )

    def _evaluar_certeza(self, campo: str, valor: str, texto: str) -> int:
        """Evaluate certainty using CoT (Chain of Thought).

        Args:
            campo: Field name
            valor: Value to evaluate
            texto: Original text for context

        Returns:
            Certainty score (0-100)
        """
        try:
            prompt = f"""
Campo: {campo}
Valor extraído: {valor}
Texto original: {texto}

Evalúa la certeza de que este valor es correcto.
Responde solo con un número entre 0 y 100.
"""
            modelA3, tempA3, _, _ = self._get_model_config()
            result = generate_json_response(
                prompt=prompt,
                model=modelA3,
                temperature=tempA3,
                max_tokens=10,
                system_prompt="Eres un evaluador de certeza. Responde solo con un JSON con el campo 'certeza'.",
            )

            certeza = int(result.get("certeza", 50))
            return max(0, min(100, certeza))

        except Exception as e:
            logger.warning(f"Error evaluando certeza para {campo}: {e}")
            return 50

    def _es_campo_requerido(self, campo: str) -> bool:
        """Check if a field is required for this user."""
        agentes = self.user_config.get("agentes", {})
        a3_config = agentes.get("A3", {})
        requeridos = a3_config.get("requeridos", {})

        if campo in requeridos:
            return requeridos[campo]

        return campo in self.CAMPOS_REQUERIDOS_DEFAULT

    def _get_threshold(self, campo: str) -> int:
        """Get threshold for a field."""
        return CAMPO_DEFAULT_THRESHOLDS.get(campo, 70)

    def _determinar_estado_global(
        self, campos: dict[str, CampoEvaluado]
    ) -> Literal["COMPLETADO", "PENDIENTE"]:
        """Determine global state based on all fields.

        Args:
            campos: Dictionary of evaluated fields

        Returns:
            "COMPLETADO" if all required fields are valid, "PENDIENTE" otherwise
        """
        for campo in campos.values():
            if campo.es_requerido and campo.accion == "preguntar":
                logger.info(
                    "[A3 _determinar_estado_global] Pendiente encontrado en campo %s",
                    campo.nombre,
                )
                return "PENDIENTE"

        logger.info("[A3 _determinar_estado_global] Todos los campos requeridos completados")
        return "COMPLETADO"

    def _generar_pregunta(self, campo: str) -> str:
        """Generate clarification question for a field."""
        from core.config_loader import ConfigLoader
        return ConfigLoader.get_pregunta_a3(campo)

    def _agrupar_preguntas(self, preguntas: list[str]) -> str:
        """Group multiple questions into one clear message."""
        if not preguntas:
            return None

        if len(preguntas) == 1:
            return preguntas[0]

        preguntas_formateadas = [f"- {p}" for p in preguntas]
        return "Faltan algunos datos:\n" + "\n".join(preguntas_formateadas)

    def _crear_evaluacion_error(self, error: str) -> EvaluacionSemantica:
        """Create an evaluation result for error cases."""
        campos = {}
        for nombre in self.CAMPOS_EVALUACION:
            es_req = nombre in self.CAMPOS_REQUERIDOS_DEFAULT
            campos[nombre] = CampoEvaluado(
                nombre=nombre,
                valor=None,
                certeza=0,
                es_requerido=es_req,
                accion="preguntar" if es_req else "skip",
                pregunta=f"Error: {error}",
            )

        return EvaluacionSemantica(
            _razonamiento_previo=f"Error en evaluación: {error}",
            campos=campos,
            estado_global="PENDIENTE",
            preguntas_agrupadas=f"Error al procesar. Por favor intenta de nuevo.",
        )

    def re_evaluar(
        self, respuesta_usuario: str, evaluacion_anterior: EvaluacionSemantica
    ) -> EvaluacionSemantica:
        """Re-evaluate after user response in interactive mode.

        Args:
            respuesta_usuario: User's response to clarification questions
            evaluacion_anterior: Previous evaluation state

        Returns:
            New EvaluacionSemantica with updated fields
        """
        texto_combinado = f"""
Datos anteriores: {json.dumps(self._extraer_datos_validos(evaluacion_anterior))}
Nueva información del usuario: {respuesta_usuario}
"""
        logger.info(
            "[A3 re_evaluar] Re-evaluar con respuesta_usuario=%s, datos_previos=%s",
            respuesta_usuario,
            self._extraer_datos_validos(evaluacion_anterior),
        )
        return self.evaluar(texto_combinado)

    def _extraer_datos_validos(self, evaluacion: EvaluacionSemantica) -> dict:
        """Extrae TODOS los valores capturados, válidos o no, para mantener la memoria.
        
        IMPORTANTE: No filtrar por accion=="siguiente" porque eso causa amnesia.
        El LLM necesita VER los valores previos aunque Python aún no los haya validado.
        """
        datos = {}
        for nombre, campo in evaluacion.campos.items():
            # Si el campo tiene un valor, lo pasamos a la memoria (aunque sea para corregirlo)
            if campo.valor:
                datos[nombre] = campo.valor
        return datos
