-- Migration: 002_production_schema.sql
-- Applied: Production schema for Customer Success FTE
-- =============================================================================

-- This migration creates the complete production schema.
-- Run with: psql -U postgres -d fte_db -f migrations/002_production_schema.sql

-- Note: Main schema is in production/database/schema.sql
-- This migration file tracks production schema changes.

-- Prerequisites:
-- 1. PostgreSQL 14+ with pgvector extension
-- 2. Database created: CREATE DATABASE fte_db;
-- 3. Base schema applied from production/database/schema.sql

-- Changes in this migration:
-- None (initial production migration)

-- To apply:
-- psql -d fte_db -f migrations/002_production_schema.sql

-- Verification:
-- SELECT * FROM schema_version ORDER BY version DESC LIMIT 1;
