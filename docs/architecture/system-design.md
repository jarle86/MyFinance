# System Design - MyFinance 4.0

High-level architecture and system design for MyFinance AI-powered personal finance OS.

---

## 1. Overview

**MyFinance** is an AI-powered personal finance OS that orchestrates multiple AI agents to handle:
- Invoice processing (OCR)
- Accounting entry generation
- SQL query execution
- Chat-based financial advice
- Intent classification

**Key Principle:** Synchronous, direct, no RAG, no message queues, no semantic state.

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interfaces                           │
│  ┌─────────────────┐              ┌─────────────────────────┐   │
│  │   Telegram Bot  │              │  Streamlit Dashboard   │   │
│  └────────┬────────┘              └───────────┬─────────────┘   │
└───────────┼─────────────────────────────────────┼─────────────────┘
            │                                     │
            ▼                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Core Processor (processor.py)                │
│              Routes input based on channel + topic_id            │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    ┌─────────┐         ┌─────────┐         ┌─────────┐
    │  IMAGE  │         │  TEXT   │         │  CHAT   │
    └────┬────┘         └────┬────┘         └────┬────┘
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Agent Orchestration (6 Agents)             │
│  ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐     │
│  │ A1  │──▶│ A2  │──▶│ A3  │──▶│ A4  │──▶│ PY  │──▶│ A5  │     │
│  │Clasif│   │OCR  │   │Eval │   │JSON │   │Val │   │SQL  │     │
│  └─────┘   └─────┘   └─────┘   └─────┘   └─────┘   └─────┘     │
│                                                 │          │
│                                                 ▼          │
│                                           ┌─────┐   ┌─────┐  │
│                                           │ A6  │   │     │  │
│                                           │Chat │   │     │  │
│                                           └─────┘   └─────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  PostgreSQL    │
                    │   Database     │
                    └─────────────────┘
```

### Pipeline de Registro
```
A1 (Clasificador) → A2 (OCR) → A3 (Evaluador) → A4 (Parser) → Python(valida) → A5 (SQL) → A6 (Humanizador)
```

---

## 3. System Components

### 3.1 Agents (6 Agents)

| Agent | Role (DB) | Input | Output | Description |
|-------|-----------|-------|--------|-------------|
| **A1** | TASK_CLASSIFY | Text | Route | Intent classification & dynamic routing |
| **A2** | TASK_OCR | Image | Extracted text | Vision-based text extraction |
| **A3** | TASK_EVALUATE | Text/OCR | Evaluation | Semantic evaluation & slot-filling (Interactive) |
| **A4** | TASK_PARSE | Validated Text | Asiento JSON | Deterministic parser for Pydantic models |
| **A5** | TASK_SQL | JSON | SQL Result | DBA with secure Tool Calling architecture |
| **A6** | TASK_CHAT | Any | User friendly | Humanizer & Financial Advisor (Primary Fallback) |

### 3.2 Flow: Registration Pipeline

```
A1 (Clasificador) → A2 (OCR) → A3 (Evaluador) → A4 (Parser) → Python(valida) → A5 (SQL) → A6 (Humanizador)
        TEXTO           TEXTO        EVAL           JSON         CUENTAS          SQL         APROB
```

### 3.3 Panel de Control de Agentes

The system includes an Admin Panel for configuring agent parameters:
- Access: Admin users only (via Streamlit dashboard)
- Configurable: Models, temperatures, prompts, thresholds per agent
- **Tool Permissions:** Enable/disable database tools for A5

### 3.4 Tool Calling (Agente A5)

A5 uses tools to operate the database autonomously:

| Tool | Function | Usage |
|------|----------|-------|
| `ejecutar_lectura_segura` | SELECT query | Resolve Account/Category UUIDs |
| `ejecutar_transaccion_doble` | INSERT (ACID) | Transactional double entry with ACID guarantee |

**Benefits:**
- No hallucinations: SQL errors caught and self-corrected
- Security: LLM never sees credentials
- Audit: Precise logs of which tools were used

### 3.5 Core Modules

| Module | Responsibility |
|--------|---------------|
| `core/processor.py` | Main router - determines route based on input |
| `core/workflow.py` | Orchestrates agent execution chains |
| `core/ai_utils.py` | LLM utilities, title generation |
| `core/config_loader.py` | Loads config from `sistema_config` table |
| `database/queries.py` | Database facade |
| `database/base_queries.py` | Generic DB connection |

### 3.5 Data Layer

- **PostgreSQL** - Primary database
- **sistema_config** - Configuration table for prompts/tasks
- **conversacion_pendiente** - Interactive conversation state

---

## 4. Processing Routes

### Route A: Chat/Asesoría
```
User Text → A1 (Classifier) → A6 (Chat/Humanizer)
```
Free conversation and financial advice.

### Route B: SQL Query
```
User Query → A1 (Classifier) → A5 (DBA Tools) → A6 (Humanizer)
```
Secure generation and explanation of SQL results.

### Route C: Image (OCR)
```
Image → A1 (Classifier) → A2 (OCR) → A3 (Evaluador) → A4 (Parser) → Python → A5 (DBA) → A6 (Humanizer)
```
Process invoice images to accounting entries through the full validation funnel.

### Route D: Text Registration
```
User Text → A1 (Classifier) → A3 (Evaluador) → A4 (Parser) → Python → A5 (DBA) → A6 (Humanizer)
```
Direct text-to-entry transformation with interactive slot-filling.

### Route E: Direct Execution
```
A4 (Parser) → A5 (DBA Tool Call)
```
Internal route for pre-validated JSON commits.

### Route F: Authorization
```
A5 (DBA) → A6 (Humanizer)
```
Purgatorio approval to Ledger execution.

---

## 5. Interactive Validation Flow

When Agent A3 (Evaluador Semántico) detects data below certainty threshold:

1. A3 Evaluates and flags missing entities.
2. If certainty < threshold → estado_global: PENDIENTE.
3. Save interactive context to conversacion_pendiente.
4. Agent A6 (Humanizer) translates A3's flags into a natural question.
5. User response → A3 merges and re-evaluates the entire context.
6. Pipeline completes to A4 when estado_global == COMPLETADO.

**Max 5 attempts** to prevent infinite loops.

---

## 6. Data Flow Examples

### Example 1: Register Expense via Image
```
1. User sends photo of receipt
2. A5 classifies → "registro"
3. A1 extracts: "Café Starbucks $450, fecha 2026-03-31"
4. A2 parses to: {entidades: {monto_total: 450, origen: "tarjeta", destino: "Starbucks"}, ...}
5. A3 validates SQL: INSERT INTO ledger ...
6. Return: "Gasto registrado: Café $450"
```

### Example 2: Query Balance
```
1. User: "¿cuánto gasté este mes?"
2. A5 classifies → "CONSULTAR"
3. A3 generates: SELECT SUM(monto) FROM ledger WHERE ...
4. A4 explains: "Este mes has gastado $X en total"
```

---

## 7. Configuration

All prompts and configuration stored in `sistema_config` table:

| Key | Purpose |
|-----|---------|
| `TASK_CLASSIFY` | A1 intent rules (Zero-Shot) |
| `TASK_OCR` | A2 extraction guidelines |
| `TASK_EVALUATE` | A3 semantic evaluation logic |
| `TASK_PARSE` | A4 accounting JSON schema (v3 + CoT) |
| `TASK_SQL` | A5 PostgreSQL dialect rules for DBA tools |
| `TASK_CHAT` | A6 advisor personality & limits |
| `MODELO_AX` | Model routing from A1 to A6 |
| `CERTEZA_XXX_A3` | Dynamic thresholds for evaluation |

### TASK_PARSE v3 Structure
- Uses `_razonamiento_previo` for Chain of Thought (prevents hallucination)
- Required fields: `monto_total`, `origen`, `destino`
- Enhanced with: `monto_impuesto`, `monto_descuento`, `monto_otros_cargos`

---

## 8. Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| Database | PostgreSQL 14+ |
| AI Models | GLM-OCR, Granite, Qwen, Claude |
| API Gateway | FastAPI (port 8000) |
| UI | Streamlit |
| Messaging | Telegram Bot API |

---

## 9. Non-Functional Requirements

- **Synchronous Processing:** All requests handled immediately
- **No External Queues:** No RabbitMQ, no semantic state
- **Database-Driven Config:** All prompts in `sistema_config`
- **Zero-Shot Prompts:** No examples, clear instructions only

---

## 10. Security Considerations

- Never hardcode API keys (use `.env`)
- Validate SQL before execution (A3)
- Sanitize user input
- Log errors without exposing secrets
- Use parameterized queries

---

## Related Documentation

- [Agent Architecture](agent-architecture.md) - Detailed agent specs
- [Setup Guide](../development/setup.md) - Environment setup
- [Routes](flows/routes.md) - Route details
- [User Flows](flows/user-flows.md) - Interactive flows
- [Troubleshooting](../guides/troubleshooting.md) - Common issues

---

*Last updated: 2026-04-01*
