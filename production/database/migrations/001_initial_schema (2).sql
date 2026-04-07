-- Migration: 001_initial_schema.sql
-- Applied: Initial database setup for Customer Success FTE
-- =============================================================================

-- This migration creates the complete schema for the Customer Success FTE.
-- Run with: psql -U postgres -d fte_db -f migrations/001_initial_schema.sql

-- Note: This is the same as schema.sql, kept here for migration tracking.
-- For subsequent changes, create new migration files (002_*.sql, 003_*.sql, etc.)

-- Prerequisites:
-- 1. PostgreSQL 14+ (for better vector support)
-- 2. pgvector extension installed
-- 3. Database created: CREATE DATABASE fte_db;

-- To apply this migration:
-- 1. Create database: createdb fte_db
-- 2. Enable extensions: psql -d fte_db -c "CREATE EXTENSION vector;"
-- 3. Run migration: psql -d fte_db -f schema.sql

-- Verification queries:
-- \dt                          -- List all tables
-- \dv                          -- List all views
-- \df                          -- List all functions
-- SELECT * FROM schema_version; -- Check schema version
