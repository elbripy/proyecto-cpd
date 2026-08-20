-- ddl-v3.sql
-- Archivo de Definición de Datos (DDL) Idempotente para el Proyecto Centralizado
-- Se ejecuta ÚNICAMENTE en la Casa Matriz (cpd-matriz-db), que centraliza la facturación
-- Cátedra: Procesamiento de Datos - UCOM 2026
-- Docente: Ing. David Britez

-- Crear la tabla única de ventas centralizada si no existe
CREATE TABLE IF NOT EXISTS ventas_locales (
    id SERIAL PRIMARY KEY,
    invoice_no VARCHAR(20) NOT NULL,    -- Soporta 'C' para cancelaciones
    stock_code VARCHAR(20) NOT NULL,    -- Soporta códigos alfanuméricos (ej. 85123A)
    description TEXT,                   -- Descripción del producto
    quantity INTEGER NOT NULL,          -- Cantidad vendida (negativa si es cancelación)
    invoice_date TIMESTAMP NOT NULL,    -- Fecha y hora de la transacción
    unit_price NUMERIC(10, 2) NOT NULL, -- Precio unitario
    customer_id VARCHAR(20),            -- ID del cliente (puede ser nulo)
    sucursal VARCHAR(100) NOT NULL,     -- Almacenará la sucursal que originó e insertó el dato
    insertado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Timestamp de auditoría de ingreso al CPD
);

-- Crear índice para acelerar reportes consolidados por sucursal
CREATE INDEX IF NOT EXISTS idx_ventas_locales_sucursal ON ventas_locales(sucursal);
