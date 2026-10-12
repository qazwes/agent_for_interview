-- 新安装自动执行；已有数据卷执行本文件即可升级，不删除 DW / Meta。
SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS agent_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_app.* TO 'didilili'@'%';
USE agent_app;
CREATE TABLE IF NOT EXISTS chat_session (
  id VARCHAR(36) PRIMARY KEY, title VARCHAR(100) NOT NULL, pinned BOOLEAN NOT NULL,
  created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, INDEX ix_session_updated(updated_at)
);
CREATE TABLE IF NOT EXISTS chat_message (
  id VARCHAR(36) PRIMARY KEY, session_id VARCHAR(36) NOT NULL, role VARCHAR(16) NOT NULL,
  content TEXT NOT NULL, status VARCHAR(16) NOT NULL, reply_to_id VARCHAR(36),
  source_message_id VARCHAR(36), payload JSON, created_at DATETIME NOT NULL,
  INDEX ix_message_session(session_id), INDEX ix_message_created(created_at),
  FOREIGN KEY (session_id) REFERENCES chat_session(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS question_favorite (
  id VARCHAR(36) PRIMARY KEY, question TEXT NOT NULL, question_hash VARCHAR(64) NOT NULL UNIQUE,
  created_at DATETIME NOT NULL
);
CREATE TABLE IF NOT EXISTS answer_feedback (
  id VARCHAR(36) PRIMARY KEY, message_id VARCHAR(36), question TEXT NOT NULL, answer JSON NOT NULL,
  status VARCHAR(16) NOT NULL, remark TEXT NOT NULL, created_at DATETIME NOT NULL,
  INDEX ix_feedback_status(status), INDEX ix_feedback_created(created_at),
  FOREIGN KEY (message_id) REFERENCES chat_message(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS model_config (
  id VARCHAR(36) PRIMARY KEY, name VARCHAR(100) NOT NULL, base_url VARCHAR(500) NOT NULL,
  model_name VARCHAR(200) NOT NULL, api_key TEXT NOT NULL, created_at DATETIME NOT NULL
);
CREATE TABLE IF NOT EXISTS app_setting (`key` VARCHAR(64) PRIMARY KEY, value TEXT NOT NULL);
