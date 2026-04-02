"""Identity Gateway - Translates external IDs to internal user_id."""

import logging
from typing import Optional
from uuid import UUID

from database import (
    get_user_by_telegram,
    get_user_by_username,
    get_user_by_id,
    create_web_user,
    get_user_roles,
    assign_role,
)

logger = logging.getLogger(__name__)


class IdentityGateway:
    """Gateway for translating external IDs to internal user_id."""

    @staticmethod
    def _build_user_dict(user_data: dict, include_roles: bool = True) -> dict:
        """Build user dict with roles."""
        user = {
            "user_id": UUID(user_data["id"])
            if isinstance(user_data["id"], str)
            else user_data["id"],
            "username": user_data.get("username"),
            "nombre": user_data.get("nombre"),
            "telegram_id": user_data.get("telegram_id"),
        }

        if include_roles:
            user["roles"] = get_user_roles(user["user_id"])
            user["is_admin"] = "admin" in user["roles"]

        return user

    @staticmethod
    def get_user_by_telegram_id(telegram_id: int) -> Optional[dict]:
        """Get user by Telegram ID."""
        from database.queries import execute_query

        query = """
            SELECT u.id, u.username, u.nombre, u.telegram_id
            FROM usuarios u
            WHERE u.telegram_id = %s AND u.activo = TRUE
        """
        result = execute_query(query, (telegram_id,), fetch=True)
        if result:
            return IdentityGateway._build_user_dict(result[0])
        return None

    @staticmethod
    def get_or_create_by_telegram(
        telegram_id: int,
        username: Optional[str] = None,
        nombre: Optional[str] = None,
    ) -> dict:
        """Get existing user or create new one from Telegram."""
        existing = IdentityGateway.get_user_by_telegram_id(telegram_id)
        if existing:
            logger.info(
                f"User found: {existing['user_id']} for telegram_id={telegram_id}"
            )
            return existing

        from database.queries import execute_query

        query = """
            INSERT INTO usuarios (telegram_id, username, nombre)
            VALUES (%s, %s, %s)
            RETURNING id, username, nombre, telegram_id
        """
        result = execute_query(
            query, (telegram_id, username, nombre), fetch=True, commit=True
        )
        user = IdentityGateway._build_user_dict(result[0])

        assign_role(user["user_id"], "user")
        user["roles"] = ["user"]
        user["is_admin"] = False

        logger.info(
            f"New user created: {user['user_id']} for telegram_id={telegram_id}"
        )
        return user

    @staticmethod
    def get_user_by_id(user_id: UUID) -> Optional[dict]:
        """Get user by internal UUID."""
        from database.queries import execute_query

        query = """
            SELECT id, username, nombre, telegram_id
            FROM usuarios
            WHERE id = %s AND activo = TRUE
        """
        result = execute_query(query, (str(user_id),), fetch=True)
        if result:
            return IdentityGateway._build_user_dict(result[0])
        return None

    @staticmethod
    def get_user_by_username(username: str) -> Optional[dict]:
        """Get user by username."""
        user = get_user_by_username(username)
        if user:
            return IdentityGateway._build_user_dict(
                {
                    "id": str(user.id),
                    "username": user.username,
                    "nombre": user.nombre,
                    "telegram_id": user.telegram_id,
                }
            )
        return None

    @staticmethod
    def authenticate_web_user(
        username: str, password: Optional[str] = None
    ) -> Optional[dict]:
        """Authenticate web user with password verification."""
        import hashlib

        from database import get_user_by_username

        user = get_user_by_username(username)
        if not user:
            return None

        # No password provided and user has no password - allow login
        if not password and not user.password_hash:
            return IdentityGateway._build_user_dict(
                {
                    "id": str(user.id),
                    "username": user.username,
                    "nombre": user.nombre,
                    "telegram_id": user.telegram_id,
                }
            )

        # Password provided - verify it
        if password and user.password_hash:
            provided_hash = hashlib.sha256(password.encode()).hexdigest()
            if provided_hash != user.password_hash:
                return None
            return IdentityGateway._build_user_dict(
                {
                    "id": str(user.id),
                    "username": user.username,
                    "nombre": user.nombre,
                    "telegram_id": user.telegram_id,
                }
            )

        return None

    @staticmethod
    def create_web_user(
        username: str, password_hash: Optional[str] = None, rol: str = "user"
    ) -> dict:
        """Create a new web user."""
        user = create_web_user(username, password_hash)

        assign_role(user.id, rol)

        user_dict = IdentityGateway._build_user_dict(
            {
                "id": str(user.id),
                "username": user.username,
                "nombre": user.nombre,
                "telegram_id": user.telegram_id,
            }
        )
        user_dict["roles"] = [rol]
        user_dict["is_admin"] = rol == "admin"

        return user_dict

    @staticmethod
    def get_all_users() -> list[dict]:
        """Get all users with roles."""
        from database import get_all_users_with_roles

        users = get_all_users_with_roles()
        result = []
        for u in users:
            roles = [r["nombre"] for r in (u["roles"] or [])]
            result.append(
                {
                    "user_id": UUID(u["id"]),
                    "username": u["username"],
                    "nombre": u["nombre"],
                    "activo": u["activo"],
                    "ultimo_acceso": u.get("ultimo_acceso"),
                    "fecha_registro": u.get("fecha_registro"),
                    "roles": roles,
                    "is_admin": "admin" in roles,
                }
            )
        return result


identity_gateway = IdentityGateway()
