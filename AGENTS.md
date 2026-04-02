# AGENTS.md - MyFinance 4.0 Agent Guidelines

This file provides guidelines for AI agents operating in this repository.

---

## 1. Project Overview

**MyFinance** is an AI-powered personal finance OS with orchestrated agents for:
- OCR invoice processing
- Accounting JSON parsing
- SQL validation/execution
- Chat/humanization
- Intent classification

**Architecture:** Synchronous, direct, no RAG, no RabbitMQ, no semantic state.

### Core Components

| Component | File | Description |
|-----------|------|-------------|
| **Processor** | `core/processor.py` | Main router with state machine for interactive mode |
| **ClasificadorAgent** | `agents/clasificador_agent.py` | Intent classification (A1) |
| **OCRAgent** | `agents/ocr_agent.py` | Invoice OCR (A2) |
| **EvaluadorAgent** | `agents/evaluador_agent.py` | Semantic evaluation and slot-filling (A3) |
| **AccountingAgent** | `agents/accounting_agent.py` | High-fidelity JSON parsing (A4) |
| **DBAAgent** | `agents/dba_agent.py` | SQL validation and Tool Calling execution (A5) |
| **ChatAgent** | `agents/chat_agent.py` | Financial advice and humanization (A6) |

---

## 2. Build/Lint/Test Commands

### Running the Application
```bash
# Run Telegram gateway
python main.py

# Run Streamlit dashboard
python -m streamlit run web/dashboard/main.py
```

### Running Tests
```bash
# Run all tests
python -m pytest

# Run TASK_CLASSIFY tests
python tests/test_classifier.py

# Run TASK_PARSE tests
python tests/test_parse.py

# Run specific test file
python -m pytest tests/test_accounting_agent.py

# Run with coverage
python -m pytest --cov=. --cov-report=term-missing
```

### Linting & Formatting
```bash
# Lint with ruff
ruff check .

# Fix auto-fixable issues
ruff check --fix .

# Format with black
black .
```

### Type Checking
```bash
# Type check with mypy
python -m mypy .
```

---

## 3. Code Style Guidelines

### Python Conventions
- **Language:** Python 3.10+
- **Style:** PEP 8 + Black (max line length 88)
- **Type Hints:** Required for all function signatures
- **Docstrings:** Google-style for public APIs

### Import Order (PEP 8)
```python
# 1. Standard library
import os
import json
from typing import Optional

# 2. Third-party
import requests
from pydantic import BaseModel

# 3. Local application
from agents import OCRAgent
from core import processor
```

### Naming Conventions
| Element | Convention | Example |
|---------|------------|---------|
| Functions/variables | snake_case | `get_balance()`, `total_amount` |
| Classes | PascalCase | `AccountingAgent`, `TransactionModel` |
| Constants | UPPER_SNAKE | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Private methods | prefix `_` | `_validate_sql()` |
| File modules | snake_case | `ai_utils.py`, `config_loader.py` |

### Error Handling
- Use custom exceptions for domain errors
- Log errors with appropriate level (`logger.error`, `logger.warning`)
- Never expose secrets in error messages
- Wrap external API calls in try/except

---

## 4. Project-Specific Rules

### Golden Rules (from REGLAS.md)
1. **Inmutabilidad:** Never change prompts, tasks, or variables in `sistema_config` without authorization.
2. **No Hardcoding:** Never hardcode parameters. Infrastructure (DB, API Keys) goes in `.env`; Application Logic (Models, Thresholds, Prompts) goes in `sistema_config`.
3. **Flow Control:** Keep flows updated; get authorization before changing flow-affecting logic.
4. **Zero-Shot Prompts:** Don't use examples or fixed values in prompts. Give clear, precise instructions to avoid "alucinar" (hallucinate).
5. **Discipline:** Follow the rules and don't modify them.

### Accounting Convention
- **Credit (True / 1):** Entry or increase in account
- **Debit (False / 0):** Exit or decrease in account

### No RAG Policy
- Synchronous architecture only
- No semantic state storage
- No RabbitMQ message queues
- Direct agent-to-agent communication

---

## 5. Agent Architecture (6 Agents)

The system now uses 6 specialized agents:

| ID | Nombre | Rol (DB) | Tarea | Descripción |
|----|--------|----------|-------|-------------|
| **A1** | Clasificador | TASK_CLASSIFY | Enrutar | Define si es Registro, Consulta, Chat, etc. |
| **A2** | Extractor (OCR) | TASK_OCR | Extraer | Extrae texto crudo de imágenes |
| **A3** | Evaluador Semántico | TASK_EVALUATE | Evaluar | Evalúa ambigüedades, coherencia y datos faltantes. Gestiona estado PENDIENTE |
| **A4** | Parser JSON | TASK_PARSE | Mapear | Recibe texto 100% validado de A3. Mapea a esquema JSON sin cuestionarlo |
| **A5** | Contable SQL | TASK_SQL | Ejecutar | Convierte JSON perfecto de A4 en PostgreSQL |
| **A6** | Humanizador | TASK_CHAT | Interfaz | Detalle y aprobación en modo interactivo |

### Pipeline de Registro
```
A1 (Clasificador) → A2 (OCR) → A3 (Evaluador) → A4 (Parser) → Python(valida) → A5 (SQL) → A6 (Humanizador)
```

### Diagram
```
┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐
│ A1  │──▶│ A2  │──▶│ A3  │──▶│ A4  │──▶│ PY  │──▶│ A5  │──▶│ A6  │
│Clasif│   │OCR  │   │Eval │   │JSON │   │Val │   │SQL  │   │Chat │
└─────┘   └─────┘   └─────┘   └─────┘   └─────┘   └─────┘   └─────┘
   TEXTO    TEXTO    EVAL     JSON     CUENTAS   SQL     APROB
```

---

## 6. Agente A3 - Evaluador Semántico (TASK_EVALUATE)

### Propósito
Evaluar coherencia de datos antes del parseo JSON. Gestiona el modo interactivo cuando la certeza está por debajo del umbral.

### Ubicación en Pipeline
A2 (OCR/Text) → **A3 (Evaluador)** → A4 (Parser) → Python (validación) → A5 (SQL)

### Campos a Evaluar (Todos configurables desde Panel de Control)

| Campo | es_requerido | threshold |
|-------|--------------|-----------|
| monto_total | ⚙️ Configurable | ⚙️ Configurable |
| origen | ⚙️ Configurable | ⚙️ Configurable |
| destino | ⚙️ Configurable | ⚙️ Configurable |
| monto | ⚙️ Configurable | ⚙️ Configurable |
| monto_impuesto | ⚙️ Configurable | ⚙️ Configurable |
| monto_descuento | ⚙️ Configurable | ⚙️ Configurable |
| monto_otros_cargos | ⚙️ Configurable | ⚙️ Configurable |
| moneda | ⚙️ Configurable | ⚙️ Configurable |
| fecha | ⚙️ Configurable | ⚙️ Configurable |
| concepto | ⚙️ Configurable | ⚙️ Configurable |
| categoria | ⚙️ Configurable | ⚙️ Configurable |

> ⚙️ = Todos configurables desde Panel de Control de Agentes

### Ejemplo de TASK_EVALUATE

```
Eres el Agente de Extracción y Parseo Financiero (Task Evaluator) del sistema MyFinance 4.0. Tu misión es analizar la entrada del usuario o el texto extraído por OCR y extraer todas las entidades contables necesarias para el registro de partida doble. No inventes, asumas ni calcules matemáticamente información que no esté explícitamente detallada en el texto.

INSTRUCCIONES DE PROCESAMIENTO:
1. ANALIZA el texto de entrada palabra por palabra contra los campos esperados.
2. REDACTA en '_razonamiento_previo' un análisis de qué tokens/palabras corresponden a qué campos, y justifica por qué asignas un nivel de certeza alto o bajo a cada uno.
3. EXTRAE Y EVALÚA cada campo de forma independiente dentro del objeto "campos". Para cada campo debes definir:
   - "valor": El dato extraído (o null si no existe).
   - "es_requerido": Booleano (configurable desde Panel de Control).
   - "certeza": Un número del 0 al 100 evaluando qué tan seguro estás de que la palabra extraída corresponde a ese campo.
   - "accion": La decisión a tomar con este campo basado en las siguientes reglas estrictas:
      * "skip": Si el campo NO es requerido ("es_requerido": false) y su valor es null.
      * "siguiente": Si el campo tiene un valor extraído y su "certeza" es ALTA (>= threshold configurado).
      * "preguntar": Si el campo ES requerido y su valor es null, O si tiene un valor pero su "certeza" es BAJA (< threshold).
   - "pregunta": Si la acción es "preguntar", redacta una pregunta natural y directa pidiendo ese dato puntual o aclarando la ambigüedad.

4. ESTADO GLOBAL: Establece "estado_global" como "PENDIENTE" si al menos UN campo tiene la acción "preguntar". Si todos los campos requeridos tienen la acción "siguiente", establece "COMPLETADO".

CAMPOS A EVALUAR:
- "monto" (Subtotal antes de impuestos/descuentos)
- "monto_total" (Total final)
- "monto_impuesto"
- "monto_descuento"
- "monto_otros_cargos"
- "moneda" (Divisa explícita)
- "fecha" (YYYY-MM-DD o texto relativo)
- "concepto" (Motivo explícito)
- "origen" (De dónde sale el dinero)
- "destino" (A dónde va el dinero)
- "categoria"

RESTRICCIONES ABSOLUTAS:
- Tu respuesta DEBE ser única y exclusivamente un objeto JSON válido.
- Prohibido incluir bloques de código markdown (```json), saludos, explicaciones u otro texto.
- Prohibido calcular montos matemáticamente.

ESTRUCTURA JSON REQUERIDA:
{
  "_razonamiento_previo": "string (Análisis de extracción palabra por palabra y justificación de certezas)",
  "campos": {
    "nombre_del_campo_aqui": {
      "valor": "dato extraido numero o string o null",
      "es_requerido": boolean,
      "certeza": numero,
      "accion": "string (ESTRICTAMENTE 'skip', 'siguiente' o 'preguntar')",
      "pregunta": "string o null"
    }
  },
  "estado_global": "string (ESTRICTAMENTE 'COMPLETADO' o 'PENDIENTE')"
}
```

### Lógica del Modo Interactivo (Por Campo)

| Paso | Condición | Acción |
|------|-----------|--------|
| 1 | ¿Campo requerido? | No → SKIP |
| 2 | ¿Palabra presente en texto? | No → Certeza=0, preguntar |
| 3 | ¿Supera umbral (threshold)? | No → Certeza=Baja, confirmar con usuario |
| 4 | ¿Más campos por evaluar? | Sí → Repetir desde Paso 1 |
| 5 | ¿Todos tienen alta certeza? | Sí → Avanzar a A4, No → **PENDIENTE** |

### Estados de Salida
- `COMPLETADO`: Datos válidos → pasar a A4
- `PENDIENTE`: Datos ambiguos → modo interactivo → A6 pregunta al usuario

---

## 7. Output Parser

### Propósito
El Output Parser es un componente que fuerza las respuestas del LLM a esquemas predefinidos (Pydantic/JSON Schema), eliminando la necesidad de regex o json.loads() en el código.

### Ubicación en Pipeline
- **Input:** Respuesta textual del LLM
- **Output Parser:** Valida y convierte a objeto Python
- **Python:** Recibe objeto validado (no texto)

### Beneficios
1. **Validación Strict:** El LLM DEBE responder en el formato exacto
2. **Sin Parsing Manual:** No más errores de json.loads()
3. **Type Safety:** Conversión automática a tipos Python

### Estructura Pydantic para A3 (Evaluador)
```python
from pydantic import BaseModel
from typing import Literal, Optional

class CampoEvaluado(BaseModel):
    valor: Optional[str | float | int] = None
    es_requerido: bool
    certeza: int  # 0-100
    accion: Literal["skip", "siguiente", "preguntar"]
    pregunta: Optional[str] = None

class EvaluacionSemantica(BaseModel):
    _razonamiento_previo: str
    campos: dict[str, CampoEvaluado]
    estado_global: Literal["COMPLETADO", "PENDIENTE"]
```

### Estructura Pydantic para A4 (Parser)
```python
from pydantic import BaseModel
from typing import Optional

class AsientoContable(BaseModel):
    monto_total: float
    origen: str
    destino: str
    monto: Optional[float] = None
    monto_impuesto: Optional[float] = None
    monto_descuento: Optional[float] = None
    monto_otros_cargos: Optional[float] = None
    moneda: Optional[str] = None
    fecha: Optional[str] = None
    concepto: Optional[str] = None
    categoria: Optional[str] = None
```

### Implementación Sugerida (Fase 2)
- LangChain Pydantic Output Parser
- Instructor library para Ollama

---

## 8. Validación de Cuentas y Categorías (Python)

### Propósito
La validación de cuentas y categorías se realiza en **Python** (no en el LLM), consultando la base de datos después de A3.

### Flujo de Validación
```
A3 (Evaluador) → A4 (Parser JSON) → Python(valida cuentas/categorías) → A5 (SQL) → A6 (Humanizador)
                                                         ↑
                                                    AQUÍ SE HACE LA VALIDACIÓN
```

### Validación de Cuentas (Python)

```python
def validar_cuentas(usuario_id: UUID, origen: str, destino: str) -> dict:
    """Valida que las cuentas existan y pertenezcan al usuario."""
    
    # Validar origen
    cuenta_origen = db.query("""
        SELECT id, nombre, tipo, naturaleza 
        FROM cuentas 
        WHERE usuario_id = :uid 
          AND nombre ILIKE :nombre
          AND activa = TRUE
    """, uid=usuario_id, nombre=origen)
    
    # Validar destino
    cuenta_destino = db.query("""...""")
    
    if not cuenta_origen:
        return {"valido": False, "error": "E001", "mensaje": "Cuenta origen no existe"}
    if not cuenta_destino:
        return {"valido": False, "error": "E002", "mensaje": "Cuenta destino no existe"}
    
    return {"valido": True, "origen": cuenta_origen, "destino": cuenta_destino}
```

### Códigos de Error de Validación
| Código | Descripción | Acción |
|--------|-------------|--------|
| E001 | Cuenta origen no existe | Modo interactivo (preguntar) |
| E002 | Cuenta destino no existe | Modo interactivo (preguntar) |
| E003 | Cuenta no pertenece al usuario | Error de seguridad |

### Validación de Categorías (Python)

```python
def validar_categoria(categoria_nombre: str) -> dict:
    """Valida que la categoría exista."""
    
    categoria = db.query("""
        SELECT id, nombre, tipo 
        FROM categorias 
        WHERE nombre ILIKE :nombre
    """, nombre=categoria_nombre)
    
    if not categoria:
        return {"valido": False, "crear": True}
    
    return {"valido": True, "categoria": categoria}
```

### Notas Importantes
- Las categorías pueden ser **globales** (del sistema) o **del usuario**
- La certeza en A3 es para la **asignación contextual**, no para validación de existencia
- Si A3 asigna una categoría con certeza baja, Python puede corregir contra DB antes de continuar

---

## 9. Panel de Control de Agentes

### Propósito
Permite al administrador configurar los parámetros de cada agente desde una interfaz web.

### Acceso
- Solo usuarios con rol **admin**
- Ubicación: Extender página de configuración en Streamlit

### Parámetros por Agente

| Agente | Parámetros Configurables |
|--------|--------------------------|
| **A1 (Clasificador)** | MODELO_A1, TEMP_A1, TASK_CLASSIFY, CERTEZA_MIN_A1 |
| **A2 (Extractor OCR)** | MODELO_A2, TEMP_A2, TASK_OCR |
| **A3 (Evaluador)** | MODELO_A3, TEMP_A3, TASK_EVALUATE, + todos los campos con es_requerido y threshold |
| **A4 (Parser)** | MODELO_A4, TEMP_A4, TASK_PARSE |
| **A5 (Contable)** | MODELO_A5, TEMP_A5, TASK_SQL |
| **A6 (Humanizador)** | MODELO_A6, TEMP_A6, TASK_CHAT |

### Validación de Parámetros
- Temperatura: 0-2
- Certeza: 0-100
- Modelos: Lista de modelos disponibles en el sistema

---

## 10. Tool Calling - Agente A5 (Contable SQL)

### Propósito
El Agente A5 usa herramientas (Tools/Function Calling) para operar la base de datos de forma autónoma y segura, eliminando la generación de texto SQL libre.

### Herramientas Disponibles

| Herramienta | Función | Uso |
|-------------|---------|-----|
| `consultar_diccionario_datos` | Ver estructura de tablas | Cuando necesita recordar nombres de columnas |
| `ejecutar_lectura_segura` | SELECT de solo lectura | Resolver UUIDs de cuentas/categorías |
| `ejecutar_transaccion_doble` | INSERT en transacción | Ejecutar partida doble |

### Flujo con Tool Calling

```
Input (A4): {monto: 500, origen: "Banco BHD", destino: "Supermercado"}
    │
    ▼
Paso 1: Tool "ejecutar_lectura_segura" → Obtener UUID de "Banco BHD"
    │
    ▼
Paso 2: Tool "ejecutar_lectura_segura" → Obtener UUID de "Supermercado"
    │
    ▼
Paso 3: Tool "ejecutar_transaccion_doble" → INSERT con UUIDs correctos
    │
    ▼
Output: {status: "success", transaction_id: "tx-999"}
```

### Ventajas del Tool Calling

| Ventaja | Descripción |
|---------|-------------|
| **Sin alucinaciones** | Errores de SQL capturados y autocorregidos por el agente |
| **Seguridad** | LLM nunca ve credenciales; Python es el ejecutor |
| **Auditoría** | Logs precisos de qué herramientas se usaron y en qué orden |
| **Dry-Run** | Panel de Control permite activar/desactivar herramientas |

### Panel de Control - Permisos de Herramientas

Desde el Panel de Control de Agentes, el admin puede activar/desactivar herramientas:

| Herramienta | Función | Default |
|-------------|---------|---------|
| `consultar_diccionario_datos` | Lectura de metadata | ✅ Activa |
| `ejecutar_lectura_segura` | SELECT lectura | ✅ Activa |
| `ejecutar_transaccion_doble` | INSERT escritura | ✅ Activa |

**Modo Dry-Run:** Desactivar `ejecutar_transaccion_doble` para pruebas sin afectar la contabilidad real.

---

## 11. Flow Routes

| Route | Name | Agent Flow | Description |
|-------|------|------------|-------------|
| **A** | Chat/Asesoría | A1 → A6 | Free conversation and financial advice |
| **B** | Consulta SQL | A1 → A5 → A6 | A1 classifies, A5 generates SQL, A6 explains |
| **C** | Imagen (OCR) | A1 → A2 → A3 → A4 → Python → A5 → A6 | Image → OCR → Eval → Parse → Validate → SQL → Human |
| **D** | Registro Texto | A1 → A3 → A4 → Python → A5 → A6 | Text → Eval → Parse → Validate → SQL → Human |
| **E** | Ejecución | A5 | Direct commit to Ledger (database) |
| **F** | Autorización | A5 | User approves from Purgatorio, moves to Ledger |

---

## 11. Interactive Validation Flow

When **Agent A3** (Evaluator) detects data below threshold:

1. **Evaluation:** A3 evaluates each field with CoT
2. **Persistence:** State saved in `conversacion_pendiente` table
3. **Interaction:** A6 formulates question to user (Humanizer)
4. **Re-evaluation:** User response goes back to A3
5. **Approval:** When `estado_global == COMPLETADO`, passes to A4

**Anti-Loop Mechanism:** Maximum **5 attempts**. If exceeded, aborts registration.

---

## 12. Configuration (sistema_config)

All customization and prompts reside in the database (or `.env`), respecting Rule #2:

| Key | Description |
|-----|-------------|
| `TASK_CLASSIFY` | Valid intentions/rules for Agent A1 |
| `TASK_OCR` | Guidelines for extracting monetary values from images (Agent A2) |
| `TASK_EVALUATE` | Evaluation logic for Agent A3 with CoT |
| `TASK_PARSE` | Strict JSON schema for accounting entry (Agent A4) |
| `TASK_SQL` | Table structure and PostgreSQL dialect rules (Agent A5) |
| `TASK_CHAT` | Personality, role, and limits for financial assistant (Agent A6) |
| `MODELO_A1` | Model for Classifier (default: qwen2.5-coder:7b) |
| `MODELO_A2` | Model for OCR (default: qwen2.5-vl) |
| `MODELO_A3` | Model for Evaluator (default: qwen2.5-coder:7b) |
| `MODELO_A4` | Model for Parser (default: qwen2.5-coder:7b) |
| `MODELO_A5` | Model for SQL (default: qwen3) |
| `MODELO_A6` | Model for Chat (default: qwen3) |
| `TEMP_A1` to `TEMP_A6` | Temperature per agent |
| `CERTEZA_MIN_A1` | Minimum certainty for classifier |
| `CERTEZA_MONTO_A3` | Threshold for amount fields |
| `CERTEZA_CUENTA_A3` | Threshold for account fields |
| `CERTEZA_CATEGORIA_A3` | Threshold for category fields |

---

## 13. Environment Variables

Required in `.env` file:
- Database credentials (PostgreSQL)
- LLM API keys (for proxy) - Ollama Cloud at localhost:8000
- Telegram bot token
- Streamlit port

Never commit `.env` to version control.

---

## 14. Testing Status

### TASK_CLASSIFY (Agent A1)
| Date | Result | Note |
|------|--------|------|
| 2026-03-31 | 10/10 ✅ | **FIXED**: "hola" classifies correctly |
| 2026-04-01 | 10/10 ✅ | Substring matching bug fixed |

### TASK_PARSE (Agent A4)
| Date | Result | Note |
|------|--------|------|
| 2026-04-01 | 13/13 ✅ | v3 with `_razonamiento_previo` |

### Resolved Issues
1. ✅ **[FIXED]** "hola" → Classified as register (case mismatch + substring matching)
2. ✅ **[FIXED]** "DOP" during registration was sent to ChatAgent instead of merge
3. ✅ **[FIXED]** Processor silent failures - added try/except in __init__
4. ✅ **[FIXED]** Empty chat responses - added fallback message

### Test Logs Location
```
logs/test_rounds/classify/  # TASK_CLASSIFY test logs
logs/test_rounds/parse/     # TASK_PARSE test logs
```

---

## 15. Changelog (2026-04-02)

### Phase 1: Architecture Update (Production Ready)

| Feature | Description |
|---------|-------------|
| **6 Agents Architecture** | Expanded to 6 specialized agents (A1-A6) |
| **A3 Evaluator** | Semantic evaluation with slot-filling logic and interactive state |
| **A5 DBA Tool Calling** | ACID-safe execution via `core.tools`. Raw SQL eliminated |
| **Config Isolation** | `.env` for infra only; `sistema_config` for all user settings |
| **Resilience Layer** | `generate_json_with_retry` and A6 primary fallback routing |
| **Dynamic Thresholds** | All certainty thresholds (monto, cuenta, etc.) moved to DB |

### Files Modified
- `main.py` - Externalized bot messages and sync config
- `AGENTS.md` - Complete rewrite for 4.0
- `core/config_loader.py` - Hierarchical retrieval (DB > .env > Default)
- `agents/dba_agent.py` - Refactored to pure Tool Calling
- `docs/*` - Full harmonization with 4.0 topology

---

*Last updated: 2026-04-02 (Final Audit)*
