#!/usr/bin/env python3
"""
End-to-End Test Suite for MyFinance 4.0 SQL Sanitization
Tests DBAAgent, SQL validation, and tool integration
"""

import logging
import sys
from uuid import uuid4

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_basic_imports():
    """Test 1: Verify all core modules import correctly"""
    logger.info("TEST 1: Basic Imports")
    try:
        from core.processor import Processor
        from agents.dba_agent import DBAAgent
        from agents.evaluador_agent import EvaluadorAgent
        from core.tools import ejecutar_lectura_segura, ejecutar_transaccion_doble
        logger.info("✅ All imports successful\n")
        return True
    except Exception as e:
        logger.error(f"❌ Import failed: {e}\n")
        return False

def test_dba_agent_instantiation():
    """Test 2: Verify DBAAgent can be instantiated"""
    logger.info("TEST 2: DBAAgent Instantiation")
    try:
        from agents.dba_agent import DBAAgent
        agent = DBAAgent()
        logger.info("✅ DBAAgent instantiated successfully\n")
        return True
    except Exception as e:
        logger.error(f"❌ DBA instantiation failed: {e}\n")
        return False

def test_sql_sanitization_safe():
    """Test 3: Sanitize safe SQL"""
    logger.info("TEST 3: SQL Sanitization - Safe SQL")
    try:
        from agents.dba_agent import DBAAgent
        agent = DBAAgent()
        test_user_id = str(uuid4())
        
        sql = f"SELECT * FROM cuentas WHERE usuario_id = '{test_user_id}'"
        cleaned = agent._sanitize_sql(sql, test_user_id)
        
        assert "SELECT" in cleaned
        assert "usuario_id" in cleaned
        logger.info(f"✅ Safe SQL cleaned: {cleaned[:60]}...\n")
        return True
    except Exception as e:
        logger.error(f"❌ Safe SQL test failed: {e}\n")
        return False

def test_sql_sanitization_natural_language():
    """Test 4: Reject natural language in SQL"""
    logger.info("TEST 4: SQL Sanitization - Natural Language Detection")
    try:
        from agents.dba_agent import DBAAgent
        agent = DBAAgent()
        test_user_id = str(uuid4())
        
        # This should fail
        sql = "dame el total de gastos del usuario"
        try:
            cleaned = agent._sanitize_sql(sql, test_user_id)
            logger.error("❌ Should have rejected natural language\n")
            return False
        except ValueError as e:
            if "natural language" in str(e).lower():
                logger.info(f"✅ Natural language correctly detected: {e}\n")
                return True
            else:
                logger.error(f"❌ Wrong error: {e}\n")
                return False
    except Exception as e:
        logger.error(f"❌ Natural language test failed: {e}\n")
        return False

def test_sql_sanitization_edge_cases():
    """Test 5: Handle edge cases"""
    logger.info("TEST 5: SQL Sanitization - Edge Cases")
    try:
        from agents.dba_agent import DBAAgent
        agent = DBAAgent()
        test_user_id = str(uuid4())
        
        # Edge case 1: Empty string
        try:
            agent._sanitize_sql("", test_user_id)
            logger.error("❌ Should have rejected empty string\n")
            return False
        except ValueError:
            logger.info("✅ Empty string correctly rejected")
        
        # Edge case 2: SELECT with function containing marker
        sql = "SELECT calcular_gastos(usuario_id) FROM cuentas"
        cleaned = agent._sanitize_sql(sql, test_user_id)
        assert "SELECT" in cleaned
        logger.info("✅ SELECT with marker function accepted")
        
        # Edge case 3: Missing usuario_id in WHERE
        sql = "SELECT * FROM cuentas WHERE activa = true"
        cleaned = agent._sanitize_sql(sql, test_user_id)
        assert "usuario_id" in cleaned
        logger.info("✅ Missing usuario_id filter auto-appended")
        
        logger.info("")
        return True
    except Exception as e:
        logger.error(f"❌ Edge case test failed: {e}\n")
        return False

def test_processor_integration():
    """Test 6: Verify Processor can be initialized"""
    logger.info("TEST 6: Processor Integration")
    try:
        from core.processor import Processor
        processor = Processor()
        logger.info("✅ Processor initialized with all agents\n")
        return True
    except Exception as e:
        logger.error(f"❌ Processor integration failed: {e}\n")
        return False

def test_dba_agent_has_sanitize_method():
    """Test 7: Verify _sanitize_sql method exists and is callable"""
    logger.info("TEST 7: DBAAgent Method Verification")
    try:
        from agents.dba_agent import DBAAgent
        agent = DBAAgent()
        
        assert hasattr(agent, '_sanitize_sql'), "Missing _sanitize_sql method"
        assert callable(getattr(agent, '_sanitize_sql')), "_sanitize_sql not callable"
        
        logger.info("✅ _sanitize_sql method exists and is callable\n")
        return True
    except Exception as e:
        logger.error(f"❌ Method verification failed: {e}\n")
        return False

def test_logging_configuration():
    """Test 8: Verify logging is properly configured"""
    logger.info("TEST 8: Logging Configuration")
    try:
        import logging
        from core.processor import Processor
        from core.ai_utils import logger as ai_logger
        
        # Check logger exists
        assert ai_logger is not None
        assert isinstance(ai_logger, logging.Logger)
        
        logger.info("✅ Logging properly configured\n")
        return True
    except Exception as e:
        logger.error(f"❌ Logging config failed: {e}\n")
        return False

def run_all_tests():
    """Run complete test suite"""
    logger.info("=" * 60)
    logger.info("MyFinance 4.0 - End-to-End Test Suite")
    logger.info("=" * 60 + "\n")
    
    tests = [
        test_basic_imports,
        test_dba_agent_instantiation,
        test_sql_sanitization_safe,
        test_sql_sanitization_natural_language,
        test_sql_sanitization_edge_cases,
        test_processor_integration,
        test_dba_agent_has_sanitize_method,
        test_logging_configuration,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            logger.error(f"❌ Test {test_func.__name__} crashed: {e}\n")
            results.append((test_func.__name__, False))
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST RESULTS SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {name}")
    
    logger.info("=" * 60)
    logger.info(f"Total: {passed}/{total} tests passed")
    logger.info("=" * 60)
    
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
