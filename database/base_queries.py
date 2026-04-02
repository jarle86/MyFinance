"""Database connection module for MyFinance."""

import os
import contextlib
from typing import Optional, Generator

import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DatabasePool:
    """Singleton database connection pool."""

    _instance: Optional["DatabasePool"] = None
    _pool: Optional[pool.ThreadedConnectionPool] = None

    def __new__(cls) -> "DatabasePool":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._pool is None:
            self._init_pool()
        else:
            # Check if pool has available connections
            self._check_pool_health()

    def _check_pool_health(self) -> None:
        """Check if pool is healthy, recreate if exhausted."""
        if self._pool is None:
            return
        try:
            # Try to get and return a test connection
            test_conn = self._pool.getconn()
            self._pool.putconn(test_conn)
        except psycopg2.pool.PoolError:
            # Pool exhausted, recreate it
            self._init_pool()

    def _init_pool(self) -> None:
        """Initialize the connection pool."""
        min_conn = int(os.getenv("DB_MIN_CONNECTIONS", "2"))
        max_conn = int(os.getenv("DB_MAX_CONNECTIONS", "10"))

        self._pool = pool.ThreadedConnectionPool(
            min_conn,
            max_conn,
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "myfinance"),
            user=os.getenv("DB_USER", "myfinance"),
            password=os.getenv("DB_PASSWORD", "myfinance"),
        )

    def get_connection(self):
        """Get a connection from the pool."""
        if self._pool is None:
            self._init_pool()
        return self._pool.getconn()

    def return_connection(self, conn) -> None:
        """Return a connection to the pool."""
        if self._pool:
            self._pool.putconn(conn)

    def close_all(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None


# Singleton instance
db_pool = DatabasePool()


@contextlib.contextmanager
def get_db_connection() -> Generator:
    """Get a database connection as a context manager.

    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM usuarios")
            # ...
    """
    conn = db_pool.get_connection()
    try:
        yield conn
    finally:
        db_pool.return_connection(conn)


def execute_query(
    query: str,
    params: tuple = None,
    fetch: bool = True,
    commit: bool = False,
) -> list | None:
    """Execute a query and return results."""
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)

            if fetch:
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                else:
                    results = []

                if commit:
                    conn.commit()

                return results

            if commit:
                conn.commit()

            return None
        except Exception as e:
            if commit:
                conn.rollback()
            raise e


def execute_many(query: str, params_list: list, commit: bool = True) -> None:
    """Execute a query with multiple parameter sets.

    Args:
        query: SQL query
        params_list: List of parameter tuples
        commit: Whether to commit the transaction
    """
    with get_db_connection() as conn:
        try:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)

            if commit:
                conn.commit()
        except Exception as e:
            if commit:
                conn.rollback()
            raise e


def test_connection() -> bool:
    """Test database connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        result = execute_query("SELECT 1 as test", fetch=True)
        return result is not None and result[0].get("test") == 1
    except Exception:
        return False
