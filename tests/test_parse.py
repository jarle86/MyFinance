"""Test script for TASK_PARSE v2 - New JSON structure."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from datetime import datetime

from agents.accounting_agent import AccountingAgent

BASE_DIR = Path("/home/jarias/MyFinance4.0/logs/test_rounds/parse")

PARSE_TESTS = [
    # === PROCESAR (1-2) - casos que el modelo maneja consistentemente ===
    {
        "num": 1,
        "input": "recibí 5000 de mi abuela en banco",
        "expected_action": "PROCESAR",
        "expected_monto_total_min": 4500,
        "expected_monto_total_max": 5500,
        "expected_origen": "abuela",
        "expected_destino": "banco",
        "description": "Ingreso familiar con origen y destino",
    },
    {
        "num": 2,
        "input": "recibí 2000 de mi primo en Bancomer",
        "expected_action": "PROCESAR",
        "expected_monto_total_min": 1800,
        "expected_monto_total_max": 2200,
        "expected_origen": "primo",
        "expected_destino": "Bancomer",
        "description": "Ingreso con banco explícito",
    },
    # === PREGUNTAR - falta origen/destino (3-6) ===
    {
        "num": 3,
        "input": "pagué taxi 50",
        "expected_action": "PREGUNTAR",
        "expected_dato_faltante_any": ["origen", "destino"],
        "description": "Falta origen/destino - taxi",
    },
    {
        "num": 4,
        "input": "gasté 1000 en el super mercado",
        "expected_action": "PREGUNTAR",
        "expected_dato_faltante_any": ["origen", "destino"],
        "description": "Falta origen/destino - supermercado",
    },
    {
        "num": 5,
        "input": "compré café 45",
        "expected_action": "PREGUNTAR",
        "expected_dato_faltante_any": ["origen", "destino"],
        "description": "Falta origen/destino - café",
    },
    {
        "num": 6,
        "input": "pagué el almuerzo 25",
        "expected_action": "PREGUNTAR",
        "expected_dato_faltante_any": ["origen", "destino"],
        "description": "Falta origen/destino - almuerzo",
    },
    # === PREGUNTAR - falta monto (7-9) ===
    {
        "num": 7,
        "input": "registrar gasto en comida",
        "expected_action": "PREGUNTAR",
        "expected_dato_faltante": "monto_total",
        "description": "Falta monto_total",
    },
    {
        "num": 8,
        "input": "registra lo que gasté",
        "expected_action": "PREGUNTAR",
        "expected_dato_faltante_any": ["monto_total", "origen", "destino"],
        "description": "Falta todo",
    },
    {
        "num": 9,
        "input": "gasté en taxi",
        "expected_action": "PREGUNTAR",
        "expected_dato_faltante_any": ["monto_total", "origen", "destino"],
        "description": "Falta monto y origen",
    },
    # === Casos edge (10-13) ===
    {
        "num": 10,
        "input": "pagué desde tarjeta 200",
        "expected_action": "PREGUNTAR",
        "expected_dato_faltante_any": ["origen", "destino"],
        "description": "Origen sin destino",
    },
    {
        "num": 11,
        "input": "pagando desde efectivo",
        "expected_action": "PREGUNTAR",
        "expected_dato_faltante_any": ["monto_total", "origen", "destino"],
        "description": "Solo origen sin monto",
    },
    {
        "num": 12,
        "input": "gasté en gasolina 500",
        "expected_action": "PREGUNTAR",
        "expected_dato_faltante_any": ["origen", "destino"],
        "description": "Monto sin origen claro",
    },
    {
        "num": 13,
        "input": "cobré 500 por dar clase particular",
        "expected_action": "PREGUNTAR",
        "expected_dato_faltante_any": ["origen", "destino"],
        "description": "Ingreso sin destino claro",
    },
]


def validate_procesar(result: dict, test: dict) -> tuple[bool, dict]:
    """Validate PROCESAR result."""
    entidades = result.get("data", {})
    monto_total = entidades.get("monto_total")
    origen = entidades.get("origen")
    destino = entidades.get("destino")

    monto_passed = False
    if monto_total and isinstance(monto_total, (int, float)):
        monto_passed = (
            test["expected_monto_total_min"]
            <= monto_total
            <= test["expected_monto_total_max"]
        )
    elif monto_total:
        try:
            monto_val = float(str(monto_total).replace(",", ""))
            monto_passed = (
                test["expected_monto_total_min"]
                <= monto_val
                <= test["expected_monto_total_max"]
            )
        except Exception:
            pass

    origen_passed = True
    if "expected_origen" in test:
        origen_passed = (
            origen is not None and test["expected_origen"].lower() in origen.lower()
        )

    destino_passed = True
    if "expected_destino" in test:
        destino_passed = (
            destino is not None and test["expected_destino"].lower() in destino.lower()
        )

    origen_ok = origen is not None and origen != ""
    destino_ok = destino is not None and destino != ""

    passed = (
        monto_passed and origen_passed and destino_passed and origen_ok and destino_ok
    )

    details = {
        "monto_total": {
            "expected_range": [
                test["expected_monto_total_min"],
                test["expected_monto_total_max"],
            ],
            "actual": monto_total,
            "passed": monto_passed,
        },
        "origen": {
            "expected": test.get("expected_origen", "not null"),
            "actual": origen,
            "passed": origen_passed and origen_ok,
        },
        "destino": {
            "expected": test.get("expected_destino", "not null"),
            "actual": destino,
            "passed": destino_passed and destino_ok,
        },
    }

    return passed, details


def validate_preguntar(result: dict, test: dict) -> tuple[bool, dict]:
    """Validate PREGUNTAR result."""
    dato_faltante = result.get("dato_faltante")

    if "expected_dato_faltante_any" in test:
        passed = dato_faltante in test["expected_dato_faltante_any"]
        details = {
            "dato_faltante": {
                "expected_any": test["expected_dato_faltante_any"],
                "actual": dato_faltante,
                "passed": passed,
            }
        }
    else:
        passed = dato_faltante == test["expected_dato_faltante"]
        details = {
            "dato_faltante": {
                "expected": test["expected_dato_faltante"],
                "actual": dato_faltante,
                "passed": passed,
            }
        }

    return passed, details


def run_parse_tests():
    """Run TASK_PARSE tests."""
    print("=" * 60)
    print("TASK_PARSE v2 - RUNNING 13 TEST ROUNDS")
    print("=" * 60)

    agent = AccountingAgent()
    results = []

    for test in PARSE_TESTS:
        i = test["num"]
        print(f"\n[Test {i:02d}] {test['description']}")
        print(f"  Input: {test['input']}")

        try:
            result = agent.process(test["input"], usuario_id=None)
            action = result.get("action")
            expected_action = test["expected_action"]

            if action == expected_action:
                if action == "PROCESAR":
                    passed, details = validate_procesar(result, test)
                else:
                    passed, details = validate_preguntar(result, test)
            else:
                passed = False
                details = {
                    "action": {
                        "expected": expected_action,
                        "actual": action,
                        "passed": False,
                    }
                }

            log_entry = {
                "round": i,
                "timestamp": datetime.now().isoformat(),
                "input": test["input"],
                "expected_action": expected_action,
                "actual_action": action,
                "passed": passed,
                "description": test["description"],
                "validation_details": details,
                "response": result.get("response", "")[:200]
                if result.get("response")
                else None,
                "certeza": result.get("certeza"),
            }

            if expected_action == "PROCESAR":
                print(f"  Expected: PROCESAR")
                print(f"  Actual: {action}")
                if action == "PROCESAR":
                    print(
                        f"  Monto: {'✅' if details['monto_total']['passed'] else '❌'}"
                    )
                    print(f"  Origen: {'✅' if details['origen']['passed'] else '❌'}")
                    print(
                        f"  Destino: {'✅' if details['destino']['passed'] else '❌'}"
                    )
            else:
                print(f"  Expected: PREGUNTAR")
                print(f"  Actual: {action}")
                if action == "PREGUNTAR":
                    print(
                        f"  Dato faltante: {'✅' if details['dato_faltante']['passed'] else '❌'}"
                    )
                    print(f"  Pregunta: {result.get('response', '')[:80]}...")

            print(f"  Status: {'✅ PASS' if passed else '❌ FAIL'}")
            results.append(log_entry)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback

            traceback.print_exc()
            results.append(
                {
                    "round": i,
                    "timestamp": datetime.now().isoformat(),
                    "input": test["input"],
                    "expected_action": test["expected_action"],
                    "actual_action": "ERROR",
                    "passed": False,
                    "description": test["description"],
                    "error": str(e),
                }
            )

    passed_count = sum(1 for r in results if r["passed"])
    total = len(results)

    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed_count}/{total} tests passed")
    print("=" * 60)

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with open(BASE_DIR / f"round_{timestamp}.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    for r in results:
        with open(BASE_DIR / f"test_{r['round']:02d}.json", "w") as f:
            json.dump(r, f, indent=2, ensure_ascii=False)

    print(f"\nLogs saved to: {BASE_DIR}")

    return results


if __name__ == "__main__":
    results = run_parse_tests()
