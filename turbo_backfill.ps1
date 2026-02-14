#!/usr/bin/env powershell
# =============================================================================
# TURBO BACKFILL - Aggressive Mode
# =============================================================================
# Kills ALL processes, frees ports, and runs maximum speed backfill
# Run this when markets are closed (holiday/weekend)
# =============================================================================

param(
    [int]$Workers = 50,
    [int]$Batch = 2000,
    [double]$Sleep = 0.5
)

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "                 TURBO BACKFILL - AGGRESSIVE MODE" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
# STEP 1: KILL ALL PROCESSES (Aggressive cleanup)
# =============================================================================
Write-Host "[1/5] KILLING ALL PROCESSES..." -ForegroundColor Red

# Kill all Python processes
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object { 
    Write-Host "  Killing Python PID $($_.Id)" -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue 
}

# Kill all Node processes  
Get-Process node -ErrorAction SilentlyContinue | ForEach-Object { 
    Write-Host "  Killing Node PID $($_.Id)" -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue 
}

# Double-check with taskkill
Start-Process -FilePath "taskkill" -ArgumentList "/F /IM python.exe /T" -Wait -WindowStyle Hidden -ErrorAction SilentlyContinue
Start-Process -FilePath "taskkill" -ArgumentList "/F /IM node.exe /T" -Wait -WindowStyle Hidden -ErrorAction SilentlyContinue
Start-Process -FilePath "taskkill" -ArgumentList "/F /IM cmd.exe /FI `"WINDOWTITLE eq *history*`" -Wait -WindowStyle Hidden -ErrorAction SilentlyContinue

Write-Host "  [OK] All processes killed" -ForegroundColor Green
Start-Sleep -Seconds 2

# =============================================================================
# STEP 2: FREE ALL PORTS
# =============================================================================
Write-Host ""
Write-Host "[2/5] FREEING PORTS 8787 and 8788..." -ForegroundColor Red

# Get and kill any process using ports 8787 or 8788
$ports = @(8787, 8788)
foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            try {
                $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
                if ($proc) {
                    Write-Host "  Killing process on port $port (PID: $($proc.Id))" -ForegroundColor Yellow
                    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                }
            } catch {}
        }
    }
}

Write-Host "  [OK] Ports freed" -ForegroundColor Green
Start-Sleep -Seconds 2

# =============================================================================
# STEP 3: VERIFY CLEAN STATE
# =============================================================================
Write-Host ""
Write-Host "[3/5] VERIFYING CLEAN STATE..." -ForegroundColor Yellow

$pythonCount = (Get-Process python -ErrorAction SilentlyContinue).Count
$nodeCount = (Get-Process node -ErrorAction SilentlyContinue).Count

Write-Host "  Python processes remaining: $pythonCount" -ForegroundColor $(if($pythonCount -eq 0){'Green'}else{'Red'})
Write-Host "  Node processes remaining: $nodeCount" -ForegroundColor $(if($nodeCount -eq 0){'Green'}else{'Red'})

if ($pythonCount -gt 0 -or $nodeCount -gt 0) {
    Write-Host "  WARNING: Some processes still running! Continuing anyway..." -ForegroundColor Red
}

# Clear any temp files that might lock
Remove-Item -Path "$PSScriptRoot\history_out\*.db-shm" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "$PSScriptRoot\history_out\*.db-wal" -Force -ErrorAction SilentlyContinue
Write-Host "  [OK] Clean state verified" -ForegroundColor Green

# =============================================================================
# STEP 4: SET ENVIRONMENT FOR MAX SPEED
# =============================================================================
Write-Host ""
Write-Host "[4/5] CONFIGURING MAXIMUM SPEED..." -ForegroundColor Yellow

$env:CPU_PROFILE = "max"
$env:HISTORY_FETCH_WORKERS = "$Workers"
$env:HISTORY_BATCH = "$Batch"
$env:HISTORY_SLEEP = "$Sleep"
$env:HISTORY_MAX_LOOKBACK_DAYS = "5000"
$env:HISTORY_WS_THROTTLE = "0"
$env:TODAY_FETCH_WORKERS = "$Workers"
$env:MAX_REST_SESSIONS = "8"
$env:FIRST_CLOSE_MAX_RETRIES = "2"

Write-Host "  CPU_PROFILE = $env:CPU_PROFILE" -ForegroundColor Cyan
Write-Host "  HISTORY_FETCH_WORKERS = $env:HISTORY_FETCH_WORKERS" -ForegroundColor Cyan
Write-Host "  HISTORY_BATCH = $env:HISTORY_BATCH" -ForegroundColor Cyan
Write-Host "  HISTORY_SLEEP = $env:HISTORY_SLEEP" -ForegroundColor Cyan
Write-Host "  HISTORY_WS_THROTTLE = $env:HISTORY_WS_THROTTLE" -ForegroundColor Cyan
Write-Host "  [OK] Environment configured" -ForegroundColor Green

# =============================================================================
# STEP 5: START BACKFILL
# =============================================================================
Write-Host ""
Write-Host "[5/5] STARTING TURBO BACKFILL..." -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop (progress is saved continuously)" -ForegroundColor Yellow
Write-Host ""

# Get initial count
$dbPath = "$PSScriptRoot\history_out\first_closes.db"
if (Test-Path $dbPath) {
    $initialCount = (& sqlite3 $dbPath "SELECT COUNT(*) FROM history_state WHERE done=1;" 2>$null)
    $totalCount = (& sqlite3 $dbPath "SELECT COUNT(*) FROM history_state;" 2>$null)
    Write-Host "Starting: $initialCount / $totalCount completed" -ForegroundColor Magenta
}

# Run historyapp
try {
    Set-Location $PSScriptRoot
    python historyapp.py
} catch {
    Write-Host "Backfill stopped or error occurred" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

# =============================================================================
# COMPLETE
# =============================================================================
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "BACKFILL STOPPED" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""

# Show final stats
if (Test-Path $dbPath) {
    $finalCount = (& sqlite3 $dbPath "SELECT COUNT(*) FROM history_state WHERE done=1;" 2>$null)
    $totalCount = (& sqlite3 $dbPath "SELECT COUNT(*) FROM history_state;" 2>$null)
    $percent = [math]::Round(($finalCount / $totalCount) * 100, 2)
    Write-Host "Final Progress: $finalCount / $totalCount ($percent%)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Restart normal operation with:" -ForegroundColor Yellow
Write-Host "  python start_all.py" -ForegroundColor Cyan
Write-Host ""

pause
