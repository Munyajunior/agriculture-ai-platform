param(
    [switch]$ResetVolumes,
    [switch]$Services,
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$ComposeFile = Join-Path $Root "infrastructure\docker\docker-compose.yaml"
$EnvFile = Join-Path $Root ".env"
$Compose = @("compose", "--env-file", $EnvFile, "-f", $ComposeFile)

function Get-DotEnvValue {
    param(
        [string]$Name,
        [string]$Default
    )

    if (Test-Path $EnvFile) {
        foreach ($Line in Get-Content $EnvFile) {
            if ($Line -match "^\s*$Name\s*=\s*(.*)\s*$") {
                return $Matches[1].Trim().Trim('"').Trim("'")
            }
        }
    }

    return $Default
}

function Invoke-DockerCompose {
    param([string[]]$Arguments)
    & docker @Compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed: $($Arguments -join ' ')"
    }
}

function Wait-ForContainerHealth {
    param(
        [string]$Name,
        [int]$TimeoutSeconds = 90
    )

    $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $Deadline) {
        $State = docker inspect --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" $Name 2>$null
        if ($LASTEXITCODE -eq 0 -and ($State -eq "healthy" -or $State -eq "running")) {
            Write-Host "$Name is $State"
            return
        }
        Start-Sleep -Seconds 2
    }

    throw "$Name did not become healthy within $TimeoutSeconds seconds"
}

function Test-ContainerExists {
    param([string]$Name)
    $Names = docker ps -a --format '{{.Names}}'
    return $Names -contains $Name
}

Set-Location $Root

if ($ResetVolumes) {
    Write-Host "Removing existing compose containers and volumes..."
    Invoke-DockerCompose @("down", "--remove-orphans", "-v")
}

$InfraServices = @(
    @{ Service = "postgres"; Container = "agri_postgres" },
    @{ Service = "redis"; Container = "agri_redis" },
    @{ Service = "minio"; Container = "agri_minio" }
)

$MissingServices = @()
foreach ($Item in $InfraServices) {
    if (Test-ContainerExists $Item.Container) {
        Write-Host "Starting existing container $($Item.Container)..."
        docker start $Item.Container | Out-Host
    } else {
        $MissingServices += $Item.Service
    }
}

if ($MissingServices.Count -gt 0) {
    Write-Host "Creating missing infrastructure services: $($MissingServices -join ', ')"
    Invoke-DockerCompose (@("up", "-d") + $MissingServices)
}

Wait-ForContainerHealth "agri_postgres"
Wait-ForContainerHealth "agri_redis"
Wait-ForContainerHealth "agri_minio"

Write-Host "Ensuring PostgreSQL password matches .env..."
$DbPassword = Get-DotEnvValue "DB_PASSWORD" "secure_password"
docker exec agri_postgres psql -U agri_user -d agriculture_ai -c "ALTER USER agri_user WITH PASSWORD '$DbPassword';" | Out-Host

Write-Host "Creating MinIO buckets..."
$MinioUser = Get-DotEnvValue "MINIO_ROOT_USER" "minioadmin"
$MinioPassword = Get-DotEnvValue "MINIO_ROOT_PASSWORD" "minioadmin123"
docker exec agri_minio mc alias set local http://127.0.0.1:9000 $MinioUser $MinioPassword | Out-Host
foreach ($Bucket in @("agriculture-images", "ai-models", "models")) {
    docker exec agri_minio mc mb --ignore-existing "local/$Bucket" | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create MinIO bucket $Bucket"
    }
}

if ($Services) {
    $ServiceNames = @(
        "api-gateway",
        "auth-service",
        "ai-service",
        "analytics-service",
        "media-service",
        "model-registry",
        "sync-service"
    )

    if ($Build) {
        Write-Host "Building and starting backend services..."
        Invoke-DockerCompose (@("up", "-d", "--build") + $ServiceNames)
    } else {
        Write-Host "Starting backend services..."
        Invoke-DockerCompose (@("up", "-d") + $ServiceNames)
    }
}

Write-Host "Infrastructure setup complete."
