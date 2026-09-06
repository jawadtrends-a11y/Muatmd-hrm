# Install Muatmd punch agent as a Windows startup task (ق-86).
#
# Run as Administrator:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
#   .\install-service.ps1
#
# Uses Task Scheduler, not a Windows service: starts at boot,
# restarts on failure, needs no extra packages.

$ErrorActionPreference = "Stop"

$TaskName = "MuatmdPunchAgent"
$AppDir   = $PSScriptRoot
$Exe      = Join-Path $AppDir "muatmd-agent.exe"

if (-not (Test-Path $Exe)) {
    Write-Host "muatmd-agent.exe not found in this folder" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $AppDir "config.json"))) {
    Write-Host "config.json not found" -ForegroundColor Red
    Write-Host "Run muatmd-agent-setup.exe first"
    exit 1
}

$action = New-ScheduledTaskAction -Execute $Exe -WorkingDirectory $AppDir
$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Days 0)

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false `
    -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger $trigger -Settings $settings `
    -Principal $principal `
    -Description "Muatmd punch agent" | Out-Null

Start-ScheduledTask -TaskName $TaskName

Write-Host ""
Write-Host "Agent installed and started." -ForegroundColor Green
Write-Host ""
Write-Host "  Status:    Get-ScheduledTask -TaskName $TaskName"
Write-Host "  Stop:      Stop-ScheduledTask -TaskName $TaskName"
Write-Host "  Remove:    Unregister-ScheduledTask -TaskName $TaskName"
Write-Host "  Log file:  $AppDir\agent.log"
Write-Host ""
