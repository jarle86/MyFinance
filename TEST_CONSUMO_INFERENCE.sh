#!/usr/bin/env bash
# 🎯 TEST: "gaste 1500 en helados para mis sobrinos, use efectivo"
# 
# This script runs the complete end-to-end test with monitoring
# Expected Flow:
#   1. User input: "gaste 1500 en helados para mis sobrinos, use efectivo"
#   2. A1: Detects "registro" intent
#   3. A3: Extracts monto=1500, concepto=helados, …, destino=null
#   4. Python Validation: ALWAYS RUNS NOW! 
#      - Sees "helados" in concepto
#      - Applies consumo inference
#      - Moves "helados" to destino
#      - Searches: buscar_categoria("helados")
#      - Gets categoria_id
#   5. Estado becomes COMPLETADO
#   6. Shows confirmation
#   7. User confirms
#   8. Transaction saved ✅

set -e

cd /home/jarias/MyFinance4.0

echo "═══════════════════════════════════════════════════════════════════"
echo "🧪 TEST: End-to-End with Consumo Inference Fix"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Input: 'gaste 1500 en helados para mis sobrinos, use efectivo'"
echo "Expected: Python catches 'helados' in concepto, moves to destino, completes"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Clean old log and start fresh
LOGFILE="./logs/system02042026.log"

echo "📋 Starting application with real-time log monitoring..."
echo ""
echo "In another terminal, run:"
echo "   tail -f $LOGFILE"
echo ""
echo "Then send this input to the bot:"
echo "   gaste 1500 en helados para mis sobrinos, use efectivo"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Start the application
echo "▶️  Starting python main.py..."
echo ""

./venv/bin/python main.py

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "Test complete. Check logs above for:"
echo "  ✅ [PIPELINE] A3 EVALUADOR OUTPUT estado_global='PENDIENTE'"
echo "  ✅ [Modo interactivo] Validación Python de entidades completada"
echo "  ✅ estado_global='COMPLETADO'"
echo "═══════════════════════════════════════════════════════════════════"
