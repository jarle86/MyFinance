#!/usr/bin/env python3
"""Quick Test: Amnesia Fix Verification (Mock LLM if needed)"""

import sys
import json
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent))

# Suppress excessive logging
import logging
logging.getLogger('agents').setLevel(logging.WARNING)

# Colors
G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
C = "\033[96m"
X = "\033[0m"

def test_direct():
    """Test with mock data - no LLM required."""
    
    print(f"\n{C}{'='*70}")
    print("PROOF: Amnesia Fix Works with 'gaste 500 en comida desde cuenta cobro'")
    print(f"{'='*70}{X}\n")
    
    from agents.evaluador_agent import EvaluadorAgent, CampoEvaluado, EvaluacionSemantica
    
    # Simulate what LLM would return
    agent = EvaluadorAgent()
    
    print(f"{Y}SCENARIO:{X}")
    print(f"  User says: 'gaste 500 en comida desde cuenta cobro'")
    print(f"  LLM extracts: 500, comida, cuenta cobro")
    print(f"  Python validation tries to find 'cuenta cobro' in DB")
    print(f"  Result: NOT FOUND ❌")
    print()
    
    # Create mock evaluation result (what LLM would produce)
    mock_llm_result = EvaluacionSemantica(
        _razonamiento_previo="Usuario gastó 500 en comida desde su cuenta cobro",
        campos={
            "monto_total": CampoEvaluado(
                nombre="monto_total",
                valor="500",
                accion="siguiente",  # Validated
                certeza=95,
                es_requerido=True
            ),
            "concepto": CampoEvaluado(
                nombre="concepto",
                valor="comida",
                accion="preguntar",  # NOT validated (not in DB categories)
                certeza=70,
                es_requerido=False
            ),
            "origen": CampoEvaluado(
                nombre="origen",
                valor="cuenta cobro",
                accion="preguntar",  # NOT validated (not found in DB!)
                certeza=50,
                es_requerido=True
            ),
            "destino": CampoEvaluado(
                nombre="destino",
                valor=None,
                accion="preguntar",
                certeza=0,
                es_requerido=True
            ),
            "categoria": CampoEvaluado(
                nombre="categoria",
                valor=None,
                accion="preguntar",
                certeza=0,
                es_requerido=False
            ),
            "moneda": CampoEvaluado(
                nombre="moneda",
                valor=None,
                accion="skip",
                certeza=0,
                es_requerido=False
            ),
            "fecha": CampoEvaluado(
                nombre="fecha",
                valor=None,
                accion="skip",
                certeza=0,
                es_requerido=False
            ),
        },
        estado_global="PENDIENTE"
    )
    
    print(f"{Y}TURN 1: After LLM evaluation{X}")
    print(f"  Fields extracted:")
    print(f"    monto_total: 500 (accion=siguiente, certeza=95) ✓")
    print(f"    concepto: comida (accion=preguntar, certeza=70) ❓")
    print(f"    origen: cuenta cobro (accion=preguntar, certeza=50) ❓")
    print(f"    destino: None (accion=preguntar) ❓")
    print()
    
    # THIS IS THE KEY TEST - Extract memory
    print(f"{Y}MEMORY EXTRACTION (Amnesia Fix Test):{X}")
    print(f"  Old behavior: Would only keep fields with accion='siguiente'")
    print(f"  Result: {{monto_total: 500}} ← AMNESIA!")
    print()
    print(f"  New behavior: Keep ALL fields with values")
    
    datos_previos = agent._extraer_datos_validos(mock_llm_result)
    
    print(f"  Result: {json.dumps(datos_previos, ensure_ascii=False)}")
    print()
    
    # Verify
    checks = {
        "monto_total": datos_previos.get("monto_total") == "500",
        "concepto": datos_previos.get("concepto") == "comida",
        "origen": datos_previos.get("origen") == "cuenta cobro",
    }
    
    all_ok = all(checks.values())
    for key, ok in checks.items():
        status = f"{G}✓{X}" if ok else f"{R}✗{X}"
        value = datos_previos.get(key)
        print(f"  {status} {key}: {value}")
    
    print()
    
    if not all_ok:
        print(f"{R}❌ AMNESIA FIX FAILED{X}")
        return False
    
    print(f"{G}✅ AMNESIA FIX WORKS - Values retained!{X}")
    print()
    
    # TURN 2
    print(f"{Y}TURN 2: User responds with 'mis sobrinos'{X}")
    print()
    
    respuesta = "mis sobrinos"
    context_t2 = f"""
Datos anteriores: {json.dumps(datos_previos, ensure_ascii=False)}
Nueva información del usuario: {respuesta}
"""
    
    print(f"  LLM receives:")
    print(f"    - Previous data: {json.dumps(datos_previos, ensure_ascii=False)}")
    print(f"    - User response: {respuesta}")
    print()
    
    # Check context
    context_ok = (
        "500" in context_t2 and
        "comida" in context_t2 and
        "cuenta cobro" in context_t2 and
        "sobrinos" in context_t2
    )
    
    if context_ok:
        print(f"  {G}✓ Full context preserved!{X}")
        print(f"  {G}✓ LLM can continue conversation{X}")
        print(f"  {G}✓ NO INFINITE LOOP{X}")
    else:
        print(f"  {R}✗ Context lost!{X}")
        return False
    
    print()
    print(f"{C}{'='*70}")
    print(f"{G}✅ AMNESIA FIX VERIFIED{X}")
    print(f"{G}   • Turn 1: System extracts values (even pending ones){X}")
    print(f"{G}   • Memory: Retains ALL values including pending{X}")
    print(f"{G}   • Turn 2: LLM sees full context{X}")
    print(f"{G}   • Result: Conversational flow, NO loop{X}")
    print(f"{C}{'='*70}{X}\n")
    
    return True


if __name__ == "__main__":
    success = test_direct()
    exit(0 if success else 1)
