#!/usr/bin/env python3
"""
Database Initialization Script

Creates all tables, indexes, and seed data for the CRM system.
Works with both local PostgreSQL and Docker containers.

Usage:
    python init_db.py                          # Uses .env variables
    python init_db.py --host localhost --user postgres
    python init_db.py --drop-first             # Drop all tables first
"""

import asyncio
import argparse
import sys
from pathlib import Path

import asyncpg


# =============================================================================
# CONFIGURATION
# =============================================================================

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "postgres",
    "password": "postgres",
    "database": "crm_fte",
}


# =============================================================================
# SCHEMA
# =============================================================================

SCHEMA_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Customer identifiers (for cross-channel matching)
CREATE TABLE IF NOT EXISTS customer_identifiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    identifier_type VARCHAR(50) NOT NULL,
    identifier_value VARCHAR(255) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(identifier_type, identifier_value)
);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    initial_channel VARCHAR(50) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'active',
    sentiment_score DECIMAL(3,2),
    resolution_type VARCHAR(50),
    escalated_to VARCHAR(255),
    metadata JSONB DEFAULT '{}'
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    channel VARCHAR(50) NOT NULL,
    direction VARCHAR(20) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tokens_used INTEGER,
    latency_ms INTEGER,
    tool_calls JSONB DEFAULT '[]',
    channel_message_id VARCHAR(255),
    delivery_status VARCHAR(50) DEFAULT 'pending'
);

-- Tickets table
CREATE TABLE IF NOT EXISTS tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    customer_id UUID REFERENCES customers(id),
    source_channel VARCHAR(50) NOT NULL,
    category VARCHAR(100),
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'open',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT
);

-- Knowledge base entries
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100),
    embedding VECTOR(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Channel configurations
CREATE TABLE IF NOT EXISTS channel_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(50) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    config JSONB NOT NULL,
    response_template TEXT,
    max_response_length INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agent performance metrics
CREATE TABLE IF NOT EXISTS agent_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,4) NOT NULL,
    channel VARCHAR(50),
    dimensions JSONB DEFAULT '{}',
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);
CREATE INDEX IF NOT EXISTS idx_customer_identifiers_value ON customer_identifiers(identifier_value);
CREATE INDEX IF NOT EXISTS idx_customer_identifiers_customer ON customer_identifiers(customer_id);
CREATE INDEX IF NOT EXISTS idx_conversations_customer ON conversations(customer_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON conversations(status);
CREATE INDEX IF NOT EXISTS idx_conversations_channel ON conversations(initial_channel);
CREATE INDEX IF NOT EXISTS idx_conversations_started ON conversations(started_at);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_channel ON tickets(source_channel);
CREATE INDEX IF NOT EXISTS idx_tickets_customer ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_created ON tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_base(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding ON knowledge_base USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_channel_configs_enabled ON channel_configs(enabled);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_name ON agent_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_recorded ON agent_metrics(recorded_at);
CREATE INDEX IF NOT EXISTS idx_agent_metrics_channel ON agent_metrics(channel);

-- Seed channel configs
INSERT INTO channel_configs (channel, enabled, config, max_response_length) VALUES
    ('email', TRUE, '{"smtp_host": "", "api_key": ""}', 2000)
    ON CONFLICT (channel) DO NOTHING;

INSERT INTO channel_configs (channel, enabled, config, max_response_length) VALUES
    ('whatsapp', TRUE, '{"twilio_sid": "", "twilio_token": ""}', 160)
    ON CONFLICT (channel) DO NOTHING;

INSERT INTO channel_configs (channel, enabled, config, max_response_length) VALUES
    ('web_form', TRUE, '{"endpoint": ""}', 1000)
    ON CONFLICT (channel) DO NOTHING;
"""


# =============================================================================
# DROP ALL TABLES
# =============================================================================

DROP_ALL_SQL = """
DROP TABLE IF EXISTS agent_metrics CASCADE;
DROP TABLE IF EXISTS channel_configs CASCADE;
DROP TABLE IF EXISTS knowledge_base CASCADE;
DROP TABLE IF EXISTS tickets CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS conversations CASCADE;
DROP TABLE IF EXISTS customer_identifiers CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
"""


# =============================================================================
# INITIALIZATION
# =============================================================================


async def init_database(
    host: str = "localhost",
    port: int = 5432,
    user: str = "postgres",
    password: str = "postgres",
    database: str = "crm_fte",
    drop_first: bool = False,
):
    """Initialize the database schema."""
    
    print(f"Connecting to PostgreSQL at {host}:{port}/{database} as {user}...")
    
    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
        print("✓ Connected successfully")
        
        # Drop tables if requested
        if drop_first:
            print("Dropping all existing tables...")
            await conn.execute(DROP_ALL_SQL)
            print("✓ Tables dropped")
        
        # Check if tables already exist
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """)
        existing_tables = [t["tablename"] for t in tables]
        
        core_tables = ["customers", "tickets", "conversations"]
        has_core = any(t in existing_tables for t in core_tables)
        
        if has_core and not drop_first:
            print("⚠ Core tables already exist. Use --drop-first to recreate.")
            print(f"   Existing tables: {', '.join(existing_tables)}")
        else:
            print("Creating schema...")
            await conn.execute(SCHEMA_SQL)
            print("✓ Schema created")
            
            # Verify
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            table_names = [t["tablename"] for t in tables]
            print(f"✓ {len(table_names)} tables created: {', '.join(table_names)}")
        
        # Check pgvector
        extensions = await conn.fetch("""
            SELECT extname FROM pg_extension WHERE extname = 'vector'
        """)
        if extensions:
            print("✓ pgvector extension enabled")
        else:
            print("✗ pgvector extension not found")
        
        await conn.close()
        print("\n✅ Database initialization complete!")
        return True
        
    except asyncpg.InvalidCatalogNameError:
        print(f"\n✗ Database '{database}' does not exist.")
        print("Create it first: CREATE DATABASE crm_fte;")
        return False
    except asyncpg.InvalidPasswordError:
        print(f"\n✗ Authentication failed for user '{user}'")
        print("Check your password or PostgreSQL pg_hba.conf")
        return False
    except ConnectionRefusedError:
        print(f"\n✗ Cannot connect to PostgreSQL at {host}:{port}")
        print("Is PostgreSQL running? Check: docker ps")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Initialize Customer Success FTE Database")
    parser.add_argument("--host", default=DB_CONFIG["host"], help="PostgreSQL host")
    parser.add_argument("--port", type=int, default=DB_CONFIG["port"], help="PostgreSQL port")
    parser.add_argument("--user", default=DB_CONFIG["user"], help="PostgreSQL user")
    parser.add_argument("--password", default=DB_CONFIG["password"], help="PostgreSQL password")
    parser.add_argument("--database", default=DB_CONFIG["database"], help="Database name")
    parser.add_argument("--drop-first", action="store_true", help="Drop all tables first")
    
    args = parser.parse_args()
    
    success = asyncio.run(init_database(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database,
        drop_first=args.drop_first,
    ))
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
