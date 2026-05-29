#requires -Version 5.1
<#
.SYNOPSIS
    Wrapper that runs the daily Serenity-Killer pipeline from the correct
    working directory and writes a timestamped log under data\logs\.

.DESCRIPTION
    Use this as the Task Scheduler action so the scheduled run does not depend
    on the caller's CWD. Example registration (run once, elevated):

        $action  = New-ScheduledTaskAction `
            -Execute 'powershell.exe' `
            -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\Users\zhaow\serenity-killer-playbook\scripts\run_daily.ps1"'
        $trigger = New-ScheduledTaskTrigger -Daily -At 08:00
        Register-ScheduledTask -TaskName 'SerenityKillerDigest' -Action $action -Trigger $trigger -Force

    Exit code is the CLI's exit code so Task Scheduler shows the failure.
#>
param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$PythonExe = 'py',
    [string[]]$ExtraArgs = @()
)

Set-Location -Path $RepoRoot

$logDir = Join-Path $RepoRoot 'data\logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logFile = Join-Path $logDir "run-$stamp.log"

$argList = @('-m', 'src.cli', 'all') + $ExtraArgs
"=== $(Get-Date -Format o) starting: $PythonExe $($argList -join ' ') ===" |
    Out-File -FilePath $logFile -Append -Encoding utf8

& $PythonExe @argList 2>&1 | Tee-Object -FilePath $logFile -Append
$code = $LASTEXITCODE

"=== $(Get-Date -Format o) finished with exit code $code ===" |
    Out-File -FilePath $logFile -Append -Encoding utf8

exit $code
