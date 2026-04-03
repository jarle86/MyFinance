"""DBA Agent (A3) - SQL generation, validation and execution for MyFinance."""

import json
from datetime import date, datetime
from decimal import Decimal
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
                            "sql": {"type": "string", "description": "Consulta SQL SELECT"},
                        },
                        "required": ["sql"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "ejecutar_transaccion_doble",
                    "description": "Registra una entrada contable de partida doble usando UUIDs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "debe_id": {"type": "string", "description": "UUID Cuenta Origen"},
                            "haber_id": {"type": "string", "description": "UUID Cuenta Destino"},
                            "monto": {"type": "number", "description": "Monto"},
                            "concepto": {"type": "string", "description": "Concepto"},
                            "fecha": {"type": "string", "description": "YYYY-MM-DD"}
                        },
                        "required": ["debe_id", "haber_id", "monto", "concepto"]
                    }
                }
            }
        ]

        try:
            logger.info(f"[A5 SQL] INPUT model='{get_model_for_task('A5')}' user_message='{user_message[:100]}...'")
            client = get_llm_client()
            message = client.generate_with_tools(
                prompt=f"Usuario ID: {user_id}\nMensaje: {user_message}",
                tools=tools,
                model=get_model_for_task("A5"),
                system_prompt=self._get_task_prompt()
            )

            if not message.tool_calls:
                logger.info(f"[A5 SQL] OUTPUT chat_response='{message.content[:50]}...'")
                return {"response": message.content, "action": "CHAT"}

            results = []
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                
                if fn_name == "ejecutar_lectura_segura":
                    res = ejecutar_lectura_segura(args["sql"])
                    results.append({"tool": fn_name, "result": res})
                elif fn_name == "ejecutar_transaccion_doble":
                    res = ejecutar_transaccion_doble(
                        usuario_id=UUID(user_id),
                        **args
                    )
                    results.append({"tool": fn_name, "result": res})

            logger.info(f"[A5 SQL] OUTPUT execution_results={results}")
            return {
                "response": "Operaciones completadas.",
                "data": results,
                "action": "SQL_SUCCESS"
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

        try:
            if not user_id:
                return {"response": "Error: usuario no identificado", "error": "no_user_id"}

            # Resolve Debe/Haber IDs (simplification for this version)
            # In double entry: 
            # - Expense: Debe = Category, Haber = Account
            # - Income: Debe = Account, Haber = Category
            
            tipo = transaction_data.get("tipo", "gasto").lower()
            monto = float(transaction_data.get("monto", 0))
            cuenta_nombre = transaction_data.get("origen") or transaction_data.get("destino")
            cat_nombre = transaction_data.get("categoria") or transaction_data.get("concepto")
            
            cuenta = get_cuenta_by_nombre(user_id, cuenta_nombre)
            categoria = get_categoria_by_nombre(cat_nombre)
            
            if not cuenta:
                return {"response": f"Cuenta '{cuenta_nombre}' no encontrada.", "error": "cuenta_not_found"}
            if not categoria:
                return {"response": f"Categoría '{cat_nombre}' no encontrada.", "error": "categoria_not_found"}
                
            if tipo == "ingreso":
                debe_id, haber_id = cuenta.id, categoria.id
            else:
                debe_id, haber_id = categoria.id, cuenta.id

            result = ejecutar_transaccion_doble(
                usuario_id=user_id,
                debe_id=debe_id,
                haber_id=haber_id,
                monto=monto,
                concepto=transaction_data.get("concepto", "Registro 4.0"),
                fecha=transaction_data.get("fecha"),
                fuente=fuente,
                proveedor=transaction_data.get("proveedor"),
                tipo=tipo
            )

            if result["status"] == "success":
                return {
                    "response": f"✅ {tipo.capitalize()} registrado: ${monto:,.2f}",
                    "data": {"id": result["id"], "monto": monto, "tipo": tipo},
                    "success": True,
                }
            elif result["status"] == "dry-run":
                return {
                    "response": f"📝 MODO DE PRUEBA: {tipo.capitalize()} de ${monto:,.2f} no guardado.",
                    "success": True
                }
            else:
                return {"response": f"Error: {result['message']}", "error": "tool_error"}

        except Exception as e:
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
