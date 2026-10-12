# 在 my-agent 目录执行：powershell -File docker/upgrade-app.ps1
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
Push-Location $projectDir
try {
    # 密码只在容器内从环境变量读取，不输出，不重新初始化已有数据卷。
    docker compose --env-file .env -f docker/docker-compose.yaml exec -T mysql sh /docker-entrypoint-initdb.d/zz-agent-app.sh
    if ($LASTEXITCODE -ne 0) { throw 'Application database migration failed' }
} finally { Pop-Location }
