-- SQLite 链路追踪表结构初稿（面向实体链接与可追溯审计）
-- 设计原则：尽量保留原值→新值→依据的留痕，并保留候选置信度与证据文本。

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS mention (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,                -- 可选：一次批处理或请求的唯一 id
    doc_id TEXT,                 -- 文档/来源标识
    mention_text TEXT NOT NULL,
    start_idx INTEGER,
    end_idx INTEGER,
    mention_norm TEXT,          -- 归一化形式（如去空格/小写）
    context TEXT,               -- 上下文片段
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS candidate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mention_id INTEGER NOT NULL REFERENCES mention(id) ON DELETE CASCADE,
    candidate_entity_id TEXT,   -- 知识库实体 id（若存在）
    candidate_name TEXT,
    score REAL,                 -- 排序/检索分数
    metadata TEXT               -- JSON 文本，保存检索来源、字段等
);

CREATE TABLE IF NOT EXISTS link_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mention_id INTEGER NOT NULL REFERENCES mention(id) ON DELETE CASCADE,
    linked_entity_id TEXT,      -- 最终链接上的实体 id，NULL 表示 NIL
    linked_entity_name TEXT,
    is_nil INTEGER DEFAULT 0,
    score REAL,                 -- 最终决策置信度
    decision_reason TEXT,       -- 简要决策依据（可为 JSON）
    evidence TEXT,              -- 证据文本或候选片段
    model_version TEXT,         -- 若使用模型，记录模型/提示版本
    actor TEXT,                 -- 哪个模块/规则/模型做出的决定
    created_at TEXT DEFAULT (datetime('now'))
);

-- 审计/留痕（记录每次对数据的改动）
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mention_id INTEGER REFERENCES mention(id),
    link_result_id INTEGER REFERENCES link_result(id),
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    actor TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_mention_doc ON mention(doc_id);
CREATE INDEX IF NOT EXISTS idx_candidate_mention ON candidate(mention_id);
CREATE INDEX IF NOT EXISTS idx_link_mention ON link_result(mention_id);

-- 管道运行跟踪（记录每次 pipeline 执行的元数据，便于审计与回放）
CREATE TABLE IF NOT EXISTS pipeline_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,        -- 外部可传的 trace/run id
    task_name TEXT,                     -- 例如: entity_linking_batch
    status TEXT,                        -- running|success|failed
    start_ts TEXT DEFAULT (datetime('now')),
    end_ts TEXT,
    actor TEXT,                         -- 哪个服务/节点触发
    metadata TEXT                       -- JSON 文本，记录参数、环境、模型版本等
);

CREATE INDEX IF NOT EXISTS idx_pipeline_run_runid ON pipeline_run(run_id);

-- 模型/组件注册表（用于记录模型版本与元信息，便于结果可追溯）
CREATE TABLE IF NOT EXISTS model_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    provider TEXT,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    metadata TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_model_name_version ON model_registry(model_name, model_version);

