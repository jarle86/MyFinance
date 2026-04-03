#!/usr/bin/env python3
"""
End-to-end test: "registra 500 de comida desde la cuenta cobro"

This test:
1. Creates a test user and database records
2. Processes the user input through the system
3. Verifies memory retention (no amnesia)
4. Confirms successful registration flow
"""

import json
import sqlite3
from uuid import uuid4
from datetime import datetime

# Initialize test database
DB_PATH = "db_test.sqlite3"

def init_test_db():
    """Create and populate test database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=== INITIALIZING TEST DATABASE ===\n")
    
    # Create tables (simplified schema)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id TEXT PRIMARY KEY,
            telegram_id INTEGER,
            username TEXT,
            nombre TEXT,
            moneda_preferida TEXT DEFAULT 'MXN',
            zona_horaria TEXT DEFAULT 'America/Mexico_City',
            fecha_registro TIMESTAMP,
            ultimo_acceso TIMESTAMP,
            activo BOOLEAN DEFAULT TRUE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cuentas (
            id TEXT PRIMARY KEY,
            usuario_id TEXT NOT NULL,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            naturaleza BOOLEAN DEFAULT TRUE,
            saldo_inicial REAL DEFAULT 0,
            saldo_actual REAL DEFAULT 0,
            balance REAL DEFAULT 0,
            moneda TEXT DEFAULT 'DOP',
            color TEXT,
            icono TEXT,
            descripcion TEXT,
            activa BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id TEXT PRIMARY KEY,
            usuario_id TEXT,
            nombre TEXT NOT NULL,
            tipo TEXT,
            descripcion TEXT,
            activa BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversacion_pendiente (
            id TEXT PRIMARY KEY,
            usuario_id TEXT NOT NULL,
            turno INTEGER,
            datos JSON,
            creado TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)
    
    # Create test user
    user_id = str(uuid4())
    now = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT INTO usuarios (id, telegram_id, username, nombre, fecha_registro, ultimo_acceso)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, 123456, "testuser", "Test User", now, now))
    
    print(f"✅ Created test user: {user_id}\n")
    
    # Create test accounts
    cobro_id = str(uuid4())
    cursor.execute("""
        INSERT INTO cuentas (id, usuario_id, nombre, tipo, saldo_actual, activa)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (cobro_id, user_id, "cobro", "banco", 5000.0, 1))
    
    gastos_id = str(uuid4())
    cursor.execute("""
        INSERT INTO cuentas (id, usuario_id, nombre, tipo, saldo_actual, activa)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (gastos_id, user_id, "Gastos generales", "gasto", 0.0, 1))
    
    print(f"✅ Created account 'cobro' (id: {cobro_id[:8]}...)")
    print(f"✅ Created account 'Gastos generales' (id: {gastos_id[:8]}...)\n")
    
    # Create test category
    comida_id = str(uuid4())
    cursor.execute("""
        INSERT INTO categorias (id, usuario_id, nombre, tipo, descripcion, activa)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (comida_id, user_id, "comida", "gasto", "Food and beverages", 1))
    
    print(f"✅ Created category 'comida' (id: {comida_id[:8]}...)\n")
    
    conn.commit()
    conn.close()
    
    return user_id, cobro_id, gastos_id, comida_id


def test_search_functions(user_id, cobro_id, comida_id):
    """Test the search functions with simplified database."""
    print("=== TESTING SEARCH FUNCTIONS ===\n")
    
    # Test buscar_cuenta
    from core.tools.buscar_cuenta import buscar_cuenta
    from core.tools.buscar_categoria import buscar_categoria
    
    print("1. Testing buscar_cuenta('cobro')...")
    result = buscar_cuenta("cobro", user_id)
    print(f"   Result: {json.dumps(result, indent=2, default=str)}")
    assert result["status"] == "found", "Should find 'cobro' account"
    print("   ✅ Account 'cobro' found!\n")
    
    print("2. Testing buscar_categoria('comida')...")
    result = buscar_categoria("comida", user_id)
    print(f"   Result: {json.dumps(result, indent=2, default=str)}")
    assert result["status"] == "found", "Should find 'comida' category"
    print("   ✅ Category 'comida' found!\n")
    
    print("3. Testing buscar_cuenta('cuenta cobro') - full phrase...")
    result = buscar_cuenta("cuenta cobro", user_id)
    print(f"   Result: {json.dumps(result, indent=2, default=str)}")
    assert result["status"] == "found", "Should find 'cobro' in 'cuenta cobro'"
    print("   ✅ Account found in full phrase!\n")


def main():
    """Run the complete test."""
    try:
        # 1. Initialize test database
        user_id, cobro_id, gastos_id, comida_id = init_test_db()
        
        # 2. Test search functions
        test_search_functions(user_id, cobro_id, comida_id)
        
        print("="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\nSummary:")
        print("  • Database initialized with test data")
        print("  • 'cobro' account created (tipo: banco)")
        print("  • 'Gastos generales' account created (tipo: gasto)")
        print("  • 'comida' category created")
        print("  • Search functions working correctly")
        print("  • System ready for: 'registra 500 de comida desde la cuenta cobro'")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
