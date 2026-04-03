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
          AND nombre ILIKE %s
        LIMIT 1
    """
    like_pattern = f"%{token}%"
    
    result = execute_query(
        query,
        (str(usuario_id), like_pattern),
        fetch=True,
    )

    if result:
        return result[0]
    return None


def _buscar_vectorial(token: str, usuario_id: UUID, threshold: float) -> Optional[dict]:
    """Phase 2: Simple similarity search (PostgreSQL compatible).

    Args:
        token: Normalized token
        usuario_id: User UUID
        threshold: Minimum similarity threshold

    Returns:
        Dict with id, nombre, similitud if found, None otherwise
    """
    # Get all accounts for this user
    query = """
        SELECT id, nombre
        FROM cuentas
        WHERE usuario_id = %s
          AND activa = TRUE
        ORDER BY LENGTH(nombre)
        LIMIT 10
    """
    result = execute_query(query, (str(usuario_id),), fetch=True)
    
    if not result:
        return None
    
    # Calculate similarity for each account
    best_match = None
    best_similarity = 0
    
    token_lower = token.lower()
    tokens = token_lower.split()  # Split into words
    
    for row in result:
        nombre_lower = row["nombre"].lower()
        
        # Check if any token is contained in nombre
        for word in tokens:
            if word in nombre_lower:
                similarity = len(word) / len(nombre_lower)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = {
                        "id": row["id"],
                        "nombre": row["nombre"],
                        "similitud": min(similarity, 1.0)
                    }
    
    if best_match and best_similarity >= threshold:
        return best_match
    
    return None


def _buscar_fuzzy_fallback(
    token: str, usuario_id: UUID, threshold: float
) -> Optional[dict]:
    """Fallback fuzzy search (SQLite compatible).

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
        ORDER BY LENGTH(nombre)
        LIMIT 5
    """
    
    result = execute_query(
        query,
        (str(usuario_id),),
        fetch=True,
    )

    if not result:
        return None

    # Find best match
    best_match = None
    token_lower = token.lower()
    
    for row in result:
        nombre_lower = row["nombre"].lower()
        # Partial match score
        if token_lower in nombre_lower:
            similarity = 0.8
            best_match = {"id": row["id"], "nombre": row["nombre"], "similitud": similarity}
            break  # Return first partial match
    
    # If no partial match, check first result
    if not best_match and result:
        best_match = {"id": result[0]["id"], "nombre": result[0]["nombre"], "similitud": 0.5}

    return best_match


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
