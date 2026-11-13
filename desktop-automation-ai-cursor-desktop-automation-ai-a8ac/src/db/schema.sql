PRAGMA foreign_keys = ON;

-- Matches project ERD (Phase 2 SDS)
CREATE TABLE IF NOT EXISTS User (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL DEFAULT '',
    password TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS User_Conf (
    conf_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conf_key TEXT NOT NULL,
    conf_value TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, conf_key)
);

CREATE TABLE IF NOT EXISTS Workflow (
    workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    trigger_type TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_active INTEGER NOT NULL DEFAULT 1,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS AutomationRule (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition TEXT NOT NULL DEFAULT '{}',
    action TEXT NOT NULL DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 100,
    rule_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    workflow_id INTEGER NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES Workflow(workflow_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Task (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_app TEXT DEFAULT '',
    target_element TEXT DEFAULT '',
    input_value TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    workflow_id INTEGER NOT NULL,
    -- Kept for executable automation steps (compatible with engine)
    step_order INTEGER NOT NULL DEFAULT 1,
    intent TEXT NOT NULL DEFAULT 'wait',
    params_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (workflow_id) REFERENCES Workflow(workflow_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS NLP_Command (
    command_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entities_json TEXT NOT NULL DEFAULT '{}',
    raw_text TEXT NOT NULL,
    parsed_intent TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    executed_at TEXT NOT NULL DEFAULT (datetime('now')),
    user_id INTEGER,
    task_id INTEGER,
    source TEXT NOT NULL DEFAULT 'text',
    FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE SET NULL,
    FOREIGN KEY (task_id) REFERENCES Task(task_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Execution_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    error_message TEXT DEFAULT '',
    status TEXT NOT NULL,
    action_id TEXT DEFAULT '',
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    user_id INTEGER,
    command_id INTEGER,
    details_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE SET NULL,
    FOREIGN KEY (command_id) REFERENCES NLP_Command(command_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Screen_capture (
    capture_id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL DEFAULT (datetime('now')),
    file_path TEXT NOT NULL,
    width INTEGER DEFAULT 0,
    height INTEGER DEFAULT 0,
    element_found TEXT DEFAULT '',
    log_id INTEGER,
    FOREIGN KEY (log_id) REFERENCES Execution_log(log_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_task_workflow ON Task(workflow_id, step_order);
CREATE INDEX IF NOT EXISTS idx_exec_started ON Execution_log(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_nlp_executed ON NLP_Command(executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_conf ON User_Conf(user_id, conf_key);
