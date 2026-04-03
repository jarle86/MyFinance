"""Database tools for Agent A5 (DBA) - Tool Calling Implementation.

Provides strict read and write operations with transactional safety.
"""

import logging
from typing import Any, Optional
from uuid import UUID

from database.base_queries import get_db_connection
from core.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


def ejecutar_lectura_segura(
    sql: str, params: Optional[tuple] = None
) -> list[dict[str, Any]]:
    """Execute a read-only SQL query safely with strict validation.

    Args:
        sql: SELECT query string.
        params: Query parameters.

    Returns:
        List of result rows as dicts.

    Raises:
        ValueError: If query violates security rules.
    """
    if not sql or not isinstance(sql, str):
        raise ValueError("SQL query must be a non-empty string")

    sql_clean = sql.strip()
    sql_upper = sql_clean.upper()

    # 1. Only allow SELECT and WITH (CTEs)
    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        logger.warning(
            f"[SECURITY] Query does not start with SELECT/WITH: {sql_clean[:50]}"
        )
        raise ValueError("Only SELECT or WITH queries are allowed in lectura_segura")

    # 2. Forbid dangerous keywords (mutating queries + dangerous functions)
    forbidden_patterns = [
        "DROP",
        "DELETE",
        "UPDATE",
        "INSERT",
        "ALTER",
        "TRUNCATE",
        "CREATE",
        "EXEC",
        "EXECUTE",
        "SCRIPT",
        "xp_",
        "sp_",
    ]
    for pattern in forbidden_patterns:
        if f" {pattern} " in f" {sql_upper} " or sql_upper.startswith(f"{pattern} "):
            logger.warning(
                f"[SECURITY] Forbidden keyword '{pattern}' in query: {sql_clean[:50]}"
            )
            raise ValueError(
                f"SQL keyword '{pattern}' is not allowed in read-only queries"
            )

    # 3. Warn if query contains natural language (non-SQL tokens)
    natural_lang_markers = [
        "calcular",
        "obtener",
        "mostrar",
        "dame",
        "cuánto",
        "total",
        "resumen",
    ]
    for marker in natural_lang_markers:
        if marker in sql_upper:
            logger.warning(
                f"[SECURITY] Possible natural language in SQL: '{marker}' found"
            )

    logger.info(f"[ejecutar_lectura_segura] Ejecutando query: {sql_clean[:80]}")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_clean, params)
                columns = (
                    [desc[0] for desc in cur.description] if cur.description else []
                )
                result = [dict(zip(columns, row)) for row in cur.fetchall()]
                logger.info(f"[ejecutar_lectura_segura] Resultado: {len(result)} filas")
                return result
    except Exception as e:
        logger.error(f"[ejecutar_lectura_segura] Error: {e}")
        raise e


def ejecutar_transaccion_doble(
    usuario_id: UUID,
    debe_id: UUID,
    haber_id: UUID,
    monto: float,
    concepto: str,
    fecha: str = None,
    fuente: str = "web",
    proveedor: Optional[str] = None,
    tipo: str = "registro",
) -> dict[str, Any]:
    """Execute an accounting double entry transaction with ACID safety.

    Args:
        usuario_id: User UUID owner.
        debe_id: Debit account/category UUID.
        haber_id: Credit account/category UUID.
        monto: Transaction amount.
        concepto: Description/Concept.
        fecha: YYYY-MM-DD string.
        fuente: Source channel.
        proveedor: Provider/Supplier name.
        tipo: 'gasto', 'ingreso', 'transparencia'.

    Returns:
        Dict with status and transaction ID.
    """
    if not ConfigLoader.get_permitir_escritura_db():
        logger.warning(
            f"DRY-RUN: Intento de escritura bloqueado por PERMITIR_ESCRITURA_DB"
        )
        return {
            "status": "dry-run",
            "message": "Escritura deshabilitada en configuración",
        }

    from datetime import date

    if not fecha:
        fecha = date.today().isoformat()

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. Start explicit transaction
                cur.execute("BEGIN;")

                # 2. Insert transaction record
                insert_query = """
                    INSERT INTO transacciones (
                        usuario_id, tipo, monto, fecha, naturaleza,
                        debe_id, haber_id, descripcion, fuente, proveedor, estado
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                # Naturaleza: True for income, False for expense
                naturaleza = tipo.lower() == "ingreso"

                cur.execute(
                    insert_query,
                    (
                        str(usuario_id),
                        tipo,
                        monto,
                        fecha,
                        naturaleza,
                        str(debe_id),
                        str(haber_id),
                        concepto,
                        fuente,
                        proveedor,
                        "confirmado",
                    ),
                )

                tx_row = cur.fetchone()
                if not tx_row:
                    raise Exception("Failed to insert transaction")
                tx_id = tx_row[0]

                # 3. Update account balances (with usuario_id for Zero Trust)
                cur.execute(
                    "UPDATE cuentas SET saldo_actual = saldo_actual + %s WHERE id = %s AND usuario_id = %s",
                    (monto, str(debe_id), str(usuario_id)),
                )
                cur.execute(
                    "UPDATE cuentas SET saldo_actual = saldo_actual - %s WHERE id = %s AND usuario_id = %s",
                    (monto, str(haber_id), str(usuario_id)),
                )

                # 4. Commit everything
                conn.commit()
                return {"status": "success", "id": str(tx_id)}

    except Exception as e:
        logger.error(f"Error en transaccion_doble (ACID Rollback): {e}")
        return {"status": "error", "message": str(e)}
