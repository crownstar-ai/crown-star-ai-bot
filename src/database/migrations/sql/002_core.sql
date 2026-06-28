-- CrownStar Core Tables
-- Version: 2

-- Memory (messages stored permanently)
CREATE TABLE IF NOT EXISTS memory_messages (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    chat_id TEXT,
    role TEXT NOT NULL,                     -- 'user' or 'assistant'
    content TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    embedding BLOB,                         -- Vector embedding (optional)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_memory_chat (chat_id),
    INDEX idx_memory_project (project_id),
    INDEX idx_memory_created (created_at)
);

-- Chat sessions (group messages)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_chat_sessions_project (project_id)
);

-- License keys
CREATE TABLE IF NOT EXISTS licenses (
    id TEXT PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    tier TEXT NOT NULL,
    issued_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    metadata TEXT DEFAULT '{}',
    INDEX idx_licenses_key (key),
    INDEX idx_licenses_email (email)
);

-- Usage tracking
CREATE TABLE IF NOT EXISTS usage_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    chat_id TEXT,
    model TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    cost REAL DEFAULT 0.0,
    tier TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_usage_user (user_id),
    INDEX idx_usage_created (created_at),
    INDEX idx_usage_tier (tier)
);

-- Rate limiting (optional)
CREATE TABLE IF NOT EXISTS rate_limit_entries (
    key TEXT PRIMARY KEY,
    count INTEGER DEFAULT 0,
    reset_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
