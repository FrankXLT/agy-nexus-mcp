<#
.SYNOPSIS
    Cross-Platform PowerShell Setup Wizard for ag-bridge-mcp (Windows / PowerShell 7+)
.DESCRIPTION
    Generates SUBDOMAIN_HASH, PATH_SECRET, normalized SHA-256 PASS_HASH, and
    configurable session/context-window environment variables.
#>
param(
    [string]$Domain = "example.com",
    [string]$Passphrase = "",
    [string]$EnvFile = "$HOME/.config/ag-bridge-mcp/secrets.env",
    [int]$TtlSeconds = 7200,
    [int]$MaxFileChars = 15000,
    [int]$MaxTotalFileChars = 24000,
    [int]$MaxFilesPerCall = 6,
    [int]$MaxDiffChars = 15000,
    [int]$MaxTranscriptTurns = 10,
    [bool]$EnforceModular = $true,
    [int]$TargetFileLines = 300,
    [int]$HardMaxFileLines = 400,
    [switch]$KeepExistingUrls,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Passphrase)) {
    if ($Domain -eq "example.com") {
        $inputDomain = Read-Host "Enter your base domain [example.com]"
        if (-not [string]::IsNullOrWhiteSpace($inputDomain)) { $Domain = $inputDomain.Trim() }
    }
    $secPass = Read-Host "Enter spoken voice passphrase for Antigravity deadbolt" -AsSecureString
    $secConfirm = Read-Host "Confirm voice passphrase" -AsSecureString
    $bstr1 = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPass)
    $bstr2 = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secConfirm)
    try {
        $Passphrase = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr1)
        $ConfirmPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr2)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr1)
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr2)
    }
    if ($Passphrase -ne $ConfirmPlain) {
        Write-Error "Passphrases did not match."
        exit 1
    }
}

if ($Domain -notmatch '^[A-Za-z0-9.-]+$') {
    Write-Error "Invalid Domain '$Domain' (only letters, digits, dots, and hyphens allowed)."
    exit 1
}

$Normalized = ($Passphrase.ToLowerInvariant() -replace '[^a-z0-9]', '')
if ([string]::IsNullOrEmpty($Normalized)) {
    Write-Error "Passphrase must contain at least one alphanumeric character."
    exit 1
}

$sha256 = [System.Security.Cryptography.SHA256]::Create()
$hashBytes = $sha256.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Normalized))
$PassHash = ($hashBytes | ForEach-Object { $_.ToString("x2") }) -join ""

function New-RandomHex([int]$ByteCount) {
    $bytes = New-Object byte[] $ByteCount
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
}

$SubdomainHash = ""
$PathSecret = ""
$HostBridgeToken = ""
if ($KeepExistingUrls -and (Test-Path $EnvFile)) {
    foreach ($line in Get-Content $EnvFile) {
        if ($line -match '^SUBDOMAIN_HASH=(.+)$') { $SubdomainHash = $Matches[1].Trim("'"" ") }
        if ($line -match '^PATH_SECRET=(.+)$') { $PathSecret = $Matches[1].Trim("'"" ") }
        if ($line -match '^HOST_BRIDGE_TOKEN=(.+)$') { $HostBridgeToken = $Matches[1].Trim("'"" ") }
    }
}
if ([string]::IsNullOrEmpty($SubdomainHash)) { $SubdomainHash = New-RandomHex 6 }
if ([string]::IsNullOrEmpty($PathSecret)) { $PathSecret = New-RandomHex 24 }
if ([string]::IsNullOrEmpty($HostBridgeToken)) { $HostBridgeToken = New-RandomHex 32 }

$parentDir = Split-Path -Parent $EnvFile
if (-not (Test-Path $parentDir)) { New-Item -ItemType Directory -Path $parentDir -Force | Out-Null }

$FullUrl = "https://ag-$SubdomainHash.$Domain/$PathSecret/mcp"
$PublicUrl = if ($Domain -ne "example.com") { "https://ag-$SubdomainHash.$Domain" } else { "" }
$TsUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$EnforceStr = if ($EnforceModular) { "true" } else { "false" }

$Content = @"
# ag-bridge-mcp runtime configuration & secrets
# Generated: $TsUtc
# Gemini Connected Apps URL: $FullUrl

# --- Perimeter & Deadbolt Security ---
SUBDOMAIN_HASH=$SubdomainHash
AG_BRIDGE_DOMAIN=$Domain
AG_BRIDGE_PUBLIC_URL=$PublicUrl
PATH_SECRET=$PathSecret
PASS_HASH=$PassHash
HOST_BRIDGE_TOKEN=$HostBridgeToken
TTL_SECONDS=$TtlSeconds
BIND_HOST=0.0.0.0
BIND_PORT=8765
HOST_BRIDGE_BIND_HOST=127.0.0.1
HOST_BRIDGE_BIND_PORT=8098

# --- Context Window & Pagination Budgets ---
MAX_FILE_CHARS=$MaxFileChars
MAX_TOTAL_FILE_CHARS=$MaxTotalFileChars
MAX_FILES_PER_CALL=$MaxFilesPerCall
MAX_DIFF_CHARS=$MaxDiffChars
MAX_TRANSCRIPT_TURNS=$MaxTranscriptTurns

# --- Modular Architecture & File Hygiene Standards ---
ENFORCE_MODULAR_HYGIENE=$EnforceStr
TARGET_FILE_LINES=$TargetFileLines
HARD_MAX_FILE_LINES=$HardMaxFileLines
"@

if (-not (Test-Path $EnvFile)) { New-Item -ItemType File -Path $EnvFile -Force | Out-Null }
if ($IsLinux -or $IsMacOS) { chmod 600 $EnvFile } else { icacls $EnvFile /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null }
Set-Content -Path $EnvFile -Value $Content -Encoding UTF8
if ($IsLinux -or $IsMacOS) { chmod 600 $EnvFile }

if (-not $Quiet) {
    Write-Host ""
    Write-Host "======================================================================"
    Write-Host " ag-bridge-mcp Configuration & Secrets Initialized "
    Write-Host "======================================================================"
    Write-Host "[+] Secrets File:      $EnvFile"
    Write-Host "[+] Subdomain Host:    ag-$SubdomainHash.$Domain"
    Write-Host "[+] Gemini MCP URL:    $FullUrl"
    Write-Host "[+] Deadbolt SHA-256:  $($PassHash.Substring(0,12))...$($PassHash.Substring($PassHash.Length-8))"
    Write-Host "[+] Session TTL:       ${TtlSeconds}s"
    Write-Host "[+] File Slice Cap:    ${MaxFileChars} chars/file (line-range pagination enabled)"
    Write-Host "[+] Diff Page Cap:     ${MaxDiffChars} chars/page (offset & per-file pagination enabled)"
    Write-Host "[+] Modular Hygiene:   $EnforceStr (<= $TargetFileLines lines/file target)"
    Write-Host "======================================================================"
}
