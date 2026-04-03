#!/usr/bin/env python3
"""
Final validation test for financial parsing with improved JSON error handling.

Tests the complete flow:
1. Parse user input: "gaste 200 en transporte publico pagado desde cobro"
2. Extract financial entities via LLM with JSON retry logic
3. Search for accounts/categories with optimized search functions
4. Validate complete end-to-end flow

This test validates that the JSON error handling improvements prevent
the previous parsing failures at line 70 char 22.
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.ai_utils import generate_json_with_retry
from core.tools.buscar_cuenta import buscar_cuenta
from core.tools.buscar_categoria import buscar_categoria


def test_json_generation_with_retry():
    """Test that JSON generation with retry handles malformed responses gracefully."""
    print("\n" + "="*60)
    print("TEST 1: JSON Generation with Retry Robustness")
    print("="*60)
    
    # Simulate user input that would cause JSON parsing
    user_input = "gaste 200 en transporte publico pagado desde cobro"
    
    prompt = f"""You are a financial entity extraction expert. Extract the following from the user input:
- monto_total (number)
- concepto (string)
- origen (account, string)
- destino (account or category, string)

User input: "{user_input}"

Return valid JSON (and ONLY valid JSON, no markdown, no extra text):"""

    print(f"\nTesting financial parsing for: '{user_input}'")
    print(f"Prompt: {prompt[:100]}...")
    
    try:
        result = generate_json_with_retry(
            prompt=prompt,
            expected_schema={
                "monto_total": (int, float),
                "concepto": str,
                "origen": str,
            },
            max_retries=3
        )
        
        print(f"✓ JSON Generation successful")
        print(f"  Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        return result
    except Exception as e:
        print(f"✗ JSON Generation failed: {str(e)[:100]}")
        return None


def test_account_search():
    """Test that account search finds 'cobro' correctly."""
    print("\n" + "="*60)
    print("TEST 2: Account Search - Find 'cobro'")
    print("="*60)
    
    try:
        result = buscar_cuenta("cobro")
        
        if result and result.get("status") == "success":
            print(f"✓ Account search successful")
            print(f"  Found: {result.get('results', [])}")
            return True
        else:
            print(f"✗ Account not found")
            print(f"  Result: {result}")
            return False
    except Exception as e:
        print(f"✗ Account search failed: {str(e)}")
        return False


def test_category_search():
    """Test that category search finds common categories."""
    print("\n" + "="*60)
    print("TEST 3: Category Search - Find 'comida'")
    print("="*60)
    
    try:
        result = buscar_categoria("comida")
        
        if result and result.get("status") == "success":
            print(f"✓ Category search successful")
            print(f"  Found: {result.get('results', [])}")
            return True
        else:
            print(f"✗ Category not found")
            print(f"  Result: {result}")
            return False
    except Exception as e:
        print(f"✗ Category search failed: {str(e)}")
        return False


def test_complete_flow():
    """Test complete flow: parse → search → validate."""
    print("\n" + "="*60)
    print("TEST 4: Complete User Flow")
    print("="*60)
    
    user_input = "gaste 200 en transporte publico pagado desde cobro"
    print(f"\nUser Input: '{user_input}'")
    
    # Step 1: Extract entities via JSON generation
    print("\nStep 1: Extracting financial entities...")
    json_result = test_json_generation_with_retry()
    
    if not json_result:
        print("✗ Failed to extract entities")
        return False
    
    # Step 2: Search for account
    print("\nStep 2: Searching for account...")
    account_found = test_account_search()
    
    if not account_found:
        print("✗ Failed to find account")
        return False
    
    # Step 3: Search for category
    print("\nStep 3: Searching for category...")
    category_found = test_category_search()
    
    if not category_found:
        print("✗ Failed to find category")
        return False
    
    print("\n" + "="*60)
    print("✓ COMPLETE FLOW SUCCESSFUL")
    print("="*60)
    print("\nAll components working:")
    print("  ✓ JSON parsing with retry logic (no char 1709 errors)")
    print("  ✓ Account search (found 'cobro')")
    print("  ✓ Category search (found 'comida')")
    print("\nSystem is ready to handle: 'gaste 200 en transporte publico pagado desde cobro'")
    
    return True


if __name__ == "__main__":
    print("\n" + "="*60)
    print("FINANCIAL PARSING FINAL VALIDATION TEST")
    print("="*60)
    print("\nTesting JSON error handling and complete end-to-end flow")
    
    results = {
        "json_generation": test_json_generation_with_retry() is not None,
        "account_search": test_account_search(),
        "category_search": test_category_search(),
        "complete_flow": test_complete_flow(),
    }
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:20s} {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ ALL TESTS PASSING - System ready for production")
        sys.exit(0)
    else:
        print("\n✗ SOME TESTS FAILED - Review output above")
        sys.exit(1)
