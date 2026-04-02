
# MyFinance - AI-Powered Personal Finance OS
Sistema de gestión financiera personal con orquestación de agentes IA y procesamiento síncrono.

---

## 📜 REGLAS DE ORO PARA DESARROLLO
1. **Inmutabilidad:** No cambiar prompts, tasks u otras variables de `sistema_config` sin autorización.
2. **Sin Hardcodeo:** No colocar parámetros hardcodeados en el código. Para eso está la tabla `sistema_config` y el archivo `.env`.
3. **Control de Flujos:** Mantener los flujos actualizados y pedir autorización antes de hacer un cambio que afecte el flujo.
4. **Prompts Robustos (Zero-Shot):** No usar ejemplos o valores fijos en prompts o tasks. Deben dar instrucciones claras y precisas para que el agente infiera sin "alucinar" o reutilizar ejemplos (evitar la literalidad).
5. **Disciplina:** Seguir las reglas y no modificarlas.

### Convención Contable (Naturaleza)
* **Crédito (True / 1):** Representa una entrada o aumento en la cuenta.
* **Débito (False / 0):** Representa una salida o disminución en la cuenta.

---

## 🏗️ Jerarquía de Archivos
```text
MyFinance/
├── agents/
|   ├── OCR_agent.py           # Agente 1 - OCR imagenes a texto
│   ├── accounting_agent.py    # Agente 2 - Contable (JSON)
│   ├── dba_agent.py           # Agente 3 - Auditor/DBA
│   ├── chat_agent.py          # Agente 4 - Chat + Humanizador
│   └── clasificador_agent.py  # Agente 5 - Clasificador de intención
├── core/
│   ├── ai_utils.py            # Utilidades IA (LLM, títulos)
│   ├── config_loader.py       # Carga configuración desde DB
│   ├── processor.py           # Router principal (canal + topic_id)
│   └── workflow.py            # Orquestación de rutas (NexusWorkflows)
├── database/
│   ├── queries.py             # Fachada de BD
│   ├── base_queries.py        # Conexión genérica
│   └── [dominios]_queries.py  # Modulares: cuentas, transacciones, etc.
├── web/dashboard/             # Interfaz Streamlit (Views, Config)
├── main.py                    # Gateway de Telegram
└── .env                       # Variables de entorno
```
*(Nota: El sistema RabbitMQ y el agente RAG han sido eliminados en favor de una arquitectura síncrona, directa y sin estado semántico).*

---

## 🧠 Arquitectura de Agentes y Modelos

El sistema utiliza un **Proxy Orquestador (Puerto 8000)** que balancea la carga hacia la GPU o CPU basándose en las palabras clave del modelo, con un `Keep-Alive` de 480 segundos.

| Agente | Rol / Función | Modelo Asignado |
| :--- | :--- | :--- |
| **A1** | **Visión (OCR):** Extrae texto y valores de facturas. | `GLM-OCR` / `qwen2.5-vl` |
| **A2** | **Contador:** Parsea texto a JSON contable estricto. | `ALIENTELLIGENCE/accountingandtaxation:latest` |
| **A3** | **Auditor/DBA:** Valida y ejecuta SQL seguro. | `granite4` / `qwen3` / `qwen2.5` |
| **A4** | **Chat/Humanizador:** Asesoría y traducción de sistema a usuario. | `granite4` / `qwen3` / `qwen2.5` |
| **A5** | **Clasificador:** Decide la ruta (Registro, Consulta, Chat). | `granite4` / `qwen3` / `qwen2.5` |

---

## 🛣️ Flujo del Sistema (Procesamiento Síncrono)

El sistema evalúa la entrada a través de `processor.py` y dispara la ruta correspondiente sin usar colas:

```text
Entrada (Telegram/Streamlit) ──▶ processor.py
                                      │
    ┌─────────────────────────────────┴─────────────────────────────────┐
    │                                                                   │
 [IMAGEN]                                                            [TEXTO]
    │                                                                   │
 RUTA C                                                            Clasificador (A5)
    │                                                                   │
    ├─▶ A1 (OCR)                                  ┌─────────────────────┼─────────────────────┐
    ├─▶ A2 (Contador)                             │                     │                     │
    ├─▶ A3 (Auditor)                         "REGISTRAR"           "CONSULTAR"             "CHAT"
    └─▶ A4 (Humanizador)                          │                     │                     │
                                               RUTA D                RUTA B                RUTA A
                                                  │                     │                     │
                                          A2 (Contador)          A3 (Query SQL)      A4 (Humanizador)
                                          [Flujo Interactivo]    A4 (Explicación)
                                                  │
                                          A3 (DBA / Insert)
```

### Rutas Operativas
| Ruta | Nombre | Flujo de Agentes | Descripción |
| :--- | :--- | :--- | :--- |
| **A** | Chat/Asesoría | A4 | Conversación libre y asesoría financiera. |
| **B** | Consulta SQL | A3 → A4 | A3 genera el SQL basado en la DB, A4 lo explica. |
| **C** | Imagen (OCR) | A1 → A2 → A3 | Extrae texto de factura, parsea a JSON y audita. |
| **D** | Registro Texto | A2 → A3 | Transforma lenguaje natural en asiento contable. |
| **E** | Ejecución | A3 | Commit directo al Ledger (Base de datos). |
| **F** | Autorización | A3 | El usuario aprueba algo en Purgatorio y pasa al Ledger. |
| **G** | Humanizador | A4 | Capa final que traduce logs técnicos a lenguaje amigable. |

---

## 🔄 Flujo Interactivo de Validación (`TASK_ASK`)

Cuando el **Agente 2 (Contador)** intenta armar el JSON en la Ruta D y nota que faltan datos obligatorios (ej. el monto o la cuenta de origen), el sistema evita "adivinar" y entra en un bucle de validación:

1. **Extracción:** A2 evalúa el mensaje. Si faltan datos, retorna `accion: PREGUNTAR` junto con los `datos_parciales` que sí encontró.
2. **Persistencia:** Se guarda el estado en la tabla `conversacion_pendiente`.
3. **Interacción:** El sistema formula la pregunta al usuario.
4. **Re-evaluación:** Al responder el usuario, el A2 une la nueva respuesta con los `datos_parciales` y vuelve a evaluar.
5. **Aprobación:** Cuando `accion == PROCESAR`, se genera un Preview. Si el usuario confirma, pasa al A3 (Auditor).

> ⚠️ **Mecanismo Anti-Loop:** El flujo interactivo tiene un límite estricto de **5 intentos máximos**. Si se supera, el sistema aborta el registro, notifica error y solicita replantear el mensaje inicial para evitar bloqueos.

---

## ⚙️ Configuración del Sistema (`sistema_config`)

Toda la personalización y prompts residen en la base de datos (o `.env`), respetando la Regla #2:

| Clave de Configuración | Descripción de su uso |
| :--- | :--- |
| `TASK_CLASSIFY` | Reglas e intenciones válidas para el Agente 5. |
| `TASK_PARSE` | Esquema JSON estricto para el asiento contable (Agente 2). |
| `TASK_ASK` | Lógica de evaluación para detectar qué entidad falta (Agente 2). |
| `TASK_SQL` | Estructura de tablas y reglas del dialecto PostgreSQL (Agente 3). |
| `TASK_OCR` | Directrices de extracción de valores monetarios de imágenes (Agente 1). |
| `TASK_CHAT` | Personalidad, rol y limitantes del asistente financiero (Agente 4). |
```
pencode -s ses_2ba40c30cffe6EqNwrXtlT8TLo

### Notas sobre los cambios:
1. **RAG Extirpado:** Borré toda mención a `Rutas que consumen/alimentan RAG`, el threshold, `pgvector` y el Agente 6.
2. **Modelos Agrupados:** Usé la notación `granite4 / qwen3 / qwen2.5` para indicar que la plataforma soporta cualquiera de esa familia en el proxy. Si logras hacer funcionar el modelo de `ALIENTELLIGENCE` (que suele tener un system prompt muy ajustado para contabilidad), será un game-changer para el JSON contable.