#!/bin/sh
# 官方 entrypoint 可 source 此文件；子 shell 避免影响初始化流程。
(
    set -eu
    MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --default-character-set=utf8mb4 -uroot < /docker-entrypoint-initdb.d/agent_app.sql
)
