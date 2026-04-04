"""Streamlit Dashboard for MyFinance."""

import os
import sys


# DYNAMICALLY find and add project root
def _find_project_root(start_path: str) -> str:
    """Find project root by looking for 'core' and 'database' directories."""
    current = start_path
    for _ in range(5):  # Look up to 5 levels
        if os.path.isdir(os.path.join(current, "core")) and os.path.isdir(
            os.path.join(current, "database")
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return start_path


# Try to find project root from various possible locations
_possible_roots = [
    os.path.dirname(os.path.abspath(__file__)),  # web/dashboard
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # MyFinance4.0
    os.getcwd(),  # current working directory
    "/home/jarias/MyFinance4.0",  # absolute path
]

_project_root = None
for _root in _possible_roots:
    if os.path.isdir(os.path.join(_root, "core")) and os.path.isdir(
        os.path.join(_root, "database")
    ):
        _project_root = _root
        break

if _project_root is None:
    raise RuntimeError(
        "Cannot find project root with 'core' and 'database' directories"
    )

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Now import everything else
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from uuid import UUID

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

try:
    from database.reportes_queries import (
        obtener_reporte_consumos,
        obtener_resumen_consumos,
        obtener_reporte_presupuestos,
        obtener_reporte_por_categoria,
        obtener_reporte_cuentas,
        obtener_balance_comprobacion,
        obtener_saldos_por_tipo,
        obtener_kpis_dashboard,
        obtener_presupuestos_activos,
        formatear_monto
    )
except ImportError:
    pass # Guard in case the user has not implemented this file yet


# Load environment from project root
load_dotenv(os.path.join(_project_root, ".env"))

# ===========================================
# LOGGING CONFIGURATION
# ===========================================
LOG_DIR = os.path.join(_project_root, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"system{datetime.now().strftime('%d%m%Y')}.log")

# Configure root logger
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.DEBUG)

# File handler - captures INFO, WARNING, ERROR
_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
)

# Add file handler to root
if not _root_logger.handlers:
    _root_logger.addHandler(_file_handler)

# Dashboard logger
logger = logging.getLogger("dashboard")


def get_log_level_from_config() -> int:
    """Get log level from config, default to INFO."""
    from core.config_loader import ConfigLoader

    level_str = ConfigLoader.get_log_level()
    return {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }.get(level_str, logging.INFO)


def log_message(level: str, message: str, username: str = None):
    """Log message with configured level filter."""
    config_level = get_log_level_from_config()

    log_str = f"dashboard | {message}"
    if username:
        log_str = f"User {username} | {message}"

    if level == "DEBUG":
        if config_level <= logging.DEBUG:
            logger.debug(log_str)
    elif level == "INFO":
        if config_level <= logging.INFO:
            logger.info(log_str)
    elif level == "WARNING":
        if config_level <= logging.WARNING:
            logger.warning(log_str)
    elif level == "ERROR":
        if config_level <= logging.ERROR:
            logger.error(log_str)


from core.processor import get_processor, MessageType
from database import (
    ChatMessage,
    ChatTopic,
    create_categoria,
    create_chat_topic,
    create_cuenta,
    crear_cuenta_con_apertura,
    delete_categoria,
    delete_cuenta,
    delete_chat_topic,
    get_categorias_by_user,
    get_chat_messages_by_topic,
    get_chat_topics_by_user,
    get_cuentas_by_user,
    get_default_categorias,
    get_or_create_default_topic,
    get_or_create_user,
    get_all_models_config,
    get_user_by_id,
    test_connection,
    update_categoria,
    update_config,
    update_cuenta,
    update_user,
    check_categoria_en_uso,
    check_cuenta_en_uso,
)
from core.ai_utils import get_available_models
from core.identity import IdentityGateway

# Page config
st.set_page_config(
    page_title="MyFinance",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Constants
DEFAULT_CHANNEL = "web"
MAX_MESSAGES = 500

# ===========================================
# SESSION RESTORATION (localStorage -> st.session_state)
# ===========================================
if "user_id" not in st.session_state:
    # Check query params first (set by JS below)
    q_user_id = st.query_params.get("restore_user_id")
    q_username = st.query_params.get("restore_username")
    
    if q_user_id and q_username:
        st.session_state.user_id = UUID(q_user_id)
        st.session_state.username = q_username
        # Clear params to avoid loop
        st.query_params.clear()
        st.rerun()
    else:
        # Inject JS to read from localStorage and redirect with params
        restore_js = """
        <script>
            const user_id = localStorage.getItem('myfinance_user');
            const username = localStorage.getItem('myfinance_username');
            if (user_id && username && !window.location.search.includes('restore_user_id')) {
                const url = new URL(window.location.href);
                url.searchParams.set('restore_user_id', user_id);
                url.searchParams.set('restore_username', username);
                window.location.href = url.href;
            }
        </script>
        """
        st.markdown(restore_js, unsafe_allow_html=True)

# Initialize messages list
if "messages" not in st.session_state:
    st.session_state.messages = []


def is_logged_in() -> bool:
    """Check if user is logged in."""
    # 🔥 BYPASS DESARROLLO
    return True
    # return "user_id" in st.session_state and st.session_state.user_id is not None


def get_user_id() -> Optional[UUID]:
    """Get current user ID from session."""
    if is_logged_in():
        # 🔥 BYPASS DESARROLLO: Retornar ID del usuario de prueba especificado
        if "user_id" not in st.session_state:
            st.session_state.user_id = UUID("9fad790c-73d0-4d53-bc8e-7221d64cb709") # Forza ID solicitado solo por esta ocasion se permite harcodear
            st.session_state.username = "jarias"
        return st.session_state.user_id
    return None


def login_page():
    """Render login page."""
    # Check if already logged in (including restored session)
    if is_logged_in():
        return

    st.title("💰 MyFinance - Login")

    # (JavaScript detection moved to global main scope)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("---")
        st.markdown("### Iniciar Sesión")

        username = st.text_input("Usuario", placeholder="Ingresa tu usuario")
        password = st.text_input(
            "Contraseña", type="password", placeholder="Ingresa tu contraseña"
        )

        remember_me = st.checkbox("🔐 Mantener sesión activa", value=False)

        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            login_clicked = st.button(
                "🎫 Iniciar Sesión", use_container_width=True, type="primary"
            )

        with col_btn2:
            register_clicked = st.button("📝 Registrarse", use_container_width=True)

        st.markdown("---")

        if login_clicked and username:
            if username == "web_test":
                user = IdentityGateway.authenticate_web_user(username, password)
                if user:
                    st.session_state.user_id = user["user_id"]
                    st.session_state.username = user["username"]

                    if remember_me:
                        # JavaScript to save to localStorage
                        save_js = f"""
                        <script>
                            localStorage.setItem('myfinance_user', '{user["user_id"]}');
                            localStorage.setItem('myfinance_username', '{user["username"]}');
                            setTimeout(() => {{ window.location.href = window.location.pathname; }}, 100);
                        </script>
                        """
                        st.markdown(save_js, unsafe_allow_html=True)
                        st.success(f"¡Bienvenido, {user['username']}! Recordaremos tu sesión.")
                        # Rerun will happen after JS redirect or manually if JS fails
                    else:
                        log_message(
                            "INFO", f"Login exitoso - usuario: {username}", username
                        )
                        st.success(f"¡Bienvenido, {user['username']}!")
                        st.rerun()
                else:
                    log_message(
                        "WARNING",
                        f"Login fallido - usuario: {username} - credenciales inválidas",
                    )
                    st.error("Credenciales inválidas")
            else:
                user = IdentityGateway.authenticate_web_user(username, password)
                if user:
                    st.session_state.user_id = user["user_id"]
                    st.session_state.username = user["username"]

                    if remember_me:
                        save_js = f"""
                        <script>
                            localStorage.setItem('myfinance_user', '{user["user_id"]}');
                            localStorage.setItem('myfinance_username', '{user["username"]}');
                        </script>
                        """
                        st.markdown(save_js, unsafe_allow_html=True)

                    log_message(
                        "INFO", f"Login exitoso - usuario: {username}", username
                    )
                    st.success(f"¡Bienvenido, {user['username']}!")
                    st.rerun()
                else:
                    log_message(
                        "WARNING",
                        f"Login fallido - usuario: {username} - credenciales incorrectas",
                    )
                    st.error("Usuario o contraseña incorrectos")

        if register_clicked:
            st.session_state.show_register = True
            st.rerun()


def register_page():
    """Render registration page."""
    st.title("💰 MyFinance - Registro")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown("---")
        st.markdown("### Crear Cuenta")

        username = st.text_input("Usuario", placeholder="Elige un nombre de usuario")
        password = st.text_input(
            "Contraseña", type="password", placeholder="Elige una contraseña"
        )
        password_confirm = st.text_input(
            "Confirmar Contraseña",
            type="password",
            placeholder="Confirma tu contraseña",
        )

        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button("🔙 Volver al Login", use_container_width=True):
                st.session_state.show_register = False
                st.rerun()

        with col_btn2:
            register_clicked = st.button(
                "✅ Crear Cuenta", use_container_width=True, type="primary"
            )

        st.markdown("---")

        if register_clicked and username and password:
            if password != password_confirm:
                log_message(
                    "WARNING",
                    f"Registro fallido - usuario: {username} - contraseñas no coinciden",
                )
                st.error("Las contraseñas no coinciden")
            elif len(password) < 4:
                log_message(
                    "WARNING",
                    f"Registro fallido - usuario: {username} - contraseña muy corta",
                )
                st.error("La contraseña debe tener al menos 4 caracteres")
            else:
                existing = IdentityGateway.get_user_by_username(username)
                if existing:
                    log_message(
                        "WARNING", f"Registro fallido - usuario: {username} - ya existe"
                    )
                    st.error("El usuario ya existe")
                else:
                    import hashlib

                    password_hash = hashlib.sha256(password.encode()).hexdigest()
                    user = IdentityGateway.create_web_user(username, password_hash)
                    st.session_state.user_id = user["user_id"]
                    st.session_state.username = user["username"]
                    log_message(
                        "INFO", f"Usuario registrado exitosamente: {username}", username
                    )
                    st.success(f"¡Cuenta creada! Bienvenido, {user['username']}")
                    st.rerun()


def load_topics(user_id: UUID, channel: str) -> list[ChatTopic]:
    """Load chat topics for user and channel."""
    try:
        return get_chat_topics_by_user(user_id, channel)
    except Exception as e:
        st.error(f"Error loading topics: {e}")
        return []


def load_messages(topic_id: UUID, channel: str) -> list[ChatMessage]:
    """Load messages for a topic."""
    try:
        return get_chat_messages_by_topic(topic_id, channel, MAX_MESSAGES)
    except Exception as e:
        st.error(f"Error loading messages: {e}")
        return []


def send_message(
    message: str,
    message_type: MessageType,
    user_id: UUID,
    channel: str,
    topic_id: UUID,
    file_path: str = None,
) -> tuple:
    """Send a message and get response."""
    processor = get_processor()

    try:
        result, _ = processor.process_with_chat_history(
            message=message,
            message_type=message_type,
            user_id=user_id,
            channel=channel,
            topic_id=topic_id,
        )
        return result.response, result.route.value if result.route else None
    except Exception as e:
        return f"Error: {str(e)}", None


def create_new_topic(
    user_id: UUID, channel: str, title: str = "Nueva conversación"
) -> ChatTopic:
    """Create a new chat topic."""
    try:
        return create_chat_topic(user_id, channel, title)
    except Exception as e:
        st.error(f"Error creating topic: {e}")
        return None


def render_chat_page(user_id: UUID, channel: str):
    """Render the chat page."""
    st.header("💬 Chat Financiero")

    # Load topics
    topics = load_topics(user_id, channel)

    # Check for pending confirmation state in session
    pending_confirmation = st.session_state.get("pending_confirmation", False)
    pending_data = st.session_state.get("pending_data", {})

    # Check for pending conversation in Database (Interactive Mode)
    from database import get_pending_conversation
    db_pending = get_pending_conversation(user_id, channel)
    
    if db_pending and db_pending.estado != "finalizada":
        st.info(f"""
        📝 **Sesión Interactiva Abierta**
        Estás en medio de un registro. Datos capturados: `{db_pending.datos}`.
        Completa los campos faltantes o escribe **'cancelar'** para empezar de nuevo.
        """, icon="ℹ️")

    # Topic selector in sidebar
    with st.sidebar:
        st.markdown("### 📋 Conversaciones")

        if st.button("🔵 Nueva Conversación", use_container_width=True):
            # Clear pending states when creating new conversation
            st.session_state.pop("pending_confirmation", None)
            st.session_state.pop("pending_data", None)

            new_topic = create_new_topic(user_id, channel, "Nueva conversación")
            if new_topic:
                st.session_state.current_topic_id = new_topic.id
                st.rerun()

        st.markdown("---")

        # Topic list
        for topic in topics:
            col1, col2 = st.columns([4, 1])
            with col1:
                if st.button(
                    f"💬 {topic.titulo[:25]}..."
                    if len(topic.titulo) > 25
                    else f"💬 {topic.titulo}",
                    key=f"topic_{topic.id}",
                    use_container_width=True,
                ):
                    # Clear pending states when switching topics
                    st.session_state.pop("pending_confirmation", None)
                    st.session_state.pop("pending_data", None)
                    st.session_state.current_topic_id = topic.id
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"delete_{topic.id}", help="Eliminar"):
                    try:
                        delete_chat_topic(topic.id)
                        if st.session_state.get("current_topic_id") == topic.id:
                            st.session_state.pop("current_topic_id", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # Current topic
    current_topic_id = st.session_state.get("current_topic_id")

    if not current_topic_id and topics:
        current_topic_id = topics[0].id
        st.session_state.current_topic_id = current_topic_id
    elif not current_topic_id:
        # Create default topic
        try:
            default_topic = get_or_create_default_topic(user_id, channel)
            current_topic_id = default_topic.id
            st.session_state.current_topic_id = current_topic_id
        except Exception:
            pass

    if not current_topic_id:
        st.warning("No hay conversaciones. Crea una nueva.")
        return

    # Load messages into session state if topic changed or not initialized
    if "messages" not in st.session_state or st.session_state.get("last_topic_id") != current_topic_id:
        st.session_state.messages = load_messages(current_topic_id, channel)
        st.session_state.last_topic_id = current_topic_id

    # Chat container
    chat_container = st.container(height=450, key="chat_container")

    with chat_container:
        for msg in st.session_state.messages:
            # Handle both object attributes and dict keys for flexibility
            role = getattr(msg, "role", msg.get("role") if isinstance(msg, dict) else "assistant")
            content = getattr(msg, "content", msg.get("content") if isinstance(msg, dict) else str(msg))
            with st.chat_message(role):
                st.markdown(content)

    # Handle confirmation buttons (if pending confirmation)
    if pending_confirmation:
        st.markdown("---")
        st.markdown("### ✅ Confirmar Registro")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirmar", use_container_width=True, key="btn_confirm"):
                # Process confirmation
                with st.spinner("Confirmando..."):
                    response, route = send_message(
                        message="confirmar",
                        message_type=MessageType.TEXT,
                        user_id=user_id,
                        channel=channel,
                        topic_id=current_topic_id,
                    )

                # Clear pending state
                st.session_state.pop("pending_confirmation", None)
                st.session_state.pop("pending_data", None)

                # Append and rerun
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()

        with col2:
            if st.button("❌ Cancelar", use_container_width=True, key="btn_cancel"):
                # Process cancel
                with st.spinner("Cancelando..."):
                    response, route = send_message(
                        message="cancelar",
                        message_type=MessageType.TEXT,
                        user_id=user_id,
                        channel=channel,
                        topic_id=current_topic_id,
                    )

                # Clear pending state
                st.session_state.pop("pending_confirmation", None)
                st.session_state.pop("pending_data", None)

                # Append and rerun
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()

    # Input area (only show if not pending confirmation)
    if not pending_confirmation:
        st.markdown("---")

        # File uploader for images/PDFs
        uploaded_file = st.file_uploader(
            "Adjuntar archivo (imagen o PDF)",
            type=["png", "jpg", "jpeg", "pdf"],
            key="file_uploader",
            label_visibility="collapsed",
        )

        # Text input
        if prompt := st.chat_input("Escribe un mensaje..."):
            # Append user message to session state immediately
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Add user message to display immediately
            with st.chat_message("user"):
                st.markdown(prompt)

            # Get response
            with st.spinner("Procesando..."):
                response, route = send_message(
                    message=prompt,
                    message_type=MessageType.TEXT,
                    user_id=user_id,
                    channel=channel,
                    topic_id=current_topic_id,
                )

            # Append assistant response to session state immediately
            st.session_state.messages.append({"role": "assistant", "content": response, "route": route})

            # Display response
            with st.chat_message("assistant"):
                st.markdown(response)
                if route:
                    st.caption(f"Ruta: {route}")

            # If it's a registration (Route D), show confirmation buttons after response
            if route == "D":
                st.markdown("---")
                st.markdown("### ¿Confirmas este registro?")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(
                        "✅ Confirmar",
                        use_container_width=True,
                        key="btn_confirm_after",
                    ):
                        # Send confirmation
                        response2, _ = send_message(
                            message="confirmar",
                            message_type=MessageType.TEXT,
                            user_id=user_id,
                            channel=channel,
                            topic_id=current_topic_id,
                        )
                        st.session_state.messages.append({"role": "assistant", "content": response2})
                        st.success(response2)
                        st.rerun()

                with col2:
                    if st.button(
                        "❌ Cancelar", use_container_width=True, key="btn_cancel_after"
                    ):
                        # Send cancel
                        response2, _ = send_message(
                            message="cancelar",
                            message_type=MessageType.TEXT,
                            user_id=user_id,
                            channel=channel,
                            topic_id=current_topic_id,
                        )
                        st.session_state.messages.append({"role": "assistant", "content": response2})
                        st.rerun()
            else:
                st.rerun()

        # Handle file upload
        if uploaded_file is not None:
            # Save to temp file
            import tempfile

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f"_{uploaded_file.name}"
            ) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            # Determine message type
            message_type = MessageType.IMAGE
            if uploaded_file.name.lower().endswith(".pdf"):
                message_type = MessageType.PDF

            # Show processing indicator
            with st.spinner("Procesando archivo..."):
                st.session_state.messages.append({"role": "user", "content": f"📎 *Archivo adjunto: {uploaded_file.name}*"})
                response, route = send_message(
                    message=tmp_path,
                    message_type=message_type,
                    user_id=user_id,
                    channel=channel,
                    topic_id=current_topic_id,
                )

            # Append and rerun
            st.session_state.messages.append({"role": "assistant", "content": response, "route": route})
            st.session_state.file_uploader = None
            st.rerun()


def render_summary_page():
    """Show summary page."""
    st.header("📊 Resumen")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Ingresos", "$0.00", "+0%")

    with col2:
        st.metric("Gastos", "$0.00", "+0%")

    with col3:
        st.metric("Balance", "$0.00", "0%")

    st.info("📌 Conecta la base de datos para ver tus datos")


def render_transactions_page(user_id: UUID):
    """Show transactions page with full details and pagination."""
    from database import (
        get_transacciones_full,
        get_transacciones_summary,
        update_transaccion,
        get_cuentas_by_user,
        get_categorias_by_user,
    )
    from uuid import UUID

    st.header("📝 Transacciones")

    per_page = 20

    if "tx_page" not in st.session_state:
        st.session_state.tx_page = 1

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        fecha_inicio = st.date_input(
            "Desde", date.today() - timedelta(days=30), key="tx_fecha_inicio"
        )

    with col2:
        fecha_fin = st.date_input("Hasta", date.today(), key="tx_fecha_fin")

    with col3:
        tipo_options = ["", "gasto", "ingreso", "transferencia"]
        tipo_labels = {
            "": "Todos",
            "gasto": "Gasto",
            "ingreso": "Ingreso",
            "transferencia": "Transferencia",
        }
        tipo_filter = st.selectbox(
            "Tipo",
            options=tipo_options,
            format_func=lambda x: tipo_labels.get(x, x),
            key="tx_tipo",
        )

    with col4:
        estado_options = ["", "confirmado", "pendiente", "cancelado"]
        estado_labels = {
            "": "Todos",
            "confirmado": "Confirmados",
            "pendiente": "Pendientes",
            "cancelado": "Cancelados",
        }
        estado_filter = st.selectbox(
            "Estado",
            options=estado_options,
            format_func=lambda x: estado_labels.get(x, x),
            key="tx_estado",
        )

    transacciones, total_count = get_transacciones_full(
        usuario_id=user_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        tipo=tipo_filter if tipo_filter else None,
        estado=estado_filter if estado_filter else None,
        page=st.session_state.tx_page,
        per_page=per_page,
    )

    summary = get_transacciones_summary(
        usuario_id=user_id,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    total_pages = max(1, (total_count + per_page - 1) // per_page)

    col_nav1, col_nav2, col_nav3 = st.columns([2, 3, 2])
    with col_nav1:
        if st.button(
            "⬅️ Anterior", key="tx_prev", disabled=st.session_state.tx_page <= 1
        ):
            st.session_state.tx_page -= 1
            st.rerun()

    with col_nav2:
        page_options = (
            list(range(1, total_pages + 1))
            if total_pages <= 10
            else list(range(1, min(11, total_pages + 1)))
        )
        selected_page = st.selectbox(
            f"Página {st.session_state.tx_page} de {total_pages}",
            options=page_options,
            index=min(st.session_state.tx_page - 1, len(page_options) - 1),
            key="tx_page_select",
        )
        if selected_page != st.session_state.tx_page:
            st.session_state.tx_page = selected_page
            st.rerun()

    with col_nav3:
        if st.button(
            "Siguiente ➡️",
            key="tx_next",
            disabled=st.session_state.tx_page >= total_pages,
        ):
            st.session_state.tx_page += 1
            st.rerun()

    st.markdown("---")

    if transacciones:
        for tx in transacciones:
            with st.container():
                col_icon, col_main, col_monto, col_actions = st.columns([0.5, 4, 2, 1])

                tipo_emoji = {
                    "gasto": "💸",
                    "ingreso": "💰",
                    "transferencia": "🔄",
                }.get(tx.get("tipo", ""), "📝")
                estado_color = {
                    "confirmado": "🟢",
                    "pendiente": "🟡",
                    "cancelado": "🔴",
                }.get(tx.get("estado", ""), "")

                with col_icon:
                    st.markdown(f"### {tipo_emoji}")

                with col_main:
                    fecha_str = (
                        tx.get("fecha").strftime("%d/%m/%Y")
                        if tx.get("fecha")
                        else "Sin fecha"
                    )
                    cuenta = tx.get("cuenta_nombre", "Sin cuenta")
                    categoria = tx.get("categoria_nombre", "Sin categoría")
                    categoria_icono = tx.get("categoria_icono", "")
                    descripcion = (
                        tx.get("descripcion")
                        or tx.get("proveedor")
                        or "Sin descripción"
                    )
                    if len(descripcion) > 50:
                        descripcion = descripcion[:47] + "..."

                    st.markdown(f"**{fecha_str}** | {cuenta}")
                    st.caption(f"{categoria_icono} {categoria} • {descripcion}")

                with col_monto:
                    monto = tx.get("monto", 0)
                    impuesto = tx.get("monto_impuesto") or 0
                    monto_total = monto + impuesto
                    es_gasto = tx.get("naturaleza", False) == False

                    if es_gasto:
                        st.markdown(
                            f"<span style='color:red'>-${monto_total:,.2f}</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<span style='color:green'>+${monto_total:,.2f}</span>",
                            unsafe_allow_html=True,
                        )

                    if impuesto > 0:
                        st.caption(f"(+IVA: ${impuesto:,.2f})")

                with col_actions:
                    if st.button("✏️", key=f"edit_{tx['id']}"):
                        st.session_state.edit_tx_id = str(tx["id"])
                        st.session_state.show_edit_modal = True

                st.markdown("---")

        if st.session_state.get("show_edit_modal") and st.session_state.get(
            "edit_tx_id"
        ):
            tx_id = UUID(st.session_state.edit_tx_id)
            tx_data = next((t for t in transacciones if t["id"] == tx_id), None)

            if tx_data:
                with st.expander("✏️ Editar Transacción", expanded=True):
                    with st.form(key=f"edit_form_{tx_id}"):
                        col_f1, col_f2 = st.columns(2)

                        with col_f1:
                            new_tipo = st.selectbox(
                                "Tipo",
                                options=["gasto", "ingreso", "transferencia"],
                                index=["gasto", "ingreso", "transferencia"].index(
                                    tx_data.get("tipo", "gasto")
                                ),
                            )
                            new_monto = st.number_input(
                                "Monto",
                                value=float(tx_data.get("monto", 0)),
                                min_value=0.01,
                                step=0.01,
                                format="%.2f",
                            )
                            new_fecha = st.date_input(
                                "Fecha", tx_data.get("fecha", date.today())
                            )
                            new_descripcion = st.text_area(
                                "Descripción",
                                value=tx_data.get("descripcion") or "",
                                max_chars=500,
                            )

                        with col_f2:
                            cuentas = get_cuentas_by_user(user_id)
                            cuenta_options = {str(c.id): c.nombre for c in cuentas}
                            cuenta_options[""] = "Sin cuenta"
                            current_cuenta = (
                                str(tx_data.get("cuenta_id"))
                                if tx_data.get("cuenta_id")
                                else ""
                            )

                            new_cuenta_id = st.selectbox(
                                "Cuenta",
                                options=list(cuenta_options.keys()),
                                index=list(cuenta_options.keys()).index(current_cuenta)
                                if current_cuenta in cuenta_options
                                else 0,
                                format_func=lambda x: cuenta_options.get(x, x),
                            )

                            categorias = get_categorias_by_user(user_id)
                            cat_options = {
                                str(c.id): f"{c.icono or ''} {c.nombre}".strip()
                                for c in categorias
                            }
                            cat_options[""] = "Sin categoría"
                            current_cat = (
                                str(tx_data.get("categoria_id"))
                                if tx_data.get("categoria_id")
                                else ""
                            )

                            new_categoria_id = st.selectbox(
                                "Categoría",
                                options=list(cat_options.keys()),
                                index=list(cat_options.keys()).index(current_cat)
                                if current_cat in cat_options
                                else 0,
                                format_func=lambda x: cat_options.get(x, x),
                            )

                            estado_options_list = [
                                "confirmado",
                                "pendiente",
                                "cancelado",
                            ]
                            new_estado = st.selectbox(
                                "Estado",
                                options=estado_options_list,
                                index=estado_options_list.index(
                                    tx_data.get("estado", "confirmado")
                                ),
                            )

                            new_impuesto = st.number_input(
                                "Impuesto",
                                value=float(tx_data.get("monto_impuesto") or 0),
                                min_value=0,
                                step=0.01,
                                format="%.2f",
                            )

                        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])

                        with col_btn1:
                            submitted = st.form_submit_button(
                                "💾 Guardar cambios", use_container_width=True
                            )

                        with col_btn2:
                            if st.form_submit_button(
                                "🗑️ Cancelar", use_container_width=True
                            ):
                                update_transaccion(
                                    transaccion_id=tx_id,
                                    estado="cancelado",
                                )
                                st.success("Transacción cancelada")
                                st.session_state.show_edit_modal = False
                                st.rerun()

                        with col_btn3:
                            if st.form_submit_button(
                                "❌ Cerrar", use_container_width=True
                            ):
                                st.session_state.show_edit_modal = False
                                st.rerun()

                        if submitted:
                            update_transaccion(
                                transaccion_id=tx_id,
                                tipo=new_tipo,
                                monto=new_monto,
                                fecha=new_fecha,
                                descripcion=new_descripcion,
                                cuenta_id=UUID(new_cuenta_id)
                                if new_cuenta_id
                                else None,
                                categoria_id=UUID(new_categoria_id)
                                if new_categoria_id
                                else None,
                                estado=new_estado,
                                monto_impuesto=new_impuesto,
                            )
                            st.success("Transacción actualizada")
                            st.session_state.show_edit_modal = False
                            st.rerun()
    else:
        st.info("📭 No hay transacciones en este período")

    st.markdown("---")

    col_sum1, col_sum2, col_sum3 = st.columns(3)
    with col_sum1:
        st.metric("💸 Total Gastos", f"${summary['total_gastos']:,.2f}")
    with col_sum2:
        st.metric("💰 Total Ingresos", f"${summary['total_ingresos']:,.2f}")
    with col_sum3:
        balance_color = "normal" if summary["balance"] >= 0 else "inverse"
        st.metric(
            "📊 Balance",
            f"${summary['balance']:,.2f}",
            delta=None,
            delta_color=balance_color,
        )


def render_reports_page():
    """Renderiza el dashboard de reportes completo."""
    
    # Configuración de página
    st.title("📊 Centro de Reportes")
    st.caption("Análisis financiero en tiempo real")
    
    # Verificar sesión
    if "user_id" not in st.session_state:
        st.error("Sesión no encontrada. Accede desde el dashboard principal.")
        st.stop()
    
    user_id = st.session_state.user_id
    
    # Check if report queries exist properly
    if 'obtener_kpis_dashboard' not in globals():
        st.error("Módulo de reportes no implementado en backend. Faltan reportes_queries.py")
        st.stop()
    
    # ==========================================
    # 📱 KPIs PRINCIPALES
    # ==========================================
    with st.container():
        kpis = obtener_kpis_dashboard(user_id)
        
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric(
            "💸 Gastado (30 días)",
            formatear_monto(kpis['total_gastado_mes']),
            delta=f"{kpis['total_transacciones_mes']} txns"
        )
        
        col2.metric(
            "🏆 Top Categoría",
            kpis['categoria_top'] or "N/A",
            delta=formatear_monto(kpis['gasto_categoria_top']) if kpis['gasto_categoria_top'] else None
        )
        
        col3.metric(
            "📈 Débitos Totales",
            formatear_monto(kpis['total_debitos'])
        )
        
        col4.metric(
            "📉 Créditos Totales",
            formatear_monto(kpis['total_creditos'])
        )
    
    st.divider()
    
    # ==========================================
    # 📑 TABS DE REPORTES
    # ==========================================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Consumos",
        "💰 Presupuestos",
        "🏷️ Por Categoría",
        "🏦 Por Cuentas",
        "📋 Balance"
    ])
    
    # ==========================================
    # TAB 1: CONSUMOS
    # ==========================================
    with tab1:
        st.subheader("Movimientos del Período")
        
        # Filtros
        col_f1, col_f2 = st.columns([1, 3])
        with col_f1:
            dias = st.selectbox(
                "Período",
                options=[7, 15, 30, 60, 90],
                index=2,
                format_func=lambda x: f"Últimos {x} días"
            )
        
        # Cargar datos
        df_consumos = obtener_reporte_consumos(user_id, dias=dias)
        df_resumen = obtener_resumen_consumos(user_id, dias=dias)
        
        if df_consumos.empty:
            st.info("No hay movimientos en este período.")
        else:
            # Gráfico de tendencia
            if not df_resumen.empty:
                st.subheader("📈 Tendencia de Gastos")
                
                fig_line = px.line(
                    df_resumen,
                    x='fecha',
                    y='total_monto',
                    title='Gastos por Día',
                    markers=True
                )
                fig_line.update_layout(
                    xaxis_title="Fecha",
                    yaxis_title="Monto (DOP)",
                    template="plotly_white"
                )
                st.plotly_chart(fig_line, use_container_width=True)
            
            # Detalle de movimientos
            st.subheader("📋 Detalle de Transacciones")
            
            # Preparar dataframe para display
            df_display = df_consumos.copy()
            df_display['fecha'] = pd.to_datetime(df_display['fecha']).dt.strftime('%d/%m/%Y')
            df_display['monto'] = df_display['monto'].apply(lambda x: formatear_monto(x))
            df_display['monto_total'] = df_display['monto_total'].apply(lambda x: formatear_monto(x))
            
            st.dataframe(
                df_display[['fecha', 'descripcion', 'cuenta_destino', 'monto_total', 'categorias']],
                use_container_width=True,
                hide_index=True
            )
    
    # ==========================================
    # TAB 2: PRESUPUESTOS
    # ==========================================
    with tab2:
        st.subheader("Presupuestos vs Ejecución Real")
        
        # Selector de período
        periodos = obtener_presupuestos_activos(user_id)
        if periodos:
            periodo_sel = st.selectbox(
                "Período",
                options=periodos,
                format_func=lambda x: pd.to_datetime(x).strftime('%B %Y')
            )
        else:
            periodo_sel = date.today().strftime('%Y-%m')
        
        df_presupuestos = obtener_reporte_presupuestos(user_id, periodo=periodo_sel)
        
        if df_presupuestos.empty:
            st.info("No hay presupuestos configurados para este período.")
        else:
            # Gráfico de barras horizontal (ejecutado vs límite)
            st.subheader("📊 Estado de Presupuestos")
            
            fig_bar = px.bar(
                df_presupuestos,
                y='categoria_nombre',
                x=['monto_ejecutado', 'monto_disponible'],
                title='Ejecutado vs Disponible',
                orientation='h',
                barmode='stack'
            )
            fig_bar.update_layout(
                yaxis_title="Categoría",
                xaxis_title="Monto (DOP)",
                legend_title="Tipo",
                template="plotly_white"
            )
            st.plotly_chart(fig_bar, use_container_width=True)
            
            # Tabla con métricas
            st.subheader("📋 Detalle por Categoría")
            
            df_pres_display = df_presupuestos.copy()
            df_pres_display['% Ejecución'] = df_pres_display['porcentaje_ejecutado'].apply(
                lambda x: f"{x:.1f}%"
            )
            df_pres_display['Límite'] = df_pres_display['monto_limite'].apply(formatear_monto)
            df_pres_display['Ejecutado'] = df_pres_display['monto_ejecutado'].apply(formatear_monto)
            df_pres_display['Disponible'] = df_pres_display['monto_disponible'].apply(formatear_monto)
            
            # Color para alertas
            def estado_alerta(alerta):
                if alerta:
                    return "⚠️ Alerta"
                return "✅ Normal"
            
            df_pres_display['Estado'] = df_pres_display['alerta_limite'].apply(estado_alerta)
            
            st.dataframe(
                df_pres_display[['categoria_nombre', 'Límite', 'Ejecutado', 'Disponible', '% Ejecución', 'Estado']],
                use_container_width=True,
                hide_index=True
            )
    
    # ==========================================
    # TAB 3: POR CATEGORÍA
    # ==========================================
    with tab3:
        st.subheader("Gastos Agrupados por Categoría")
        
        df_categorias = obtener_reporte_por_categoria(user_id)
        
        if df_categorias.empty:
            st.info("No hay datos de categorías.")
        else:
            # Gráfico de pastel
            col_pie, col_bar = st.columns(2)
            
            with col_pie:
                fig_pie = px.pie(
                    df_categorias,
                    values='total_monto',
                    names='categoria_nombre',
                    title='Distribución por Categoría',
                    hole=0.4
                )
                fig_pie.update_layout(template="plotly_white")
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col_bar:
                fig_bar = px.bar(
                    df_categorias,
                    x='categoria_nombre',
                    y='total_monto',
                    title='Total por Categoría',
                    color='categoria_naturaleza'
                )
                fig_bar.update_layout(
                    xaxis_title="Categoría",
                    yaxis_title="Monto (DOP)",
                    template="plotly_white",
                    showlegend=False
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # Tabla detallada
            st.subheader("📋 Resumen por Categoría")
            
            df_cat_display = df_categorias.copy()
            df_cat_display['Total'] = df_cat_display['total_monto'].apply(formatear_monto)
            df_cat_display['% Total'] = (
                df_cat_display['total_monto'] / df_cat_display['total_monto'].sum() * 100
            ).apply(lambda x: f"{x:.1f}%")
            
            st.dataframe(
                df_cat_display[['categoria_nombre', 'cantidad_transacciones', 'Total', '% Total']],
                use_container_width=True,
                hide_index=True
            )
    
    # ==========================================
    # TAB 4: POR CUENTAS
    # ==========================================
    with tab4:
        st.subheader("Estado de Cuentas / Bolsillos")
        
        df_cuentas = obtener_reporte_cuentas(user_id)
        
        if df_cuentas.empty:
            st.info("No hay cuentas registradas.")
        else:
            # KPIs por cuenta
            col_ac1, col_ac2, col_ac3 = st.columns(3)
            
            total_balance = df_cuentas['balance_actual'].sum()
            num_cuentas = len(df_cuentas)
            cuenta_mayor = df_cuentas.loc[df_cuentas['balance_actual'].idxmax()]
            
            col_ac1.metric("💼 Total Patrim.", formatear_monto(total_balance))
            col_ac2.metric("🏦 Cuentas Activas", str(num_cuentas))
            col_ac3.metric("📈 Mayor Balance", cuenta_mayor['cuenta_nombre'])
            
            # Gráfico de balances
            fig_cuentas = px.bar(
                df_cuentas,
                x='cuenta_nombre',
                y='balance_actual',
                title='Balance por Cuenta',
                color='tipo_cuenta'
            )
            fig_cuentas.update_layout(
                xaxis_title="Cuenta",
                yaxis_title="Balance (DOP)",
                template="plotly_white"
            )
            st.plotly_chart(fig_cuentas, use_container_width=True)
            
            # Tabla de cuentas
            st.subheader("📋 Detalle de Cuentas")
            
            df_cuentas_display = df_cuentas.copy()
            df_cuentas_display['balance_actual'] = df_cuentas_display['balance_actual'].apply(formatear_monto)
            
            st.dataframe(
                df_cuentas_display[['cuenta_nombre', 'tipo_cuenta', 'balance_actual']],
                use_container_width=True,
                hide_index=True
            )
    
    # ==========================================
    # TAB 5: BALANCE
    # ==========================================
    with tab5:
        st.subheader("Balance de Comprobación")
        
        balance = obtener_balance_comprobacion(user_id)
        df_saldos_tipo = obtener_saldos_por_tipo(user_id)
        
        # Cards de resumen
        col_b1, col_b2, col_b3 = st.columns(3)
        
        col_b1.metric(
            "📈 Total Débitos",
            formatear_monto(balance['total_debitos']),
            delta=f"Dif: {formatear_monto(balance['diferencia'])}" if balance['diferencia'] != 0 else None
        )
        
        col_b2.metric(
            "📉 Total Créditos",
            formatear_monto(balance['total_creditos'])
        )
        
        estado_balance = "✅ Cuadrado" if balance['diferencia'] == 0 else "⚠️ Descuadrado"
        col_b3.metric("Estado", estado_balance)
        
        # Verificación visual
        if balance['diferencia'] == 0:
            st.success("📗 El libro mayor está cuadrado. Débitos = Créditos")
        else:
            st.error(f"📕 Diferencia detectada: {formatear_monto(balance['diferencia'])}")
        
        # Gráfico de saldos por tipo
        if not df_saldos_tipo.empty:
            st.subheader("📊 Saldos por Tipo de Cuenta")
            
            fig_tipos = px.pie(
                df_saldos_tipo,
                values='total_balance',
                names='tipo_cuenta',
                title='Distribución por Tipo',
                hole=0.4
            )
            fig_tipos.update_layout(template="plotly_white")
            st.plotly_chart(fig_tipos, use_container_width=True)
        
        # Resumen final
        st.subheader("📋 Resumen Ejecutivo")
        
        resumen_data = {
            'Concepto': ['Total Débitos', 'Total Créditos', 'Diferencia', 'Saldos Pendientes'],
            'Monto': [
                formatear_monto(balance['total_debitos']),
                formatear_monto(balance['total_creditos']),
                formatear_monto(balance['diferencia']),
                formatear_monto(abs(balance['diferencia'])) if balance['diferencia'] != 0 else "N/A"
            ]
        }
        
        st.table(pd.DataFrame(resumen_data))
    
    # Footer
    st.divider()
    st.caption("📊 MyFinance Reports | Datos actualizados en tiempo real")


def render_categories_page():
    """Show categories page."""
    st.header("🏷️ Categorías")

    st.info("📌 Las categorías se cargarán desde la base de datos")


# ===========================================
# GESTIONAR PAGE (Cuentas y Categorías)
# ===========================================


def render_gestionar_page(user_id: UUID):
    """Show gestión page with tabs for Cuentas and Categorías."""
    st.header("⚙️ Gestión")

    tab_cuentas, tab_categorias = st.tabs(["💰 Cuentas", "🏷️ Categorías"])

    with tab_cuentas:
        render_cuentas_tab(user_id)

    with tab_categorias:
        render_categorias_tab(user_id)


def render_cuentas_tab(user_id: UUID):
    """Render cuentas management tab with extended fields."""
    from datetime import date
    from decimal import Decimal

    st.subheader("💰 Cuentas")

    cuentas = get_cuentas_by_user(user_id)

    # Tipos de cuenta
    TIPOS_CUENTA = [
        "efectivo",
        "banco",
        "tarjeta_credito",
        "inversion",
        "prestamo",
        "activo",
        "pasivo",
        "ingreso",
        "gasto",
        "patrimonio",
    ]

    TIPOS_LABELS = {
        "efectivo": "💵 Efectivo",
        "banco": "🏦 Banco",
        "tarjeta_credito": "💳 Tarjeta de Crédito",
        "inversion": "📈 Inversión/Certificado",
        "prestamo": "🏦 Préstamo",
        "activo": "Activo",
        "pasivo": "Pasivo",
        "ingreso": "Ingreso",
        "gasto": "Gasto",
        "patrimonio": "Patrimonio",
    }

    # Form to create new cuenta
    with st.expander("➕ Nueva Cuenta", expanded=False):
        with st.form("new_cuenta_form", clear_on_submit=True):
            nombre = st.text_input("Nombre", placeholder="Ej: Efectivo, Banco, Tarjeta")
            tipo = st.selectbox(
                "Tipo", TIPOS_CUENTA, format_func=lambda x: TIPOS_LABELS.get(x, x)
            )

            # Common fields
            saldo_inicial = st.number_input(
                "Saldo Inicial", min_value=0.0, value=0.0, step=100.0
            )
            balance = st.number_input("Balance", min_value=0.0, value=0.0, step=100.0)

            # Extended fields based on type
            limite_credito = fecha_corte = fecha_pago = tasa_interes = None
            alerta_cuota = False
            fecha_vencimiento = tasa_rendimiento = monto_original = None
            alerta_vencimiento = False
            monto_pagado = saldo_pendiente = Decimal("0")

            st.markdown("---")

            if tipo == "tarjeta_credito":
                st.markdown("**📅 Datos de Tarjeta de Crédito**")
                limite_credito = st.number_input(
                    "Límite de crédito", min_value=0.0, value=10000.0, step=1000.0
                )
                fecha_corte = st.number_input(
                    "Fecha de corte (día)", min_value=1, max_value=31, value=15
                )
                fecha_pago = st.number_input(
                    "Fecha de pago (día)", min_value=1, max_value=31, value=25
                )
                tasa_interes = st.number_input(
                    "Tasa de interés (%)", min_value=0.0, value=0.0, step=0.5
                )
                alerta_cuota = st.checkbox("Alerta de cuota", value=False)

            elif tipo == "inversion":
                st.markdown("**📈 Datos de Inversión/Certificado**")
                fecha_vencimiento = st.date_input(
                    "Fecha de vencimiento", value=date.today()
                )
                tasa_rendimiento = st.number_input(
                    "Tasa de rendimiento (%)", min_value=0.0, value=5.0, step=0.5
                )
                monto_original = st.number_input(
                    "Monto original", min_value=0.0, value=saldo_inicial, step=1000.0
                )
                alerta_vencimiento = st.checkbox("Alerta de vencimiento", value=False)

            elif tipo == "prestamo":
                st.markdown("**🏦 Datos de Préstamo**")
                fecha_vencimiento = st.date_input(
                    "Fecha de vencimiento", value=date.today()
                )
                tasa_interes = st.number_input(
                    "Tasa de interés (%)", min_value=0.0, value=10.0, step=0.5
                )
                monto_original = st.number_input(
                    "Monto original", min_value=0.0, value=saldo_inicial, step=1000.0
                )
                monto_pagado = st.number_input(
                    "Monto pagado", min_value=0.0, value=0.0, step=100.0
                )
                saldo_pendiente = st.number_input(
                    "Saldo pendiente", min_value=0.0, value=saldo_inicial, step=100.0
                )
                alerta_cuota = st.checkbox("Alerta de cuota", value=False)

            submitted = st.form_submit_button("Crear")

            if submitted and nombre:
                try:
                    from decimal import Decimal

                    # Debug: ensure user_id is valid
                    if not user_id:
                        st.error("Error: usuario no identificado")
                        return

                    # Llamada a la nueva función transaccional
                    cuenta = crear_cuenta_con_apertura(
                        user_id,
                        nombre,
                        tipo,
                        activa=tipo in ["banco", "efectivo", "inversion"],
                        saldo_inicial=Decimal(str(saldo_inicial)),
                        balance=Decimal(str(balance)),
                        limite_credito=Decimal(str(limite_credito)) if limite_credito else None,
                        fecha_corte=int(fecha_corte) if fecha_corte else None,
                        fecha_pago=int(fecha_pago) if fecha_pago else None,
                        tasa_interes=Decimal(str(tasa_interes)) if tasa_interes else None,
                        alerta_cuota=alerta_cuota,
                        fecha_vencimiento=fecha_vencimiento,
                        tasa_rendimiento=Decimal(str(tasa_rendimiento)) if tasa_rendimiento else None,
                        monto_original=Decimal(str(monto_original)) if monto_original else None,
                        alerta_vencimiento=alerta_vencimiento,
                        monto_pagado=Decimal(str(monto_pagado)),
                        saldo_pendiente=Decimal(str(saldo_pendiente)),
                    )
                    
                    st.success(f"✓ Cuenta '{cuenta.nombre}' creada y asiento de apertura registrado en el Ledger.")
                    st.rerun()
                except Exception as e:
                    # Capturamos el error propagado por el Rollback
                    st.error(f"Error al crear la cuenta: {str(e)}")
                    log_message("ERROR", f"Fallo en creación de cuenta: {str(e)}", st.session_state.get('username'))

    # Show cuentas
    if cuentas:
        # Table header
        col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
        with col1:
            st.markdown("**Nombre**")
        with col2:
            st.markdown("**Tipo**")
        with col3:
            st.markdown("**Balance**")
        with col4:
            st.markdown("**Estado**")
        with col5:
            st.markdown("**Acciones**")

        st.markdown("---")

        for cuenta in cuentas:
            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
            with col1:
                st.write(cuenta.nombre)
            with col2:
                st.caption(TIPOS_LABELS.get(cuenta.tipo, cuenta.tipo))
            with col3:
                st.write(f"${cuenta.balance:,.2f}")
            with col4:
                if cuenta.activa:
                    st.success("✅")
                else:
                    st.error("❌")
            with col5:
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✏️", key=f"edit_{cuenta.id}"):
                        st.session_state.edit_cuenta_id = cuenta.id
                with c2:
                    uso = check_cuenta_en_uso(cuenta.id)
                    if st.button("🗑️", key=f"del_{cuenta.id}", disabled=uso["en_uso"]):
                        if uso["en_uso"]:
                            st.warning(uso["mensaje"])
                        else:
                            result = delete_cuenta(cuenta.id)
                            if result["success"]:
                                st.success(result["mensaje"])
                                st.rerun()
                            else:
                                st.error(result["mensaje"])

        # Edit modal
        if "edit_cuenta_id" in st.session_state:
            cuenta_id = st.session_state.edit_cuenta_id
            cuenta = next((c for c in cuentas if c.id == cuenta_id), None)
            if cuenta:
                with st.form(f"edit_cuenta_{cuenta.id}"):
                    st.markdown("### ✏️ Editar Cuenta")
                    new_nombre = st.text_input("Nombre", value=cuenta.nombre)

                    tipo_idx = (
                        TIPOS_CUENTA.index(cuenta.tipo)
                        if cuenta.tipo in TIPOS_CUENTA
                        else 0
                    )
                    new_tipo = st.selectbox(
                        "Tipo",
                        TIPOS_CUENTA,
                        index=tipo_idx,
                        format_func=lambda x: TIPOS_LABELS.get(x, x),
                    )

                    new_saldo = st.number_input(
                        "Saldo Actual",
                        value=float(cuenta.saldo_actual),
                        min_value=0.0,
                        step=100.0,
                    )
                    new_balance = st.number_input(
                        "Balance",
                        value=float(cuenta.balance),
                        min_value=0.0,
                        step=100.0,
                    )
                    new_activa = st.checkbox("Activa", value=cuenta.activa)

                    st.markdown("---")

                    # Extended fields for edit
                    new_limite = cuenta.limite_credito
                    new_fecha_corte = cuenta.fecha_corte
                    new_fecha_pago = cuenta.fecha_pago
                    new_tasa = cuenta.tasa_interes
                    new_alerta_cuota = cuenta.alerta_cuota
                    new_fecha_venc = cuenta.fecha_vencimiento
                    new_tasa_rend = cuenta.tasa_rendimiento
                    new_monto_orig = cuenta.monto_original
                    new_alerta_venc = cuenta.alerta_vencimiento
                    new_monto_pag = cuenta.monto_pagado
                    new_saldo_pend = cuenta.saldo_pendiente

                    if new_tipo == "tarjeta_credito":
                        st.markdown("**📅 Datos de Tarjeta de Crédito**")
                        new_limite = st.number_input(
                            "Límite de crédito",
                            value=float(new_limite or 0),
                            min_value=0.0,
                        )
                        new_fecha_corte = st.number_input(
                            "Fecha de corte (día)",
                            value=new_fecha_corte or 15,
                            min_value=1,
                            max_value=31,
                        )
                        new_fecha_pago = st.number_input(
                            "Fecha de pago (día)",
                            value=new_fecha_pago or 25,
                            min_value=1,
                            max_value=31,
                        )
                        new_tasa = st.number_input(
                            "Tasa de interés (%)",
                            value=float(new_tasa or 0),
                            min_value=0.0,
                        )
                        new_alerta_cuota = st.checkbox(
                            "Alerta de cuota", value=new_alerta_cuota
                        )

                    elif new_tipo == "inversion":
                        st.markdown("**📈 Datos de Inversión/Certificado**")
                        new_fecha_venc = st.date_input(
                            "Fecha de vencimiento", value=new_fecha_venc or date.today()
                        )
                        new_tasa_rend = st.number_input(
                            "Tasa de rendimiento (%)",
                            value=float(new_tasa_rend or 0),
                            min_value=0.0,
                        )
                        new_monto_orig = st.number_input(
                            "Monto original",
                            value=float(new_monto_orig or 0),
                            min_value=0.0,
                        )
                        new_alerta_venc = st.checkbox(
                            "Alerta de vencimiento", value=new_alerta_venc
                        )

                    elif new_tipo == "prestamo":
                        st.markdown("**🏦 Datos de Préstamo**")
                        new_fecha_venc = st.date_input(
                            "Fecha de vencimiento", value=new_fecha_venc or date.today()
                        )
                        new_tasa = st.number_input(
                            "Tasa de interés (%)",
                            value=float(new_tasa or 0),
                            min_value=0.0,
                        )
                        new_monto_orig = st.number_input(
                            "Monto original",
                            value=float(new_monto_orig or 0),
                            min_value=0.0,
                        )
                        new_monto_pag = st.number_input(
                            "Monto pagado",
                            value=float(new_monto_pag or 0),
                            min_value=0.0,
                        )
                        new_saldo_pend = st.number_input(
                            "Saldo pendiente",
                            value=float(new_saldo_pend or 0),
                            min_value=0.0,
                        )
                        new_alerta_cuota = st.checkbox(
                            "Alerta de cuota", value=new_alerta_cuota
                        )

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.form_submit_button("💾 Guardar"):
                            from decimal import Decimal

                            update_cuenta(
                                cuenta.id,
                                nombre=new_nombre,
                                tipo=new_tipo,
                                saldo_actual=Decimal(str(new_saldo)),
                                balance=Decimal(str(new_balance)),
                                activa=new_activa,
                                limite_credito=Decimal(str(new_limite))
                                if new_limite
                                else None,
                                fecha_corte=int(new_fecha_corte)
                                if new_fecha_corte
                                else None,
                                fecha_pago=int(new_fecha_pago)
                                if new_fecha_pago
                                else None,
                                tasa_interes=Decimal(str(new_tasa))
                                if new_tasa
                                else None,
                                alerta_cuota=new_alerta_cuota,
                                fecha_vencimiento=new_fecha_venc,
                                tasa_rendimiento=Decimal(str(new_tasa_rend))
                                if new_tasa_rend
                                else None,
                                monto_original=Decimal(str(new_monto_orig))
                                if new_monto_orig
                                else None,
                                alerta_vencimiento=new_alerta_venc,
                                monto_pagado=Decimal(str(new_monto_pag)),
                                saldo_pendiente=Decimal(str(new_saldo_pend)),
                            )
                            st.success("Cuenta actualizada")
                            del st.session_state.edit_cuenta_id
                            st.rerun()
                    with c2:
                        if st.form_submit_button("❌ Cancelar"):
                            del st.session_state.edit_cuenta_id
                            st.rerun()
    else:
        st.info("No hay cuentas. Crea una para comenzar.")


def render_users_page():
    """Render usuarios management page."""
    from database import (
        get_all_users_with_roles,
        update_user,
        deactivate_user,
        get_all_roles,
        assign_role,
        remove_role,
        create_web_user,
    )
    from core.identity import IdentityGateway
    import hashlib

    st.subheader("👥 Gestión de Usuarios")

    users = IdentityGateway.get_all_users()
    roles = get_all_roles()

    col1, col2 = st.columns([4, 1])
    with col1:
        st.subheader("Usuarios")
    with col2:
        if st.button("➕ Nuevo Usuario", use_container_width=True):
            st.session_state.show_new_user_form = True

    if st.session_state.get("show_new_user_form"):
        with st.expander("➕ Crear Nuevo Usuario", expanded=True):
            with st.form("new_user_form", clear_on_submit=True):
                new_username = st.text_input("Usuario", placeholder="Nombre de usuario")
                new_password = st.text_input(
                    "Contraseña",
                    type="password",
                    placeholder="Contraseña (mín. 4 caracteres)",
                )
                new_password_confirm = st.text_input(
                    "Confirmar Contraseña",
                    type="password",
                    placeholder="Confirmar contraseña",
                )
                new_nombre = st.text_input(
                    "Nombre (opcional)", placeholder="Nombre completo"
                )
                new_rol = st.selectbox(
                    "Rol inicial",
                    options=["user", "admin"],
                    format_func=lambda x: "👑 Admin" if x == "admin" else "👤 Usuario",
                )

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    submitted = st.form_submit_button(
                        "✅ Crear Usuario", use_container_width=True
                    )
                with col_btn2:
                    cancel = st.form_submit_button(
                        "❌ Cancelar", use_container_width=True
                    )

                if cancel:
                    st.session_state.show_new_user_form = False
                    st.rerun()

                if submitted:
                    if not new_username:
                        st.error("El usuario es requerido")
                    elif len(new_password) < 4:
                        st.error("La contraseña debe tener al menos 4 caracteres")
                    elif new_password != new_password_confirm:
                        st.error("Las contraseñas no coinciden")
                    else:
                        existing = IdentityGateway.get_user_by_username(new_username)
                        if existing:
                            st.error("El usuario ya existe")
                        else:
                            password_hash = hashlib.sha256(
                                new_password.encode()
                            ).hexdigest()
                            user = IdentityGateway.create_web_user(
                                new_username, password_hash, new_rol
                            )
                            if new_nombre:
                                update_user(user["user_id"], nombre=new_nombre)
                            st.success(
                                f"✓ Usuario '{new_username}' creado con rol '{new_rol}'"
                            )
                            st.session_state.show_new_user_form = False
                            st.rerun()

    st.markdown("---")

    if users:
        for user in users:
            with st.container():
                col_icon, col_info, col_roles, col_actions = st.columns([0.5, 3, 2, 2])

                with col_icon:
                    if user.get("activo", True):
                        st.markdown("🟢")
                    else:
                        st.markdown("🔴")

                with col_info:
                    st.markdown(f"**{user.get('username', 'N/A')}**")
                    if user.get("nombre"):
                        st.caption(user["nombre"])
                    st.caption(f"ID: {str(user['user_id'])[:8]}...")
                    if user.get("ultimo_acceso"):
                        last_access = user["ultimo_acceso"]
                        if hasattr(last_access, "strftime"):
                            st.caption(
                                f"Último acceso: {last_access.strftime('%d/%m/%Y %H:%M')}"
                            )

                with col_roles:
                    current_roles = user.get("roles", [])
                    st.markdown("**Roles:**")
                    for rol in current_roles:
                        badge = "👑" if rol == "admin" else "👤"
                        st.markdown(f"  {badge} {rol}")

                with col_actions:
                    if user.get("username") != st.session_state.get("username"):
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button(
                                "✏️", key=f"edit_user_{user['user_id']}", help="Editar"
                            ):
                                st.session_state.edit_user_id = str(user["user_id"])
                        with c2:
                            if user.get("activo", True):
                                btn_label = "🚫"
                                help_text = "Desactivar"
                            else:
                                btn_label = "✅"
                                help_text = "Activar"
                            if st.button(
                                btn_label,
                                key=f"toggle_user_{user['user_id']}",
                                help=help_text,
                            ):
                                deactivate_user(user["user_id"])
                                st.success(
                                    f"Usuario {'desactivado' if user.get('activo') else 'activado'}"
                                )
                                st.rerun()
                    else:
                        st.caption("👤 (tú)")

                st.markdown("---")

        if st.session_state.get("edit_user_id"):
            edit_user_id = UUID(st.session_state.edit_user_id)
            edit_user = next((u for u in users if u["user_id"] == edit_user_id), None)
            if edit_user:
                with st.expander("✏️ Editar Usuario", expanded=True):
                    with st.form(f"edit_user_{edit_user_id}", clear_on_submit=False):
                        edit_username = st.text_input(
                            "Usuario",
                            value=edit_user.get("username", ""),
                            disabled=True,
                        )
                        edit_nombre = st.text_input(
                            "Nombre",
                            value=edit_user.get("nombre") or "",
                            placeholder="Nombre completo",
                        )

                        new_password = st.text_input(
                            "Nueva Contraseña (dejar vacío para no cambiar)",
                            type="password",
                            placeholder="Nueva contraseña",
                        )

                        current_roles = edit_user.get("roles", [])
                        selected_roles = st.multiselect(
                            "Roles",
                            options=[r["nombre"] for r in roles],
                            default=current_roles,
                        )

                        submitted = st.form_submit_button(
                            "💾 Guardar", use_container_width=True
                        )
                        cancel = st.form_submit_button(
                            "❌ Cancelar", use_container_width=True
                        )

                        if cancel:
                            del st.session_state.edit_user_id
                            st.rerun()

                        if submitted:
                            updates = {}
                            if edit_nombre != (edit_user.get("nombre") or ""):
                                updates["nombre"] = edit_nombre

                            if new_password:
                                if len(new_password) < 4:
                                    st.error(
                                        "La contraseña debe tener al menos 4 caracteres"
                                    )
                                else:
                                    password_hash = hashlib.sha256(
                                        new_password.encode()
                                    ).hexdigest()
                                    updates["password_hash"] = password_hash

                            if updates:
                                update_user(edit_user_id, **updates)

                            new_roles = set(selected_roles)
                            old_roles = set(current_roles)
                            for rol in new_roles - old_roles:
                                assign_role(edit_user_id, rol)
                            for rol in old_roles - new_roles:
                                remove_role(edit_user_id, rol)

                            st.success("✓ Usuario actualizado")
                            del st.session_state.edit_user_id
                            st.rerun()
    else:
        st.info("No hay usuarios registrados")


def render_categorias_tab(user_id: UUID):
    """Render categorías management tab."""
    st.subheader("🏷️ Categorías")

    categorias = get_categorias_by_user(user_id)
    default_categorias = get_default_categorias()

    with st.expander("➕ Nueva Categoría", expanded=False):
        with st.form("new_categoria_form", clear_on_submit=True):
            origen = st.radio("Origen", ["Copiar de predeterminadas", "Crear nueva"])

            nombre = None
            icono = "📦"
            color = "#4ECDC4"

            if origen == "Copiar de predeterminadas":
                opciones = {c.nombre: c for c in default_categorias}
                selected_default = st.selectbox(
                    "Seleccionar plantilla", list(opciones.keys())
                )
                selected = opciones[selected_default]
                # Allow custom name for copied category
                nombre = st.text_input(
                    "Nombre de la categoría",
                    value=f"{selected.nombre} (copia)",
                    placeholder="Nombre personalizado",
                    key="copy_cat_nombre",
                )
                icono = st.text_input(
                    "Icono (emoji)", value=selected.icono or "📦", key="copy_cat_icono"
                )
                color = st.color_picker(
                    "Color", value=selected.color or "#4ECDC4", key="copy_cat_color"
                )
            else:
                nombre = st.text_input(
                    "Nombre", placeholder="Ej: Comida, Transporte", key="new_cat_nombre"
                )
                icono = st.text_input("Icono (emoji)", value="📦", key="new_cat_icono")
                color = st.color_picker("Color", value="#4ECDC4", key="new_cat_color")

            presupuesto = st.number_input(
                "Presupuesto mensual ($)", min_value=0.0, value=0.0, step=100.0
            )
            alerta = st.slider("Alerta al % del presupuesto", 0, 100, 80)

            submitted = st.form_submit_button("Crear")

            if submitted and nombre:
                try:
                    from decimal import Decimal

                    # Debug: ensure user_id is valid
                    if not user_id:
                        st.error("Error: usuario no identificado")
                        return

                    cat = create_categoria(
                        user_id,
                        nombre,
                        icono,
                        color,
                        Decimal(str(presupuesto)) if presupuesto > 0 else None,
                        Decimal(str(alerta)) if presupuesto > 0 else None,
                    )
                    st.success(f"✓ '{cat.nombre}' creada exitosamente!")
                    # Full page rerun
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    if default_categorias:
        with st.expander("📋 Predeterminadas (copiar)", expanded=False):
            for cat in default_categorias:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"{cat.icono} {cat.nombre}")
                with col2:
                    if st.button("➕", key=f"copy_{cat.id}"):
                        try:
                            create_categoria(user_id, cat.nombre, cat.icono, cat.color)
                            st.success(f"'{cat.nombre}' copiada")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    if categorias:
        col1, col2, col3, col4, col5 = st.columns([3, 1, 2, 2, 1])
        with col1:
            st.markdown("**Nombre**")
        with col2:
            st.markdown("**Icono**")
        with col3:
            st.markdown("**Presupuesto**")
        with col4:
            st.markdown("**Alerta %**")
        with col5:
            st.markdown("**Acciones**")

        st.markdown("---")

        for cat in categorias:
            col1, col2, col3, col4, col5 = st.columns([3, 1, 2, 2, 1])
            with col1:
                st.write(cat.nombre)
            with col2:
                st.write(cat.icono or "📦")
            with col3:
                st.write(f"${cat.presupuesto:,.2f}" if cat.presupuesto else "—")
            with col4:
                st.write(f"{cat.alerta_umbral}%" if cat.alerta_umbral else "—")
            with col5:
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✏️", key=f"edit_cat_{cat.id}"):
                        st.session_state.edit_categoria_id = cat.id
                with c2:
                    uso = check_categoria_en_uso(cat.id)
                    if st.button("🗑️", key=f"del_cat_{cat.id}", disabled=uso["en_uso"]):
                        if uso["en_uso"]:
                            st.warning(uso["mensaje"])
                        else:
                            result = delete_categoria(cat.id)
                            if result["success"]:
                                st.success(result["mensaje"])
                                st.rerun()
                            else:
                                st.error(result["mensaje"])

        if "edit_categoria_id" in st.session_state:
            cat_id = st.session_state.edit_categoria_id
            cat = next((c for c in categorias if c.id == cat_id), None)
            if cat:
                with st.form(f"edit_cat_{cat.id}"):
                    st.markdown("### ✏️ Editar Categoría")
                    new_presupuesto = st.number_input(
                        "Presupuesto mensual ($)",
                        value=float(cat.presupuesto or 0),
                        min_value=0.0,
                        step=100.0,
                    )
                    new_alerta = st.slider(
                        "Alerta al % del presupuesto",
                        0,
                        100,
                        int(cat.alerta_umbral or 80),
                    )

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.form_submit_button("💾 Guardar"):
                            from decimal import Decimal

                            update_categoria(
                                cat.id,
                                presupuesto=Decimal(str(new_presupuesto))
                                if new_presupuesto > 0
                                else None,
                                alerta_umbral=Decimal(str(new_alerta))
                                if new_presupuesto > 0
                                else None,
                            )
                            st.success("Categoría actualizada")
                            del st.session_state.edit_categoria_id
                            st.rerun()
                    with c2:
                        if st.form_submit_button("❌ Cancelar"):
                            del st.session_state.edit_categoria_id
                            st.rerun()
    else:
        st.info("No hay categorías. Crea una para comenzar.")


def render_settings_page():
    """Show settings page with unified agent configuration."""
    st.header("⚙️ Configuración")

    tab_env, tab_agentes = st.tabs(["🔧 Variables de Entorno", "🤖 Agentes"])

    with tab_env:
        st.subheader("Variables de entorno")

        env_vars = {
            "DB_HOST": os.getenv("DB_HOST", "localhost"),
            "DB_PORT": os.getenv("DB_PORT", "5432"),
            "DB_NAME": os.getenv("DB_NAME", "myfinance"),
            "OPENAI_BASE_URL": os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1"),
        }

        for key, value in env_vars.items():
            st.text_input(key, value, disabled=True)

        st.warning("⚠️ No modificar directamente - usar archivo .env")

    with tab_agentes:
        render_unified_agents_page()


def render_unified_agents_page():
    """Render all agents in tabs with global config."""
    user_id = get_user_id()

    available_models = get_available_models()
    model_names = [m["name"] for m in available_models]

    subtab_a1, subtab_a2, subtab_a3, subtab_a4, subtab_a5, subtab_a6 = st.tabs(
        [
            "🤖 A1 - Clasificador",
            "📷 A2 - OCR (Vision)",
            "🔍 A3 - Evaluador",
            "📝 A4 - Parser",
            "💾 A5 - SQL",
            "💬 A6 - Chat",
        ]
    )

    AGENT_INFO = {
        "A1": {
            "label": "A1 - Clasificador",
            "description": "Determina la ruta/intención del mensaje",
            "config_key": "MODELO_CLASIFICADOR",
            "task_key": "TASK_CLASSIFY",
        },
        "A2": {
            "label": "A2 - OCR",
            "description": "Extrae texto y valores de facturas/imágenes",
            "config_key": "MODELO_OCR",
            "task_key": "TASK_OCR",
        },
        "A3": {
            "label": "A3 - Evaluador",
            "description": "Evalúa certeza de campos y usa Tool Calling",
            "config_key": "MODELO_DBA",
            "task_key": "TASK_EVALUATE",
            "has_thresholds": True,
        },
        "A4": {
            "label": "A4 - Parser",
            "description": "Convierte texto a JSON contable",
            "config_key": "MODELO_CONTABILIDAD",
            "task_key": "TASK_PARSE",
        },
        "A5": {
            "label": "A5 - SQL",
            "description": "Valida y ejecuta consultas SQL",
            "config_key": "MODELO_SQL",
            "task_key": "TASK_SQL",
        },
        "A6": {
            "label": "A6 - Chat",
            "description": "Asistente financiero y traducción",
            "config_key": "MODELO_CHAT",
            "task_key": "TASK_CHAT",
        },
    }

    CAMPOS_A3 = [
        ("monto_total", "Monto Total", True),
        ("monto", "Monto", False),
        ("monto_impuesto", "Impuesto", False),
        ("monto_descuento", "Descuento", False),
        ("monto_otros_cargos", "Otros Cargos", False),
        ("origen", "Origen", True),
        ("destino", "Destino", True),
        ("categoria", "Categoría", False),
        ("moneda", "Moneda", False),
        ("fecha", "Fecha", False),
        ("concepto", "Concepto", False),
        ("descripcion", "Descripción", False),
    ]

    def render_agent_tab(subtab, agente: str):
        with subtab:
            from core.config_loader import ConfigLoader

            info = AGENT_INFO[agente]
            st.markdown(f"### {info['label']}")
            st.caption(info["description"])

            # Load current config
            current_model = ConfigLoader.get_model(agente)
            current_temp = ConfigLoader.get_temp(agente)
            current_tokens = ConfigLoader.get_tokens(agente)
            current_timeout = ConfigLoader.get_timeout(agente)

            config_key = info["config_key"]
            task_key = info.get("task_key", "")

            # TASK Prompt
            task_content = ConfigLoader.get_task(task_key) if task_key else ""
            edit_key = f"edit_task_{agente}"
            save_key = f"save_task_{agente}"
            cancel_key = f"cancel_task_{agente}"

            if edit_key not in st.session_state:
                st.session_state[edit_key] = False

            with st.expander("📜 TASK (Prompt)"):
                if st.session_state[edit_key]:
                    edited_content = st.text_area(
                        "Editar Prompt",
                        value=task_content,
                        height=300,
                        key=f"task_edit_{agente}",
                    )
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("💾 Guardar", key=save_key):
                            if edited_content and edited_content.strip():
                                ConfigLoader.set(
                                    task_key,
                                    edited_content.strip(),
                                    descripcion=f"Prompt para {agente}",
                                    modulo="agentes",
                                )
                                st.success(f"✅ Prompt de {agente} actualizado")
                                st.session_state[edit_key] = False
                                st.rerun()
                            else:
                                st.error("El prompt no puede estar vacío")
                    with col_btn2:
                        if st.button("❌ Cancelar", key=cancel_key):
                            st.session_state[edit_key] = False
                            st.rerun()
                else:
                    display_content = (
                        task_content
                        if task_content
                        else "(Sin configurar - Click en Editar para crear)"
                    )
                    st.text_area(
                        "Prompt",
                        value=display_content[:500] + "..."
                        if len(display_content) > 500
                        else display_content,
                        height=150,
                        disabled=True,
                        key=f"task_view_{agente}",
                    )
                    if st.button("✏️ Editar Prompt", key=f"btn_edit_{agente}"):
                        st.session_state[edit_key] = True
                        st.rerun()

            st.markdown("#### 🌐 Configuración Global")

            # Model selector
            if model_names:

                def format_model(name: str) -> str:
                    source = next(
                        (m["source"] for m in available_models if m["name"] == name),
                        "local",
                    )
                    badge = "☁️" if source == "cloud" else "💻"
                    return f"{name} {badge}"

                options_with_labels = [format_model(m) for m in model_names]
                current_idx = (
                    options_with_labels.index(format_model(current_model))
                    if current_model in model_names
                    else 0
                )

                selected = st.selectbox(
                    "Modelo",
                    options=options_with_labels,
                    index=current_idx,
                    key=f"model_{agente}",
                )
                selected_model = model_names[options_with_labels.index(selected)]
            else:
                selected_model = current_model
                st.text_input("Modelo", value=current_model, disabled=True)

            # Parameters
            col1, col2, col3 = st.columns(3)
            with col1:
                nueva_temp = st.number_input(
                    "Temperatura",
                    min_value=0.0,
                    max_value=2.0,
                    value=float(current_temp),
                    step=0.1,
                    key=f"temp_{agente}",
                )
            with col2:
                nuevos_tokens = st.number_input(
                    "Max Tokens",
                    min_value=1,
                    max_value=4096,
                    value=int(current_tokens),
                    step=1,
                    key=f"tokens_{agente}",
                )
            with col3:
                nuevo_timeout = st.number_input(
                    "Timeout (seg)",
                    min_value=5,
                    max_value=300,
                    value=int(current_timeout),
                    step=5,
                    key=f"timeout_{agente}",
                )

            # A3 Thresholds
            if info.get("has_thresholds"):
                st.markdown("---")
                st.markdown("##### 🎯 Thresholds A3")

                nuevos_thresholds = {}
                nuevos_requeridos = {}
                nuevas_preguntas = {}

                cols = st.columns(4)
                col_idx = 0
                for campo, label, req_default in CAMPOS_A3:
                    with cols[col_idx % 4]:
                        if campo != "descripcion":
                            current_t = ConfigLoader.get_threshold_a3(campo)
                            nuevos_thresholds[campo] = st.number_input(
                                f"{label}",
                                min_value=0,
                                max_value=100,
                                value=current_t,
                                key=f"th_{agente}_{campo}",
                            )
                        else:
                            st.text_input(
                                f"{label} (contexto)", value="--", disabled=True
                            )
                            nuevos_thresholds[campo] = None

                        current_r = ConfigLoader.get_requerido_a3(campo)
                        nuevos_requeridos[campo] = st.checkbox(
                            f"Req", value=current_r, key=f"req_{agente}_{campo}"
                        )
                        
                        current_q = ConfigLoader.get_pregunta_a3(campo)
                        nuevas_preguntas[campo] = st.text_input(
                            f"Pregunta", value=current_q, key=f"q_{agente}_{campo}"
                        )
                    col_idx += 1
                    if col_idx % 4 == 0:
                        cols = st.columns(4)

            # Tools (only in A3 tab)
            if agente == "A3":
                st.markdown("---")
                st.markdown("##### 🛠️ Herramientas")
                tool_buscar = st.checkbox(
                    "🔍 buscar_entidad",
                    value=ConfigLoader.get_tool_buscar_entidad(),
                    key=f"tool_ent_{agente}",
                )
                tool_dry = st.checkbox(
                    "📖 Modo Dry-Run",
                    value=ConfigLoader.get_tool_dry_run(),
                    key=f"tool_dry_{agente}",
                )

            # Save button
            if st.button(f"💾 Guardar Config {agente}", key=f"save_{agente}"):
                ConfigLoader.set_model(agente, selected_model)
                ConfigLoader.set_temp(agente, nueva_temp)
                ConfigLoader.set_tokens(agente, nuevos_tokens)
                ConfigLoader.set_timeout(agente, nuevo_timeout)

                if info.get("has_thresholds"):
                    for campo, valor in nuevos_thresholds.items():
                        if valor is not None:
                            ConfigLoader.set_threshold_a3(campo, valor)
                    for campo, valor in nuevos_requeridos.items():
                        ConfigLoader.set_requerido_a3(campo, valor)
                    for campo, valor in nuevas_preguntas.items():
                        if valor:
                            ConfigLoader.set_pregunta_a3(campo, valor)

                if agente == "A3":
                    ConfigLoader.set_tool_buscar_entidad(tool_buscar)
                    ConfigLoader.set_tool_dry_run(tool_dry)

                st.success(f"✅ Configuración de {agente} guardada")
                st.rerun()

    render_agent_tab(subtab_a1, "A1")
    render_agent_tab(subtab_a2, "A2")
    render_agent_tab(subtab_a3, "A3")
    render_agent_tab(subtab_a4, "A4")
    render_agent_tab(subtab_a5, "A5")
    render_agent_tab(subtab_a6, "A6")


def render_user_config_page():
    """Render global configuration page with all agents."""
    from core.config_loader import ConfigLoader

    st.subheader("⚙️ Configuración Global de Agentes")

    available_models = get_available_models()
    model_names = [m["name"] for m in available_models]

    AGENTES = ["A1", "A2", "A3", "A4", "A5", "A6"]
    AGENTE_LABELS = {
        "A1": "A1 - Clasificador",
        "A2": "A2 - OCR (Vision)",
        "A3": "A3 - Evaluador",
        "A4": "A4 - Parser",
        "A5": "A5 - SQL",
        "A6": "A6 - Chat",
    }

    CAMPOS_EVALUACION = [
        ("monto_total", "Monto Total", True),
        ("monto", "Monto", False),
        ("monto_impuesto", "Monto Impuesto", False),
        ("monto_descuento", "Monto Descuento", False),
        ("monto_otros_cargos", "Otros Cargos", False),
        ("origen", "Origen", True),
        ("destino", "Destino", True),
        ("categoria", "Categoría", False),
        ("moneda", "Moneda", False),
        ("fecha", "Fecha", False),
        ("concepto", "Concepto", False),
        ("descripcion", "Descripción", False),
    ]

    st.subheader("🎯 Thresholds - Evaluador A3")

    threshold_cols = st.columns(4)
    col_idx = 0

    nuevos_thresholds = {}
    nuevos_requeridos = {}

    for campo, label, requerido_default in CAMPOS_EVALUACION:
        with threshold_cols[col_idx % 4]:
            if campo != "descripcion":
                current_t = ConfigLoader.get_threshold_a3(campo)
                nuevos_thresholds[campo] = st.number_input(
                    f"{label}",
                    min_value=0,
                    max_value=100,
                    value=current_t,
                    key=f"threshold_{campo}",
                )
            else:
                st.text_input(f"{label} (contexto)", value="--", disabled=True)
                nuevos_thresholds[campo] = None

            current_r = ConfigLoader.get_requerido_a3(campo)
            nuevos_requeridos[campo] = st.checkbox(
                f"Requerido",
                value=current_r,
                key=f"requerido_{campo}",
            )

        col_idx += 1
        if col_idx % 4 == 0:
            threshold_cols = st.columns(4)

    st.markdown("---")
    st.subheader("🤖 Modelos y Parámetros por Agente")

    nuevos_agentes = {}

    for agente in AGENTES:
        st.markdown(f"**{AGENTE_LABELS[agente]}**")

        current_model = ConfigLoader.get_model(agente)
        current_temp = ConfigLoader.get_temp(agente)
        current_tokens = ConfigLoader.get_tokens(agente)
        current_timeout = ConfigLoader.get_timeout(agente)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            selected_model = st.selectbox(
                "Modelo",
                options=model_names,
                index=model_names.index(current_model)
                if current_model in model_names
                else 0,
                key=f"global_model_{agente}",
            )

        with col2:
            nueva_temp = st.number_input(
                "Temperatura",
                min_value=0.0,
                max_value=2.0,
                value=float(current_temp),
                step=0.1,
                key=f"temp_{agente}",
            )

        with col3:
            nuevos_tokens = st.number_input(
                "Max Tokens",
                min_value=1,
                max_value=4096,
                value=int(current_tokens),
                step=1,
                key=f"tokens_{agente}",
            )

        with col4:
            nuevo_timeout = st.number_input(
                "Timeout (s)",
                min_value=5,
                max_value=300,
                value=int(current_timeout),
                step=5,
                key=f"timeout_{agente}",
            )

        nuevos_agentes[agente] = {
            "modelo": selected_model,
            "temperatura": nueva_temp,
            "max_tokens": nuevos_tokens,
            "timeout": nuevo_timeout,
        }

        st.markdown("---")

    st.subheader("🛠️ Herramientas (Tool Calling)")

    col_tools1, col_tools2 = st.columns(2)

    with col_tools1:
        tool_buscar_entidad = st.checkbox(
            "buscar_entidad",
            value=ConfigLoader.get_tool_buscar_entidad(),
            key="tool_buscar_entidad",
        )

    with col_tools2:
        tool_dry_run = st.checkbox(
            "MODO_DRY_RUN (solo lectura)",
            value=ConfigLoader.get_tool_dry_run(),
            key="tool_dry_run",
        )

    st.markdown("---")

    st.subheader("📝 Configuración del Sistema")

    col_log1, col_log2 = st.columns(2)

    with col_log1:
        current_log_level = ConfigLoader.get_log_level()
        log_level_options = ["INFO", "WARNING", "ERROR"]
        log_level_idx = (
            log_level_options.index(current_log_level)
            if current_log_level in log_level_options
            else 0
        )
        selected_log_level = st.selectbox(
            "Nivel de Logging",
            options=log_level_options,
            index=log_level_idx,
            key="log_level_select",
        )

    col_sys1, col_sys2 = st.columns(2)
    with col_sys1:
        keywords_esc = st.text_input(
            "Palabras Clave de Escape (separadas por coma)",
            value=ConfigLoader.get_keywords_escape(),
            key="sys_keywords_escape",
        )
    with col_sys2:
        allow_write = st.checkbox(
            "Habilitar Escritura en DB (Producción)",
            value=ConfigLoader.get_permitir_escritura_db(),
            key="sys_allow_write",
        )

    st.markdown("---")

    col_save = st.columns(1)[0]

    with col_save:
        if st.button("💾 Guardar Configuración Global", use_container_width=True):
            for agente, config in nuevos_agentes.items():
                ConfigLoader.set_model(agente, config["modelo"])
                ConfigLoader.set_temp(agente, config["temperatura"])
                ConfigLoader.set_tokens(agente, config["max_tokens"])
                ConfigLoader.set_timeout(agente, config["timeout"])

            for campo, valor in nuevos_thresholds.items():
                if valor is not None:
                    ConfigLoader.set_threshold_a3(campo, valor)
            for campo, valor in nuevos_requeridos.items():
                ConfigLoader.set_requerido_a3(campo, valor)

            ConfigLoader.set_tool_buscar_entidad(tool_buscar_entidad)
            ConfigLoader.set_tool_dry_run(tool_dry_run)
            ConfigLoader.set_log_level(selected_log_level)
            ConfigLoader.set("KEYWORDS_ESCAPE", keywords_esc, "Palabras clave para detener flujos", "sistema")
            ConfigLoader.set("PERMITIR_ESCRITURA_DB", "true" if allow_write else "false", "Habilitar transacciones de escritura", "herramientas")

            log_message(
                "INFO",
                f"Configuración global actualizada - Log Level: {selected_log_level}",
                st.session_state.get("username"),
            )
            st.success("✅ Configuración global guardada correctamente")
            st.rerun()


def main():
    """Run the Streamlit dashboard."""
    from database import is_admin

    try:
        db_connected = test_connection()
    except Exception as e:
        log_message("ERROR", f"Error al conectar DB: {str(e)}")
        db_connected = False

    if not db_connected:
        log_message("ERROR", "Conexión a base de datos fallida")
        st.error("⚠️ Base de datos no conectada. Verifica la configuración.")
        return

    log_message("INFO", "Dashboard iniciado")

    # 1. Global Session Restore from Query Params (Priority)
    q_params = st.query_params
    if q_params.get("session_restore") == "true" and q_params.get("user"):
        st.session_state.user_id = q_params["user"]
        st.session_state.username = q_params.get("username", "Unknown")
        st.session_state.session_restored = True
        st.query_params.clear()
        log_message("INFO", f"Sesión restaurada globalmente para: {st.session_state.username}")
        st.rerun()

    # 2. Check login state
    if not is_logged_in():
        # Session search JS (if no user in session)
        detect_js = """
        <script>
        if (!window.sessionRestored) {
            window.sessionRestored = true;
            const savedUser = localStorage.getItem('myfinance_user');
            const savedUsername = localStorage.getItem('myfinance_username');
            if (savedUser && savedUsername) {
                console.log("Found session in localStorage, restoring...");
                window.location.href = "?session_restore=true&user=" + savedUser + "&username=" + encodeURIComponent(savedUsername);
            }
        }
        </script>
        """
        st.markdown(detect_js, unsafe_allow_html=True)
        
        # if st.session_state.get("show_register"):
        #     register_page()
        # else:
        #     login_page()
        # return
        pass # 🔥 BYPASS DESARROLLO

    user_id = get_user_id()

    user_is_admin = is_admin(user_id)

    st.sidebar.title(f"💰 MyFinance")
    st.sidebar.markdown(f"**Usuario:** {st.session_state.get('username', 'Unknown')}")
    if user_is_admin:
        st.sidebar.markdown("**Rol:** 👑 Admin")

    if st.sidebar.button("🚪 Cerrar Sesión"):
        # Clear localStorage
        clear_js = """
        <script>
            localStorage.removeItem('myfinance_user');
            localStorage.removeItem('myfinance_username');
        </script>
        """
        st.markdown(clear_js, unsafe_allow_html=True)
        st.session_state.clear()
        st.rerun()

    st.sidebar.markdown("---")

    nav_options = [
        "💬 Chat",
        "⚙️ Gestionar",
        "📊 Resumen",
        "📝 Transacciones",
        "📈 Reportes",
        "⚙️ Configuración",
    ]

    if user_is_admin:
        nav_options.insert(2, "👥 Usuarios")

    page = st.sidebar.radio("Navegación:", nav_options)

    if page == "💬 Chat":
        render_chat_page(user_id, DEFAULT_CHANNEL)
    elif page == "👥 Usuarios":
        render_users_page()
    elif page == "⚙️ Gestionar":
        render_gestionar_page(user_id)
    elif page == "📊 Resumen":
        render_summary_page()
    elif page == "📝 Transacciones":
        render_transactions_page(user_id)
    elif page == "📈 Reportes":
        render_reports_page()
    elif page == "⚙️ Configuración":
        render_settings_page()


if __name__ == "__main__":
    main()
