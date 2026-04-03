"""Tools module for MyFinance - Tool Calling implementations."""

from pathlib import Path
import importlib.util
import sys

from .buscar_entidad import buscar_entidad
from .buscar_cuenta import buscar_cuenta
from .buscar_categoria import buscar_categoria
from .resolver_moneda import resolver_moneda

# Legacy and A5 tools from core/tools.py moved here for package import compatibility.
# Avoid direct recursive import `from core.tools import ...` while inside package.
_tools_module_name = "core._tools_impl"
_tools_path = Path(__file__).resolve().parent.parent / "tools.py"

if _tools_module_name not in sys.modules:
    spec = importlib.util.spec_from_file_location(_tools_module_name, _tools_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_tools_module_name] = module
    spec.loader.exec_module(module)
else:
    module = sys.modules[_tools_module_name]

ejecutar_lectura_segura = module.ejecutar_lectura_segura
ejecutar_transaccion_doble = module.ejecutar_transaccion_doble

__all__ = [
    "buscar_entidad",
    "buscar_cuenta",
    "buscar_categoria",
    "resolver_moneda",
    "ejecutar_lectura_segura",
    "ejecutar_transaccion_doble",
]
