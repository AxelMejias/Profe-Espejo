# ============================================================
# seed.ps1 — Carga los datos semilla en foodstore_db
#
# COMO USAR (desde la raiz del proyecto):
#   .\app\db\seed.ps1
#
# O desde la carpeta app/db:
#   .\seed.ps1
#
# REQUISITOS PREVIOS:
#   1. Tener PostgreSQL instalado
#   2. Haber creado la DB y corrido las migraciones:
#        alembic upgrade head
# ============================================================

$DB_NAME = "foodstore_db"
$DB_USER = "postgres"

# Buscar psql en las versiones instaladas de PostgreSQL
$psqlPath = $null
$pgVersions = @("18", "17", "16", "15", "14", "13")
foreach ($v in $pgVersions) {
    $candidate = "C:\Program Files\PostgreSQL\$v\bin\psql.exe"
    if (Test-Path $candidate) {
        $psqlPath = $candidate
        break
    }
}

if (-not $psqlPath) {
    # Intentar desde PATH
    $psqlPath = (Get-Command psql -ErrorAction SilentlyContinue).Source
}

if (-not $psqlPath) {
    Write-Host "ERROR: No se encontro psql. Asegurate de tener PostgreSQL instalado." -ForegroundColor Red
    exit 1
}

Write-Host "Usando: $psqlPath" -ForegroundColor Cyan

# Pedir password
$password = Read-Host "Contrasena de PostgreSQL (usuario '$DB_USER')"

# Ubicar el archivo SQL relativo a donde esta este script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sqlFile = Join-Path $scriptDir "seed_data.sql"

if (-not (Test-Path $sqlFile)) {
    Write-Host "ERROR: No se encontro seed_data.sql en $scriptDir" -ForegroundColor Red
    exit 1
}

Write-Host "Cargando datos en '$DB_NAME'..." -ForegroundColor Yellow

$env:PGPASSWORD = $password
& $psqlPath -U $DB_USER -d $DB_NAME -f $sqlFile
$exitCode = $LASTEXITCODE
$env:PGPASSWORD = ""

if ($exitCode -eq 0) {
    Write-Host "Datos cargados correctamente." -ForegroundColor Green
} else {
    Write-Host "Ocurrio un error. Revisa que la DB exista y las migraciones esten aplicadas (alembic upgrade head)." -ForegroundColor Red
    exit $exitCode
}
