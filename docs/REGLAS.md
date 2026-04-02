# REGLAS DE ORO - MyFinance 4.0

Estas son las reglas fundamentales que TODOS los desarrolladores deben seguir al trabajar en MyFinance 4.0.

---

## 📜 Reglas

### 1. Inmutabilidad
**No cambiar prompts, tasks u otras variables de `sistema_config` sin autorización.**

- Los prompts y configuraciones residen en la tabla `sistema_config` de la base de datos
- Cualquier modificación requiere aprobación del lead/official
- No modificar directamente en la base de datos sin proceso de cambio

### 2. Sin Hardcodeo
**No colocar parámetros hardcodeados en el código. Para eso está la tabla `sistema_config` y el archivo `.env`.**

- Toda configuración debe estar en `.env` o `sistema_config`
- Si necesitas un valor configurable, agrégalo a `.env` o pide que se agregue a la DB
- Exceptions: Constantes true/fijas (ej: rutas de archivos, límites de seguridad)

### 3. Control de Flujos
**Mantener los flujos actualizados y pedir autorización antes de hacer un cambio que afecte el flujo.**

- Los flujos están documentados en `docs/flows/routes.md`
- Si vas a cambiar una ruta, agente o lógica de procesamiento, documenta el cambio
- Solicita revisión antes de modificar flujos de procesamiento

### 4. Prompts Robustos (Zero-Shot)
**No usar ejemplos o valores fijos en prompts o tasks. Deben dar instrucciones claras y precisas para que el agente infiera sin "alucinar" o reutilizar ejemplos (evitar la literalidad).**

- Los prompts deben ser zero-shot: dar instrucciones sin ejemplos
- Evitar frases como "por ejemplo...", "como este..."
- Usar instrucciones claras: "Extrae...", "Determina...", "Clasifica..."
- El agente debe inferir, no copiar patrones

### 5. Disciplina
**Seguir las reglas y no modificarlas.**

- Estas reglas son obligatorias, no opcionales
- Si encuentras un caso que no fits, discútelo primero antes de hacer excepciones
- La consistencia del sistema depende de la disciplina de todos

---

## 🔧 Implementación en Código

### Configuración (Core Tools)

```python
# ✅ CORRECTO: Usar ConfigLoader (DB > .env > Default)
from core.config_loader import ConfigLoader
prompt = ConfigLoader.get_task_sql()
model = ConfigLoader.get_model("A5")

# ❌ INCORRECTO: Hardcodear o usar métodos antiguos
prompt = "SELECT * FROM..."
```

### Variables de Entorno

```python
# ✅ CORRECTO: Usar ConfigLoader (centralizado)
from core.config_loader import ConfigLoader
db_host = ConfigLoader.get("DB_HOST")

# ❌ INCORRECTO: Usar os.getenv directamente en lógica de agentes
import os
db_host = os.getenv("DB_HOST")
```

---

## 📋 Lista de Verificación (QA 4.0)

Antes de hacer commit, verifica:

- [ ] ¿Los prompts vienen de `sistema_config` (vía ConfigLoader)?
- [ ] ¿El modelo se obtiene vía `ConfigLoader.get_model("AX")`?
- [ ] ¿Los prompts son zero-shot (sin ejemplos)?
- [ ] ¿La respuesta del LLM usa `generate_json_with_retry` si es JSON?
- [ ] ¿El Agente A5 usa **Tool Calling** en lugar de SQL directo?
- [ ] ¿Seguiste las 5 reglas de oro?

---

## 📚 Referencias

- [System Design](../architecture/system-design.md)
- [Routes Documentation](../flows/routes.md)
- [AGENTS.md](../../AGENTS.md) - Source of Truth para Agentes A1-A6

---

*Last updated: 2026-04-02*
