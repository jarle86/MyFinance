"""DBA Agent (A5) - SQL generation, validation and execution for MyFinance."""

import json
from datetime import date, datetime
from decimal import Decimal
import logging
from typing import Optional
from uuid import UUID

from core.config_loader import get_task_sql
from core.ai_utils import generate_json_response, get_model_for_task
from database import (
    create_transaccion,
    execute_sql,
    get_balance,
    get_cuenta_by_nombre,
    get_categoria_by_nombre,
    get_transacciones_by_user,
)

logger = logging.getLogger(__name__)


class DBAAgent:
    """Agent A3: Generates and executes SQL queries."""

    def __init__(self):
        """Initialize the DBA agent."""
        pass

    def _get_task_prompt(self) -> str:
        """Get the SQL prompt from config.

        Returns:
            Prompt from sistema_config

        Raises:
            ValueError: If TASK_SQL not configured in database
        """
        prompt = get_task_sql()

        if not prompt:
            raise ValueError(
                "TASK_SQL not configured in sistema_config. "
                "Add the prompt to the database before running."
            )

        return prompt

    def _sanitize_sql(self, sql: str, user_id: str) -> str:
        """
        Sanitize and clean LLM-generated SQL before execution.

        Removes natural language artifacts and enforces user_id filtering.

        Args:
            sql: Raw SQL from LLM
            user_id: Current user UUID as string

        Returns:
            Sanitized SQL string

        Raises:
            ValueError: If SQL contains prohibited patterns or natural language
        """
        if not sql or not isinstance(sql, str):
            raise ValueError("SQL must be a non-empty string")

        # Remove common natural language markers that might be in SQL
        natural_lang_markers = [
            "calcular",
            "obtener",
            "mostrar",
            "dame",
            "cuánto",
            "resumen",
            "total",
            "suma",
            "promedio",
            "listar",
            "dame el",
            "quiero",
            "por favor",
            "buscar",
            "encuentra",
        ]

        sql_lower = sql.lower()
        for marker in natural_lang_markers:
            if marker in sql_lower and sql_lower.find("select") == -1:
                raise ValueError(
                    f"Possible natural language in SQL: '{marker}' detected"
                )

        # Enforce user_id filtering if not present
        if "where" in sql_lower:
            if "usuario_id" not in sql_lower and f"'{user_id}'" not in sql:
                logger.warning(
                    f"[A5 sanitize] SQL has WHERE but no usuario_id filter. Appending..."
                )
                sql = sql.rstrip(";") + f" AND usuario_id = '{user_id}';"

        logger.debug(f"[A5 sanitize] SQL sanitized successfully (length: {len(sql)})")
        return sql

    def process_request(
        self,
        user_message: str,
        user_id: str,
    ) -> dict:
        """Process a request using Tool Calling for A5.

        Mandatory: Use tools for all DB operations.
        """
        from core.ai_utils import get_llm_client
        from core.tools import ejecutar_lectura_segura, ejecutar_transaccion_doble

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "ejecutar_lectura_segura",
                    "description": "Consulta SELECT para ver balances, cuentas o transacciones.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "sql": {
                                "type": "string",
                                "description": "Consulta SQL SELECT",
                            },
                        },
                        "required": ["sql"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "ejecutar_transaccion_doble",
                    "description": "Registra una entrada contable de partida doble usando UUIDs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "debe_id": {
                                "type": "string",
                                "description": "UUID Cuenta Origen",
                            },
                            "haber_id": {
                                "type": "string",
                                "description": "UUID Cuenta Destino",
                            },
                            "monto": {"type": "number", "description": "Monto"},
                            "concepto": {"type": "string", "description": "Concepto"},
                            "fecha": {"type": "string", "description": "YYYY-MM-DD"},
                        },
                        "required": ["debe_id", "haber_id", "monto", "concepto"],
                    },
                },
            },
        ]

        try:
            logger.info(
                f"[A5 SQL] INPUT model='{get_model_for_task('A5')}' user_message='{user_message[:100]}...'"
            )
            client = get_llm_client()
            message = client.generate_with_tools(
                prompt=f"Usuario ID: {user_id}\nMensaje: {user_message}",
                tools=tools,
                model=get_model_for_task("A5"),
                system_prompt=self._get_task_prompt(),
            )

            if not message.tool_calls:
                logger.info(
                    f"[A5 SQL] OUTPUT chat_response='{message.content[:50]}...'"
                )
                return {"response": message.content, "action": "CHAT"}

            results = []
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                if fn_name == "ejecutar_lectura_segura":
                    try:
                        # Clean and validate SQL before execution
                        sql_query = args.get("sql", "")
                        sql_cleaned = self._sanitize_sql(sql_query, user_id)
                        logger.debug(
                            f"[A5 execute_tool] Cleaned SQL: {sql_cleaned[:100]}"
                        )

                        res = ejecutar_lectura_segura(sql_cleaned)
                        results.append({"tool": fn_name, "result": res})
                    except ValueError as e:
                        logger.warning(f"[A5 execute_tool] SQL validation error: {e}")
                        results.append({"tool": fn_name, "error": str(e)})
                    except Exception as e:
                        logger.error(f"[A5 execute_tool] Execution error: {e}")
                        results.append({"tool": fn_name, "error": str(e)})

                elif fn_name == "ejecutar_transaccion_doble":
                    try:
                        res = ejecutar_transaccion_doble(
                            usuario_id=UUID(user_id), **args
                        )
                        results.append({"tool": fn_name, "result": res})
                    except Exception as e:
                        logger.error(f"[A5 execute_tool] Transaction error: {e}")
                        results.append({"tool": fn_name, "error": str(e)})

            logger.info(f"[A5 SQL] OUTPUT execution_results={results}")
            return {
                "response": "Operaciones completadas.",
                "data": results,
                "action": "SQL_SUCCESS",
            }

        except Exception as e:
            logger.error(f"Error procesando A5 Tool Call: {e}")
            return {"response": f"Error técnico: {str(e)}", "action": "ERROR"}

    def validate_and_execute(
        self,
        transaction_data: dict,
        user_id: Optional[UUID] = None,
        fuente: str = "web",
    ) -> dict:
        """Validate and execute a transaction using Core Tools.

        Args:
            transaction_data: Dict with transaction details
            user_id: User UUID
            fuente: Source channel

        Returns:
            Dict with execution result
        """
        from core.tools import ejecutar_transaccion_doble
        from database import get_cuenta_by_nombre, get_categoria_by_nombre

        logger.info(
            f"[A5] INPUT: transaction_data={transaction_data} user_id={user_id} fuente={fuente}"
        )

        try:
            if not user_id:
                return {
                    "response": "Error: usuario no identificado",
                    "error": "no_user_id",
                }

            # Resolve Debe/Haber IDs (simplification for this version)
            # In double entry:
            # - Expense: Debe = Category, Haber = Account
            # - Income: Debe = Account, Haber = Category

            # 🚀 EL FIX: Priorizar monto_total y manejar correctamente los None
            tipo = transaction_data.get("tipo", "gasto").lower()
            
            monto_raw = transaction_data.get("monto_total") or transaction_data.get("monto")
            monto = float(monto_raw) if monto_raw is not None else 0.0
            
            # 🚀 EL FIX DEFINITIVO PARA LOS UUIDs
            import uuid

            def extract_uuid(val):
                if not val: return None
                try:
                    return str(uuid.UUID(str(val)))
                except ValueError:
                    return None

            origen_val = transaction_data.get("origen")
            destino_val = transaction_data.get("destino")
            cat_val = transaction_data.get("categoria") or transaction_data.get("descripcion")

            # 1. Resolver Cuentas (Origen y Destino)
            origen_id = extract_uuid(origen_val)
            if not origen_id:
                c = get_cuenta_by_nombre(user_id, origen_val)
                if c:
                    origen_id = str(c.id)

            destino_id = extract_uuid(destino_val)
            if not destino_id:
                c = get_cuenta_by_nombre(user_id, destino_val)
                if c:
                    destino_id = str(c.id)

            # 2. Resolver Categoría ID (opcional para la lógica contable estricta, pero se guarda)
            cat_id = extract_uuid(cat_val)
            if not cat_id and cat_val:
                cat = get_categoria_by_nombre(cat_val, user_id)
                if cat:
                    cat_id = str(cat.id)
                    # REGLA ORO: Heredar el tipo de la categoría en lugar de defaulting a "gasto"
                    if cat.tipo:
                        tipo = cat.tipo.lower()

            # 3. Validar que tenemos ambas cuentas (Debe y Haber)
            if not origen_id:
                logger.warning(f"[A5] Error: Cuenta de Origen '{origen_val}' no resuelta.")
                return {
                    "response": f"Error: Cuenta de Origen '{origen_val}' no encontrada.",
                    "error": "origen_not_found",
                }
            if not destino_id:
                logger.warning(f"[A5] Error: Cuenta de Destino '{destino_val}' no resuelta.")
                return {
                    "response": f"Error: Cuenta de Destino '{destino_val}' no encontrada.",
                    "error": "destino_not_found",
                }

            # 4. Asignar Partida Doble: Origen (Haber) -> Destino (Debe) para gastos
            if tipo == "ingreso":
                debe_id, haber_id = origen_id, destino_id
            else:
                debe_id, haber_id = destino_id, origen_id

            result = ejecutar_transaccion_doble(
                usuario_id=user_id,
                debe_id=debe_id,
                haber_id=haber_id,
                monto=monto,
                concepto=transaction_data.get("concepto") or transaction_data.get("descripcion") or "Registro 4.0",
                fecha=transaction_data.get("fecha"),
                fuente=fuente,
                proveedor=transaction_data.get("proveedor"),
                tipo=tipo,
            )

            if result["status"] == "success":
                logger.info(
                    f"[A5] OUTPUT: success tx_id={result.get('id')} monto={monto} tipo={tipo}"
                )
                return {
                    "response": f"✅ {tipo.capitalize()} registrado: ${monto:,.2f}",
                    "data": {"id": result["id"], "monto": monto, "tipo": tipo},
                    "success": True,
                }
            elif result["status"] == "dry-run":
                logger.info(f"[A5] OUTPUT: dry-run modo prueba monto={monto}")
                return {
                    "response": f"📝 MODO DE PRUEBA: {tipo.capitalize()} de ${monto:,.2f} no guardado.",
                    "success": True,
                }
            else:
                logger.warning(f"[A5] OUTPUT: error {result.get('message')}")
                return {
                    "response": f"Error: {result['message']}",
                    "error": "tool_error",
                }

        except Exception as e:
            logger.error(f"[A5] ERROR: {str(e)}")
            return {"response": f"Error al registrar: {str(e)}", "error": str(e)}

    def check_balance(self, user_message: str, user_id: Optional[UUID] = None) -> dict:
        """Check user balance using secure reading tool."""
        from core.tools import ejecutar_lectura_segura

        try:
            sql = f"SELECT nombre, saldo_actual FROM cuentas WHERE usuario_id = '{str(user_id)}' AND activa = TRUE"
            cuentas = ejecutar_lectura_segura(sql)

            response = "🏦 Tus balances actuales:\n"
            for c in cuentas:
                response += f"- {c['nombre']}: ${c['saldo_actual']:,.2f}\n"

            return {"response": response, "data": cuentas}

        except Exception as e:
            return {"response": f"Error al obtener balance: {str(e)}", "error": str(e)}
