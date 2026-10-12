#!/bin/bash
# 首次初始化时执行；entrypoint 可能 source 此文件，因此使用子 shell。
(
    set -eu
    : "${DW_QUERY_PASSWORD:?DW_QUERY_PASSWORD is required}"
    # 限定字符集，避免密码中的引号改变 SQL 语义。
    case "$DW_QUERY_PASSWORD" in
        *[!a-zA-Z0-9_-]*)
            echo 'DW_QUERY_PASSWORD may only contain letters, digits, _ and -' >&2
            exit 1
            ;;
    esac
    MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket -uroot <<SQL
CREATE USER IF NOT EXISTS 'dw_reader'@'%' IDENTIFIED BY '${DW_QUERY_PASSWORD}';
GRANT SELECT ON dw.* TO 'dw_reader'@'%';
SQL
)
