# Install the Serenity-Killer daily pipeline as a Windows scheduled task.
# Runs at 08:00 every day under the current user.
# Usage:
#   .\scripts\install_task.ps1            # install
#   .\scripts\install_task.ps1 -Uninstall # remove

param(
    [switch]$Uninstall
)

$TaskName = "SerenityKillerPipeline"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$LogDir   = Join-Path $env:LOCALAPPDATA "serenity-killer-playbook"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if ($Uninstall) {
    schtasks /Delete /TN $TaskName /F | Out-Host
    Write-Host "Removed $TaskName"
    return
}

$pyExe   = (Get-Command py -ErrorAction SilentlyContinue).Source
if (-not $pyExe) { $pyExe = (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $pyExe) {
    Write-Host "Could not find py/python on PATH. Install Python 3.11+." -ForegroundColor Red
    exit 1
}

$cmd = "cd /d `"$RepoRoot`" && `"$pyExe`" -m src.cli all >> `"$LogDir\pipeline.log`" 2>&1"
$action = "cmd /c `"$cmd`""

schtasks /Create /SC DAILY /TN $TaskName /TR $action /ST 08:00 /RU $env:USERNAME /F | Out-Host
Write-Host ""
Write-Host "Installed task '$TaskName' to run daily at 08:00."
Write-Host "Logs: $LogDir\pipeline.log"
Write-Host "To run now:        schtasks /Run /TN $TaskName"
Write-Host "To check:          schtasks /Query /TN $TaskName /V /FO LIST"
Write-Host "To remove later:   .\scripts\install_task.ps1 -Uninstall"
