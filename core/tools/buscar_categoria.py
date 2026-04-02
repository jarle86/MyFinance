"""Tool: Buscar Categoria - Entity resolution for category lookups."""

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


def buscar_categoria(
    token: str,
    usuario_id: Optional[UUID] = None,
    threshold: Optional[float] = None,
) -> dict:
    """Search for a categoria (category) using the validation funnel.

    Searches both user categories and global system categories.

    Args:
        token: Token to search for (e.g., "Alimentación", "Food")
        usuario_id: Optional user UUID for user-specific categories
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

    umbral = threshold or get_default_threshold("categoria")

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

    opciones = _obtener_sugeridas(usuario_id)
    return format_response(
        status="not_found",
        fase=3,
        opciones_sugeridas=opciones,
    )


def _buscar_exacta(token: str, usuario_id: Optional[UUID]) -> Optional[dict]:
    """Phase 1: Exact search using ILIKE.

    Searches user categories first, then global categories.

    Args:
        token: Normalized token
        usuario_id: Optional user UUID

    Returns:
        Dict with id and nombre if found, None otherwise
    """
    if usuario_id:
        query = """
            SELECT id, nombre
            FROM categorias
            WHERE usuario_id = %s
              AND activa = TRUE
              AND LOWER(nombre) LIKE %s
            LIMIT 1
        """
        result = execute_query(
            query,
            (str(usuario_id), token),
            fetch=True,
        )
        if result:
            return result[0]

    query = """
        SELECT id, nombre
        FROM categorias
        WHERE usuario_id IS NULL
          AND activa = TRUE
          AND LOWER(nombre) LIKE %s
        LIMIT 1
    """
    result = execute_query(query, (token,), fetch=True)
    if result:
        return result[0]

    return None


def _buscar_vectorial(
    token: str, usuario_id: Optional[UUID], threshold: float
) -> Optional[dict]:
    """Phase 2: Fuzzy search for categories.

    Searches user categories first, then global categories.

    Args:
        token: Normalized token
        usuario_id: Optional user UUID
        threshold: Minimum similarity threshold

    Returns:
        Dict with id, nombre, similitud if found, None otherwise
    """
    if usuario_id:
        query = """
            SELECT id, nombre,
                   1 - (levenshtein(LOWER(nombre), %s)::float / 
                        GREATEST(LENGTH(nombre), LENGTH(%s))) as similitud
            FROM categorias
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

    query = """
        SELECT id, nombre,
               1 - (levenshtein(LOWER(nombre), %s)::float / 
                    GREATEST(LENGTH(nombre), LENGTH(%s))) as similitud
        FROM categorias
        WHERE usuario_id IS NULL
          AND activa = TRUE
        ORDER BY similitud DESC
        LIMIT 1
    """
    result = execute_query(
        query,
        (token, token),
        fetch=True,
    )

    if result and result[0].get("similitud", 0) >= threshold:
        return result[0]

    return None


def _obtener_sugeridas(usuario_id: Optional[UUID], limite: int = 10) -> list[str]:
    """Get suggested category names for fallback.

    Args:
        usuario_id: Optional user UUID
        limite: Maximum number of suggestions

    Returns:
        List of category names
    """
    if usuario_id:
        query = """
            (SELECT nombre FROM categorias WHERE usuario_id = %s AND activa = TRUE)
            UNION
            (SELECT nombre FROM categorias WHERE usuario_id IS NULL AND activa = TRUE)
            ORDER BY nombre
            LIMIT %s
        """
        result = execute_query(query, (str(usuario_id), limite), fetch=True)
    else:
        query = """
            SELECT nombre
            FROM categorias
            WHERE usuario_id IS NULL
              AND activa = TRUE
            ORDER BY nombre
            LIMIT %s
        """
        result = execute_query(query, (limite,), fetch=True)

    return [row["nombre"] for row in result] if result else []
