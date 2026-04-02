"""Tool: Buscar Cuenta - Entity resolution for account lookups."""

import logging
from typing import Optional
from uuid import UUID

from database import execute_query
from .validation_helpers import (
    normalizar_token,
    get_default_threshold,
    format_response,
)

logger = logging.getLogger(__name__)


def buscar_cuenta(
    token: str,
    usuario_id: UUID,
    threshold: Optional[float] = None,
) -> dict:
    """Search for a cuenta (account) using the validation funnel.

    Args:
        token: Token to search for (e.g., "BHD", "Efectivo")
        usuario_id: User's UUID for filtering accounts
        threshold: Optional custom threshold (default from config)

    Returns:
        Dict with status, uuid, confidence, fase, opciones_sugeridas
    """
    if not token:
        return format_response(status="not_found", fase=1, error="Token vacío")

    token_limpio = normalizar_token(token)
    if not token_limpio:
        return format_response(
            status="not_found", fase=1, error="Token inválido después de normalización"
        )

    umbral = threshold or get_default_threshold("cuenta")

    resultado = _buscar_exacta(token_limpio, usuario_id)
    if resultado:
        return format_response(
            status="found",
            fase=1,
            confidence=1.0,
            uuid=resultado["id"],
            nombre=resultado["nombre"],
        )

    resultado = _buscar_vectorial(token_limpio, usuario_id, umbral)
    if resultado:
        return format_response(
            status="found",
            fase=2,
            confidence=resultado["similitud"],
            uuid=resultado["id"],
            nombre=resultado["nombre"],
        )

    opciones = _obtener_sugerencias(usuario_id)
    return format_response(
        status="not_found",
        fase=3,
        opciones_sugeridas=opciones,
    )


def _buscar_exacta(token: str, usuario_id: UUID) -> Optional[dict]:
    """Phase 1: Exact search using ILIKE.

    Args:
        token: Normalized token
        usuario_id: User UUID

    Returns:
        Dict with id and nombre if found, None otherwise
    """
    query = """
        SELECT id, nombre
        FROM cuentas
        WHERE usuario_id = %s
          AND activa = TRUE
          AND (LOWER(nombre) LIKE %s
               OR LOWER(nombre) LIKE %s
               OR LOWER(nombre) LIKE %s)
        LIMIT 1
    """
    like_exacto = token
    like_inicio = f"%{token}%"
    like_fin = f"{token}%"

    result = execute_query(
        query,
        (str(usuario_id), like_exacto, like_inicio, like_fin),
        fetch=True,
    )

    if result:
        return result[0]
    return None


def _buscar_vectorial(token: str, usuario_id: UUID, threshold: float) -> Optional[dict]:
    """Phase 2: Vectorial search using pgvector.

    Falls back to Levenshtein if pgvector not available.

    Args:
        token: Normalized token
        usuario_id: User UUID
        threshold: Minimum similarity threshold

    Returns:
        Dict with id, nombre, similitud if found, None otherwise
    """
    try:
        query = """
            SELECT id, nombre,
                   1 - (levenshtein(LOWER(nombre), %s)::float / 
                        GREATEST(LENGTH(nombre), LENGTH(%s))) as similitud
            FROM cuentas
            WHERE usuario_id = %s
              AND activa = TRUE
            ORDER BY similitud DESC
            LIMIT 1
        """
        result = execute_query(
            query,
            (token, token, str(usuario_id)),
            fetch=True,
        )

        if result and result[0].get("similitud", 0) >= threshold:
            return result[0]
    except Exception as e:
        logger.warning(f"Vectorial search failed, using fallback: {e}")

    return _buscar_fuzzy_fallback(token, usuario_id, threshold)


def _buscar_fuzzy_fallback(
    token: str, usuario_id: UUID, threshold: float
) -> Optional[dict]:
    """Fallback fuzzy search using LIKE patterns.

    Args:
        token: Normalized token
        usuario_id: User UUID
        threshold: Minimum similarity threshold

    Returns:
        Dict with id, nombre, similitud if found, None otherwise
    """
    query = """
        SELECT id, nombre
        FROM cuentas
        WHERE usuario_id = %s
          AND activa = TRUE
          AND (
            LOWER(nombre) LIKE %s
            OR LOWER(nombre) LIKE %s
            OR %s = ANY(string_to_array(LOWER(nombre), ' '))
          )
        ORDER BY LENGTH(nombre)
        LIMIT 5
    """
    like_pattern = f"%{token}%"
    tokens = token.split()

    result = execute_query(
        query,
        (str(usuario_id), like_pattern, f"{token}%", token),
        fetch=True,
    )

    for row in result:
        nombre_lower = row["nombre"].lower()
        if token in nombre_lower:
            return {"id": row["id"], "nombre": row["nombre"], "similitud": 0.8}

    if result:
        return {"id": result[0]["id"], "nombre": result[0]["nombre"], "similitud": 0.5}

    return None


def _obtener_sugerencias(usuario_id: UUID, limite: int = 5) -> list[str]:
    """Get suggested account names for fallback.

    Args:
        usuario_id: User UUID
        limite: Maximum number of suggestions

    Returns:
        List of account names
    """
    query = """
        SELECT nombre
        FROM cuentas
        WHERE usuario_id = %s
          AND activa = TRUE
        ORDER BY nombre
        LIMIT %s
    """
    result = execute_query(query, (str(usuario_id), limite), fetch=True)
    return [row["nombre"] for row in result] if result else []
