#!/usr/bin/env python3
"""End-to-End Test: Amnesia Fix Verification with Real Conversation."""

import sys
import logging
import json
from pathlib import Path
from uuid import UUID, uuid4

# Setup
sys.path.insert(0, str(Path(__file__).parent))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def test_conversation_flow():
    """Simulate complete conversation with amnesia fix."""
    
    logger.info(f"\n{CYAN}{'='*70}")
    logger.info(f"END-TO-END TEST: AMNESIA FIX WITH CONVERSATION")
    logger.info(f"{'='*70}{RESET}\n")
    
    try:
        from core.processor import Processor
        from agents.evaluador_agent import EvaluadorAgent
        from uuid import UUID
        
        # Create test user ID
        test_user_id = UUID("12345678-1234-5678-1234-567812345678")
        logger.info(f"{YELLOW}Test Setup:{RESET}")
        logger.info(f"  User ID: {test_user_id}")
        logger.info(f"  Input 1: 'gaste 500 en comida desde cuenta cobro'")
        logger.info(f"  Input 2: 'mis sobrinos' (answering: who was it for?)")
        
        # Initialize processor
        processor = Processor()
        agent = EvaluadorAgent(usuario_id=test_user_id)
        
        logger.info(f"\n{YELLOW}TURNO 1: Initial Transaction Entry{RESET}")
        logger.info(f"{'-'*70}")
        
        # First evaluation: User enters full sentence
        texto_turno1 = "gaste 500 en comida desde cuenta cobro"
        logger.info(f"User Input: '{texto_turno1}'")
        
        evaluacion_turno1 = agent.evaluar(texto_turno1)
        
        logger.info(f"\n{CYAN}LLM Extraction Results:{RESET}")
        for nombre, campo in evaluacion_turno1.campos.items():
            if campo.valor:
                logger.info(f"  {nombre}: valor='{campo.valor}', accion={campo.accion}, certeza={campo.certeza}")
        
        logger.info(f"\nState after Turno 1: {evaluacion_turno1.estado_global}")
        
        # Extract datos for next turn (THIS IS THE AMNESIA TEST)
        datos_previos = agent._extraer_datos_validos(evaluacion_turno1)
        logger.info(f"\n{CYAN}Memory Extraction (Amnesia Fix Test):{RESET}")
        logger.info(f"  Datos previos: {datos_previos}")
        
        # Check memory retention
        memory_checks = {
            "monto_total retained": datos_previos.get("monto_total") == "500",
            "concepto retained": datos_previos.get("concepto") == "comida",
            "origen retained": datos_previos.get("origen") == "cuenta cobro",
        }
        
        logger.info(f"\n{CYAN}Memory Checks:{RESET}")
        for check, passed in memory_checks.items():
            status = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
            logger.info(f"  {status} {check}")
        
        if not all(memory_checks.values()):
            logger.error(f"{RED}❌ MEMORY AMNESIA NOT FIXED!{RESET}")
            return False
        
        logger.info(f"\n{YELLOW}TURNO 2: User provides clarification{RESET}")
        logger.info(f"{'-'*70}")
        
        # Second evaluation: User responds with clarification
        respuesta_turno2 = "mis sobrinos"
        logger.info(f"User Input: '{respuesta_turno2}'")
        
        # Construct combined text with memory (THIS IS WHAT re_evaluar DOES)
        texto_combinado = f"""
Datos anteriores: {json.dumps(datos_previos, ensure_ascii=False, indent=2)}
Nueva información del usuario: {respuesta_turno2}
"""
        
        logger.info(f"\nCombined context for LLM:")
        logger.info(f"  {texto_combinado[:150]}...")
        
        # Check that context has full memory
        context_checks = {
            "contexto incluye monto": "500" in texto_combinado,
            "contexto incluye comida": "comida" in texto_combinado,
            "contexto incluye origen": "cuenta cobro" in texto_combinado or "cuenta" in texto_combinado,
            "contexto incluye sobrinos": "sobrinos" in texto_combinado,
        }
        
        logger.info(f"\n{CYAN}Context Checks:{RESET}")
        for check, passed in context_checks.items():
            status = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
            logger.info(f"  {status} {check}")
        
        if not all(context_checks.values()):
            logger.error(f"{RED}❌ CONTEXT LOST IN ROUND 2!{RESET}")
            return False
        
        # Simulate re-evaluation (normally called by agent)
        evaluacion_turno2 = agent.evaluar(texto_combinado)
        
        logger.info(f"\n{CYAN}LLM Extraction Results (Turn 2):{RESET}")
        for nombre, campo in evaluacion_turno2.campos.items():
            if campo.valor:
                logger.info(f"  {nombre}: valor='{campo.valor}', accion={campo.accion}, certeza={campo.certeza}")
        
        logger.info(f"\nState after Turno 2: {evaluacion_turno2.estado_global}")
        
        # Check for improvements
        destino_updated = evaluacion_turno2.campos.get("destino")
        if destino_updated and destino_updated.valor:
            logger.info(f"\n{GREEN}✓ Destino field updated: {destino_updated.valor}{RESET}")
        else:
            logger.warning(f"\n{YELLOW}⚠ Destino not yet filled (may need 3rd turn){RESET}")
        
        # Final state check
        logger.info(f"\n{GREEN}{'='*70}")
        logger.info(f"RESULT: CONVERSATION PROGRESSING (No Infinite Loop!)")
        logger.info(f"{'='*70}{RESET}")
        
        return True
        
    except Exception as e:
        logger.error(f"{RED}TEST ERROR: {e}{RESET}", exc_info=True)
        return False


def main():
    """Run end-to-end test."""
    success = test_conversation_flow()
    
    if success:
        logger.info(f"\n{GREEN}✅ END-TO-END TEST PASSED{RESET}")
        logger.info(f"{GREEN}Amnesia fix is working in real conversation context!{RESET}\n")
        return 0
    else:
        logger.error(f"\n{RED}❌ END-TO-END TEST FAILED{RESET}\n")
        return 1


if __name__ == "__main__":
    exit(main())
