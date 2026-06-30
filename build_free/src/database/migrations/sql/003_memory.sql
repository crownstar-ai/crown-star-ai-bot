-- CrownStar Memory Extensions
-- Version: 3

-- Vector index table (for semantic search)
CREATE TABLE IF NOT EXISTS vector_index (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,               -- 'message', 'document', 'embedding'
    entity_id TEXT NOT NULL,
    embedding BLOB NOT NULL,
    metadata TEXT DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_vector_entity (entity_type, entity_id)
);

-- Knowledge base
CREATE TABLE IF NOT EXISTS knowledge_entries (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    title TEXT,
    content TEXT NOT NULL,
    source TEXT,                              -- URL, file path, etc.
    embedding BLOB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT DEFAULT '{}',
    INDEX idx_knowledge_project (project_id)
);

-- Conversation summaries (for memory context)
CREATE TABLE IF NOT EXISTS conversation_summaries (
    chat_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,
    FOREIGN KEY (chat_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);
