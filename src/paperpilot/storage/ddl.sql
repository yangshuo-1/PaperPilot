-- paper_valt SQLite schema v1.
-- Migration strategy: apply numbered, idempotent migrations in stores/db.py;
-- record the resulting version in meta; never rewrite or delete legacy data
-- without an explicit backup and rollback step.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', '1');

CREATE TABLE IF NOT EXISTS folders (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    parent_id TEXT REFERENCES folders(id) ON DELETE CASCADE,
    "order" INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    short_title TEXT,
    authors TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(authors)),
    year INTEGER,
    venue TEXT,
    arxiv_id TEXT,
    doi TEXT,
    source_url TEXT,
    repo_url TEXT,
    local_pdf_path TEXT,
    understanding_status TEXT NOT NULL DEFAULT 'not_started'
        CHECK (understanding_status IN (
            'not_started', 'indexed', 'readpack_ready', 'analysis_drafted',
            'code_mapped', 'needs_review'
        )),
    updated_at TEXT,
    starred INTEGER NOT NULL DEFAULT 0 CHECK (starred IN (0, 1)),
    read_status TEXT NOT NULL DEFAULT 'unread'
        CHECK (read_status IN ('unread', 'reading', 'read')),
    folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL,
    reading_progress REAL CHECK (reading_progress IS NULL OR
        (reading_progress >= 0 AND reading_progress <= 100)),
    current_page INTEGER CHECK (current_page IS NULL OR current_page >= 1),
    total_pages INTEGER CHECK (total_pages IS NULL OR total_pages >= 1),
    document_version TEXT,
    last_read_at TEXT,
    abstract TEXT,
    primary_category TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    tag TEXT NOT NULL CHECK (length(trim(tag)) > 0),
    created_at TEXT,
    PRIMARY KEY (paper_id, tag)
);

CREATE TABLE IF NOT EXISTS annotations (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('anchor', 'highlight', 'note')),
    anchor_id TEXT,
    source_type TEXT NOT NULL DEFAULT 'pdf_text',
    document_version TEXT,
    page INTEGER CHECK (page IS NULL OR page >= 1),
    paragraph_id TEXT,
    quote TEXT,
    start_offset INTEGER CHECK (start_offset IS NULL OR start_offset >= 0),
    end_offset INTEGER CHECK (end_offset IS NULL OR end_offset >= 0),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'stale')),
    needs_relocation INTEGER NOT NULL DEFAULT 0 CHECK (needs_relocation IN (0, 1)),
    color TEXT NOT NULL DEFAULT 'yellow',
    content TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS reading_list (
    paper_id TEXT PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
    added_at TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0 CHECK (priority >= 0 AND priority <= 100)
);

-- The trigram tokenizer is required for usable Chinese substring search.
CREATE VIRTUAL TABLE IF NOT EXISTS paper_fts USING fts5(
    paper_id UNINDEXED,
    title,
    abstract,
    authors,
    content,
    tokenize='trigram'
);

-- Page text is persisted at import/migration time so reader search can return
-- deterministic PDF page anchors without parsing the source PDF per request.
CREATE TABLE IF NOT EXISTS paper_pages (
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    page INTEGER NOT NULL CHECK (page >= 1),
    text TEXT NOT NULL,
    document_version TEXT,
    PRIMARY KEY (paper_id, page)
);

CREATE INDEX IF NOT EXISTS idx_papers_folder_id ON papers(folder_id);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
CREATE INDEX IF NOT EXISTS idx_annotations_paper_id ON annotations(paper_id);
CREATE INDEX IF NOT EXISTS idx_annotations_anchor_id ON annotations(anchor_id);
CREATE INDEX IF NOT EXISTS idx_reading_list_priority ON reading_list(priority, added_at);
CREATE INDEX IF NOT EXISTS idx_paper_pages_version ON paper_pages(paper_id, document_version);
