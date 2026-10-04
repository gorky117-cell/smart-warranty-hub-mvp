# Back up the production Postgres (Railway) to C:\Users\lenovo\swh_backups\swh_prod_<date>.dump
#
#   powershell -ExecutionPolicy Bypass -File scripts\backup_prod_db.ps1
#
# - Asks for Railway's DATABASE_PUBLIC_URL with a hidden prompt (Read-Host -AsSecureString).
# - The URL and password are never printed, never written to a file and never put on the pg_dump
#   command line: the password is handed to pg_dump through PGPASSWORD for this process only and
#   removed afterwards.
# - Verifies the dump with pg_restore --list and prints OK or FAILED.
# Backups are git-ignored (swh_backups/, *.dump). Never commit them.

$ErrorActionPreference = "Stop"
$pgBin = "C:\Program Files\PostgreSQL\18\bin"
$pgDump = Join-Path $pgBin "pg_dump.exe"
$pgRestore = Join-Path $pgBin "pg_restore.exe"
$backupDir = "C:\Users\lenovo\swh_backups"

function Fail([string]$message) {
    Write-Host ""
    Write-Host "FAILED: $message" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $pgDump) -or -not (Test-Path $pgRestore)) {
    Fail "pg_dump.exe / pg_restore.exe not found in $pgBin"
}

$secure = Read-Host "Paste Railway DATABASE_PUBLIC_URL (hidden)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $url = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

try {
    $url = $url.Trim().Trim('"').Trim("'")
    if (-not ($url -match '^postgres(ql)?://')) { Fail "that does not look like a postgresql:// URL" }
    try { $uri = [Uri]$url } catch { Fail "could not read the URL" }
    $userInfo = $uri.UserInfo
    $sep = $userInfo.IndexOf(":")
    if ($sep -lt 1) { Fail "the URL has no user:password part" }
    $dbUser = [Uri]::UnescapeDataString($userInfo.Substring(0, $sep))
    $env:PGPASSWORD = [Uri]::UnescapeDataString($userInfo.Substring($sep + 1))
    $dbHost = $uri.Host
    $dbPort = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }
    $dbName = $uri.AbsolutePath.TrimStart("/")
    if (-not $dbName) { Fail "the URL has no database name" }
    $url = $null
    $userInfo = $null

    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $file = Join-Path $backupDir ("swh_prod_{0}.dump" -f (Get-Date -Format "yyyy-MM-dd_HHmm"))

    Write-Host "Dumping database '$dbName' on $dbHost`:$dbPort to $file ..."
    & $pgDump --host=$dbHost --port=$dbPort --username=$dbUser --dbname=$dbName --format=custom --no-owner --no-password --file=$file
    if ($LASTEXITCODE -ne 0) { Fail "pg_dump exited with code $LASTEXITCODE" }
    if (-not (Test-Path $file)) { Fail "no dump file was written" }

    $list = & $pgRestore --list $file
    if ($LASTEXITCODE -ne 0) { Fail "pg_restore --list could not read the dump (exit $LASTEXITCODE)" }
    # "TABLE <schema> <name>" entries only; "TABLE DATA" entries are counted separately below.
    $tables = @($list | Where-Object { $_ -match '^\d+;\s+\d+\s+\d+\s+TABLE\s' -and $_ -notmatch '\sTABLE DATA\s' }).Count
    $tablesWithData = @($list | Where-Object { $_ -match '\sTABLE DATA\s' }).Count
    $sizeMb = [Math]::Round((Get-Item $file).Length / 1MB, 2)

    Write-Host ""
    Write-Host "File:         $file"
    Write-Host "Size:         $sizeMb MB"
    Write-Host "Tables:       $tables"
    Write-Host "Table data:   $tablesWithData"
    if ($tables -gt 0) {
        Write-Host "OK: backup written and readable." -ForegroundColor Green
        exit 0
    }
    Fail "the dump contains no tables"
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    $url = $null
    $secure = $null
}
