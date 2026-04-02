"""Tool: Buscar Entidad - Main orchestrator for entity resolution.

This tool is called by Agent A3 (Evaluador) when certainty < threshold.
It orchestrates the validation funnel: Exact → Vectorial → Fallback.
"""

import logging
from typing import Optional
from uuid import UUID

from .buscar_cuenta import buscar_cuenta
from .buscar_categoria import buscar_categoria
from .resolver_moneda import resolver_moneda
from .validation_helpers import format_response

logger = logging.getLogger(__name__)


TIPO_MAP = {
    "origen": "cuenta",
    "destino": "cuenta",
    "cuenta": "cuenta",
    "categoria": "categoria",
    "categoría": "categoria",
    "moneda": "moneda",
    "monto": "moneda",
    "monto_total": "moneda",
    "monto_impuesto": "moneda",
    "monto_descuento": "moneda",
    "monto_otros_cargos": "moneda",
    "fecha": "fecha",
    "concepto": "concepto",
    "descripcion": "descripcion",
}


def buscar_entidad(
    tipo: str,
    token: str,
    usuario_id: Optional[UUID] = None,
    threshold: Optional[float] = None,
) -> dict:
    """Main entity resolution tool - orchestrator for the validation funnel.

    Called by Agent A3 when certainty < threshold.

    Args:
        tipo: Field type (origen, destino, categoria, moneda, etc.)
        token: Token to resolve (e.g., "BHD", "Alimentación", "USD")
        usuario_id: User UUID for account/category lookups
        threshold: Custom threshold (uses defaults if not provided)

    Returns:
        Dict with:
        - status: "found" or "not_found"
        - fase: 1 (exacta), 2 (vectorial), 3 (fallback)
        - confidence: 0.0 - 1.0
        - uuid: Entity UUID if found (for cuenta/categoria)
        - nombre: Entity name if found
        - opciones_sugeridas: List of alternatives if not found

    Example:
        >>> buscar_entidad(tipo="origen", token="BHD", usuario_id=user_id)
        {"status": "found", "fase": 1, "confidence": 1.0, "uuid": "...", "nombre": "Banco BHD"}

        >>> buscar_entidad(tipo="categoria", token="comida", usuario_id=user_id)
        {"status": "found", "fase": 2, "confidence": 0.75, "uuid": "...", "nombre": "Alimentación"}

        >>> buscar_entidad(tipo="moneda", token="0P", usuario_id=None)
        {"status": "found", "fase": 1, "confidence": 1.0, "uuid": "DOP", "nombre": "Peso Dominicano"}
    """
    if not token:
        return format_response(
            status="not_found",
            fase=1,
            error="Token vacío",
        )

    tipo_normalizado = _normalizar_tipo(tipo)
    if not tipo_normalizado:
        return format_response(
            status="not_found",
            fase=1,
            error=f"Tipo desconocido: {tipo}",
        )

    if tipo_normalizado == "cuenta":
        return buscar_cuenta(
            token=token,
            usuario_id=usuario_id,
            threshold=threshold,
        )

    if tipo_normalizado == "categoria":
        return buscar_categoria(
            token=token,
            usuario_id=usuario_id,
            threshold=threshold,
        )

    if tipo_normalizado == "moneda":
        return resolver_moneda(
            token=token,
            default="DOP",
            threshold=threshold,
        )

    if tipo_normalizado == "fecha":
        return _resolver_fecha(token)

    if tipo_normalizado in ("concepto", "descripcion"):
        return _resolver_texto(token)

    return format_response(
        status="not_found",
        fase=1,
        error=f"Tipo no soportado para búsqueda: {tipo}",
    )


def _normalizar_tipo(tipo: str) -> Optional[str]:
    """Normalize the field type to a standard type.

    Args:
        tipo: Raw field type from A3

    Returns:
        Normalized type or None if unknown
    """
    if not tipo:
        return None

    tipo_lower = tipo.lower().strip()
    return TIPO_MAP.get(tipo_lower)


def _resolver_fecha(token: str) -> dict:
    """Resolve a date token.

    Dates are typically validated by A3's CoT evaluation,
    this is a fallback for ambiguous cases.

    Args:
        token: Date string

    Returns:
        Dict with status and resolved date
    """
    import re
    from datetime import datetime, date

    if not token:
        return format_response(
            status="not_found",
            fase=1,
            error="Token de fecha vacío",
        )

    token_clean = token.strip()

    patrones = [
        (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),
        (r"(\d{2})/(\d{2})/(\d{4})", "%d/%m/%Y"),
        (r"(\d{2})-(\d{2})-(\d{4})", "%d-%m-%Y"),
    ]

    for patron, formato in patrones:
        match = re.match(patron, token_clean)
        if match:
            try:
                fecha = datetime.strptime(token_clean, formato).date()
                return format_response(
                    status="found",
                    fase=1,
                    confidence=1.0,
                    uuid=fecha.isoformat(),
                    nombre=fecha.strftime("%d/%m/%Y"),
                )
            except ValueError:
                continue

    return format_response(
        status="not_found",
        fase=3,
        opciones_sugeridas=["hoy", "ayer", "dd/mm/aaaa"],
    )


def _resolver_texto(token: str) -> dict:
    """Resolve a text/concept token.

    Concepts and descriptions are evaluated contextually by A3,
    this returns the token as-is with low confidence.

    Args:
        token: Text string

    Returns:
        Dict with status and the original token
    """
    if not token:
        return format_response(
            status="not_found",
            fase=1,
            error="Token de texto vacío",
        )

    return format_response(
        status="found",
        fase=1,
        confidence=0.5,
        uuid=token,
        nombre=token,
    )
