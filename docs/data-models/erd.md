# Entity-Relationship Diagram - MyFinance 4.0

Visual representation of the database schema relationships.

---

## 1. Core Entity Relationships

### 1.1 Main Entities

```mermaid
erDiagram
    USUARIO ||--o{ CUENTA : tiene
    USUARIO ||--o{ TRANSACCION : registra
    USUARIO ||--o{ CONVERSACION_PENDIENTE : tiene
    USUARIO ||--o{ CONFIGURACION_AUTORIZACION : tiene
    USUARIO ||--o{ ETIQUETA : crea
    
    CUENTA ||--o{ TRANSACCION : genera
    CATEGORIA ||--o{ TRANSACCION : categoriza
    
    TRANSACCION ||--|{ AUTORIZACION : requiere
    TRANSACCION }o--|| ETIQUETA : etiquetada
    
    CONVERSACION_PENDIENTE ||--o{ PREGUNTA : contiene
```

---

## 2. User & Account Hierarchy

### 2.1 User to Account Relationship

```mermaid
erDiagram
    USUARIO {
        uuid id PK
        bigint telegram_id UK
        string username
        string nombre
        boolean activo
    }
    
    CUENTA {
        uuid id PK
        uuid usuario_id FK
        string nombre
        string tipo
        boolean naturaleza
        uuid padre_id FK
        decimal saldo_inicial
        decimal saldo_actual
    }
    
    USUARIO ||--o{ CUENTA : tiene
    
    CUENTA ||--o{ CUENTA : padre_hijo
```

---

## 3. Transaction Flow

### 3.1 Complete Transaction Lifecycle

```mermaid
erDiagram
    USUARIO {
        uuid id PK
    }
    
    CUENTA {
        uuid id PK
        uuid usuario_id FK
        string nombre
    }
    
    CATEGORIA {
        uuid id PK
        uuid usuario_id FK
        string nombre
    }
    
    TRANSACCION {
        uuid id PK
        uuid usuario_id FK
        uuid cuenta_id FK
        uuid categoria_id FK
        string tipo
        decimal monto
        date fecha
        boolean naturaleza
        uuid debe_id FK
        uuid haber_id FK
        string estado
    }
    
    AUTORIZACION {
        uuid id PK
        uuid usuario_id FK
        uuid transaccion_id FK
        string estado
    }
    
    ETIQUETA {
        uuid id PK
        uuid usuario_id FK
        string nombre
    }
    
    TRANSACCION_ETIQUETA {
        uuid transaccion_id FK
        uuid etiqueta_id FK
    }
    
    USUARIO ||--o{ TRANSACCION : registra
    USUARIO ||--o{ CATEGORIA : define
    CUENTA ||--o{ TRANSACCION : belongs_to
    CATEGORIA ||--o{ TRANSACCION : categorizes
    TRANSACCION ||--|{ AUTORIZACION : puede_necesitar
    TRANSACCION }o--|| ETIQUETA : tiene
```

---

## 4. Authorization Workflow

### 4.1 Purgatorio States

```mermaid
erDiagram
    TRANSACCION {
        uuid id PK
        string estado
    }
    
    AUTORIZACION {
        uuid id PK
        uuid transaccion_id FK
        string estado
        uuid revisado_por FK
        timestamp fecha_revision
    }
    
    TRANSACCION ||--|{ AUTORIZACION : trigger
    
    AUTORIZACION {
        string estado
    }
```

**State Transition:**
```mermaid
stateDiagram-v2
    [*] --> Pendiente
    Pendiente --> Aprobado: User approves
    Pendiente --> Rechazado: User rejects
    Pendiente --> InfoRequerida: More info needed
    InfoRequerida --> Pendiente: User provides info
    Aprobado --> [*]
    Rechazado --> [*]
```

---

## 5. Interactive Conversation Flow

### 5.1 Conversacion Pendiente States

```mermaid
erDiagram
    USUARIO {
        uuid id PK
    }
    
    CONVERSACION_PENDIENTE {
        uuid id PK
        uuid usuario_id FK
        string estado
        integer intentos
        json datos
        text pregunta_actual
    }
    
    PREGUNTA {
        uuid id PK
        uuid conversacion_id FK
        text pregunta
        string tipo_respuesta
        text respuesta
        boolean respondida
    }
    
    USUARIO ||--o{ CONVERSACION_PENDIENTE : tiene
    CONVERSACION_PENDIENTE ||--o{ PREGUNTA : formula
```

**State Machine:**
```mermaid
stateDiagram-v2
    [*] --> Iniciada
    Iniciada --> Preguntando: Missing data detected
    Preguntando --> EsperandoConfirmacion: All data collected
    EsperandoConfirmacion --> Completada: User confirms
    Preguntando --> Excedida: Max attempts reached
    Completada --> [*]
    Excedida --> [*]
    EsperandoConfirmacion --> Cancelada: User cancels
    Cancelada --> [*]
```

---

## 6. Configuration System

### 6.1 System Configuration

```mermaid
erDiagram
    SISTEMA_CONFIG {
        int id PK
        string clave UK
        text valor
        string descripcion
        string modulo
        boolean activo
    }
    
    USUARIO {
        uuid id PK
        json config
    }
    
    CONFIGURACION_AUTORIZACION {
        uuid id PK
        uuid usuario_id FK UK
        decimal monto_auto_aprobar
        decimal monto_requiere_aprobacion
    }
    
    SISTEMA_CONFIG ||--|| CONFIGURACION_AUTORIZACION : comparte_esquema
    USUARIO ||--|| CONFIGURACION_AUTORIZACION : define_reglas
```

---

## 7. Complete ERD

### 7.1 Full Database Diagram

```mermaid
erDiagram
    USUARIO {
        uuid id PK
        bigint telegram_id UK
        string username
        string nombre
        timestamp fecha_registro
        boolean activo
        string moneda_preferida
    }
    
    CUENTA {
        uuid id PK
        uuid usuario_id FK
        string nombre
        string tipo
        boolean naturaleza
        uuid padre_id FK
        decimal saldo_inicial
        decimal saldo_actual
    }
    
    CATEGORIA {
        uuid id PK
        uuid usuario_id FK
        string nombre
        uuid padre_id FK
        decimal presupuesto
    }
    
    TRANSACCION {
        uuid id PK
        uuid usuario_id FK
        uuid cuenta_id FK
        uuid categoria_id FK
        string tipo
        decimal monto
        date fecha
        string descripcion
        boolean naturaleza
        uuid debe_id FK
        uuid haber_id FK
        string estado
        timestamp created_at
    }
    
    ETIQUETA {
        uuid id PK
        uuid usuario_id FK
        string nombre
    }
    
    TRANSACCION_ETIQUETA {
        uuid transaccion_id FK
        uuid etiqueta_id FK
    }
    
    AUTORIZACION {
        uuid id PK
        uuid usuario_id FK
        uuid transaccion_id FK
        string estado
        uuid revisado_por FK
        timestamp fecha_revision
    }
    
    CONVERSACION_PENDIENTE {
        uuid id PK
        uuid usuario_id FK
        string estado
        integer intentos
        json datos
    }
    
    PREGUNTA {
        uuid id PK
        uuid conversacion_id FK
        text pregunta
        text respuesta
    }
    
    SISTEMA_CONFIG {
        int id PK
        string clave UK
        text valor
        string modulo
    }
    
    CONFIGURACION_AUTORIZACION {
        uuid id PK
        uuid usuario_id FK
        decimal monto_auto_aprobar
        decimal monto_requiere_aprobacion
    }
    
    USUARIO ||--o{ CUENTA : tiene
    USUARIO ||--o{ TRANSACCION : registra
    USUARIO ||--o{ CATEGORIA : define
    USUARIO ||--o{ ETIQUETA : crea
    USUARIO ||--o{ CONVERSACION_PENDIENTE : tiene
    USUARIO ||--o{ CONFIGURACION_AUTORIZACION : tiene
    
    CUENTA ||--o{ TRANSACCION : genera
    CUENTA ||--o{ CUENTA : padre_hijo
    
    CATEGORIA ||--o{ TRANSACCION : categoriza
    CATEGORIA ||--o{ CATEGORIA : padre_hijo
    
    TRANSACCION ||--|{ AUTORIZACION : requiere
    TRANSACCION }o--|| ETIQUETA : etiquetada
    
    CONVERSACION_PENDIENTE ||--o{ PREGUNTA : contiene
    
    CONFIGURACION_AUTORIZACION }o--|| SISTEMA_CONFIG : hereda_config
```

---

## 8. Relationship Details

### 8.1 Cardinality Summary

| Relationship | Type | Description |
|--------------|------|-------------|
| USUARIO → CUENTA | 1:N | User can have multiple accounts |
| USUARIO → TRANSACCION | 1:N | User can have many transactions |
| CUENTA → TRANSACCION | 1:N | Account can have many transactions |
| CATEGORIA → TRANSACCION | 1:N | Category can have many transactions |
| TRANSACCION → AUTORIZACION | 1:1 | Transaction may need authorization |
| TRANSACCION → ETIQUETA | N:M | Transaction can have multiple tags |
| USUARIO → CONVERSACION_PENDIENTE | 1:N | User can have pending conversations |
| CONVERSACION_PENDIENTE → PREGUNTA | 1:N | Conversation has many questions |

### 8.2 Cascade Rules

| Parent Table | Child Table | On Delete |
|--------------|-------------|-----------|
| USUARIO | CUENTA | CASCADE |
| USUARIO | TRANSACCION | CASCADE |
| USUARIO | CATEGORIA | CASCADE |
| USUARIO | CONVERSACION_PENDIENTE | CASCADE |
| CUENTA | TRANSACCION | SET NULL |
| CATEGORIA | TRANSACCION | SET NULL |
| TRANSACCION | AUTORIZACION | CASCADE |
| CONVERSACION_PENDIENTE | PREGUNTA | CASCADE |

---

## 9. Index Strategy

### 9.1 Primary Indexes

| Table | Index | Type | Columns |
|-------|-------|------|---------|
| USUARIO | pk_usuario | PRIMARY | id |
| CUENTA | pk_cuenta | PRIMARY | id |
| TRANSACCION | pk_transaccion | PRIMARY | id |
| CATEGORIA | pk_categoria | PRIMARY | id |

### 9.2 Secondary Indexes

| Table | Index | Type | Columns |
|-------|-------|------|---------|
| USUARIO | idx_telegram | UNIQUE | telegram_id |
| TRANSACCION | idx_fecha_usuario | COMPOSITE | fecha, usuario_id |
| TRANSACCION | idx_estado | INDEX | estado |
| CONVERSACION_PENDIENTE | idx_estado_usuario | COMPOSITE | estado, usuario_id |
| AUTORIZACION | idx_estado | INDEX | estado |

---

## 10. Visual Legend

```mermaid
flowchart TB
    subgraph Entities
        A["USUARIO"]
        B["CUENTA"]
        C["TRANSACCION"]
    end
    
    subgraph Relationships
        AB["1:N"]
    end
    
    A --> AB
    AB --> B
    B --> C
```

| Symbol | Meaning |
|--------|---------|
| PK | Primary Key |
| FK | Foreign Key |
| UK | Unique Key |
| 1:1 | One to One |
| 1:N | One to Many |
| N:M | Many to Many |

---

## Related Documentation

- [Database Schemas](./schemas.md) - Detailed table definitions
- [Routes](../flows/routes.md) - How data is used in processing
- [System Design](../architecture/system-design.md) - Architecture overview

---

*Last updated: 2026-03-31*
