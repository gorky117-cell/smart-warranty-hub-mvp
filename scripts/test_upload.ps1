$ErrorActionPreference = "Stop"

$repoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $repoRoot

$cookiePath = Join-Path $repoRoot "cookies.txt"
$uploadFile = "C:\Users\lenovo\Desktop\sample_invoice.pdf"

if (Test-Path $cookiePath) {
  Remove-Item $cookiePath -Force
}

Write-Host "Logging in to get auth cookie..."
$loginResponse = & curl.exe -i -L -c $cookiePath -X POST "http://127.0.0.1:8000/auth/login"

if (-not (Test-Path $cookiePath)) {
  Write-Host "ERROR: cookies.txt was not created. Login likely failed." -ForegroundColor Red
  exit 1
}

$cookieHasToken = Select-String -Path $cookiePath -Pattern "access_token" -Quiet
if (-not $cookieHasToken) {
  $user = $env:SWH_USERNAME
  $pass = $env:SWH_PASSWORD
  if ($user -and $pass) {
    Write-Host "Retrying login with SWH_USERNAME/SWH_PASSWORD..."
    Remove-Item $cookiePath -Force
    $loginResponse = & curl.exe -i -L -c $cookiePath -X POST "http://127.0.0.1:8000/auth/login" `
      -H "Content-Type: application/x-www-form-urlencoded" `
      -d "username=$user&password=$pass"
    $cookieHasToken = Select-String -Path $cookiePath -Pattern "access_token" -Quiet
  }
}
if (-not $cookieHasToken) {
  Write-Host "ERROR: access_token not found in cookies.txt. Login failed or no cookie set." -ForegroundColor Red
  Write-Host "Login response (first 20 lines):"
  $loginResponse | Select-Object -First 20 | ForEach-Object { Write-Host $_ }
  Write-Host "Tip: set env vars SWH_USERNAME and SWH_PASSWORD and re-run." -ForegroundColor Yellow
  exit 1
}

if (-not (Test-Path $uploadFile)) {
  Write-Host "ERROR: Upload file not found: $uploadFile" -ForegroundColor Red
  exit 1
}

function Invoke-Upload($useBearer, $token) {
  $temp = New-TemporaryFile
  try {
    if ($useBearer -and $token) {
      $status = & curl.exe -sS -o $temp -w "%{http_code}" `
        -H "Authorization: Bearer $token" `
        -F "file=@$uploadFile" `
        "http://127.0.0.1:8000/artifacts/upload"
    } else {
      $status = & curl.exe -sS -o $temp -w "%{http_code}" `
        -b $cookiePath `
        -F "file=@$uploadFile" `
        "http://127.0.0.1:8000/artifacts/upload"
    }
    $body = Get-Content -Raw $temp
    return @{ Status = [int]$status; Body = $body }
  } finally {
    Remove-Item $temp -Force -ErrorAction SilentlyContinue
  }
}

Write-Host "Uploading invoice with cookie..."
$resp = Invoke-Upload $false ""
$statusCode = $resp.Status
$respText = $resp.Body

if ($statusCode -eq 401 -or $respText -match "Missing token") {
  Write-Host "Cookie auth failed, retrying with Bearer token..."
  $tokenLine = Select-String -Path $cookiePath -Pattern "access_token" | Select-Object -First 1
  $tokenValue = ""
  if ($tokenLine) {
    $parts = $tokenLine.Line -split "`t"
    if ($parts.Count -ge 7) {
      $tokenValue = $parts[6]
    } else {
      $tokenValue = ($tokenLine.Line -split "\s+")[-1]
    }
  }
  if (-not $tokenValue) {
    Write-Host "ERROR: Could not extract access_token from cookies.txt" -ForegroundColor Red
    exit 1
  }
  $resp = Invoke-Upload $true $tokenValue
  $respText = $resp.Body
  $statusCode = $resp.Status
}

Write-Host "FINAL STATUS: $statusCode"
Write-Host "RESPONSE:"
Write-Host $respText

if ($statusCode -eq 200) {
  exit 0
}
exit 1
