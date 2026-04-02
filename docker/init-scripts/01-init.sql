-- MyFinance Database Initialization Script
-- Run on first container start

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";  -- For future RAG

-- ===========================================
-- USUARIOS (Users)
-- ===========================================
CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    nombre VARCHAR(255),
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ultimo_acceso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config JSONB DEFAULT '{}',
    activo BOOLEAN DEFAULT TRUE,
    moneda_preferida VARCHAR(10) DEFAULT 'MXN',
    zona_horaria VARCHAR(50) DEFAULT 'America/Mexico_City',
    pin_seguridad VARCHAR(4),
    intentos_fallidos INTEGER DEFAULT 0,
    bloqueado_hasta TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_usuarios_telegram ON usuarios(telegram_id);
CREATE INDEX IF NOT EXISTS idx_usuarios_activo ON usuarios(activo);

-- ===========================================
-- CUENTAS (Accounts)
-- ===========================================
CREATE TABLE IF NOT EXISTS cuentas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id UUID REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre VARCHAR(255) NOT NULL,
    tipo VARCHAR(50) NOT NULL CHECK (tipo IN (
        'efectivo', 'banco', 'tarjeta_credito', 'inversion', 'prestamo', 
        'activo', 'pasivo', 'ingreso', 'gasto', 'patrimonio'
    )),
    naturaleza BOOLEAN NOT NULL,  -- TRUE = credit increases, FALSE = debit increases
    padre_id UUID REFERENCES cuentas(id),
    saldo_inicial DECIMAL(15,2) DEFAULT 0,
    saldo_actual DECIMAL(15,2) DEFAULT 0,
    balance DECIMAL(15,2) DEFAULT 0,  -- Current balance (for all types)
    moneda VARCHAR(10) DEFAULT 'MXN',
    color VARCHAR(7),
    icono VARCHAR(50),
    descripcion TEXT,
    -- Tarjeta de crédito fields
    limite_credito DECIMAL(15,2),
    fecha_corte INTEGER,  -- Day of month (1-31)
    fecha_pago INTEGER,   -- Day of month (1-31)
    tasa_interes DECIMAL(5,2),  -- Interest rate %
    alerta_cuota BOOLEAN DEFAULT FALSE,
    -- Inversión/Certificado fields
    fecha_vencimiento DATE,
    tasa_rendimiento DECIMAL(5,2),  -- Expected return %
    monto_original DECIMAL(15,2),
    alerta_vencimiento BOOLEAN DEFAULT FALSE,
    -- Préstamo fields
    monto_pagado DECIMAL(15,2) DEFAULT 0,
    saldo_pendiente DECIMAL(15,2) DEFAULT 0,
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activa BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_cuentas_usuario ON cuentas(usuario_id);
CREATE INDEX IF NOT EXISTS idx_cuentas_tipo ON cuentas(tipo);
CREATE INDEX IF NOT EXISTS idx_cuentas_padre ON cuentas(padre_id);

-- ===========================================
-- CATEGORIAS (Categories)
-- ===========================================
CREATE TABLE IF NOT EXISTS categorias (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id UUID REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre VARCHAR(255) NOT NULL,
    icono VARCHAR(50),
    color VARCHAR(7),
    padre_id UUID REFERENCES categorias(id),
    presupuesto DECIMAL(15,2),
    alerta_umbral DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activa BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_categorias_usuario ON categorias(usuario_id);

-- ===========================================
-- TRANSACCIONES (Transactions)
-- ===========================================
CREATE TABLE IF NOT EXISTS transacciones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id UUID REFERENCES usuarios(id) ON DELETE CASCADE,
    cuenta_id UUID REFERENCES cuentas(id) ON DELETE SET NULL,
    categoria_id UUID REFERENCES categorias(id) ON DELETE SET NULL,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('ingreso', 'gasto', 'transferencia')),
    monto DECIMAL(15,2) NOT NULL,
    fecha DATE NOT NULL,
    fecha_original VARCHAR(255),
    descripcion TEXT,
    proveedor VARCHAR(255),
    naturaleza BOOLEAN NOT NULL,
    debe_id UUID REFERENCES cuentas(id),
    haber_id UUID REFERENCES cuentas(id),
    ocr_procesado BOOLEAN DEFAULT FALSE,
    ocr_datos JSONB,
    imagen_url TEXT,
    estado VARCHAR(20) DEFAULT 'confirmado' CHECK (estado IN ('pendiente', 'confirmado', 'cancelado')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fuente VARCHAR(50) DEFAULT 'telegram'
);

CREATE INDEX IF NOT EXISTS idx_transacciones_usuario ON transacciones(usuario_id);
CREATE INDEX IF NOT EXISTS idx_transacciones_fecha ON transacciones(fecha);
CREATE INDEX IF NOT EXISTS idx_transacciones_cuenta ON transacciones(cuenta_id);
CREATE INDEX IF NOT EXISTS idx_transacciones_categoria ON transacciones(categoria_id);
CREATE INDEX IF NOT EXISTS idx_transacciones_estado ON transacciones(estado);
CREATE INDEX IF NOT EXISTS idx_transacciones_fecha_usuario ON transacciones(fecha, usuario_id);

-- ===========================================
-- ETIQUETAS (Tags)
-- ===========================================
CREATE TABLE IF NOT EXISTS etiquetas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id UUID REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre VARCHAR(100) NOT NULL,
    color VARCHAR(7),
    UNIQUE(usuario_id, nombre)
);

CREATE TABLE IF NOT EXISTS transacciones_etiquetas (
    transaccion_id UUID REFERENCES transacciones(id) ON DELETE CASCADE,
    etiqueta_id UUID REFERENCES etiquetas(id) ON DELETE CASCADE,
    PRIMARY KEY (transaccion_id, etiqueta_id)
);

-- ===========================================
-- AUTORIZACION (Purgatorio)
-- ===========================================
CREATE TABLE IF NOT EXISTS transacciones_autorizacion (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id UUID REFERENCES usuarios(id) ON DELETE CASCADE,
    transaccion_id UUID REFERENCES transacciones(id) ON DELETE CASCADE,
    estado VARCHAR(20) DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'aprobado', 'rechazado', 'info_requerida')),
    monto_umbral DECIMAL(15,2),
    revisado_por UUID REFERENCES usuarios(id),
    fecha_revision TIMESTAMP,
    comentarios TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_autorizacion_usuario ON transacciones_autorizacion(usuario_id, estado);
CREATE INDEX IF NOT EXISTS idx_autorizacion_estado ON transacciones_autorizacion(estado);

-- ===========================================
-- CONVERSACION_PENDIENTE (Interactive)
-- ===========================================
CREATE TABLE IF NOT EXISTS conversacion_pendiente (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id UUID REFERENCES usuarios(id) ON DELETE CASCADE,
    estado VARCHAR(30) DEFAULT 'iniciada' CHECK (estado IN ('iniciada', 'preguntando', 'esperando_confirmacion', 'completada', 'cancelada', 'excedida')),
    intentos INTEGER DEFAULT 0,
    max_intentos INTEGER DEFAULT 5,
    datos JSONB DEFAULT '{}',
    datos_faltantes TEXT[],
    pregunta_actual TEXT,
    ruta_anterior VARCHAR(10),
    ultimo_mensaje TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversacion_usuario ON conversacion_pendiente(usuario_id, estado);
CREATE INDEX IF NOT EXISTS idx_conversacion_estado ON conversacion_pendiente(estado);

-- ===========================================
-- PREGUNTAS (Questions)
-- ===========================================
CREATE TABLE IF NOT EXISTS preguntas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversacion_id UUID REFERENCES conversacion_pendiente(id) ON DELETE CASCADE,
    pregunta TEXT NOT NULL,
    tipo_respuesta VARCHAR(30),
    respuesta TEXT,
    respondida BOOLEAN DEFAULT FALSE,
    orden INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    respondida_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_preguntas_conversacion ON preguntas(conversacion_id);

-- ===========================================
-- SISTEMA_CONFIG (Configuration)
-- ===========================================
CREATE TABLE IF NOT EXISTS sistema_config (
    id SERIAL PRIMARY KEY,
    clave VARCHAR(100) UNIQUE NOT NULL,
    valor TEXT NOT NULL,
    descripcion TEXT,
    tipo VARCHAR(20) DEFAULT 'string',
    modulo VARCHAR(50),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_por VARCHAR(255)
);

-- Default configuration
INSERT INTO sistema_config (clave, valor, descripcion, modulo) VALUES
('TASK_CLASSIFY', 'Clasificador de intención - Detecta REGISTRAR, CONSULTAR, CHAT', 'Intent classification rules', 'A5'),
('TASK_PARSE', 'Esquema JSON para asiento contable', 'Accounting JSON schema', 'A2'),
('TASK_ASK', 'Lógica para detectar entidades faltantes', 'Missing entity detection', 'A2'),
('TASK_SQL', 'Estructura de tablas y reglas PostgreSQL', 'Table structure and SQL rules', 'A3'),
('TASK_OCR', 'Directrices para extracción de valores', 'OCR extraction guidelines', 'A1'),
('TASK_CHAT', 'Personalidad del asistente financiero', 'Chat personality and rules', 'A4')
ON CONFLICT (clave) DO NOTHING;

-- ===========================================
-- LOGS_OPERACIONES (Logs)
-- ===========================================
CREATE TABLE IF NOT EXISTS logs_operaciones (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    operacion VARCHAR(50) NOT NULL,
    modulo VARCHAR(50) NOT NULL,
    parametros JSONB,
    resultado JSONB,
    exitosa BOOLEAN DEFAULT TRUE,
    duracion_ms INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_logs_usuario ON logs_operaciones(usuario_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_modulo ON logs_operaciones(modulo, timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_exitosa ON logs_operaciones(exitosa, timestamp);

-- ===========================================
-- FUNCTIONS & TRIGGERS
-- ===========================================

-- Function to update account balance
CREATE OR REPLACE FUNCTION fn_actualizar_saldo_cuenta()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE cuentas c
    SET saldo_actual = (
        SELECT COALESCE(SUM(
            CASE 
                WHEN t.naturaleza = TRUE THEN t.monto
                ELSE -t.monto
            END
        ), 0)
        FROM transacciones t
        WHERE t.cuenta_id = c.id
            AND t.estado = 'confirmado'
    ) + c.saldo_inicial
    WHERE c.id = COALESCE(NEW.cuenta_id, OLD.cuenta_id);
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for balance update
DROP TRIGGER IF EXISTS tr_transaccion_saldo ON transacciones;
CREATE TRIGGER tr_transaccion_saldo
AFTER INSERT OR UPDATE ON transacciones
FOR EACH ROW
EXECUTE FUNCTION fn_actualizar_saldo_cuenta();

-- ===========================================
-- DEFAULT DATA (Sample Categories)
-- ===========================================
INSERT INTO categorias (nombre, icono, color) VALUES
('Alimentación', '🍽️', '#FF6B6B'),
('Transporte', '🚗', '#4ECDC4'),
('Servicios', '💡', '#45B7D1'),
('Entretenimiento', '🎬', '#96CEB4'),
('Salud', '🏥', '#FFEAA7'),
('Educación', '📚', '#DDA0DD'),
('Compras', '🛒', '#FFA07A'),
('Otros', '📦', '#95A5A6')
ON CONFLICT DO NOTHING;

-- ===========================================
-- SECURITY (RLS)
-- ===========================================
-- Enable Row Level Security
ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE cuentas ENABLE ROW LEVEL SECURITY;
ALTER TABLE transacciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE categorias ENABLE ROW LEVEL SECURITY;

-- Note: RLS policies should be configured per-application
-- This is a placeholder for future security implementation

-- ===========================================
-- SUCCESS MESSAGE
-- ===========================================
DO $$
BEGIN
    RAISE NOTICE 'MyFinance database initialized successfully!';
    RAISE NOTICE 'Vector extension enabled for future RAG support';
END $$;
