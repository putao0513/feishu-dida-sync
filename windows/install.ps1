$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'capture.ps1'
$exe = (Get-Command powershell.exe).Source
$command = '"{0}" -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{1}" "%1"' -f $exe, $script
$key = 'HKCU:\Software\Classes\*\shell\QuickCaptureToBase'
$cmdKey = Join-Path $key 'command'
New-Item -Path $key -Force | Out-Null
Set-Item -Path $key -Value 'Quick capture to workbench'
New-Item -Path $cmdKey -Force | Out-Null
Set-Item -Path $cmdKey -Value $command
Write-Output 'Installed. Right-click any file to capture it.'
