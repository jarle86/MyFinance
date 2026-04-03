"""Configuration loader for MyFinance.

Loads configuration from the sistema_config table in the database.
"""

from typing import Optional

from database import get_config_value, get_all_config, update_config, set_config


# Agent constants
AGENTS = ["A1", "A2", "A3", "A4", "A5", "A6"]

# A3 campos for thresholds
A3_CAMPOS = [
    "monto_total",
    "monto",
    "monto_impuesto",
    "monto_descuento",
    "monto_otros_cargos",
    "origen",
    "destino",
    "categoria",
    "moneda",
    "fecha",
    "concepto",
    "descripcion",
]

# Default values
DEFAULTS = {
    "temp": "0.7",
    "tokens": "2048",
    "timeout": "60",
    "threshold": "70",
    "requerido": "true",
    "herramienta_buscar_entidad": "true",
    "herramienta_dry_run": "false",
    "keywords_escape": "cancelar, saltar, stop, salir, detener",
    "permitir_escritura_db": "true",
}

PREGUNTAS_DEFAULT_A3 = {
    "monto_total": "¿Cuál es el monto total de la transacción?",
    "monto": "¿Cuál es el monto (subtotal)?",
    "monto_impuesto": "¿Cuál es el monto del impuesto?",
    "monto_descuento": "¿Cuál es el monto del descuento?",
    "monto_otros_cargos": "¿Hay otros cargos adicionales?",
    "origen": "¿De dónde salió el dinero? (ej: Efectivo, Banco)",
    "destino": "¿A dónde fue el dinero? (ej: Supermercado, Ahorros)",
    "categoria": "¿Cuál es la categoría? (ej: Alimentación, Transporte)",
    "moneda": "¿En qué moneda? (ej: DOP, USD)",
    "fecha": "¿En qué fecha se realizó?",
    "concepto": "¿Cuál es el concepto o detalle?",
    "descripcion": "¿Tienes una descripción adicional?",
}


def _ensure_config(
    cls, key: str, default: str, descripcion: str = "", modulo: str = ""
) -> str:
    """Ensure config exists, create with default if null."""
    value = cls.get(key)
    if not value:
        cls.set(key, default, descripcion, modulo)
        return default
    return value


# Predefined configuration keys
class ConfigKeys:
    """Configuration key constants."""

    TASK_CLASSIFY = "TASK_CLASSIFY"
    TASK_PARSE = "TASK_PARSE"
    TASK_ASK = "TASK_ASK"
    TASK_SQL = "TASK_SQL"
    TASK_OCR = "TASK_OCR"
    TASK_CHAT = "TASK_CHAT"
    TASK_MERGE = "TASK_MERGE"
    TASK_EVALUATE = "TASK_EVALUATE"


class ConfigLoader:
    """Configuration loader with caching."""

    _cache: dict[str, str] = {}
    _loaded: bool = False

    @classmethod
    def load(cls) -> None:
        """Load all configuration into cache."""
        if cls._loaded:
            return

        try:
            cls._cache = get_all_config()
            cls._loaded = True
            cls._ensure_defaults()
        except Exception:
            cls._cache = {}
            cls._loaded = True

    @classmethod
    def _ensure_defaults(cls) -> None:
        """Ensure default configurations exist."""
        for agente in AGENTS:
            _ensure_config(
                cls,
                f"TEMP_{agente}",
                DEFAULTS["temp"],
                f"Temperatura para {agente}",
                "agentes",
            )
            _ensure_config(
                cls,
                f"TOKENS_{agente}",
                DEFAULTS["tokens"],
                f"Max tokens para {agente}",
                "agentes",
            )
            _ensure_config(
                cls,
                f"TIMEOUT_{agente}",
                DEFAULTS["timeout"],
                f"Timeout para {agente}",
                "agentes",
            )

            # Default models for each agent
            default_model = "qwen2.5-coder:7b"
            if agente == "A2":
                default_model = "qwen2.5-vl"
            elif agente in ("A5", "A6"):
                default_model = "qwen2.5-coder:7b"

            _ensure_config(
                cls,
                f"MODELO_{agente}",
                default_model,
                f"Modelo para {agente}",
                "agentes",
            )

            if agente == "A3":
                for campo in A3_CAMPOS:
                    _ensure_config(
                        cls,
                        f"THRESHOLD_A3_{campo.upper()}",
                        DEFAULTS["threshold"],
                        f"Threshold A3 {campo}",
                        "agentes",
                    )
                    _ensure_config(
                        cls,
                        f"REQUERIDO_A3_{campo.upper()}",
                        DEFAULTS["requerido"],
                        f"Requerido A3 {campo}",
                        "agentes",
                    )
                    _ensure_config(
                        cls,
                        f"PREGUNTA_A3_{campo.upper()}",
                        PREGUNTAS_DEFAULT_A3.get(
                            campo, f"¿Podrías proporcionar {campo}?"
                        ),
                        f"Pregunta aclaración A3 {campo}",
                        "agentes",
                    )

        _ensure_config(
            cls,
            "HERRAMIENTA_BUSCAR_ENTIDAD",
            "true",
            "Habilitar tool buscar_entidad",
            "herramientas",
        )
        _ensure_config(
            cls,
            "PERMITIR_ESCRITURA_DB",
            "false",
            "Habilitar transacciones de escritura (Producción)",
            "herramientas",
        )
        _ensure_config(
            cls,
            "KEYWORDS_ESCAPE",
            "cancelar, cancel, stop, abortar, descartar",
            "Palabras clave para detener flujos",
            "sistema",
        )
        _ensure_config(
            cls,
            "LOG_LEVEL",
            "INFO",
            "Nivel de logging (INFO, WARNING, ERROR)",
            "sistema",
        )
        _ensure_config(
            cls,
            "HERRAMIENTA_DRY_RUN",
            DEFAULTS["herramienta_dry_run"],
            "Modo dry-run",
            "herramientas",
        )
        _ensure_config(
            cls,
            "UMBRAL_FUZZY_A4",
            "0.7",
            "Threshold para fuzzy matching en A4",
            "agentes",
        )
        _ensure_config(
            cls,
            "KEYWORDS_ESCAPE",
            DEFAULTS["keywords_escape"],
            "Palabras clave para detener flujos",
            "sistema",
        )
        _ensure_config(
            cls,
            "BOT_WELCOME_MESSAGE",
            "¡Bienvenido a MyFinance! 💰\n\nTu asistente financiero personal.\n\nPuedo ayudarte a:\n• Registrar gastos e ingresos\n• Consultar tu balance\n• Procesar receipts (envía una imagen)\n• Darte consejos financieros\n\nEnvía un mensaje para comenzar:",
            "Bot Welcome Message",
            "telegram",
        )
        _ensure_config(
            cls,
            "BOT_HELP_MESSAGE",
            '📖 Ayuda de MyFinance\n\nRegistrar gasto:\n"Pagué $500 en taxi"\n"Gasté 200 en supermercado"\n\nRegistrar ingreso:\n"Recibí $10000 de salary"\n"Me pagaron $500"\n\nConsultar:\n"¿Cuánto gasté este mes?"\n"¿Cuál es mi balance?"\n\nComandos:\n/start - Iniciar\n/help - Ver ayuda\n/cancel - Cancelar operación\n\nEnvía una imagen de tu receipt para procesarlo.',
            "Bot Help Message",
            "telegram",
        )
        cls.load()  # Reload after ensuring defaults

    @classmethod
    def reload(cls) -> None:
        """Force reload configuration."""
        cls._loaded = False
        cls._cache = {}
        cls.load()

    @classmethod
    def get(cls, key: str, default: str = "") -> str:
        """Get configuration value by key."""
        if not cls._loaded:
            cls.load()
        return cls._cache.get(key, default)

    @classmethod
    def get_int(cls, key: str, default: int = 0) -> int:
        """Get configuration value as int."""
        val = cls.get(key, str(default))
        try:
            return int(val)
        except ValueError:
            return default

    @classmethod
    def get_float(cls, key: str, default: float = 0.0) -> float:
        """Get configuration value as float."""
        val = cls.get(key, str(default))
        try:
            return float(val)
        except ValueError:
            return default

    @classmethod
    def get_bool(cls, key: str, default: bool = False) -> bool:
        """Get configuration value as bool."""
        val = cls.get(key, "").lower()
        return val in ("true", "1", "yes", "on") or (default and not val)

    @classmethod
    def set(cls, key: str, value: str, descripcion: str = "", modulo: str = "") -> bool:
        """Set configuration value by key (insert if not exists)."""
        success = set_config(key, value, descripcion, modulo)
        if success:
            cls._cache[key] = value
        return success

    @classmethod
    def get_temp(cls, agente: str) -> float:
        """Get temperature for an agent."""
        return cls.get_float(f"TEMP_{agente}", 0.7)

    @classmethod
    def set_temp(cls, agente: str, value: float) -> bool:
        """Set temperature for an agent."""
        return cls.set(
            f"TEMP_{agente}", str(value), f"Temperatura para {agente}", "agentes"
        )

    @classmethod
    def get_tokens(cls, agente: str) -> int:
        """Get max_tokens for an agent."""
        return cls.get_int(f"TOKENS_{agente}", 2048)

    @classmethod
    def set_tokens(cls, agente: str, value: int) -> bool:
        """Set max_tokens for an agent."""
        return cls.set(
            f"TOKENS_{agente}", str(value), f"Max tokens para {agente}", "agentes"
        )

    @classmethod
    def get_timeout(cls, agente: str) -> int:
        """Get timeout for an agent."""
        return cls.get_int(f"TIMEOUT_{agente}", 60)

    @classmethod
    def set_timeout(cls, agente: str, value: int) -> bool:
        """Set timeout for an agent."""
        return cls.set(
            f"TIMEOUT_{agente}", str(value), f"Timeout para {agente}", "agentes"
        )

    @classmethod
    def get_model(cls, agente: str) -> str:
        """Get model for an agent (DB Only)."""
        key = f"MODELO_{agente.upper()}"
        return cls.get(key)

    @classmethod
    def set_model(cls, agente: str, model: str) -> bool:
        """Set model for an agent."""
        key = f"MODELO_{agente.upper()}"
        return cls.set(
            key,
            model,
            f"Modelo para {agente}",
            "agentes",
        )

    @classmethod
    def get_threshold_a3(cls, campo: str) -> int:
        """Get threshold for A3 field."""
        return cls.get_int(f"THRESHOLD_A3_{campo.upper()}", 70)

    @classmethod
    def set_threshold_a3(cls, campo: str, value: int) -> bool:
        """Set threshold for A3 field."""
        return cls.set(
            f"THRESHOLD_A3_{campo.upper()}",
            str(value),
            f"Threshold A3 {campo}",
            "agentes",
        )

    @classmethod
    def get_requerido_a3(cls, campo: str) -> bool:
        """Get requerido for A3 field."""
        return cls.get_bool(f"REQUERIDO_A3_{campo.upper()}", True)

    @classmethod
    def set_requerido_a3(cls, campo: str, value: bool) -> bool:
        """Set requerido for A3 field."""
        return cls.set(
            f"REQUERIDO_A3_{campo.upper()}",
            "true" if value else "false",
            f"Requerido A3 {campo}",
            "agentes",
        )

    @classmethod
    def get_pregunta_a3(cls, campo: str) -> str:
        """Get clarification question for A3 field."""
        default_q = PREGUNTAS_DEFAULT_A3.get(campo, f"¿Podrías proporcionar {campo}?")
        return cls.get(f"PREGUNTA_A3_{campo.upper()}", default_q)

    @classmethod
    def set_pregunta_a3(cls, campo: str, value: str) -> bool:
        """Set clarification question for A3 field."""
        return cls.set(
            f"PREGUNTA_A3_{campo.upper()}",
            value,
            f"Pregunta aclaración A3 {campo}",
            "agentes",
        )

    @classmethod
    def get_tool_buscar_entidad(cls) -> bool:
        """Get if tool buscar_entidad is enabled."""
        return cls.get_bool("HERRAMIENTA_BUSCAR_ENTIDAD", True)

    @classmethod
    def set_tool_buscar_entidad(cls, value: bool) -> bool:
        """Set tool buscar_entidad enabled."""
        return cls.set(
            "HERRAMIENTA_BUSCAR_ENTIDAD",
            "true" if value else "false",
            "Habilitar tool buscar_entidad",
            "herramientas",
        )

    @classmethod
    def get_tool_dry_run(cls) -> bool:
        """Get if dry-run mode is enabled."""
        return cls.get_bool("HERRAMIENTA_DRY_RUN", False)

    @classmethod
    def set_tool_dry_run(cls, value: bool) -> bool:
        """Set dry-run mode enabled."""
        return cls.set(
            "HERRAMIENTA_DRY_RUN",
            "true" if value else "false",
            "Modo dry-run",
            "herramientas",
        )

    @classmethod
    def get_keywords_escape(cls) -> str:
        """Get escape keywords for commands."""
        return cls.get("KEYWORDS_ESCAPE", DEFAULTS["keywords_escape"])

    @classmethod
    def get_permitir_escritura_db(cls) -> bool:
        """Get if DB writing is allowed."""
        return cls.get_bool("PERMITIR_ESCRITURA_DB", True)

    @classmethod
    def get_task(cls, task_name: str) -> str:
        """Get a task prompt from configuration."""
        return cls.get(task_name, "")

    @classmethod
    def get_log_level(cls) -> str:
        """Get log level configuration."""
        return cls.get("LOG_LEVEL", "INFO").upper()

    @classmethod
    def set_log_level(cls, level: str) -> bool:
        """Set log level configuration."""
        valid_levels = ["INFO", "WARNING", "ERROR"]
        if level.upper() not in valid_levels:
            level = "INFO"
        return cls.set(
            "LOG_LEVEL", level.upper(), "Nivel de logging del dashboard", "sistema"
        )

    @classmethod
    def get_agent_config(cls, agente: str) -> dict:
        """Get agent configuration from JSON stored in sistema_config.

        Args:
            agente: Agent name (e.g., 'A1', 'A2', 'clasificador')

        Returns:
            Dict with agent parameters (min_certeza, temperature, max_tokens, etc.)
        """
        import json

        config_json = cls.get(f"CONFIG_{agente.upper()}", "{}")
        try:
            return json.loads(config_json) if config_json else {}
        except json.JSONDecodeError:
            return {}

    @classmethod
    def set_agent_config(cls, agente: str, config: dict) -> bool:
        """Set agent configuration as JSON in sistema_config.

        Args:
            agente: Agent name (e.g., 'A1', 'A2', 'clasificador')
            config: Dict with agent parameters

        Returns:
            True if saved successfully
        """
        import json

        config_json = json.dumps(config, ensure_ascii=False)
        return cls.set(
            f"CONFIG_{agente.upper()}",
            config_json,
            f"Configuración del agente {agente}",
            "agentes",
        )

    @classmethod
    def get_required(cls, key: str) -> str:
        """Get a required configuration value."""
        value = cls.get(key)
        if not value:
            raise ValueError(f"Required configuration '{key}' not found")
        return value


# Convenience functions
def get_task_classify() -> str:
    """Get the TASK_CLASSIFY configuration."""
    return ConfigLoader.get_task(ConfigKeys.TASK_CLASSIFY)


def get_task_parse() -> str:
    """Get the TASK_PARSE configuration."""
    return ConfigLoader.get_task(ConfigKeys.TASK_PARSE)


def get_task_ask() -> str:
    """Get the TASK_ASK configuration."""
    return ConfigLoader.get_task(ConfigKeys.TASK_ASK)


def get_task_sql() -> str:
    """Get the TASK_SQL configuration."""
    return ConfigLoader.get_task(ConfigKeys.TASK_SQL)


def get_task_ocr() -> str:
    """Get the TASK_OCR configuration."""
    return ConfigLoader.get_task(ConfigKeys.TASK_OCR)


def get_task_chat() -> str:
    """Get the TASK_CHAT configuration."""
    return ConfigLoader.get_task(ConfigKeys.TASK_CHAT)


def get_task_evaluate() -> str:
    """Get the TASK_EVALUATE configuration."""
    return ConfigLoader.get_task(ConfigKeys.TASK_EVALUATE)
