CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(10) NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_users_role CHECK (role IN ('user', 'admin'))
);

CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    author_id INTEGER NOT NULL REFERENCES users (id) ON DELETE RESTRICT,
    status VARCHAR(10) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_documents_status CHECK (status IN ('pending', 'indexed', 'failed'))
);

CREATE INDEX ix_documents_author_id ON documents (author_id);
CREATE INDEX ix_documents_created_at ON documents (created_at);
CREATE INDEX ix_documents_status ON documents (status);

CREATE TABLE document_tags (
    document_id INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    PRIMARY KEY (document_id, tag_id)
);

CREATE INDEX ix_document_tags_tag_id ON document_tags (tag_id);

CREATE TABLE bookmarks (
    user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, document_id)
);

CREATE INDEX ix_bookmarks_document_id ON bookmarks (document_id);
CREATE INDEX ix_bookmarks_created_at ON bookmarks (created_at);

CREATE TABLE search_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users (id) ON DELETE SET NULL,
    query VARCHAR(500) NOT NULL,
    results_count INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_search_events_created_at ON search_events (created_at);
CREATE INDEX ix_search_events_user_id_created_at ON search_events (user_id, created_at);
CREATE INDEX ix_search_events_query ON search_events (query);
