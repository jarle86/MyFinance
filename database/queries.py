"""Database queries for MyFinance."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from .base_queries import db_pool, execute_query, get_db_connection
from .models import (
    BalanceResponse,
    ChatMessage,
    ChatTopic,
    ConversacionPendiente,
    Cuenta,
    Categoria,
    SistemaConfig,
    Transaccion,
    TransaccionAutorizacion,
    Usuario,
)


# ===========================================
# USUARIOS (Users)
# ===========================================


def get_or_create_user(telegram_id: int, username: Optional[str] = None) -> Usuario:
    """Get user by telegram_id or create if not exists."""
    query = """
        INSERT INTO usuarios (telegram_id, username)
        VALUES (%s, %s)
        ON CONFLICT (telegram_id) DO UPDATE SET
            username = EXCLUDED.username,
            ultimo_acceso = CURRENT_TIMESTAMP
        RETURNING id, telegram_id, username, nombre, fecha_registro,
                  ultimo_acceso, config, activo, moneda_preferida, zona_horaria
    """
    result = execute_query(query, (telegram_id, username), fetch=True, commit=True)
    if result:
        return Usuario(**result[0])
    raise Exception("Failed to get or create user")


def get_user_by_telegram(telegram_id: int) -> Optional[Usuario]:
    """Get user by telegram ID."""
    query = """
        SELECT id, telegram_id, username, nombre, fecha_registro,
               ultimo_acceso, config, activo, moneda_preferida, zona_horaria
        FROM usuarios
        WHERE telegram_id = %s AND activo = TRUE
    """
    result = execute_query(query, (telegram_id,), fetch=True)
    if result:
        return Usuario(**result[0])
    return None


def get_user_by_id(user_id: UUID) -> Optional[Usuario]:
    """Get user by internal UUID."""
    query = """
        SELECT id, telegram_id, username, nombre, fecha_registro,
               ultimo_acceso, config, activo, moneda_preferida, zona_horaria,
               password_hash
        FROM usuarios
        WHERE id = %s AND activo = TRUE
    """
    result = execute_query(query, (str(user_id),), fetch=True)
    if result:
        return Usuario(**result[0])
    return None


def get_user_by_username(username: str) -> Optional[Usuario]:
    """Get user by username."""
    query = """
        SELECT id, telegram_id, username, nombre, fecha_registro,
               ultimo_acceso, config, activo, moneda_preferida, zona_horaria,
               password_hash
        FROM usuarios
        WHERE username = %s AND activo = TRUE
    """
    result = execute_query(query, (username,), fetch=True)
    if result:
        return Usuario(**result[0])
    return None


def create_web_user(username: str, password_hash: Optional[str] = None) -> Usuario:
    """Create a new web user (no telegram_id)."""
    query = """
        INSERT INTO usuarios (username, password_hash)
        VALUES (%s, %s)
        RETURNING id, telegram_id, username, nombre, fecha_registro,
                  ultimo_acceso, config, activo, moneda_preferida, zona_horaria,
                  password_hash
    """
    result = execute_query(query, (username, password_hash), fetch=True, commit=True)
    if result:
        return Usuario(**result[0])
    raise Exception("Failed to create web user")


def update_user_password(user_id: UUID, password_hash: str) -> bool:
    """Update user's password hash."""
    query = """
        UPDATE usuarios
        SET password_hash = %s
        WHERE id = %s
    """
    execute_query(query, (password_hash, str(user_id)), commit=True)
    return True


def update_user_access(telegram_id: int) -> None:
    """Update user's last access time."""
    query = (
        "UPDATE usuarios SET ultimo_acceso = CURRENT_TIMESTAMP WHERE telegram_id = %s"
    )
    execute_query(query, (telegram_id,), commit=True)


def update_user(
    user_id: UUID,
    username: Optional[str] = None,
    nombre: Optional[str] = None,
    activo: Optional[bool] = None,
    password_hash: Optional[str] = None,
    config: Optional[dict] = None,
) -> bool:
    """Update user details."""
    import json

    updates = []
    params = []

    if username is not None:
        updates.append("username = %s")
        params.append(username)
    if nombre is not None:
        updates.append("nombre = %s")
        params.append(nombre)
    if activo is not None:
        updates.append("activo = %s")
        params.append(activo)
    if password_hash is not None:
        updates.append("password_hash = %s")
        params.append(password_hash)
    if config is not None:
        updates.append("config = %s")
        params.append(json.dumps(config))

    if not updates:
        return False

    params.append(str(user_id))
    query = f"UPDATE usuarios SET {', '.join(updates)} WHERE id = %s"
    execute_query(query, tuple(params), commit=True)
    return True


def deactivate_user(user_id: UUID) -> bool:
    """Deactivate a user (soft delete)."""
    query = "UPDATE usuarios SET activo = FALSE WHERE id = %s"
    execute_query(query, (str(user_id),), commit=True)
    return True


def delete_user(user_id: UUID) -> bool:
    """Permanently delete a user and their data."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN")
            try:
                cur.execute(
                    "DELETE FROM usuario_roles WHERE usuario_id = %s", (str(user_id),)
                )
                cur.execute(
                    "DELETE FROM conversaciones_pendientes WHERE usuario_id = %s",
                    (str(user_id),),
                )
                cur.execute(
                    "DELETE FROM transacciones WHERE usuario_id = %s", (str(user_id),)
                )
                cur.execute(
                    "DELETE FROM chat_topics WHERE usuario_id = %s", (str(user_id),)
                )
                cur.execute(
                    "DELETE FROM categorias WHERE usuario_id = %s", (str(user_id),)
                )
                cur.execute(
                    "DELETE FROM cuentas WHERE usuario_id = %s", (str(user_id),)
                )
                cur.execute("DELETE FROM usuarios WHERE id = %s", (str(user_id),))
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                raise e


# ===========================================
# ROLES
# ===========================================


def get_all_roles() -> list[dict]:
    """Get all available roles."""
    query = """
        SELECT id, nombre, descripcion
        FROM roles
        ORDER BY nombre
    """
    result = execute_query(query, fetch=True)
    return result if result else []


def get_user_roles(usuario_id: UUID) -> list[str]:
    """Get all roles for a user."""
    query = """
        SELECT r.nombre
        FROM usuario_roles ur
        JOIN roles r ON r.id = ur.rol_id
        WHERE ur.usuario_id = %s
    """
    result = execute_query(query, (str(usuario_id),), fetch=True)
    return [r["nombre"] for r in result] if result else []


def has_role(usuario_id: UUID, rol: str) -> bool:
    """Check if user has a specific role."""
    query = """
        SELECT 1 FROM usuario_roles ur
        JOIN roles r ON r.id = ur.rol_id
        WHERE ur.usuario_id = %s AND r.nombre = %s
    """
    result = execute_query(query, (str(usuario_id), rol), fetch=True)
    return len(result) > 0


def is_admin(usuario_id: UUID) -> bool:
    """Check if user is admin."""
    return has_role(usuario_id, "admin")


def assign_role(usuario_id: UUID, rol: str) -> bool:
    """Assign a role to a user."""
    query_rol = "SELECT id FROM roles WHERE nombre = %s"
    result = execute_query(query_rol, (rol,), fetch=True)
    if not result:
        return False

    rol_id = result[0]["id"]

    query_assign = """
        INSERT INTO usuario_roles (usuario_id, rol_id)
        VALUES (%s, %s)
        ON CONFLICT (usuario_id, rol_id) DO NOTHING
    """
    execute_query(query_assign, (str(usuario_id), str(rol_id)), commit=True)
    return True


def remove_role(usuario_id: UUID, rol: str) -> bool:
    """Remove a role from a user."""
    query_rol = "SELECT id FROM roles WHERE nombre = %s"
    result = execute_query(query_rol, (rol,), fetch=True)
    if not result:
        return False

    rol_id = result[0]["id"]

    query_remove = """
        DELETE FROM usuario_roles
        WHERE usuario_id = %s AND rol_id = %s
    """
    execute_query(query_remove, (str(usuario_id), str(rol_id)), commit=True)
    return True


def get_all_users_with_roles() -> list[dict]:
    """Get all users with their roles."""
    query = """
        SELECT 
            u.id, u.username, u.nombre, u.activo, u.ultimo_acceso,
            u.fecha_registro,
            COALESCE(
                json_agg(json_build_object('id', r.id, 'nombre', r.nombre)) FILTER (WHERE r.id IS NOT NULL),
                '[]'
            ) as roles
        FROM usuarios u
        LEFT JOIN usuario_roles ur ON u.id = ur.usuario_id
        LEFT JOIN roles r ON r.id = ur.rol_id
        GROUP BY u.id, u.username, u.nombre, u.activo, u.ultimo_acceso, u.fecha_registro
        ORDER BY u.fecha_registro DESC
    """
    result = execute_query(query, fetch=True)
    return result if result else []


# ===========================================
# CUENTAS (Accounts)
# ===========================================


def get_cuentas_by_user(usuario_id: UUID) -> list[Cuenta]:
    """Get all accounts for a user."""
    query = """
        SELECT id, usuario_id, nombre, tipo, naturaleza, padre_id,
               saldo_inicial, saldo_actual, moneda, color, icono,
               descripcion, created_at, updated_at, activa
        FROM cuentas
        WHERE usuario_id = %s AND activa = TRUE
        ORDER BY nombre
    """
    result = execute_query(query, (str(usuario_id),), fetch=True)
    return [Cuenta(**row) for row in result] if result else []


def get_cuenta_by_id(cuenta_id: UUID) -> Optional[Cuenta]:
    """Get account by ID."""
    query = """
        SELECT id, usuario_id, nombre, tipo, naturaleza, padre_id,
               saldo_inicial, saldo_actual, moneda, color, icono,
               descripcion, created_at, updated_at, activa
        FROM cuentas
        WHERE id = %s
    """
    result = execute_query(query, (str(cuenta_id),), fetch=True)
    return Cuenta(**result[0]) if result else None


def get_cuenta_by_nombre(usuario_id: UUID, nombre: str) -> Optional[Cuenta]:
    """Get account by name for a user."""
    query = """
        SELECT id, usuario_id, nombre, tipo, naturaleza, padre_id,
               saldo_inicial, saldo_actual, moneda, color, icono,
               descripcion, created_at, updated_at, activa
        FROM cuentas
        WHERE usuario_id = %s AND LOWER(nombre) = LOWER(%s) AND activa = TRUE
    """
    result = execute_query(query, (str(usuario_id), nombre), fetch=True)
    return Cuenta(**result[0]) if result else None


def create_cuenta(
    usuario_id: UUID,
    nombre: str,
    tipo: str,
    naturaleza: bool = True,
    saldo_inicial: Decimal = Decimal("0"),
    balance: Optional[Decimal] = None,
    limite_credito: Optional[Decimal] = None,
    fecha_corte: Optional[int] = None,
    fecha_pago: Optional[int] = None,
    tasa_interes: Optional[Decimal] = None,
    alerta_cuota: bool = False,
    fecha_vencimiento: Optional[date] = None,
    tasa_rendimiento: Optional[Decimal] = None,
    monto_original: Optional[Decimal] = None,
    alerta_vencimiento: bool = False,
    monto_pagado: Decimal = Decimal("0"),
    saldo_pendiente: Decimal = Decimal("0"),
) -> Cuenta:
    """Create a new account with extended fields."""
    query = """
        INSERT INTO cuentas (
            usuario_id, nombre, tipo, naturaleza, saldo_inicial, saldo_actual,
            balance, limite_credito, fecha_corte, fecha_pago, tasa_interes, alerta_cuota,
            fecha_vencimiento, tasa_rendimiento, monto_original, alerta_vencimiento,
            monto_pagado, saldo_pendiente
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
    """
    if balance is None:
        balance = saldo_inicial

    result = execute_query(
        query,
        (
            str(usuario_id),
            nombre,
            tipo,
            naturaleza,
            saldo_inicial,
            saldo_inicial,
            balance,
            limite_credito,
            fecha_corte,
            fecha_pago,
            tasa_interes,
            alerta_cuota,
            fecha_vencimiento,
            tasa_rendimiento,
            monto_original,
            alerta_vencimiento,
            monto_pagado,
            saldo_pendiente,
        ),
        fetch=True,
        commit=True,
    )
    return Cuenta(**result[0])


def crear_cuenta_con_apertura(
    user_id,
    nombre,
    tipo,
    activa,
    saldo_inicial,
    balance,
    limite_credito=None,
    fecha_corte=None,
    fecha_pago=None,
    tasa_interes=None,
    alerta_cuota=False,
    fecha_vencimiento=None,
    tasa_rendimiento=None,
    monto_original=None,
    alerta_vencimiento=False,
    monto_pagado=0,
    saldo_pendiente=0,
):
    """
    Crea una cuenta y su asiento de apertura en el Ledger usando una transacción ACID.
    """
    from types import SimpleNamespace
    from psycopg2.extras import RealDictCursor

    conn = db_pool.get_connection()

    # Clasificación contable
    CUENTAS_ACTIVO = ["efectivo", "banco", "inversion", "activo", "corretaje", "gasto", "costo"]
    CUENTAS_PASIVO = ["tarjeta_credito", "prestamo", "pasivo", "patrimonio", "ingreso"]

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # --- 1. RESOLVER CUENTA DE PATRIMONIO ---
            cur.execute(
                """
                SELECT id FROM cuentas 
                WHERE nombre = 'Patrimonio de Apertura' AND usuario_id = %s
            """,
                (str(user_id),),
            )
            patrimonio = cur.fetchone()

            if patrimonio:
                patrimonio_id = patrimonio["id"]
            else:
                # Crear la cuenta de sistema si no existe
                cur.execute(
                    """
                    INSERT INTO cuentas (usuario_id, nombre, tipo, naturaleza, saldo_actual, balance, activa)
                    VALUES (%s, 'Patrimonio de Apertura', 'patrimonio', true, 0, 0, true)
                    RETURNING id
                """,
                    (str(user_id),),
                )
                patrimonio_id = cur.fetchone()["id"]

            # --- 2. INSERTAR LA NUEVA CUENTA ---
            naturaleza_cuenta = False if tipo.lower() in CUENTAS_ACTIVO else True
            
            cur.execute(
                """
                INSERT INTO cuentas (
                    usuario_id, nombre, tipo, naturaleza, activa, saldo_actual, balance, 
                    limite_credito, fecha_corte, fecha_pago, tasa_interes, 
                    alerta_cuota, fecha_vencimiento, tasa_rendimiento, 
                    monto_original, alerta_vencimiento, monto_pagado, saldo_pendiente
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) RETURNING *
            """,
                (
                    str(user_id),
                    nombre,
                    tipo,
                    naturaleza_cuenta,
                    activa,
                    saldo_inicial,
                    balance,
                    limite_credito,
                    fecha_corte,
                    fecha_pago,
                    tasa_interes,
                    alerta_cuota,
                    fecha_vencimiento,
                    tasa_rendimiento,
                    monto_original,
                    alerta_vencimiento,
                    monto_pagado,
                    saldo_pendiente,
                ),
            )
            nueva_cuenta = cur.fetchone()
            nueva_cuenta_id = nueva_cuenta["id"]

            # --- 3. ASIENTO DE APERTURA (PARTIDA DOBLE) ---
            if saldo_inicial > 0:
                # Determinar Debe y Haber según naturaleza
                if tipo in CUENTAS_ACTIVO:
                    debe_id = nueva_cuenta_id
                    haber_id = patrimonio_id
                elif tipo in CUENTAS_PASIVO:
                    debe_id = patrimonio_id
                    haber_id = nueva_cuenta_id
                else:
                    debe_id = nueva_cuenta_id
                    haber_id = patrimonio_id

                # Insertar la transacción
                cur.execute(
                    """
                    INSERT INTO transacciones (
                        usuario_id, debe_id, haber_id, monto, descripcion, 
                        fecha, tipo, estado, fuente, naturaleza
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, 'confirmado', 'sistema', true
                    )
                """,
                    (
                        str(user_id),
                        str(debe_id),
                        str(haber_id),
                        saldo_inicial,
                        f"Asiento de Apertura - {nombre}",
                        datetime.now().date(),
                        "apertura",
                    ),
                )

            # --- 4. COMMIT DE LA TRANSACCIÓN ACID ---
            conn.commit()

            return SimpleNamespace(**nueva_cuenta)

    except Exception as e:
        conn.rollback()  # 🛡️ EL SALVAVIDAS
        raise Exception(f"Fallo en transacción ACID: {str(e)}")
    finally:
        db_pool.return_connection(conn)


def update_cuenta(
    cuenta_id: UUID,
    nombre: Optional[str] = None,
    tipo: Optional[str] = None,
    saldo_actual: Optional[Decimal] = None,
    balance: Optional[Decimal] = None,
    activa: Optional[bool] = None,
    # Extended fields
    limite_credito: Optional[Decimal] = None,
    fecha_corte: Optional[int] = None,
    fecha_pago: Optional[int] = None,
    tasa_interes: Optional[Decimal] = None,
    alerta_cuota: Optional[bool] = None,
    fecha_vencimiento: Optional[date] = None,
    tasa_rendimiento: Optional[Decimal] = None,
    monto_original: Optional[Decimal] = None,
    alerta_vencimiento: Optional[bool] = None,
    monto_pagado: Optional[Decimal] = None,
    saldo_pendiente: Optional[Decimal] = None,
) -> Optional[Cuenta]:
    """Update an account with extended fields.

    Args:
        cuenta_id: Account UUID
        nombre: New name
        tipo: New type
        saldo_actual: New balance
        balance: Current balance
        activa: Active status
        ... extended fields for specific account types
    """
    updates = []
    params = []

    if nombre is not None:
        updates.append("nombre = %s")
        params.append(nombre)
    if tipo is not None:
        updates.append("tipo = %s")
        params.append(tipo)
    if saldo_actual is not None:
        updates.append("saldo_actual = %s")
        params.append(str(saldo_actual))
    if balance is not None:
        updates.append("balance = %s")
        params.append(str(balance))
    if activa is not None:
        updates.append("activa = %s")
        params.append(activa)
    # Extended fields
    if limite_credito is not None:
        updates.append("limite_credito = %s")
        params.append(str(limite_credito) if limite_credito else None)
    if fecha_corte is not None:
        updates.append("fecha_corte = %s")
        params.append(fecha_corte)
    if fecha_pago is not None:
        updates.append("fecha_pago = %s")
        params.append(fecha_pago)
    if tasa_interes is not None:
        updates.append("tasa_interes = %s")
        params.append(str(tasa_interes) if tasa_interes else None)
    if alerta_cuota is not None:
        updates.append("alerta_cuota = %s")
        params.append(alerta_cuota)
    if fecha_vencimiento is not None:
        updates.append("fecha_vencimiento = %s")
        params.append(str(fecha_vencimiento) if fecha_vencimiento else None)
    if tasa_rendimiento is not None:
        updates.append("tasa_rendimiento = %s")
        params.append(str(tasa_rendimiento) if tasa_rendimiento else None)
    if monto_original is not None:
        updates.append("monto_original = %s")
        params.append(str(monto_original) if monto_original else None)
    if alerta_vencimiento is not None:
        updates.append("alerta_vencimiento = %s")
        params.append(alerta_vencimiento)
    if monto_pagado is not None:
        updates.append("monto_pagado = %s")
        params.append(str(monto_pagado))
    if saldo_pendiente is not None:
        updates.append("saldo_pendiente = %s")
        params.append(str(saldo_pendiente))

    if not updates:
        return get_cuenta_by_id(cuenta_id)

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(cuenta_id))

    query = f"UPDATE cuentas SET {', '.join(updates)} WHERE id = %s RETURNING *"

    result = execute_query(query, tuple(params), fetch=True, commit=True)
    return Cuenta(**result[0]) if result else None


def check_cuenta_en_uso(cuenta_id: UUID) -> dict:
    """Check if account is in use by transactions.

    Args:
        cuenta_id: Account UUID

    Returns:
        Dict with usage info
    """
    query = """
        SELECT COUNT(*) as tx_count
        FROM transacciones
        WHERE cuenta_id = %s
    """
    result = execute_query(query, (str(cuenta_id),), fetch=True)
    tx_count = result[0]["tx_count"] if result else 0

    return {
        "en_uso": tx_count > 0,
        "tx_count": tx_count,
        "mensaje": f"Tiene {tx_count} transacción(es) asociada(s)"
        if tx_count > 0
        else "Sin uso",
    }


def delete_cuenta(cuenta_id: UUID) -> dict:
    """Delete an account (only if not in use).

    Args:
        cuenta_id: Account UUID

    Returns:
        Dict with result
    """
    uso = check_cuenta_en_uso(cuenta_id)

    if uso["en_uso"]:
        return {
            "success": False,
            "error": "cuenta_en_uso",
            "mensaje": uso["mensaje"],
        }

    query = "DELETE FROM cuentas WHERE id = %s"
    execute_query(query, (str(cuenta_id),), commit=True)

    return {"success": True, "mensaje": "Cuenta eliminada"}


# ===========================================
# CATEGORIAS (Categories)
# ===========================================


def get_categorias_by_user(usuario_id: UUID) -> list[Categoria]:
    """Get all categories for a user."""
    query = """
        SELECT id, usuario_id, nombre, icono, color, padre_id,
               tipo, presupuesto, alerta_umbral, created_at, activa
        FROM categorias
        WHERE usuario_id = %s AND activa = TRUE
        ORDER BY nombre
    """
    result = execute_query(query, (str(usuario_id),), fetch=True)
    return [Categoria(**row) for row in result] if result else []


def get_default_categorias() -> list[Categoria]:
    """Get default system categories."""
    query = """
        SELECT id, usuario_id, nombre, icono, color, padre_id,
               tipo, presupuesto, alerta_umbral, created_at, activa
        FROM categorias
        WHERE usuario_id IS NULL
        ORDER BY nombre
    """
    result = execute_query(query, None, fetch=True)
    if not result:
        return []

    # Fix NULL usuario_id for Pydantic
    cleaned = []
    for row in result:
        row = dict(row)
        if row.get("usuario_id") is None:
            row["usuario_id"] = "00000000-0000-0000-0000-000000000000"  # Dummy UUID
        cleaned.append(row)

    return [Categoria(**row) for row in cleaned]


def get_categoria_by_nombre(nombre: str, usuario_id: Optional[UUID] = None) -> Optional[Categoria]:
    """Get category by name (default or user)."""
    if usuario_id:
        query = """
            SELECT id, usuario_id, nombre, icono, color, padre_id,
                   tipo, presupuesto, alerta_umbral, created_at, activa
            FROM categorias
            WHERE LOWER(nombre) = LOWER(%s) AND (usuario_id = %s OR usuario_id IS NULL)
            ORDER BY usuario_id DESC NULLS LAST
            LIMIT 1
        """
        result = execute_query(query, (nombre, str(usuario_id)), fetch=True)
    else:
        query = """
            SELECT id, usuario_id, nombre, icono, color, padre_id,
                   tipo, presupuesto, alerta_umbral, created_at, activa
            FROM categorias
            WHERE LOWER(nombre) = LOWER(%s)
            LIMIT 1
        """
        result = execute_query(query, (nombre,), fetch=True)
        
    if not result:
        return None
        
    # Fix NULL usuario_id for Pydantic on root categories
    row = dict(result[0])
    if row.get("usuario_id") is None:
        row["usuario_id"] = "00000000-0000-0000-0000-000000000000"
        
    return Categoria(**row)


def create_categoria(
    usuario_id: UUID,
    nombre: str,
    icono: Optional[str] = None,
    color: Optional[str] = None,
    presupuesto: Optional[Decimal] = None,
    alerta_umbral: Optional[Decimal] = None,
) -> Categoria:
    """Create a new category for a user."""
    query = """
        INSERT INTO categorias (usuario_id, nombre, icono, color, presupuesto, alerta_umbral)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, usuario_id, nombre, icono, color, padre_id,
                  presupuesto, alerta_umbral, created_at, activa
    """
    result = execute_query(
        query,
        (
            str(usuario_id),
            nombre,
            icono,
            color,
            str(presupuesto) if presupuesto else None,
            str(alerta_umbral) if alerta_umbral else None,
        ),
        fetch=True,
        commit=True,
    )
    return Categoria(**result[0])


def update_categoria(
    categoria_id: UUID,
    nombre: Optional[str] = None,
    icono: Optional[str] = None,
    color: Optional[str] = None,
    presupuesto: Optional[Decimal] = None,
    alerta_umbral: Optional[Decimal] = None,
    activa: Optional[bool] = None,
) -> Optional[Categoria]:
    """Update a category.

    Args:
        categoria_id: Category UUID
        nombre: New name
        icono: New icon
        color: New color
        presupuesto: New budget
        alerta_umbral: New alert threshold
        activa: Active status

    Returns:
        Updated Categoria or None
    """
    updates = []
    params = []

    if nombre is not None:
        updates.append("nombre = %s")
        params.append(nombre)
    if icono is not None:
        updates.append("icono = %s")
        params.append(icono)
    if color is not None:
        updates.append("color = %s")
        params.append(color)
    if presupuesto is not None:
        updates.append("presupuesto = %s")
        params.append(str(presupuesto))
    if alerta_umbral is not None:
        updates.append("alerta_umbral = %s")
        params.append(str(alerta_umbral))
    if activa is not None:
        updates.append("activa = %s")
        params.append(activa)

    if not updates:
        return get_categoria_by_nombre(str(categoria_id))

    params.append(str(categoria_id))
    query = f"UPDATE categorias SET {', '.join(updates)} WHERE id = %s RETURNING *"

    result = execute_query(query, tuple(params), fetch=True, commit=True)
    return Categoria(**result[0]) if result else None


def check_categoria_en_uso(categoria_id: UUID) -> dict:
    """Check if category is in use by transactions.

    Args:
        categoria_id: Category UUID

    Returns:
        Dict with usage info
    """
    query = """
        SELECT COUNT(*) as tx_count
        FROM transacciones
        WHERE categoria_id = %s
    """
    result = execute_query(query, (str(categoria_id),), fetch=True)
    tx_count = result[0]["tx_count"] if result else 0

    return {
        "en_uso": tx_count > 0,
        "tx_count": tx_count,
        "mensaje": f"Tiene {tx_count} transacción(es) asociada(s)"
        if tx_count > 0
        else "Sin uso",
    }


def delete_categoria(categoria_id: UUID) -> dict:
    """Delete a category (only if not in use).

    Args:
        categoria_id: Category UUID

    Returns:
        Dict with result
    """
    uso = check_categoria_en_uso(categoria_id)

    if uso["en_uso"]:
        return {
            "success": False,
            "error": "categoria_en_uso",
            "mensaje": uso["mensaje"],
        }

    query = "DELETE FROM categorias WHERE id = %s"
    execute_query(query, (str(categoria_id),), commit=True)

    return {"success": True, "mensaje": "Categoría eliminada"}


# ===========================================
# TRANSACCIONES (Transactions)
# ===========================================


def create_transaccion(
    usuario_id: UUID,
    tipo: str,
    monto: Decimal,
    fecha: date,
    naturaleza: bool,
    cuenta_id: Optional[UUID] = None,
    categoria_id: Optional[UUID] = None,
    descripcion: Optional[str] = None,
    proveedor: Optional[str] = None,
    debe_id: Optional[UUID] = None,
    haber_id: Optional[UUID] = None,
    estado: str = "confirmado",
    fuente: str = "telegram",
) -> Transaccion:
    """Create a new transaction."""
    query = """
        INSERT INTO transacciones (
            usuario_id, tipo, monto, fecha, naturaleza,
            cuenta_id, categoria_id, descripcion, proveedor,
            debe_id, haber_id, estado, fuente
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, usuario_id, cuenta_id, categoria_id, tipo, monto,
                  fecha, fecha_original, descripcion, proveedor, naturaleza,
                  debe_id, haber_id, ocr_procesado, ocr_datos, imagen_url,
                  estado, created_at, updated_at, fuente
    """
    result = execute_query(
        query,
        (
            str(usuario_id),
            tipo,
            monto,
            fecha,
            naturaleza,
            str(cuenta_id) if cuenta_id else None,
            str(categoria_id) if categoria_id else None,
            descripcion,
            proveedor,
            str(debe_id) if debe_id else None,
            str(haber_id) if haber_id else None,
            estado,
            fuente,
        ),
        fetch=True,
        commit=True,
    )
    return Transaccion(**result[0])


def get_transacciones_by_user(
    usuario_id: UUID,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    categoria_id: Optional[UUID] = None,
    tipo: Optional[str] = None,
    limit: int = 100,
) -> list[Transaccion]:
    """Get transactions for a user with filters."""
    params = [str(usuario_id)]
    query = """
        SELECT id, usuario_id, cuenta_id, categoria_id, tipo, monto,
               fecha, fecha_original, descripcion, proveedor, naturaleza,
               debe_id, haber_id, ocr_procesado, ocr_datos, imagen_url,
               estado, created_at, updated_at, fuente
        FROM transacciones
        WHERE usuario_id = %s
    """

    if fecha_inicio:
        query += " AND fecha >= %s"
        params.append(fecha_inicio)

    if fecha_fin:
        query += " AND fecha <= %s"
        params.append(fecha_fin)

    if categoria_id:
        query += " AND categoria_id = %s"
        params.append(str(categoria_id))

    if tipo:
        query += " AND tipo = %s"
        params.append(tipo)

    query += f" ORDER BY fecha DESC, created_at DESC LIMIT {limit}"

    result = execute_query(query, tuple(params), fetch=True)
    return [Transaccion(**row) for row in result] if result else []


def get_transacciones_full(
    usuario_id: UUID,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    tipo: Optional[str] = None,
    estado: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[dict], int]:
    """Get transactions with full details (LEFT JOIN cuenta and categoria).

    Args:
        usuario_id: User UUID
        fecha_inicio: Start date filter
        fecha_fin: End date filter
        tipo: Transaction type ('ingreso', 'gasto', 'transferencia')
        estado: Transaction state ('pendiente', 'confirmado', 'cancelado')
        page: Page number (1-indexed)
        per_page: Items per page

    Returns:
        Tuple of (transactions list, total count)
    """
    params = [str(usuario_id)]
    base_query = """
        FROM transacciones t
        LEFT JOIN cuentas c ON t.cuenta_id = c.id
        LEFT JOIN categorias cat ON t.categoria_id = cat.id
        WHERE t.usuario_id = %s
    """

    if fecha_inicio:
        base_query += " AND t.fecha >= %s"
        params.append(fecha_inicio)

    if fecha_fin:
        base_query += " AND t.fecha <= %s"
        params.append(fecha_fin)

    if tipo:
        base_query += " AND t.tipo = %s"
        params.append(tipo)

    if estado:
        base_query += " AND t.estado = %s"
        params.append(estado)

    count_query = f"SELECT COUNT(*) as total {base_query}"
    count_result = execute_query(count_query, tuple(params), fetch=True)
    total_count = count_result[0]["total"] if count_result else 0

    offset = (page - 1) * per_page
    select_query = f"""
        SELECT
            t.id, t.usuario_id, t.cuenta_id, t.categoria_id, t.tipo, t.monto,
            t.fecha, t.fecha_original, t.descripcion, t.proveedor, t.naturaleza,
            t.debe_id, t.haber_id, t.monto_impuesto, t.monto_descuento,
            t.monto_otros_cargos, t.origen_raw, t.destino_raw, t.subtipo_registro,
            t.ocr_procesado, t.ocr_datos, t.imagen_url, t.estado,
            t.created_at, t.updated_at, t.fuente,
            c.nombre as cuenta_nombre, c.icono as cuenta_icono,
            cat.nombre as categoria_nombre, cat.icono as categoria_icono, cat.color as categoria_color
        {base_query}
        ORDER BY t.fecha DESC, t.created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([per_page, offset])

    result = execute_query(select_query, tuple(params), fetch=True)
    return result if result else [], total_count


def get_transacciones_summary(
    usuario_id: UUID,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
) -> dict:
    """Get transaction summary totals.

    Args:
        usuario_id: User UUID
        fecha_inicio: Start date filter
        fecha_fin: End date filter

    Returns:
        Dict with total_gastos, total_ingresos, balance
    """
    params = [str(usuario_id)]
    where_clause = "WHERE usuario_id = %s AND estado = 'confirmado'"

    if fecha_inicio:
        where_clause += " AND fecha >= %s"
        params.append(fecha_inicio)

    if fecha_fin:
        where_clause += " AND fecha <= %s"
        params.append(fecha_fin)

    query = f"""
        SELECT
            COALESCE(SUM(CASE WHEN tipo = 'gasto' THEN monto ELSE 0 END), 0) as total_gastos,
            COALESCE(SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END), 0) as total_ingresos,
            COALESCE(SUM(CASE WHEN naturaleza = TRUE THEN monto ELSE -monto END), 0) as balance
        FROM transacciones
        {where_clause}
    """

    result = execute_query(query, tuple(params), fetch=True)
    if result:
        return {
            "total_gastos": result[0]["total_gastos"],
            "total_ingresos": result[0]["total_ingresos"],
            "balance": result[0]["balance"],
        }
    return {"total_gastos": 0, "total_ingresos": 0, "balance": 0}


def update_transaccion(
    transaccion_id: UUID,
    tipo: Optional[str] = None,
    monto: Optional[Decimal] = None,
    fecha: Optional[date] = None,
    descripcion: Optional[str] = None,
    proveedor: Optional[str] = None,
    cuenta_id: Optional[UUID] = None,
    categoria_id: Optional[UUID] = None,
    estado: Optional[str] = None,
    monto_impuesto: Optional[Decimal] = None,
    monto_descuento: Optional[Decimal] = None,
    monto_otros_cargos: Optional[Decimal] = None,
) -> Optional[Transaccion]:
    """Update a transaction.

    Args:
        transaccion_id: Transaction UUID
        tipo: Transaction type
        monto: Amount
        fecha: Date
        descripcion: Description
        proveedor: Vendor
        cuenta_id: Account UUID
        categoria_id: Category UUID
        estado: State ('pendiente', 'confirmado', 'cancelado')
        monto_impuesto: Tax amount
        monto_descuento: Discount amount
        monto_otros_cargos: Other charges

    Returns:
        Updated Transaccion or None if not found
    """
    updates = []
    params = []

    if tipo is not None:
        updates.append("tipo = %s")
        params.append(tipo)
    if monto is not None:
        updates.append("monto = %s")
        params.append(monto)
    if fecha is not None:
        updates.append("fecha = %s")
        params.append(fecha)
    if descripcion is not None:
        updates.append("descripcion = %s")
        params.append(descripcion)
    if proveedor is not None:
        updates.append("proveedor = %s")
        params.append(proveedor)
    if cuenta_id is not None:
        updates.append("cuenta_id = %s")
        params.append(str(cuenta_id))
    if categoria_id is not None:
        updates.append("categoria_id = %s")
        params.append(str(categoria_id))
    if estado is not None:
        updates.append("estado = %s")
        params.append(estado)
    if monto_impuesto is not None:
        updates.append("monto_impuesto = %s")
        params.append(monto_impuesto)
    if monto_descuento is not None:
        updates.append("monto_descuento = %s")
        params.append(monto_descuento)
    if monto_otros_cargos is not None:
        updates.append("monto_otros_cargos = %s")
        params.append(monto_otros_cargos)

    if not updates:
        return None

    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(str(transaccion_id))

    query = f"""
        UPDATE transacciones
        SET {", ".join(updates)}
        WHERE id = %s
        RETURNING id, usuario_id, cuenta_id, categoria_id, tipo, monto,
                  fecha, fecha_original, descripcion, proveedor, naturaleza,
                  monto_impuesto, monto_descuento, monto_otros_cargos,
                  origen_raw, destino_raw, subtipo_registro,
                  ocr_procesado, ocr_datos, imagen_url, estado,
                  created_at, updated_at, fuente
    """

    result = execute_query(query, tuple(params), fetch=True, commit=True)
    return Transaccion(**result[0]) if result else None


def get_balance(
    usuario_id: UUID,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
) -> BalanceResponse:
    """Calculate balance for a user."""
    params = [str(usuario_id)]
    query_where = " WHERE usuario_id = %s"
    query_group = ""

    if fecha_inicio:
        query_where += " AND fecha >= %s"
        params.append(fecha_inicio)

    if fecha_fin:
        query_where += " AND fecha <= %s"
        params.append(fecha_fin)

    # Get totals by type
    query = f"""
        SELECT
            COALESCE(SUM(CASE WHEN tipo = 'ingreso' THEN monto ELSE 0 END), 0) as total_ingresos,
            COALESCE(SUM(CASE WHEN tipo = 'gasto' THEN monto ELSE 0 END), 0) as total_gastos
        FROM transacciones
        {query_where} AND estado = 'confirmado'
    """
    result = execute_query(query, tuple(params), fetch=True)

    total_ingresos = (
        Decimal(str(result[0]["total_ingresos"])) if result else Decimal("0")
    )
    total_gastos = Decimal(str(result[0]["total_gastos"])) if result else Decimal("0")

    # Get by category
    query_cat = f"""
        SELECT c.nombre, COALESCE(SUM(t.monto), 0) as total
        FROM transacciones t
        LEFT JOIN categorias c ON t.categoria_id = c.id
        {query_where} AND t.tipo = 'gasto' AND t.estado = 'confirmado'
        GROUP BY c.nombre
        ORDER BY total DESC
    """
    result_cat = execute_query(query_cat, tuple(params), fetch=True)

    por_categoria = {
        row["nombre"]: Decimal(str(row["total"])) for row in result_cat if row["nombre"]
    }

    return BalanceResponse(
        total_ingresos=total_ingresos,
        total_gastos=total_gastos,
        balance=total_ingresos - total_gastos,
        por_categoria=por_categoria,
    )


# ===========================================
# AUTORIZACION (Purgatorio)
# ===========================================


def create_autorizacion(
    usuario_id: UUID,
    transaccion_id: UUID,
    monto_umbral: Optional[Decimal] = None,
) -> TransaccionAutorizacion:
    """Create authorization request."""
    query = """
        INSERT INTO transacciones_autorizacion (usuario_id, transaccion_id, monto_umbral)
        VALUES (%s, %s, %s)
        RETURNING id, usuario_id, transaccion_id, estado, monto_umbral,
                  revisado_por, fecha_revision, comentarios, created_at, updated_at
    """
    result = execute_query(
        query,
        (
            str(usuario_id),
            str(transaccion_id),
            str(monto_umbral) if monto_umbral else None,
        ),
        fetch=True,
        commit=True,
    )
    return TransaccionAutorizacion(**result[0])


def get_autorizaciones_pendientes(usuario_id: UUID) -> list[TransaccionAutorizacion]:
    """Get pending authorizations for a user."""
    query = """
        SELECT a.id, a.usuario_id, a.transaccion_id, a.estado, a.monto_umbral,
               a.revisado_por, a.fecha_revision, a.comentarios, a.created_at, a.updated_at
        FROM transacciones_autorizacion a
        WHERE a.usuario_id = %s AND a.estado = 'pendiente'
        ORDER BY a.created_at DESC
    """
    result = execute_query(query, (str(usuario_id),), fetch=True)
    return [TransaccionAutorizacion(**row) for row in result] if result else []


def update_autorizacion(
    autorizacion_id: UUID,
    estado: str,
    revisado_por: UUID,
    comentarios: Optional[str] = None,
) -> TransaccionAutorizacion:
    """Update authorization status."""
    query = """
        UPDATE transacciones_autorizacion
        SET estado = %s, revisado_por = %s, comentarios = %s,
            fecha_revision = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING id, usuario_id, transaccion_id, estado, monto_umbral,
                  revisado_por, fecha_revision, comentarios, created_at, updated_at
    """
    result = execute_query(
        query,
        (estado, str(revisado_por), comentarios, str(autorizacion_id)),
        fetch=True,
        commit=True,
    )
    return TransaccionAutorizacion(**result[0])


# ===========================================
# SISTEMA_CONFIG
# ===========================================


def get_config(clave: str) -> Optional[SistemaConfig]:
    """Get system configuration by key."""
    query = """
        SELECT id, clave, valor, descripcion, tipo, modulo, activo,
               created_at, updated_at
        FROM sistema_config
        WHERE clave = %s AND activo = TRUE
    """
    result = execute_query(query, (clave,), fetch=True)
    return SistemaConfig(**result[0]) if result else None


def get_config_value(clave: str, default: str = "") -> str:
    """Get system configuration value by key with default."""
    config = get_config(clave)
    return config.valor if config else default


def get_all_config() -> dict[str, str]:
    """Get all active configuration."""
    query = """
        SELECT clave, valor
        FROM sistema_config
        WHERE activo = TRUE
    """
    result = execute_query(query, None, fetch=True)
    return {row["clave"]: row["valor"] for row in result} if result else {}


def create_config(
    clave: str, valor: str, descripcion: str = "", modulo: str = ""
) -> bool:
    """Insert new system configuration.

    Args:
        clave: Configuration key
        valor: Configuration value
        descripcion: Description
        modulo: Module/agent name

    Returns:
        True if inserted, False otherwise
    """
    query = """
        INSERT INTO sistema_config (clave, valor, descripcion, modulo, activo, created_at, updated_at)
        VALUES (%s, %s, %s, %s, TRUE, NOW(), NOW())
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (clave, valor, descripcion, modulo))
            conn.commit()
            cursor.close()
        return True
    except Exception as e:
        logger.error(f"Error creating config {clave}: {e}")
        return False


def set_config(clave: str, valor: str, descripcion: str = "", modulo: str = "") -> bool:
    """Set config (UPDATE if exists, INSERT if not).

    Args:
        clave: Configuration key
        valor: New value
        descripcion: Description
        modulo: Module/agent name

    Returns:
        True if success
    """
    if update_config(clave, valor):
        return True
    return create_config(clave, valor, descripcion, modulo)


def update_config(clave: str, valor: str) -> bool:
    """Update system configuration value.

    Args:
        clave: Configuration key
        valor: New value

    Returns:
        True if updated, False otherwise
    """
    query = """
        UPDATE sistema_config
        SET valor = %s, updated_at = NOW()
        WHERE clave = %s AND activo = TRUE
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, (valor, clave))
        rows_affected = cursor.rowcount
        conn.commit()
        cursor.close()
    return rows_affected > 0


def get_all_models_config() -> dict[str, dict]:
    """Get all MODELO_* configurations.

    Returns:
        Dict with clave as key and {valor, descripcion, modulo} as value
    """
    query = """
        SELECT clave, valor, descripcion, modulo
        FROM sistema_config
        WHERE clave LIKE 'MODELO_%' AND activo = TRUE
        ORDER BY clave
    """
    result = execute_query(query, None, fetch=True)
    if not result:
        return {}
    return {
        row["clave"]: {
            "valor": row["valor"],
            "descripcion": row["descripcion"],
            "modulo": row["modulo"],
        }
        for row in result
    }


def execute_sql(query: str, params: Optional[tuple] = None) -> list[dict]:
    """Execute a raw SQL query and return results.

    Args:
        query: SQL query string (SELECT only for safety)
        params: Query parameters

    Returns:
        List of result rows as dicts
    """

    query_clean = query.strip().upper()
    if not query_clean.startswith("SELECT"):
        raise ValueError("Solo se permiten consultas SELECT")

    forbidden = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE"]
    for keyword in forbidden:
        if keyword in query_clean:
            raise ValueError(f"Consulta no permitida: {keyword}")

    result = execute_query(query, params, fetch=True, commit=False)
    return result if result else []


# ===========================================
# LOGS
# ===========================================


def log_operacion(
    usuario_id: Optional[UUID],
    operacion: str,
    modulo: str,
    parametres: Optional[dict] = None,
    resultado: Optional[dict] = None,
    exitosa: bool = True,
    duracion_ms: Optional[int] = None,
) -> None:
    """Log an operation."""
    query = """
        INSERT INTO logs_operaciones (
            usuario_id, operacion, modulo, parametros, resultado, exitosa, duracion_ms
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    execute_query(
        query,
        (
            str(usuario_id) if usuario_id else None,
            operacion,
            modulo,
            str(parametres) if parametres else None,
            str(resultado) if resultado else None,
            exitosa,
            duracion_ms,
        ),
        commit=True,
    )


# ===========================================
# CONVERSACION PENDIENTE (Interactive Mode)
# ===========================================


def create_pending_conversation(
    usuario_id: UUID,
    canal: str,
    datos_parciales: dict,
    pregunta_actual: str,
    ruta_anterior: str,
    ultimo_mensaje: str,
    datos_faltantes: Optional[list[str]] = None,
    estado: str = "iniciada",
) -> "ConversacionPendiente":
    """Create a new pending conversation for interactive mode."""
    import json

    query = """
        INSERT INTO conversacion_pendiente (
            usuario_id, estado, intentos, datos, pregunta_actual, 
            ruta_anterior, ultimo_mensaje, datos_faltantes
        )
        VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s)
        RETURNING id, usuario_id, estado, intentos, max_intentos, 
                  datos, datos_faltantes, pregunta_actual, ruta_anterior, 
                  ultimo_mensaje, started_at, updated_at, completed_at
    """
    result = execute_query(
        query,
        (
            str(usuario_id),
            estado,
            0,
            json.dumps(datos_parciales) if datos_parciales else "{}",
            pregunta_actual,
            ruta_anterior,
            ultimo_mensaje,
            datos_faltantes,
        ),
        fetch=True,
        commit=True,
    )
    if result:
        return ConversacionPendiente(**result[0])
    raise Exception("Failed to create pending conversation")


def get_pending_conversation(
    usuario_id: UUID,
    canal: str = "web",
) -> Optional["ConversacionPendiente"]:
    """Get active pending conversation for user and channel."""
    # Note: canal is not in the conversacion_pendiente table
    # We use usuario_id to find pending conversations
    query = """
        SELECT id, usuario_id, estado, intentos, max_intentos,
               datos, datos_faltantes, pregunta_actual, ruta_anterior,
               ultimo_mensaje, started_at, updated_at, completed_at
        FROM conversacion_pendiente
        WHERE usuario_id = %s 
          AND estado IN ('iniciada', 'preguntando', 'esperando_confirmacion')
        ORDER BY updated_at DESC
        LIMIT 1
    """
    result = execute_query(query, (str(usuario_id),), fetch=True)
    if result:
        return ConversacionPendiente(**result[0])
    return None


def update_pending_conversation(
    conversation_id: UUID,
    datos: Optional[dict] = None,
    intentos: Optional[int] = None,
    estado: Optional[str] = None,
    pregunta_actual: Optional[str] = None,
    dato_faltante: Optional[str] = None,
) -> bool:
    """Update pending conversation state."""
    import json

    updates = []
    params = []

    if datos is not None:
        updates.append("datos = %s::jsonb")
        params.append(json.dumps(datos) if isinstance(datos, dict) else datos)
    if intentos is not None:
        updates.append("intentos = %s")
        params.append(intentos)
    if estado is not None:
        updates.append("estado = %s")
        params.append(estado)
    if pregunta_actual is not None:
        updates.append("pregunta_actual = %s")
        params.append(pregunta_actual)
    if dato_faltante is not None:
        updates.append("datos_faltantes = %s")
        # Ensure dato_faltante is a list (for text[] column in PostgreSQL)
        if isinstance(dato_faltante, str):
            params.append([dato_faltante])
        else:
            params.append(dato_faltante)

    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(str(conversation_id))

        query = f"""
            UPDATE conversacion_pendiente
            SET {", ".join(updates)}
            WHERE id = %s
        """
        execute_query(query, tuple(params), commit=True)

    return True


def complete_pending_conversation(
    conversation_id: UUID,
    estado: str = "completada",
) -> bool:
    """Mark pending conversation as completed."""
    query = """
        UPDATE conversacion_pendiente
        SET estado = %s, completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """
    execute_query(query, (estado, str(conversation_id)), commit=True)
    return True


def cancel_pending_conversation(
    conversation_id: UUID,
) -> bool:
    """Cancel pending conversation."""
    return complete_pending_conversation(conversation_id, "cancelada")


# ===========================================
# CHAT TOPICS AND MESSAGES
# ===========================================


def create_chat_topic(
    usuario_id: UUID,
    canal: str = "web",
    titulo: str = "General",
) -> ChatTopic:
    """Create a new chat topic."""
    query = """
        INSERT INTO chat_topics (usuario_id, canal, titulo)
        VALUES (%s, %s, %s)
        RETURNING id, usuario_id, canal, titulo, created_at, updated_at, activo
    """
    result = execute_query(
        query, (str(usuario_id), canal, titulo), fetch=True, commit=True
    )
    if result:
        return ChatTopic(**result[0])
    raise Exception("Failed to create chat topic")


def get_chat_topics_by_user(
    usuario_id: UUID,
    canal: str = "web",
    limit: int = 50,
) -> list[ChatTopic]:
    """Get all chat topics for a user and channel."""
    query = """
        SELECT id, usuario_id, canal, titulo, created_at, updated_at, activo
        FROM chat_topics
        WHERE usuario_id = %s AND canal = %s AND activo = true
        ORDER BY updated_at DESC
        LIMIT %s
    """
    result = execute_query(query, (str(usuario_id), canal, limit), fetch=True)
    if result:
        return [ChatTopic(**row) for row in result]
    return []


def get_chat_topic(topic_id: UUID, canal: str = "web") -> Optional[ChatTopic]:
    """Get a specific chat topic."""
    query = """
        SELECT id, usuario_id, canal, titulo, created_at, updated_at, activo
        FROM chat_topics
        WHERE id = %s AND canal = %s AND activo = true
    """
    result = execute_query(query, (str(topic_id), canal), fetch=True)
    if result:
        return ChatTopic(**result[0])
    return None


def get_or_create_default_topic(
    usuario_id: UUID,
    canal: str = "web",
) -> ChatTopic:
    """Get or create default 'General' topic for user and channel."""
    query = """
        SELECT id, usuario_id, canal, titulo, created_at, updated_at, activo
        FROM chat_topics
        WHERE usuario_id = %s AND canal = %s AND titulo = 'General' AND activo = true
        ORDER BY created_at DESC
        LIMIT 1
    """
    result = execute_query(query, (str(usuario_id), canal), fetch=True)

    if result:
        return ChatTopic(**result[0])

    return create_chat_topic(usuario_id, canal, "General")


def update_chat_topic_title(topic_id: UUID, titulo: str) -> Optional[ChatTopic]:
    """Update chat topic title."""
    query = """
        UPDATE chat_topics
        SET titulo = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s AND activo = true
        RETURNING id, usuario_id, canal, titulo, created_at, updated_at, activo
    """
    result = execute_query(query, (titulo, str(topic_id)), fetch=True, commit=True)
    if result:
        return ChatTopic(**result[0])
    return None


def delete_chat_topic(topic_id: UUID) -> bool:
    """Soft delete a chat topic (set activo = false)."""
    query = """
        UPDATE chat_topics
        SET activo = false, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """
    execute_query(query, (str(topic_id),), commit=True)
    return True


def create_chat_message(
    topic_id: UUID,
    canal: str = "web",
    role: str = "user",
    content: str = "",
    route: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> ChatMessage:
    """Create a new chat message."""
    query = """
        INSERT INTO chat_messages (topic_id, canal, role, content, route, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, topic_id, canal, role, content, route, metadata, created_at
    """
    result = execute_query(
        query,
        (
            str(topic_id),
            canal,
            role,
            content,
            route,
            str(metadata) if metadata else "{}",
        ),
        fetch=True,
        commit=True,
    )
    if result:
        return ChatMessage(**result[0])
    raise Exception("Failed to create chat message")


def get_chat_messages_by_topic(
    topic_id: UUID,
    canal: str = "web",
    limit: int = 500,
) -> list[ChatMessage]:
    """Get chat messages for a topic, most recent last."""
    query = """
        SELECT id, topic_id, canal, role, content, route, metadata, created_at
        FROM chat_messages
        WHERE topic_id = %s AND canal = %s
        ORDER BY created_at ASC
        LIMIT %s
    """
    result = execute_query(query, (str(topic_id), canal, limit), fetch=True)
    if result:
        return [ChatMessage(**row) for row in result]
    return []


def get_topic_title_suggestion(first_message: str) -> str:
    """Generate a title suggestion from the first message."""
    words = first_message.split()[:5]
    title = " ".join(words)
    if len(first_message) > 50:
        title += "..."
    return title


def prune_old_messages(topic_id: UUID, canal: str = "web", keep_last: int = 500) -> int:
    """Delete old messages keeping only the last N."""
    query = """
        DELETE FROM chat_messages
        WHERE id NOT IN (
            SELECT id FROM chat_messages
            WHERE topic_id = %s AND canal = %s
            ORDER BY created_at DESC
            LIMIT %s
        )
        AND topic_id = %s AND canal = %s
    """
    cursor = execute_query(
        query,
        (str(topic_id), canal, keep_last, str(topic_id), canal),
        fetch=False,
        commit=True,
    )
    return cursor.rowcount if cursor else 0
