"""Test script for TASK_CLASSIFY and TASK_PARSE."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime

from agents.clasificador_agent import ClasificadorAgent

BASE_DIR = Path("/home/jarias/MyFinance4.0/logs/test_rounds")

CLASSIFY_TESTS = [
    {"input": "hola", "expected": "chat", "description": "Saludo simple"},
    {
        "input": "buenos días, qué tal?",
        "expected": "chat",
        "description": "Saludo con contexto",
    },
    {"input": "pagué el taxi", "expected": "registro", "description": "Gasto simple"},
    {
        "input": "recibí 5000 de mi abuela",
        "expected": "registro",
        "description": "Ingreso simple",
    },
    {
        "input": "gasté 150 en el super mercado de la esquina",
        "expected": "registro",
        "description": "Gasto con descripción",
    },
    {
        "input": "cuánto gasté esta semana?",
        "expected": "consulta",
        "description": "Pregunta sobre gastos",
    },
    {
        "input": "estoy dentro del presupuesto este mes?",
        "expected": "consulta",
        "description": "Validación presupuesto",
    },
    {
        "input": "aprueba la transacción anterior",
        "expected": "autorizar",
        "description": "Aprobar transacción",
    },
    {
        "input": "rechaza el pago pendiente",
        "expected": "autorizar",
        "description": "Rechazar transacción",
    },
    {
        "input": "pagué el taxi pero cuánto llevo gastado hoy?",
        "expected": "consulta",
        "description": "Mixto: registro + consulta",
    },
]

PARSE_TESTS = [
    {"input": "pagué taxi 50", "expected_monto": 50.0, "expected_origen": None},
    {
        "input": "gasté 1000 en el super",
        "expected_monto": 1000.0,
        "expected_origen": None,
    },
    {
        "input": "recibí 5000 de mi abuela",
        "expected_monto": 5000.0,
        "expected_origen": None,
    },
    {
        "input": "pagué el almuerzo 25",
        "expected_monto": 25.0,
        "expected_origen": None,
    },
]


def run_classify_tests():
    """Run TASK_CLASSIFY tests."""
    print("=" * 60)
    print("TASK_CLASSIFY - RUNNING 10 TEST ROUNDS")
    print("=" * 60)

    classifier = ClasificadorAgent()
    results = []

    for i, test in enumerate(CLASSIFY_TESTS, 1):
        print(f"\n[Test {i:02d}] {test['description']}")
        print(f"  Input: {test['input']}")

        try:
            result = classifier.classify_with_details(test["input"])
            actual = result["intencion"]
            passed = actual == test["expected"]

            log_entry = {
                "round": i,
                "timestamp": datetime.now().isoformat(),
                "input": test["input"],
                "expected": test["expected"],
                "actual": actual,
                "certeza": result["certeza"],
                "es_ambiguo": result["es_ambiguo"],
                "route": result["route"],
                "passed": passed,
                "description": test["description"],
            }

            print(f"  Expected: {test['expected']}")
            print(f"  Actual: {actual}")
            print(f"  Certeza: {result['certeza']}")
            print(f"  Route: {result['route']}")
            print(f"  Status: {'✅ PASS' if passed else '❌ FAIL'}")

            results.append(log_entry)

        except Exception as e:
            print(f"  Error: {e}")
            results.append(
                {
                    "round": i,
                    "timestamp": datetime.now().isoformat(),
                    "input": test["input"],
                    "expected": test["expected"],
                    "actual": "ERROR",
                    "certeza": 0,
                    "es_ambiguo": True,
                    "route": None,
                    "passed": False,
                    "description": test["description"],
                    "error": str(e),
                }
            )

    # Save logs
    classify_dir = BASE_DIR / "classify"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with open(classify_dir / f"round_{timestamp}.json", "w") as f:
        json.dump(results, f, indent=2)

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{total} tests passed")
    print("=" * 60)

    # Save individual logs
    for r in results:
        with open(classify_dir / f"test_{r['round']:02d}.json", "w") as f:
            json.dump(r, f, indent=2)

    return results


def run_parse_tests():
    """Run TASK_PARSE tests (only if classify tests pass)."""
    print("\n" + "=" * 60)
    print("TASK_PARSE - RUNNING TESTS")
    print("=" * 60)

    from agents.accounting_agent import AccountingAgent

    agent = AccountingAgent()
    results = []

    for i, test in enumerate(PARSE_TESTS, 1):
        print(f"\n[Test {i:02d}]")
        print(f"  Input: {test['input']}")

        try:
            result = agent.process(test["input"], usuario_id=None)

            # Parse the result based on action
            if result.get("action") == "PROCESAR":
                entidades = result.get("entidades", {})
                actual_monto = entidades.get("monto_total")
                actual_origen = entidades.get("origen", "")

                passed_monto = str(actual_monto) == str(test["expected_monto"])

                log_entry = {
                    "round": i,
                    "timestamp": datetime.now().isoformat(),
                    "input": test["input"],
                    "expected_monto": test["expected_monto"],
                    "actual_monto": actual_monto,
                    "expected_origen": test["expected_origen"],
                    "actual_origen": actual_origen,
                    "action": result.get("action"),
                    "passed": passed_monto,
                }
            else:
                log_entry = {
                    "round": i,
                    "timestamp": datetime.now().isoformat(),
                    "input": test["input"],
                    "expected_monto": test["expected_monto"],
                    "actual_monto": None,
                    "expected_origen": test["expected_origen"],
                    "actual_origen": None,
                    "action": result.get("action"),
                    "pregunta": result.get("response", ""),
                    "passed": False,
                }

            print(f"  Expected monto: {test['expected_monto']}")
            if log_entry.get("actual_monto"):
                print(f"  Actual monto: {log_entry['actual_monto']}")
            print(f"  Action: {log_entry['action']}")
            print(f"  Status: {'✅ PASS' if log_entry['passed'] else '❌ FAIL'}")

            results.append(log_entry)

        except Exception as e:
            print(f"  Error: {e}")
            results.append(
                {
                    "round": i,
                    "timestamp": datetime.now().isoformat(),
                    "input": test["input"],
                    "expected_tipo": test["expected_tipo"],
                    "actual_tipo": "ERROR",
                    "passed": False,
                    "error": str(e),
                }
            )

    # Save logs
    parse_dir = BASE_DIR / "parse"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with open(parse_dir / f"round_{timestamp}.json", "w") as f:
        json.dump(results, f, indent=2)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{total} tests passed")
    print("=" * 60)

    return results


if __name__ == "__main__":
    classify_results = run_classify_tests()

    # Ask before running parse tests
    classify_passed = sum(1 for r in classify_results if r["passed"])
    classify_total = len(classify_results)

    print(f"\n📊 CLASSIFY RESULTS: {classify_passed}/{classify_total} passed")

    if classify_passed == classify_total:
        print("\n▶️  All CLASSIFY tests passed. Ready for PARSE tests.")
        print("   (Run this script again with --parse flag to continue)")
    else:
        print(f"\n⚠️  {classify_total - classify_passed} CLASSIFY tests failed.")
        print("   Fix issues before running PARSE tests.")
