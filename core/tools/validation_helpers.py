"""Validation funnel for entity resolution."""

import re
from typing import Optional
from uuid import UUID


def normalizar_token(token: str) -> str:
    """Normalize a token for matching.

    Args:
        token: Raw token from user input

    Returns:
        Normalized token (lowercase, stripped, no special chars)
    """
    if not token:
        return ""
    token = token.strip()
    token = token.lower()
    token = re.sub(r"[^\w\s]", "", token)
    token = re.sub(r"\s+", " ", token)
    return token.strip()


def get_default_threshold(tipo: str) -> float:
    """Get default similarity threshold for a field type.

    Args:
        tipo: Field type (cuenta, categoria, moneda)

    Returns:
        Default threshold (0.0 - 1.0)
    """
    thresholds = {
        "cuenta": 0.70,
        "categoria": 0.65,
        "moneda": 0.85,
        "origen": 0.70,
        "destino": 0.70,
    }
    return thresholds.get(tipo, 0.70)


def format_response(
    status: str,
    fase: int,
    confidence: float = 0.0,
    uuid: Optional[str] = None,
    nombre: Optional[str] = None,
    opciones_sugeridas: Optional[list] = None,
    error: Optional[str] = None,
) -> dict:
    """Format a standard response for tool calling.

    Args:
        status: "found" or "not_found"
        fase: Phase of the funnel (1=exacta, 2=vectorial, 3=fallback)
        confidence: Match confidence (0.0 - 1.0)
        uuid: Entity UUID if found
        nombre: Entity name if found
        opciones_sugeridas: List of suggested alternatives
        error: Error message if failed

    Returns:
        Standardized response dict
    """
    response = {
        "status": status,
        "fase": fase,
        "confidence": confidence,
    }

    if uuid:
        response["uuid"] = str(uuid)
    if nombre:
        response["nombre"] = nombre
    if opciones_sugeridas:
        response["opciones_sugeridas"] = opciones_sugeridas
    if error:
        response["error"] = error

    return response
