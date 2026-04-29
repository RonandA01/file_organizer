# ============================================================
#  build.ps1 — Rebuild File Organizer EXE + Installer
#  Usage: Right-click → "Run with PowerShell"
#         or in terminal: .\build.ps1
# ============================================================

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$PYTHON_PYINSTALLER = "C:\Users\ronde\AppData\Local\Python\pythoncore-3.14-64\Scripts\pyinstaller.exe"
$INNO_SETUP         = "C:\Users\ronde\AppData\Local\InnoSetup6\ISCC.exe"
$SPEC_FILE          = "file_organizer.spec"
$ISS_FILE           = "installer.iss"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  File Organizer — Build Script"         -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Stage 1: PyInstaller ──────────────────────────────────
Write-Host "[1/2] Building EXE with PyInstaller..." -ForegroundColor Yellow
$t1 = Get-Date
& $PYTHON_PYINSTALLER $SPEC_FILE --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: PyInstaller failed (exit code $LASTEXITCODE)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
$elapsed1 = [math]::Round(((Get-Date) - $t1).TotalSeconds, 1)
Write-Host "  Done in ${elapsed1}s" -ForegroundColor Green

# ── Stage 2: Inno Setup ───────────────────────────────────
Write-Host ""
Write-Host "[2/2] Building installer with Inno Setup..." -ForegroundColor Yellow
$t2 = Get-Date
& $INNO_SETUP $ISS_FILE
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Inno Setup failed (exit code $LASTEXITCODE)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
$elapsed2 = [math]::Round(((Get-Date) - $t2).TotalSeconds, 1)
Write-Host "  Done in ${elapsed2}s" -ForegroundColor Green

# ── Summary ───────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Build complete!" -ForegroundColor Green
$installer = Get-ChildItem "installer_output\*.exe" | Sort-Object LastWriteTime | Select-Object -Last 1
if ($installer) {
    $sizeMB = [math]::Round($installer.Length / 1MB, 1)
    Write-Host "  Output: $($installer.Name)  ($sizeMB MB)" -ForegroundColor Green
    Write-Host "  Path:   $($installer.FullName)" -ForegroundColor Gray
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close"
