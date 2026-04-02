-- Chat schema for MyFinance 4.0
-- Supports multi-channel (telegram, web, api) chat history

-- Table: chat_topics
CREATE TABLE IF NOT EXISTS chat_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id UUID REFERENCES usuarios(id) ON DELETE CASCADE,
    canal VARCHAR(30) NOT NULL DEFAULT 'web',
    titulo VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activo BOOLEAN DEFAULT true
);

-- Table: chat_messages
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id UUID REFERENCES chat_topics(id) ON DELETE CASCADE,
    canal VARCHAR(30) NOT NULL DEFAULT 'web',
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    route VARCHAR(10),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chat_topics_usuario_canal ON chat_topics(usuario_id, canal, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_topic_canal ON chat_messages(topic_id, canal, created_at ASC);

-- Default topic for new chats (created on-demand)
-- Function to get or create default topic for user+channel
CREATE OR REPLACE FUNCTION get_or_create_default_topic(p_usuario_id UUID, p_canal VARCHAR)
RETURNS UUID AS $$
DECLARE
    v_topic_id UUID;
BEGIN
    -- Try to find existing default topic
    SELECT id INTO v_topic_id
    FROM chat_topics
    WHERE usuario_id = p_usuario_id 
      AND canal = p_canal 
      AND titulo = 'General'
      AND activo = true
    ORDER BY created_at DESC
    LIMIT 1;

    -- If not found, create new
    IF v_topic_id IS NULL THEN
        INSERT INTO chat_topics (usuario_id, canal, titulo)
        VALUES (p_usuario_id, p_canal, 'General')
        RETURNING id INTO v_topic_id;
    END IF;

    RETURN v_topic_id;
END;
$$ LANGUAGE plpgsql;

-- Function to create topic with auto-title
CREATE OR REPLACE FUNCTION create_chat_topic_with_title(
    p_usuario_id UUID, 
    p_canal VARCHAR,
    p_titulo VARCHAR
)
RETURNS UUID AS $$
DECLARE
    v_topic_id UUID;
BEGIN
    INSERT INTO chat_topics (usuario_id, canal, titulo)
    VALUES (p_usuario_id, p_canal, p_titulo)
    RETURNING id INTO v_topic_id;

    RETURN v_topic_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get recent messages (keeps last N)
CREATE OR REPLACE FUNCTION get_topic_messages(
    p_topic_id UUID,
    p_canal VARCHAR,
    p_limit INT DEFAULT 500
)
RETURNS TABLE (
    id UUID,
    topic_id UUID,
    canal VARCHAR,
    role VARCHAR,
    content TEXT,
    route VARCHAR,
    metadata JSONB,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cm.id, cm.topic_id, cm.canal, cm.role, 
        cm.content, cm.route, cm.metadata, cm.created_at
    FROM chat_messages cm
    WHERE cm.topic_id = p_topic_id 
      AND cm.canal = p_canal
    ORDER BY cm.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;