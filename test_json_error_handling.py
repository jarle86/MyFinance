#!/usr/bin/env python3
"""
Test JSON error handling with financial parsing scenario
"""

import json
import sys

print("Testing JSON error handling...\n")

# Simulate the error response that was failing
test_input = "gaste 200 en transporte publico pagado desde cobro"

print(f"Input: {test_input}\n")

# Test 1: Valid JSON
print("Test 1: Valid JSON parsing")
valid_json = '''
{
  "_razonamiento_previo": "Usuario dice gaste (verbo), 200 (monto), transporte publico (concepto), pagado (estado), desde cobro (origen)",
  "campos": {
    "monto_total": {
      "valor": "200",
      "es_requerido": true,
      "certeza": 95,
      "accion": "siguiente",
      "pregunta": null
    },
    "concepto": {
      "valor": "transporte publico",
      "es_requerido": false,
      "certeza": 90,
      "accion": "siguiente",
      "pregunta": null
    },
    "origen": {
      "valor": "cobro",
      "es_requerido": true,
      "certeza": 85,
      "accion": "siguiente",
      "pregunta": null
    }
  },
  "estado_global": "COMPLETADO"
}
'''

try:
    result = json.loads(valid_json)
    print("✓ Valid JSON parsed successfully\n")
except json.JSONDecodeError as e:
    print(f"✗ Error: {e}\n")
    sys.exit(1)

# Test 2: JSON with markdown wrapping
print("Test 2: JSON with markdown wrapping")
markdown_json = '''```json
{
  "_razonamiento_previo": "Usuario especifica monto y origen",
  "campos": {
    "monto_total": {"valor": "200", "certeza": 95, "accion": "siguiente"}
  },
  "estado_global": "PENDIENTE"
}
```'''

clean_text = markdown_json.strip()
if clean_text.startswith("```json"): clean_text = clean_text[7:]
elif clean_text.startswith("```"): clean_text = clean_text[3:]
if clean_text.endswith("```"): clean_text = clean_text[:-3]
clean_text = clean_text.strip()

try:
    result = json.loads(clean_text)
    print("✓ Markdown-wrapped JSON parsed successfully\n")
except json.JSONDecodeError as e:
    print(f"✗ Error: {e}\n")
    sys.exit(1)

# Test 3: JSON with trailing text
print("Test 3: JSON with trailing text")
json_with_text = '''{"monto_total": {"valor": "200"}, "estado_global": "COMPLETADO"}
Some trailing text that shouldn't be there'''

clean_text = json_with_text.strip()
if not clean_text.startswith('{'): 
    start_idx = clean_text.find('{')
    if start_idx != -1:
        clean_text = clean_text[start_idx:]

if not clean_text.endswith('}'):
    last_brace = clean_text.rfind('}')
    if last_brace != -1:
        clean_text = clean_text[:last_brace+1]

try:
    result = json.loads(clean_text)
    print("✓ JSON with trailing text parsed successfully\n")
except json.JSONDecodeError as e:
    print(f"✗ Error: {e}\n")
    sys.exit(1)

print("="*60)
print("✓ All JSON error handling tests PASSED")
print("="*60)
