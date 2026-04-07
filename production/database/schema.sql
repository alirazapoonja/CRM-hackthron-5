-- =============================================================================
-- CUSTOMER SUCCESS FTE - CRM/TICKET MANAGEMENT SYSTEM
-- =============================================================================
-- This PostgreSQL schema serves as your complete CRM system for tracking:
-- - Customers (unified across all channels: Email, WhatsApp, Web Form)
-- - Conversations and message history with channel metadata
-- - Support tickets and their lifecycle
-- - Knowledge base for AI responses (with pgvector for semantic search)
-- - Channel configurations for multi-channel support
-- - Performance metrics and reporting
--
-- ARCHITECTURE NOTES:
-- - This is a custom-built CRM system using PostgreSQL
-- - No external CRM (Salesforce, HubSpot) required for this hackathon
-- - Supports multi-channel customer identification and conversation continuity
-- - Uses pgvector extension for semantic search in knowledge base
-- - All tables use UUID primary keys for distributed system compatibility
-- =============================================================================

-- Enable pgvector extension for semantic search capabilities
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- CORE TABLES
-- =============================================================================

-- Customers table (unified across channels) - YOUR CUSTOMER DATABASE
-- Stores unified customer profiles that aggregate identity across all channels
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'  -- Additional customer attributes, preferences, tags
);

-- Customer identifiers (for cross-channel matching)
-- Enables matching customers across different channels using various identifiers
CREATE TABLE customer_identifiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    identifier_type VARCHAR(50) NOT NULL,  -- 'email', 'phone', 'whatsapp'
    identifier_value VARCHAR(255) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(identifier_type, identifier_value)
);

-- Conversations table
-- Tracks conversation sessions that may span multiple messages and channels
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    initial_channel VARCHAR(50) NOT NULL,  -- 'email', 'whatsapp', 'web_form'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'active',  -- 'active', 'closed', 'escalated'
    sentiment_score DECIMAL(3,2),  -- Overall conversation sentiment (-1.00 to 1.00)
    resolution_type VARCHAR(50),  -- 'resolved', 'escalated', 'abandoned'
    escalated_to VARCHAR(255),  -- Email/name of human agent if escalated
    metadata JSONB DEFAULT '{}'  -- Conversation-level metadata
);

-- Messages table (with channel tracking)
-- Individual messages within conversations, tracking channel and delivery status
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    channel VARCHAR(50) NOT NULL,  -- 'email', 'whatsapp', 'web_form'
    direction VARCHAR(20) NOT NULL,  -- 'inbound', 'outbound'
    role VARCHAR(20) NOT NULL,  -- 'customer', 'agent', 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tokens_used INTEGER,  -- Token count for LLM cost tracking
    latency_ms INTEGER,  -- Response latency for performance monitoring
    tool_calls JSONB DEFAULT '[]',  -- Tool calls made during message generation
    channel_message_id VARCHAR(255),  -- External ID (Gmail message ID, Twilio SID)
    delivery_status VARCHAR(50) DEFAULT 'pending'  -- 'pending', 'sent', 'delivered', 'failed'
);

-- Tickets table
-- Formal support tickets with lifecycle tracking
CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    customer_id UUID REFERENCES customers(id),
    source_channel VARCHAR(50) NOT NULL,  -- Channel where ticket originated
    category VARCHAR(100),  -- 'technical', 'billing', 'feature_request', etc.
    priority VARCHAR(20) DEFAULT 'medium',  -- 'low', 'medium', 'high', 'critical'
    status VARCHAR(50) DEFAULT 'open',  -- 'open', 'in_progress', 'resolved', 'closed'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT
);

-- Knowledge base entries
-- Product documentation and FAQ entries with vector embeddings for semantic search
CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100),  -- For filtering and organization
    embedding VECTOR(1536),  -- For semantic search using pgvector
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Channel configurations
-- Stores configuration for each communication channel
CREATE TABLE channel_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(50) UNIQUE NOT NULL,  -- 'email', 'whatsapp', 'web_form'
    enabled BOOLEAN DEFAULT TRUE,
    config JSONB NOT NULL,  -- API keys, webhook URLs, credentials
    response_template TEXT,  -- Template for channel-specific responses
    max_response_length INTEGER,  -- Character limit for responses
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agent performance metrics
-- Tracks agent performance for monitoring and reporting
CREATE TABLE agent_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,  -- 'response_time', 'resolution_rate', etc.
    metric_value DECIMAL(10,4) NOT NULL,
    channel VARCHAR(50),  -- Optional: channel-specific metrics
    dimensions JSONB DEFAULT '{}',  -- Additional metric dimensions (date_range, etc.)
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================

-- Customer indexes
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customer_identifiers_value ON customer_identifiers(identifier_value);
CREATE INDEX idx_customer_identifiers_customer ON customer_identifiers(customer_id);

-- Conversation indexes
CREATE INDEX idx_conversations_customer ON conversations(customer_id);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_conversations_channel ON conversations(initial_channel);
CREATE INDEX idx_conversations_started ON conversations(started_at);

-- Message indexes
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_channel ON messages(channel);
CREATE INDEX idx_messages_created ON messages(created_at);
CREATE INDEX idx_messages_role ON messages(role);

-- Ticket indexes
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_channel ON tickets(source_channel);
CREATE INDEX idx_tickets_customer ON tickets(customer_id);
CREATE INDEX idx_tickets_created ON tickets(created_at);

-- Knowledge base indexes
CREATE INDEX idx_knowledge_category ON knowledge_base(category);
CREATE INDEX idx_knowledge_embedding ON knowledge_base USING ivfflat (embedding vector_cosine_ops);

-- Channel config index
CREATE INDEX idx_channel_configs_enabled ON channel_configs(enabled);

-- Metrics indexes
CREATE INDEX idx_agent_metrics_name ON agent_metrics(metric_name);
CREATE INDEX idx_agent_metrics_recorded ON agent_metrics(recorded_at);
CREATE INDEX idx_agent_metrics_channel ON agent_metrics(channel);

-- =============================================================================
-- INITIAL DATA SEEDS
-- =============================================================================

-- Default channel configurations (to be updated with actual credentials)
INSERT INTO channel_configs (channel, enabled, config, max_response_length) VALUES
    ('email', TRUE, '{"smtp_host": "", "api_key": ""}', 2000),
    ('whatsapp', TRUE, '{"twilio_sid": "", "twilio_token": ""}', 160),
    ('web_form', TRUE, '{"endpoint": ""}', 1000)
ON CONFLICT (channel) DO NOTHING;
