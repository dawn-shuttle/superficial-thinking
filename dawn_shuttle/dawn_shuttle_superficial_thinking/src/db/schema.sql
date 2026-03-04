-- 精准记忆表
CREATE TABLE IF NOT EXISTS precise_memories (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    token_count INTEGER,
    importance REAL,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_precise_timestamp ON precise_memories(timestamp);

-- 模糊记忆表
CREATE TABLE IF NOT EXISTS fuzzy_memories (
    id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    triples TEXT,
    keywords TEXT,
    weight REAL,
    importance REAL,
    timestamp TEXT,
    last_accessed TEXT,
    source_ids TEXT,
    access_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_fuzzy_weight ON fuzzy_memories(weight);
CREATE INDEX IF NOT EXISTS idx_fuzzy_timestamp ON fuzzy_memories(timestamp);

-- 记忆关联表
CREATE TABLE IF NOT EXISTS memory_edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    weight REAL,
    FOREIGN KEY (source_id) REFERENCES fuzzy_memories(id),
    FOREIGN KEY (target_id) REFERENCES fuzzy_memories(id)
);

CREATE INDEX IF NOT EXISTS idx_edge_source ON memory_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edge_target ON memory_edges(target_id);
