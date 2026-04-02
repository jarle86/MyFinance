"""Tool: Resolver Moneda - Entity resolution for currency lookups."""

import logging
from typing import Optional

from .validation_helpers import (
    normalizar_token,
    get_default_threshold,
    format_response,
)

logger = logging.getLogger(__name__)

MONEDAS_CONOCIDAS = {
    "dop": {"codigo": "DOP", "nombre": "Peso Dominicano", "simbolo": "RD$"},
    "pesos": {"codigo": "DOP", "nombre": "Peso Dominicano", "simbolo": "RD$"},
    "rd": {"codigo": "DOP", "nombre": "Peso Dominicano", "simbolo": "RD$"},
    "rd$": {"codigo": "DOP", "nombre": "Peso Dominicano", "simbolo": "RD$"},
    "usd": {"codigo": "USD", "nombre": "Dólar Estadounidense", "simbolo": "$"},
    "dolares": {"codigo": "USD", "nombre": "Dólar Estadounidense", "simbolo": "$"},
    "dollar": {"codigo": "USD", "nombre": "Dólar Estadounidense", "simbolo": "$"},
    "eur": {"codigo": "EUR", "nombre": "Euro", "simbolo": "€"},
    "euro": {"codigo": "EUR", "nombre": "Euro", "simbolo": "€"},
    "euros": {"codigo": "EUR", "nombre": "Euro", "simbolo": "€"},
    "mxn": {"codigo": "MXN", "nombre": "Peso Mexicano", "simbolo": "$"},
    "pesosmx": {"codigo": "MXN", "nombre": "Peso Mexicano", "simbolo": "$"},
    "cop": {"codigo": "COP", "nombre": "Peso Colombiano", "simbolo": "$"},
    "pesoscol": {"codigo": "COP", "nombre": "Peso Colombiano", "simbolo": "$"},
    "0p": {
        "codigo": "DOP",
        "nombre": "Peso Dominicano",
        "simbolo": "RD$",
        "alternativo": True,
    },
    "p": {
        "codigo": "DOP",
        "nombre": "Peso Dominicano",
        "simbolo": "RD$",
        "alternativo": True,
    },
    "$": {
        "codigo": "DOP",
        "nombre": "Peso (default)",
        "simbolo": "$",
        "alternativo": True,
    },
}


def resolver_moneda(
    token: str,
    default: str = "DOP",
    threshold: Optional[float] = None,
) -> dict:
    """Resolve a currency token using the validation funnel.

    Args:
        token: Token to resolve (e.g., "USD", "RD$", "0P", "dolares")
        default: Default currency if not found
        threshold: Optional custom threshold (default 0.85 for currencies)

    Returns:
        Dict with status, codigo, nombre, simbolo, confidence, fase
    """
    if not token:
        return format_response(
            status="not_found",
            fase=1,
            opciones_sugeridas=["DOP", "USD"],
            error="Token vacío",
        )

    token_limpio = normalizar_token(token)
    if not token_limpio:
        return format_response(
            status="not_found",
            fase=1,
            opciones_sugeridas=["DOP", "USD"],
            error="Token inválido después de normalización",
        )

    umbral = threshold or get_default_threshold("moneda")

    resultado = _buscar_exacta(token_limpio)
    if resultado:
        return format_response(
            status="found",
            fase=1,
            confidence=1.0,
            uuid=resultado["codigo"],
            nombre=resultado["nombre"],
            opciones_sugeridas=[default],
        )

    resultado = _buscar_fuzzy(token_limpio, umbral)
    if resultado:
        return format_response(
            status="found",
            fase=2,
            confidence=resultado["similitud"],
            uuid=resultado["codigo"],
            nombre=resultado["nombre"],
            opciones_sugeridas=[default],
        )

    opciones = list(MONEDAS_CONOCIDAS.keys())
    opciones_limpias = [
        MONEDAS_CONOCIDAS[o]["codigo"]
        for o in opciones
        if not MONEDAS_CONOCIDAS[o].get("alternativo")
    ]

    return format_response(
        status="not_found",
        fase=3,
        opciones_sugeridas=opciones_limpias[:5],
    )


def _buscar_exacta(token: str) -> Optional[dict]:
    """Phase 1: Exact match in known currencies.

    Args:
        token: Normalized token

    Returns:
        Dict with codigo, nombre, simbolo if found, None otherwise
    """
    if token in MONEDAS_CONOCIDAS:
        moneda = MONEDAS_CONOCIDAS[token]
        return {
            "codigo": moneda["codigo"],
            "nombre": moneda["nombre"],
            "simbolo": moneda["simbolo"],
        }
    return None


def _buscar_fuzzy(token: str, threshold: float) -> Optional[dict]:
    """Phase 2: Fuzzy match for currency tokens.

    Args:
        token: Normalized token
        threshold: Minimum similarity threshold

    Returns:
        Dict with codigo, nombre, simbolo, similitud if found, None otherwise
    """
    mejores_opciones = []

    for clave, moneda in MONEDAS_CONOCIDAS.items():
        if moneda.get("alternativo"):
            continue

        similitud = _calcular_similitud(token, clave)
        if similitud >= threshold:
            mejores_opciones.append(
                {
                    "codigo": moneda["codigo"],
                    "nombre": moneda["nombre"],
                    "simbolo": moneda["simbolo"],
                    "similitud": similitud,
                }
            )

    if mejores_opciones:
        mejores_opciones.sort(key=lambda x: x["similitud"], reverse=True)
        return mejores_opciones[0]

    return None


def _calcular_similitud(token1: str, token2: str) -> float:
    """Calculate simple similarity between two tokens.

    Uses character overlap and first character match.

    Args:
        token1: First token
        token2: Second token

    Returns:
        Similarity score (0.0 - 1.0)
    """
    if token1 == token2:
        return 1.0

    if token1[0] == token2[0] if token1 and token2 else False:
        base = 0.7
    else:
        base = 0.3

    overlap = sum(1 for c in token1 if c in token2)
    max_len = max(len(token1), len(token2))

    if max_len == 0:
        return base

    return base + (overlap / max_len) * 0.3
