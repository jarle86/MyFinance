"""Database models for MyFinance."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TipoCuenta(str, Enum):
    """Account types."""

    EFECTIVO = "efectivo"
    BANCO = "banco"
    TARJETA_CREDITO = "tarjeta_credito"
    INVERSION = "inversion"
    PRESTAMO = "prestamo"
    ACTIVO = "activo"
    PASIVO = "pasivo"
    INGRESO = "ingreso"
    GASTO = "gasto"
    PATRIMONIO = "patrimonio"


class TipoTransaccion(str, Enum):
    """Transaction types."""

    INGRESO = "ingreso"
    GASTO = "gasto"
    TRANSFERENCIA = "transferencia"


class EstadoTransaccion(str, Enum):
    """Transaction states."""

    PENDIENTE = "pendiente"
    CONFIRMADO = "confirmado"
    CANCELADO = "cancelado"


class EstadoAutorizacion(str, Enum):
    """Authorization states."""

    PENDIENTE = "pendiente"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    INFO_REQUERIDA = "info_requerida"


class UsuarioBase(BaseModel):
    """Base user model."""

    telegram_id: Optional[int] = None
    username: Optional[str] = None
    nombre: Optional[str] = None
    moneda_preferida: str = "MXN"
    zona_horaria: str = "America/Mexico_City"
    password_hash: Optional[str] = None


class Usuario(UsuarioBase):
    """User model with ID."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fecha_registro: datetime
    ultimo_acceso: datetime
    config: dict = {}
    activo: bool = True


class CuentaBase(BaseModel):
    """Base account model."""

    nombre: str
    tipo: TipoCuenta
    naturaleza: bool = True  # True = credit increases
    saldo_inicial: Decimal = Decimal("0")
    saldo_actual: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")  # Current balance
    moneda: str = "DOP"
    color: Optional[str] = None
    icono: Optional[str] = None
    descripcion: Optional[str] = None
    # Tarjeta de crédito fields
    limite_credito: Optional[Decimal] = None
    fecha_corte: Optional[int] = None  # Day of month (1-31)
    fecha_pago: Optional[int] = None  # Day of month (1-31)
    tasa_interes: Optional[Decimal] = None  # Interest rate %
    alerta_cuota: bool = False
    # Inversión/Certificado fields
    fecha_vencimiento: Optional[date] = None
    tasa_rendimiento: Optional[Decimal] = None  # Expected return %
    monto_original: Optional[Decimal] = None
    alerta_vencimiento: bool = False
    # Préstamo fields
    monto_pagado: Decimal = Decimal("0")
    saldo_pendiente: Decimal = Decimal("0")
    # Alias support for multiple names/synonyms
    alias: Optional[list[str]] = []


class Cuenta(CuentaBase):
    """Account model with ID."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    padre_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    activa: bool = True


class CategoriaBase(BaseModel):
    """Base category model."""

    nombre: str
    icono: Optional[str] = None
    color: Optional[str] = None
    presupuesto: Optional[Decimal] = None
    alerta_umbral: Optional[Decimal] = None
    # Alias support for multiple names/synonyms
    alias: Optional[list[str]] = []


class Categoria(CategoriaBase):
    """Category model with ID."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    padre_id: Optional[UUID] = None
    created_at: datetime
    activa: bool = True


class TransaccionBase(BaseModel):
    """Base transaction model."""

    tipo: TipoTransaccion
    monto: Decimal
    fecha: date
    fecha_original: Optional[str] = None
    descripcion: Optional[str] = None
    proveedor: Optional[str] = None
    naturaleza: bool = False  # False = debit (expense)
    monto_impuesto: Optional[Decimal] = None
    monto_descuento: Optional[Decimal] = None
    monto_otros_cargos: Optional[Decimal] = None
    origen_raw: Optional[str] = None
    destino_raw: Optional[str] = None
    subtipo_registro: Optional[str] = None
    ocr_procesado: bool = False
    ocr_datos: Optional[dict] = None
    imagen_url: Optional[str] = None
    estado: EstadoTransaccion = EstadoTransaccion.CONFIRMADO
    fuente: str = "telegram"


class Transaccion(TransaccionBase):
    """Transaction model with ID."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    cuenta_id: Optional[UUID] = None
    categoria_id: Optional[UUID] = None
    debe_id: Optional[UUID] = None
    haber_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class TransaccionWithDetails(Transaccion):
    """Transaction model with joined details."""

    cuenta_nombre: Optional[str] = None
    cuenta_icono: Optional[str] = None
    categoria_nombre: Optional[str] = None
    categoria_icono: Optional[str] = None
    categoria_color: Optional[str] = None


class TransaccionAutorizacionBase(BaseModel):
    """Base authorization model."""

    estado: EstadoAutorizacion = EstadoAutorizacion.PENDIENTE
    monto_umbral: Optional[Decimal] = None
    comentarios: Optional[str] = None


class TransaccionAutorizacion(TransaccionAutorizacionBase):
    """Authorization model with ID."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    transaccion_id: UUID
    revisado_por: Optional[UUID] = None
    fecha_revision: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ConversacionPendienteBase(BaseModel):
    """Base pending conversation model."""

    estado: str = "iniciada"
    intentos: int = 0
    max_intentos: int = 5
    datos: dict = {}
    datos_faltantes: Optional[list[str]] = []
    pregunta_actual: Optional[str] = None
    ruta_anterior: Optional[str] = None
    ultimo_mensaje: Optional[str] = None


class ConversacionPendiente(ConversacionPendienteBase):
    """Pending conversation model with ID."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    started_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class PreguntaBase(BaseModel):
    """Base question model."""

    pregunta: str
    tipo_respuesta: Optional[str] = None
    respuesta: Optional[str] = None
    respondida: bool = False
    orden: Optional[int] = None


class Pregunta(PreguntaBase):
    """Question model with ID."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversacion_id: UUID
    created_at: datetime
    respondida_at: Optional[datetime] = None


class SistemaConfig(BaseModel):
    """System configuration model."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    clave: str
    valor: str
    descripcion: Optional[str] = None
    tipo: str = "string"
    modulo: Optional[str] = None
    activo: bool = True
    created_at: datetime
    updated_at: datetime


# Response models for API


class TransaccionCreate(TransaccionBase):
    """Schema for creating a transaction."""

    cuenta_id: Optional[UUID] = None
    categoria_id: Optional[UUID] = None


class TransaccionPreview(BaseModel):
    """Preview of a transaction before confirmation."""

    tipo: str
    cuenta: str
    monto: Decimal
    fecha: date
    descripcion: Optional[str] = None

    def to_message(self) -> str:
        """Convert to user-friendly message."""
        return f"""📝 Preview del registro:

Tipo: {self.tipo}
Cuenta: {self.cuenta}
Monto: ${self.monto:,.2f}
Fecha: {self.fecha}
{self.descripcion and f"Descripción: {self.descripcion}" or ""}

¿Confirmas?"""


class BalanceResponse(BaseModel):
    """Balance response model."""

    total_ingresos: Decimal
    total_gastos: Decimal
    balance: Decimal
    por_categoria: dict[str, Decimal]


# Chat models


class ChatTopicBase(BaseModel):
    """Base chat topic model."""

    canal: str = "web"
    titulo: str = "General"


class ChatTopic(ChatTopicBase):
    """Chat topic model with ID."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    usuario_id: UUID
    created_at: datetime
    updated_at: datetime
    activo: bool = True


class ChatMessageBase(BaseModel):
    """Base chat message model."""

    canal: str = "web"
    role: str = "user"
    content: str
    route: Optional[str] = None
    metadata: dict = {}


class ChatMessage(ChatMessageBase):
    """Chat message model with ID."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    topic_id: UUID
    created_at: datetime


class AsientoContable(BaseModel):
    """Strict accounting JSON schema for Agent A4."""

    monto_total: Optional[float] = None
    origen: Optional[str] = None
    destino: Optional[str] = None
    monto: Optional[float] = None
    monto_impuesto: Optional[float] = None
    monto_descuento: Optional[float] = None
    monto_otros_cargos: Optional[float] = None
    moneda: Optional[str] = None
    fecha: Optional[str] = None
    concepto: Optional[str] = None
    categoria: Optional[str] = None
    _razonamiento_previo: Optional[str] = None
