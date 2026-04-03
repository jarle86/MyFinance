-- Migration: Add alias support to cuentas and categorias tables
-- Run this on existing databases to add alias columns

-- Add alias column to cuentas table
ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS alias TEXT[] DEFAULT '{}';

-- Add alias column to categorias table
ALTER TABLE categorias ADD COLUMN IF NOT EXISTS alias TEXT[] DEFAULT '{}';

-- Create GIN indexes for alias arrays (for performance on containment queries)
CREATE INDEX IF NOT EXISTS idx_cuentas_alias ON cuentas USING GIN(alias);
CREATE INDEX IF NOT EXISTS idx_categorias_alias ON categorias USING GIN(alias);

-- Update comment
COMMENT ON COLUMN cuentas.alias IS 'Array of alternative names/synonyms for the account';
COMMENT ON COLUMN categorias.alias IS 'Array of alternative names/synonyms for the category';