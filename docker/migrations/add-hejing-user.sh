#!/bin/sh
# 仅用于已有 didilili 账号的数据卷；新环境由 MYSQL_USER 创建 HeJing。
# 复制认证信息以保留原密码，不输出密码或认证哈希，不删除旧账号。
set -eu
: "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD is required}"
MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket -uroot <<'SQL'
SET @source_plugin = (SELECT plugin FROM mysql.user WHERE User = 'didilili' AND Host = '%');
SET @source_auth = (SELECT authentication_string FROM mysql.user WHERE User = 'didilili' AND Host = '%');
SET @create_user = CONCAT(
    'CREATE USER IF NOT EXISTS ''HeJing''@''%'' IDENTIFIED WITH ',
    QUOTE(@source_plugin), ' AS ', QUOTE(@source_auth)
);
PREPARE create_user_stmt FROM @create_user;
EXECUTE create_user_stmt;
DEALLOCATE PREPARE create_user_stmt;
GRANT SELECT ON dw.* TO 'HeJing'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON meta.* TO 'HeJing'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON agent_app.* TO 'HeJing'@'%';
SELECT 'HeJing account ready; existing user retained.' AS result;
SQL
