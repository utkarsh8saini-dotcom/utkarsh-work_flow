# install_scheduled_task.ps1 — make the tracker + tunnel start automatically at logon,
# so prices keep updating 24/7 and your phone URL is always available.
# (The laptop must stay powered on and not asleep for true 24/7.)
#
#   Run once:   powershell -ExecutionPolicy Bypass -File .\install_scheduled_task.ps1
#   Remove:     Unregister-ScheduledTask -TaskName FlightTracker24x7 -Confirm:$false
#
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$here\run_public.ps1`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 2) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "FlightTracker24x7" -Action $action -Trigger $trigger `
  -Settings $settings -Description "Flight Price Tracker + Cloudflare tunnel (24/7)" -Force | Out-Null
Write-Host "Registered scheduled task 'FlightTracker24x7' — it will launch run_public.ps1 at each logon." -ForegroundColor Green
Write-Host "Also stop the laptop from sleeping (Settings > Power) for genuine 24/7 tracking." -ForegroundColor Yellow
