"""Main processor for routing inputs to the appropriate agents."""

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import UUID

from database import get_or_create_user, update_user_access, get_user_by_id
from agents.accounting_agent import AccountingAgent
from agents.dba_agent import DBAAgent
from agents.clasificador_agent import ClasificadorAgent
from agents.chat_agent import ChatAgent
from agents.evaluador_agent import EvaluadorAgent
from core.validation import ValidationLayer
from core.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class Route(str, Enum):
    """Processing routes."""

    A = "A"  # Chat/Asesoría
    B = "B"  # SQL Query
    C = "C"  # Image (OCR)
    D = "D"  # Text Registration
    E = "E"  # Direct Execution
    F = "F"  # Authorization
    G = "G"  # Humanizer
    X = "X"  # System Command / Escape


@dataclass
class ProcessResult:
    """Result of processing an input."""

    route: Route
    response: str
    data: Optional[dict] = None
    action: Optional[str] = None  # PREGUNTAR, PROCESAR, etc.


class MessageType(str, Enum):
    """Types of user input."""

    TEXT = "text"
    IMAGE = "image"
    PDF = "pdf"
    COMMAND = "command"


class Processor:
    """Main processor that routes inputs to appropriate agents."""

    def __init__(
        self, user_config: Optional[dict] = None, usuario_id: Optional[UUID] = None
    ):
        """Initialize the processor with agents.

        Args:
            user_config: User's agent configuration from usuarios.config
            usuario_id: User UUID for entity lookups
        """
        self._user_context: dict = {}
        self._user_config = user_config or {}
        self._usuario_id = usuario_id

        try:
            self.accounting = AccountingAgent()
            self.dba = DBAAgent()
            self.clasificador = ClasificadorAgent()
            self.chat = ChatAgent(user_config=self._user_config)
            self.evaluador = EvaluadorAgent(
                user_config=self._user_config, usuario_id=self._usuario_id
            )
            self.validation = ValidationLayer(user_config=self._user_config)
            logger.info("✅ Processor initialized with all agents")
        except Exception as e:
            logger.error(f"❌ Error initializing Processor agents: {e}", exc_info=True)

    def set_user_config(self, user_config: dict, usuario_id: UUID):
        """Set user configuration after initialization.

        Args:
            user_config: User's agent configuration
            usuario_id: User UUID
        """
        self._user_config = user_config
        self._usuario_id = usuario_id
        self.chat = ChatAgent(user_config=user_config)
        self.evaluador = EvaluadorAgent(user_config=user_config, usuario_id=usuario_id)

    def process(
        self,
        message: str,
        message_type: MessageType = MessageType.TEXT,
        telegram_id: Optional[int] = None,
        user_id: Optional[UUID] = None,
        channel: str = "web",
        topic_id: Optional[UUID] = None,
    ) -> ProcessResult:
        """Process a message and return the result.

        Args:
            message: The user's message or file path
            message_type: Type of input (text, image, pdf, command)
            telegram_id: Optional Telegram user ID (for Telegram channel)
            user_id: Optional internal user UUID (for web/api channels)
            channel: Channel identifier ('telegram', 'web', 'api')
            topic_id: Optional topic UUID for chat context

        Returns:
            ProcessResult with route and response
        """
        # Get or create user
        user = None
        if user_id is None and telegram_id:
            try:
                user = get_or_create_user(telegram_id)
                user_id = user.id
                update_user_access(telegram_id)
            except Exception as e:
                logger.warning(
                    f"Could not create user from telegram_id {telegram_id}: {e}"
                )
                return ProcessResult(
                    route=Route.A,
                    response="Error: No se pudo identificar al usuario. Intenta más tarde.",
                )

        if not user_id:
            return ProcessResult(
                route=Route.A,
                response="Error: Usuario no identificado.",
            )

        # Route based on message type and content
        if message_type == MessageType.IMAGE:
            logger.info(f"[PIPELINE] ROUTE=C image={message[:50]}")
            return self._process_image(message, user_id, channel)
        elif message_type == MessageType.PDF:
            logger.info(f"[PIPELINE] ROUTE=C pdf={message[:50]}")
            return self._process_pdf(message, user_id, channel)
        elif message_type == MessageType.COMMAND:
            logger.info(f"[PIPELINE] ROUTE=X command={message}")
            return self._process_command(message)
        else:
            return self._process_text(message, user, user_id, channel, topic_id)

    def _process_document(
        self, path: str, doc_type: str, user_id: Optional[UUID], channel: str
    ) -> ProcessResult:
        """Unified document processing (image/PDF → OCR → A3 → A4 → A5)."""
        from agents.ocr_agent import OCRAgent

        ocr_agent = OCRAgent()

        if doc_type == "pdf":
            result = ocr_agent.process_pdf(path)
        else:
            result = ocr_agent.process(path)

        if not result.get("ocr_completed"):
            return ProcessResult(
                route=Route.C,
                response=result.get("response", f"No se pudo procesar {doc_type}"),
                data=result,
            )

        ocr_data = result.get("data", {})
        texto_extraido = self._generar_texto_desde_ocr(ocr_data)

        logger.info(f"[PIPELINE] ROUTE=C OCR→A3 texto='{texto_extraido[:60]}...'")
        evaluacion = self.evaluador.evaluar(texto_extraido)

        # Python Validation Layer (ALWAYS executed - A3 output is just a suggestion)
        # Python validates, infers, resolves entities, and determines final state
        logger.info(
            f"[PIPELINE] VALIDATION A3→PYTHON estado={evaluacion.estado_global}"
        )
        evaluacion = self._validar_entidades_python(evaluacion, user_id)
        logger.info(f"[PIPELINE] VALIDATION COMPLETE estado={evaluacion.estado_global}")

        if evaluacion.estado_global == "PENDIENTE":
            pregunta = self.chat.agrupar_preguntas(evaluacion)
            return ProcessResult(
                route=Route.C,
                response=pregunta,
                data={"evaluacion": evaluacion.model_dump(), "ocr_data": ocr_data},
                action="PREGUNTAR",
            )

        # Generar Preview y Solicitar Confirmación
        preview = self._generar_preview(evaluacion)

        if user_id:
            from database import (
                create_pending_conversation,
                get_pending_conversation,
                update_pending_conversation,
            )

            # Combinar datos de evaluación y OCR para persistencia
            datos_para_confirmar = evaluacion.model_dump()
            datos_para_confirmar["ocr_data"] = ocr_data

            # Extract actual missing fields for metadata
            campos_faltantes = [
                nombre
                for nombre, campo in evaluacion.campos.items()
                if campo.accion == "preguntar"
            ]

            create_pending_conversation(
                usuario_id=user_id,
                canal=channel,
                datos_parciales=datos_para_confirmar,
                pregunta_actual=preview,
                ruta_anterior="C",
                ultimo_mensaje=texto_extraido[:50] + "...",
                datos_faltantes=campos_faltantes,
                estado="esperando_confirmacion",
            )

        confirmation_hint = "\n\n📌 Responde **'Confirmar'** para guardar o **'Cancelar'** para descartar."
        return ProcessResult(
            route=Route.C,
            response=preview + confirmation_hint,
            data={"evaluacion": evaluacion.model_dump(), "ocr_data": ocr_data},
            action="CONFIRMAR",
        )

    def _generar_texto_desde_ocr(self, ocr_data: dict) -> str:
        """Generate text from OCR data for evaluation.

        Args:
            ocr_data: Dictionary with extracted OCR data

        Returns:
            Formatted text for A3 evaluation
        """
        texto = []
        if ocr_data.get("monto"):
            texto.append(f"Monto: {ocr_data['monto']}")
        if ocr_data.get("fecha"):
            texto.append(f"Fecha: {ocr_data['fecha']}")
        if ocr_data.get("proveedor"):
            texto.append(f"Proveedor: {ocr_data['proveedor']}")
        if ocr_data.get("categoria"):
            texto.append(f"Categoría: {ocr_data['categoria']}")
        return "\n".join(texto) if texto else "Sin datos"

    def _evaluacion_a_transaction_data(self, evaluacion, ocr_data: dict) -> dict:
        """Convert A3 evaluation to transaction data for A5.

        Args:
            evaluacion: EvaluacionSemantica from A3
            ocr_data: Original OCR data

        Returns:
            Transaction data dict for DBA agent
        """
        datos = {}
        for nombre, campo in evaluacion.campos.items():
            if campo.valor and campo.accion == "siguiente":
                datos[nombre] = campo.valor

        if not datos and ocr_data:
            datos = ocr_data

        return datos

    def _validar_entidades_python(self, evaluacion, user_id: Optional[UUID]) -> any:
        """Capa de Validación Determinista con Inferencia de Consumo."""

        campos = evaluacion.campos

        # 1. LOOP DE VALIDACIÓN CONTRA DB
        for nombre in ["origen", "destino", "categoria"]:
            campo = campos.get(nombre)
            if not campo:
                continue


            if not campo.valor:
                continue

        # 1.1 Resolución de Fecha Relativa (hoy)
        fecha = campos.get("fecha")
        if fecha and (not fecha.valor or "hoy" in str(fecha.valor).lower()):
            from datetime import date
            fecha.valor = date.today().isoformat()
            fecha.certeza = 100
            fecha.accion = "siguiente"
            logger.info(f"📅 [PYTHON VALIDATION] Fecha resuelta como hoy: {fecha.valor}")

            # Búsqueda en DB (Fuzzy/Alias/Exacta)
            resultado = self.validation.validar_campo(
                campo=nombre, valor=campo.valor, usuario_id=user_id
            )

            if resultado["es_valido"]:
                # ÉXITO: Actualizamos con el nombre oficial y guardamos el UUID en metadata
                campo.valor = str(resultado["valor_resuelto"])
                campo.certeza = 100
                campo.accion = "siguiente"
                campo.metadata = {"uuid": resultado.get("uuid")}
            else:
                # FALLO: No encontrado en DB
                # Bajar certeza para forzar revisión/pregunta
                logger.warning(
                    f"[PYTHON VALIDATION] {nombre}='{campo.valor}' not found in DB."
                )
                campo.certeza = max(10, campo.certeza - 40)
                
                # Siempre obligamos a preguntar si no está en DB oficial, 
                # para que el Agente o el usuario lo resuelvan.
                campo.accion = "preguntar"
                evaluacion.estado_global = "PENDIENTE"

        # 2. VERIFICACIÓN DE REQUERIDOS (Hard-Check)
        # Monto es obligatorio
        monto = campos.get("monto_total")
        if not monto or not monto.valor or monto.valor == 0:
            monto.accion = "preguntar"
            evaluacion.estado_global = "PENDIENTE"
        
        # Si todo es "siguiente" pero hay algo pendiente de ID, no debería ser completado
        # Pero por ahora confiamos en que 'preguntar' gatillará A6.

        return evaluacion

    def _process_image(
        self, image_path: str, user_id: Optional[UUID], channel: str
    ) -> ProcessResult:
        """Process an image (Route C)."""
        return self._process_document(image_path, "imagen", user_id, channel)

    def _process_pdf(
        self, pdf_path: str, user_id: Optional[UUID], channel: str
    ) -> ProcessResult:
        """Process a PDF (Route C)."""
        return self._process_document(pdf_path, "pdf", user_id, channel)

    def _process_command(self, command: str) -> ProcessResult:
        """Process a command."""
        command_lower = command.lower().strip()

        if command_lower in ["/start", "/help"]:
            return ProcessResult(
                route=Route.A,
                response=self._get_help_message(),
            )
        elif command_lower == "/status":
            return ProcessResult(
                route=Route.B,
                response="Función de balance en desarrollo",
            )
        elif command_lower == "/cancel":
            return ProcessResult(
                route=Route.A,
                response="Operación cancelada. ¿En qué puedo ayudarte?",
            )
        else:
            return ProcessResult(
                route=Route.A,
                response=f"Comando no reconocido: {command}\n\n{self._get_help_message()}",
            )

    def _handle_slot_filling(
        self,
        pending_conv,
        text: str,
        user_id: Optional[UUID],
    ) -> ProcessResult:
        """Handle slot filling phase with intelligent merge and checklist generation."""
        from agents.accounting_agent import AccountingAgent
        from database import update_pending_conversation

        text_lower = text.lower().strip()

        partial_data = (
            pending_conv.datos
            if isinstance(pending_conv.datos, dict)
            else json.loads(pending_conv.datos or "{}")
        )

        confirm_keywords_simple = [
            "sí",
            "si",
            "correcto",
            "yes",
            "así es",
            "asi es",
            "confirmar",
        ]

        es_confirm_simple = text_lower in confirm_keywords_simple

        if pending_conv.dato_faltante == "confirmacion_explicita" and es_confirm_simple:
            logger.debug("Loop prevention: confirmacion_explicita + respuesta simple")
            return self._transition_to_confirmation(
                pending_conv, {"entidades": partial_data}
            )

        # 1. Extraer nuevas entidades de la respuesta del usuario usando A3
        # Esto mantiene la inteligencia del LLM para entender qué dijo el usuario ahora
        eval_actual = self.evaluador.evaluar(text)
        
        # 2. Validar esas nuevas entidades (para resolver UUIDs, normalizar montos, etc.)
        python_res = self._validar_entidades_python(eval_actual)
        
        # 3. Fusionar determinísticamente en el estado parcial
        # Los nuevos campos con valor sobreescriben los anteriores (o llenan huecos)
        nuevas_entidades = python_res.get("entidades", {})
        for k, v in nuevas_entidades.items():
            if v is not None:
                partial_data[k] = v
        
        # 4. Re-evaluar el estado GLOBAL fusionado
        # Pasamos el JSON fusionado por el validador final (basado en lo que ya tenemos)
        resultado_global = self._validar_entidades_python(
            evaluacion_previa=None, # Forzamos re-validación base desde el dict
            entidades_manual=partial_data
        )
        
        entidades_finales = resultado_global.get("entidades", {})
        estado_global = resultado_global.get("estado_global", "PENDIENTE")

        # 5. Manejo de Intentos
        if pending_conv.intentos >= 4:
            from database import cancel_pending_conversation
            cancel_pending_conversation(pending_conv.id)
            return ProcessResult(
                route=Route.D,
                response="⚠️ Límite de intentos alcanzado. Registro cancelado.",
                action="CANCELADO",
            )

        # 6. Decidir siguiente paso basado en el Valencia de Validación (No en A4)
        if estado_global == "PENDIENTE":
            campo_faltante = resultado_global.get("campo_faltante")
            pregunta = ConfigLoader.get_pregunta_a3(campo_faltante)
            
            update_pending_conversation(
                pending_conv.id,
                datos=entidades_finales,
                intentos=pending_conv.intentos + 1,
                estado="preguntando",
                pregunta_actual=pregunta,
                dato_faltante=campo_faltante,
                ultimo_mensaje=text
            )

            checklist = self._generate_checklist(entidades_finales)
            respuesta_final = f"{checklist}\n👉 {pregunta}"

            return ProcessResult(
                route=Route.D,
                response=respuesta_final,
                data=resultado_global,
                action="PREGUNTAR",
            )

        # 7. Si está COMPLETADO, transformamos con A4 para el formato final y confirmamos
        # Aquí A4 solo hace el mapeo técnico a AsientoContable
        final_transform = self.accounting.process(
            json.dumps(entidades_finales, ensure_ascii=False),
            usuario_id=str(user_id) if user_id else None
        )
        
        return self._transition_to_confirmation(pending_conv, final_transform)

    def _transition_to_confirmation(
        self, pending_conv, merge_result: dict
    ) -> ProcessResult:
        """Transition from slot filling to confirmation phase."""
        from agents.accounting_agent import AccountingAgent
        from database import update_pending_conversation

        preview = self.accounting._format_preview(merge_result.get("entidades", {}))

        fuzzy_match_info = ""
        if merge_result.get("fuzzy_match_used"):
            fuzzy_match_info = (
                f"\n\n💡 *Nota:* Se usaron coincidencias fuzzy para algunos campos."
            )

        update_pending_conversation(
            pending_conv.id,
            datos=merge_result.get("entidades", {}),
            estado="esperando_confirmacion",
            pregunta_actual=preview,
        )

        confirmation_hint = "\n\n📌 Responde **'Confirmar'** para guardar o **'Cancelar'** para descartar."

        return ProcessResult(
            route=Route.D,
            response=preview + fuzzy_match_info + confirmation_hint,
            data=merge_result.get("entidades"),
            action="CONFIRMAR",
        )

    def _generate_checklist(self, entidades: dict) -> str:
        """Generate visual checklist with ✅/❌ status."""
        nombres = {
            "monto_total": "Monto",
            "origen": "Origen",
            "destino": "Destino",
            "fecha": "Fecha",
            "categoria": "Categoría",
            "moneda": "Moneda",
        }
        checklist = "📝 **Completando datos:**\n"
        for campo in [
            "monto_total",
            "origen",
            "destino",
            "fecha",
            "categoria",
            "moneda",
        ]:
            valor = entidades.get(campo)
            if valor:
                checklist += f"✅ {nombres.get(campo, campo)}: {valor}\n"
            else:
                checklist += f"❌ {nombres.get(campo, campo)}: *Pendiente*\n"
        return checklist

    def _generar_preview(self, evaluacion) -> str:
        """Generate preview from A3 evaluation.

        Args:
            evaluacion: EvaluacionSemantica from A3

        Returns:
            Formatted preview message
        """
        return self.chat.generar_preview(evaluacion)

    def _process_text(
        self,
        text: str,
        user,
        user_id: Optional[UUID],
        channel: str,
        topic_id: Optional[UUID],
    ) -> ProcessResult:
        """Process text input (Routes A, B, D, F)."""
        import json
        import re

        from agents.accounting_agent import AccountingAgent
        from agents.chat_agent import ChatAgent
        from agents.clasificador_agent import ClasificadorAgent
        from agents.dba_agent import DBAAgent
        from database import (
            cancel_pending_conversation,
            complete_pending_conversation,
            create_pending_conversation,
            get_pending_conversation,
            update_pending_conversation,
        )

        text_lower = text.lower().strip()

        # Detection keywords for correction mode
        correction_keywords = [
            "corregir",
            "cambiar",
            "mal",
            "error",
            "arregla",
            "ta mal",
            "equivocado",
        ]
        is_correction = any(kw in text_lower for kw in correction_keywords)

        # 1. ESCAPE HATCH (Configurable keywords)
        keywords_str = ConfigLoader.get_keywords_escape()
        cancel_keywords = [k.strip().lower() for k in keywords_str.split(",")]

        is_cancel = any(
            text_lower == kw or text_lower.startswith(kw + " ")
            for kw in cancel_keywords
        )

        pending_conv = None
        if user_id:
            try:
                pending_conv = get_pending_conversation(user_id, channel)
            except Exception:
                pass

        # 2. MÁQUINA DE ESTADOS: FASE DE CONFIRMACIÓN
        if pending_conv and pending_conv.estado == "esperando_confirmacion":
            if is_cancel:
                cancel_pending_conversation(pending_conv.id)
                return ProcessResult(
                    route=Route.X,
                    response="❌ Operación detenida por comando de sistema. ¿En qué puedo ayudarte?",
                )

            if is_correction:
                update_pending_conversation(
                    pending_conv.id,
                    estado="preguntando",
                    pregunta_actual="¿Qué dato deseas corregir?",
                    dato_faltante=["correccion"],
                )
                return ProcessResult(
                    route=Route.D,
                    response="🔄 Entendido. ¿Qué dato deseas corregir?\n\n"
                    + self._generate_checklist(
                        pending_conv.datos
                        if isinstance(pending_conv.datos, dict)
                        else json.loads(pending_conv.datos or "{}")
                    ),
                    data={"datos": pending_conv.datos, "mode": "correccion"},
                    action="CORREGIR",
                )

            confirm_keywords = [
                "confirmar",
                "confirm",
                "si",
                "sí",
                "yes",
                "✅",
                "aprobar",
                "aceptar",
            ]
            is_confirm = any(
                text_lower == kw or f" {kw}" in text_lower or text_lower.endswith(kw)
                for kw in confirm_keywords
            )

            if is_confirm:
                transaction_data = (
                    pending_conv.datos
                    if isinstance(pending_conv.datos, dict)
                    else json.loads(pending_conv.datos or "{}")
                )

                # 🚀 EL FIX: Aplanar el diccionario para extraer solo los valores útiles
                datos_limpios = {}
                if "campos" in transaction_data:
                    for nombre, info in transaction_data["campos"].items():
                        if info.get("valor") is not None:
                            # Priorizamos el UUID guardado por Python Validation, si no, usamos el valor
                            meta_uuid = info.get("metadata", {}).get("uuid") if info.get("metadata") else None
                            datos_limpios[nombre] = meta_uuid if meta_uuid else info.get("valor")
                else:
                    datos_limpios = transaction_data

                # A4: Final Parser JSON (Pure record mapping)
                logger.info(
                    f"[PIPELINE] A4 PARSE INPUT datos_limpios={list(datos_limpios.keys())}"
                )
                
                # Le enviamos los datos limpios y aplanados al Agente A4
                parsing_result = self.accounting.process(
                    json.dumps(datos_limpios),
                    usuario_id=str(pending_conv.usuario_id),
                )

                final_json = parsing_result.get("entidades", {})
                logger.info(
                    f"[PIPELINE] A4 PARSE OUTPUT entities={list(final_json.keys())}"
                )

                try:
                    logger.info(
                        f"[PIPELINE] A5 DB_EXECUTE INPUT user_id={pending_conv.usuario_id}"
                    )
                    db_result = self.dba.validate_and_execute(
                        final_json,
                        user_id=pending_conv.usuario_id,
                        fuente=channel,
                    )
                    logger.info(
                        f"[PIPELINE] A5 DB_EXECUTE OUTPUT status={db_result.get('success')}"
                    )

                    if db_result.get("error"):
                        update_pending_conversation(
                            pending_conv.id,
                            estado="preguntando",
                            pregunta_actual=f"Error: {db_result.get('error')}. ¿Qué dato deseas corregir?",
                            dato_faltante=["correccion"],
                        )
                        return ProcessResult(
                            route=Route.D,
                            response=f"⚠️ Error al guardar: {db_result.get('error')}\n\n"
                            + self._generate_checklist(transaction_data)
                            + "\n¿Qué dato deseas corregir?",
                            data={
                                "datos": transaction_data,
                                "error": db_result.get("error"),
                            },
                            action="CORREGIR",
                        )

                    complete_pending_conversation(pending_conv.id, "completada")
                    logger.info(
                        f"[PIPELINE] TX_COMPLETED id={pending_conv.id} action=PROCESAR"
                    )

                    response = self.chat.humanize(
                        db_result.get("response", "Registrado exitosamente")
                    )
                    logger.info(f"[PIPELINE] A6 HUMANIZE OUTPUT '{response[:60]}...'")
                    return ProcessResult(
                        route=Route.D,
                        response=response,
                        data=db_result.get("data"),
                        action="PROCESAR",
                    )
                except Exception as e:
                    logger.error(f"[PIPELINE] TX_ERROR: {str(e)}")
                    update_pending_conversation(
                        pending_conv.id,
                        estado="preguntando",
                        pregunta_actual="Error inesperado. ¿Qué dato deseas corregir?",
                        dato_faltante="correccion",
                    )
                    return ProcessResult(
                        route=Route.D,
                        response=f"⚠️ Error inesperado: {str(e)}\n\n"
                        + self._generate_checklist(transaction_data)
                        + "\n¿Qué dato deseas corregir?",
                        data={"datos": transaction_data, "error": str(e)},
                        action="CORREGIR",
                    )
            else:
                return ProcessResult(
                    route=Route.D,
                    response=f"Tienes un registro en espera. Por favor responde 'Confirmar' o 'Cancelar'.\n\n{pending_conv.pregunta_actual}",
                    data={"datos": pending_conv.datos},
                    action="CONFIRMAR",
                )

        # 3. MÁQUINA DE ESTADOS: FASE INTERACTIVA (SLOT FILLING)
        if pending_conv and pending_conv.estado in ("preguntando", "iniciada"):
            if is_cancel:
                cancel_pending_conversation(pending_conv.id)
                return ProcessResult(
                    route=Route.A, response="❌ Conversación cancelada."
                )

            if pending_conv.intentos >= 4:
                cancel_pending_conversation(pending_conv.id)
                return ProcessResult(
                    route=Route.D,
                    response="⚠️ Límite de intentos alcanzado. Registro cancelado.",
                    action="CANCELADO",
                )

            partial_data = (
                pending_conv.datos
                if isinstance(pending_conv.datos, dict)
                else json.loads(pending_conv.datos or "{}")
            )

            from agents.evaluador_agent import EvaluacionSemantica

            try:
                # Load previous valid inputs matching Pydantic structure
                if "estado_global" in partial_data:
                    eval_anterior = EvaluacionSemantica(**partial_data)
                else:
                    eval_anterior = EvaluacionSemantica(
                        _razonamiento_previo="", campos={}, estado_global="PENDIENTE"
                    )
            except Exception as e:
                logger.error(f"Error parsing EvaluacionSemantica: {e}")
                eval_anterior = EvaluacionSemantica(
                    _razonamiento_previo="", campos={}, estado_global="PENDIENTE"
                )

            # Mismo Evaluador re-evalua los nuevos inputs
            logger.debug(
                "[Modo interactivo] Re-evaluando datos: %s",
                {"texto": text, "previo": eval_anterior.model_dump()},
            )
            eval_nueva = self.evaluador.re_evaluar(text, eval_anterior)

            logger.info(
                "[Modo interactivo] Resultado A3 estado_global=%s, campos_pendientes=%s",
                eval_nueva.estado_global,
                [
                    nombre
                    for nombre, v in eval_nueva.campos.items()
                    if v.accion == "preguntar"
                ],
            )

            # Python Validation Layer (ALWAYS executed - A3 output is just a suggestion)
            # Python is the boss: validates, infers, and can override LLM state
            eval_nueva = self._validar_entidades_python(eval_nueva, user_id)
            logger.info(
                "[Modo interactivo] Validación Python de entidades completada: estado_global=%s, campos_pendientes=%s",
                eval_nueva.estado_global,
                [
                    nombre
                    for nombre, v in eval_nueva.campos.items()
                    if v.accion == "preguntar"
                ],
            )

            if eval_nueva.estado_global == "PENDIENTE":
                pregunta = (
                    self.chat.agrupar_preguntas(eval_nueva)
                    or "¿Puedes darme los datos que faltan?"
                )

                # Extract actual missing fields for metadata
                campos_faltantes = [
                    nombre
                    for nombre, campo in eval_nueva.campos.items()
                    if campo.accion == "preguntar"
                ]

                update_pending_conversation(
                    pending_conv.id,
                    datos=eval_nueva.model_dump(),
                    intentos=pending_conv.intentos + 1,
                    estado="preguntando",
                    pregunta_actual=pregunta,
                    dato_faltante=campos_faltantes or ["general"],
                )

                return ProcessResult(
                    route=Route.D,
                    response=pregunta,
                    data={"evaluacion": eval_nueva.model_dump()},
                    action="PREGUNTAR",
                )
            else:
                entidades = {
                    nombre: campo.valor
                    for nombre, campo in eval_nueva.campos.items()
                    if campo.valor
                }

                preview = self._generar_preview(eval_nueva)

                update_pending_conversation(
                    pending_conv.id,
                    datos=eval_nueva.model_dump(),
                    estado="esperando_confirmacion",
                    pregunta_actual=preview,
                )

                confirmation_hint = "\n\n📌 Responde **'Confirmar'** para guardar o **'Cancelar'** para descartar."
                return ProcessResult(
                    route=Route.D,
                    response=preview + confirmation_hint,
                    data=entidades,
                    action="CONFIRMAR",
                )

        # 4. FLUJO NORMAL (NUEVO REGISTRO / MENSAJE)
        if any(
            re.search(rf"\b{kw}\b", text_lower)
            for kw in ["aprobar", "rechazar", "pendiente"]
        ):
            return ProcessResult(
                route=Route.F,
                response="Función de autorización en desarrollo",
            )

        try:
            intent = self.clasificador.classify(text)
        except Exception as e:
            logger.error(f"Error en Clasificador Agent (A1): {e}")
            fallback_response = self.chat.chat(
                "Error técnico en clasificación. Pide al usuario que por favor repita su mensaje."
            )
            return ProcessResult(
                route=Route.A,
                response=fallback_response
                or "Lo siento, tuve un problema al procesar tu solicitud. ¿Podrías repetirla?",
                action="FALLBACK",
            )

        logger.info(f"[PIPELINE] A1 INPUT='{text[:80]}' → OUTPUT_INTENT='{intent}'")

        if intent == "registro":
            logger.info(f"[PIPELINE] A3 EVALUADOR INPUT='{text[:80]}'")
            evaluu_raw = self.evaluador.evaluar(text)
            logger.info(
                f"[PIPELINE] A3 EVALUADOR OUTPUT estado_global='{evaluu_raw.estado_global}' campos_pendientes={[k for k, v in evaluu_raw.campos.items() if v.accion == 'preguntar']}"
            )

            # Python Validation Layer (ALWAYS executed - A3 output is just a suggestion)
            # Python validates, infers, resolves entities, and determines final state
            evaluacion = self._validar_entidades_python(evaluu_raw, user_id)
            logger.info(
                f"[PIPELINE] PYTHON_VALIDATION OUTPUT estado_global='{evaluacion.estado_global}' campos_pendientes={[k for k, v in evaluacion.campos.items() if v.accion == 'preguntar']}"
            )

            if evaluacion.estado_global == "PENDIENTE":
                logger.info(
                    f"[PIPELINE] A6 agrupar_preguntas INPUT campos_pendientes={[k for k, v in evaluacion.campos.items() if v.accion == 'preguntar']}"
                )
                pregunta = (
                    self.chat.agrupar_preguntas(evaluacion)
                    or "¿Podrías darme más detalles de la transacción?"
                )
                logger.info(f"[PIPELINE] A6 agrupar_preguntas OUTPUT='{pregunta[:80]}'")

                if user_id:
                    # Extract actual missing fields for metadata
                    campos_faltantes = [
                        nombre
                        for nombre, campo in evaluacion.campos.items()
                        if campo.accion == "preguntar"
                    ]

                    create_pending_conversation(
                        usuario_id=user_id,
                        canal=channel,
                        datos_parciales=evaluacion.model_dump(),
                        pregunta_actual=pregunta,
                        ruta_anterior="D",
                        ultimo_mensaje=text,
                        datos_faltantes=campos_faltantes,
                        estado="preguntando",
                    )

                return ProcessResult(
                    route=Route.D,
                    response=pregunta,
                    data={"evaluacion": evaluacion.model_dump()},
                    action="PREGUNTAR",
                )

            entidades = {
                nombre: campo.valor
                for nombre, campo in evaluacion.campos.items()
                if campo.valor
            }

            preview = self._generar_preview(evaluacion)

            if user_id:
                # Extract actual missing fields for metadata
                campos_faltantes = [
                    nombre
                    for nombre, campo in evaluacion.campos.items()
                    if campo.accion == "preguntar"
                ]

                create_pending_conversation(
                    usuario_id=user_id,
                    canal=channel,
                    datos_parciales=evaluacion.model_dump(),
                    pregunta_actual=preview,
                    ruta_anterior="D",
                    ultimo_mensaje=text,
                    datos_faltantes=campos_faltantes,
                    estado="esperando_confirmacion",
                )

                confirmation_hint = "\n\n📌 Responde **'Confirmar'** para guardar o **'Cancelar'** para descartar."
                return ProcessResult(
                    route=Route.D,
                    response=preview + confirmation_hint,
                    data=entidades,
                    action="CONFIRMAR",
                )

        elif intent == "consulta":
            # Migración a A5 Tool Calling
            result = self.dba.process_request(text, user_id=str(user_id))

            if result.get("action") == "SQL_SUCCESS":
                data = result.get("data", [])
                response = self.chat.humanize(
                    f"He consultado la base de datos: {json.dumps(data)}"
                )
            else:
                response = self.chat.humanize(
                    result.get("response", "No encontré resultados.")
                )

            return ProcessResult(route=Route.B, response=response, data=result)

        else:
            try:
                response = self.chat.chat(text)
                if not response or not response.strip():
                    response = "Estoy aquí para ayudarte con tus finanzas. ¿Qué necesitas registrar o consultar?"
                return ProcessResult(route=Route.A, response=response)
            except Exception as e:
                logger.error(
                    f"❌ Error crítico en ChatAgent (A6): {str(e)}", exc_info=True
                )
                return ProcessResult(
                    route=Route.A,
                    response="Lo siento, tuve un problema técnico con mi motor de lenguaje. ¿Podrías intentar de nuevo en un momento?",
                )

    def process_with_chat_history(
        self,
        message: str,
        message_type: MessageType = MessageType.TEXT,
        user_id: Optional[UUID] = None,
        channel: str = "web",
        topic_id: Optional[UUID] = None,
    ) -> tuple[ProcessResult, Optional[UUID]]:
        """Process message and save to chat history.

        Returns:
            Tuple of (ProcessResult, new_topic_id if created)
        """
        from database import (
            create_chat_message,
            create_chat_topic,
            get_or_create_default_topic,
            get_topic_title_suggestion,
            prune_old_messages,
        )

        new_topic_created = None

        # Get or create topic
        if topic_id is None:
            if user_id:
                topic = get_or_create_default_topic(user_id, channel)
                topic_id = topic.id
            else:
                return (
                    ProcessResult(
                        route=Route.A,
                        response="Error: usuario no identificado",
                    ),
                    None,
                )

        # Save user message
        if user_id and topic_id:
            try:
                create_chat_message(
                    topic_id=topic_id,
                    canal=channel,
                    role="user",
                    content=message,
                    route=None,
                )
            except Exception:
                pass  # Don't fail if chat history fails

        # Process the message
        result = self.process(
            message=message,
            message_type=message_type,
            user_id=user_id,
            channel=channel,
            topic_id=topic_id,
        )

        # Save assistant response
        if user_id and topic_id:
            try:
                create_chat_message(
                    topic_id=topic_id,
                    canal=channel,
                    role="assistant",
                    content=result.response,
                    route=result.route.value,
                )

                # Update topic title if first message
                messages_count = 0
                from database import get_chat_messages_by_topic

                try:
                    msgs = get_chat_messages_by_topic(topic_id, channel, limit=2)
                    messages_count = len(msgs)
                except Exception:
                    pass

                if messages_count == 2:  # Just added second message (first was user)
                    # Generate title from first user message
                    title = get_topic_title_suggestion(message)
                    from database import update_chat_topic_title

                    try:
                        update_chat_topic_title(topic_id, title)
                    except Exception:
                        pass

                # Prune old messages (keep last 500)
                try:
                    prune_old_messages(topic_id, channel, 500)
                except Exception:
                    pass

            except Exception:
                pass  # Don't fail if chat history fails

        return result, new_topic_created

    def _get_help_message(self) -> str:
        """Get help message."""
        return """¡Bienvenido a MyFinance! 💰

    Puedo ayudarte con:

    📝 **Registrar gastos**
    "Pagué $500 en taxi"
    "Gasté 200 en supermercado"

    💰 **Consultar saldo**
    "¿Cuánto gasté este mes?"
    "¿Cuál es mi balance?"

    📊 **Ver reportes**
    "Dame un reporte de febrero"

    📷 **Procesar receipts**
    "Envía una imagen de tu ticket"

    Comandos:
    /status - Ver estado de cuenta
    /cancel - Cancelar operación
    /help - Ver esta ayuda

    ¿En qué puedo ayudarte?"""

    def get_user_context(self, telegram_id: int) -> dict:
        """Get user context for conversation state."""
        return self._user_context.get(telegram_id, {})

    def set_user_context(self, telegram_id: int, context: dict) -> None:
        """Set user context for conversation state."""
        self._user_context[telegram_id] = context


# Singleton processor
processor = Processor()


def get_processor() -> Processor:
    """Get the processor singleton."""
    return processor
