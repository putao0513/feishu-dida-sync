param([string]$Target)
$ErrorActionPreference = 'Stop'
$name = [System.IO.Path]::GetFileName($Target)
$payload = @{
  title = $name
  content = "Captured from Windows Explorer: $Target"
  url = ''
  source = 'explorer-context-menu'
} | ConvertTo-Json -Compress
$bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
try {
  Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/capture' -Method Post `
    -ContentType 'application/json; charset=utf-8' -Body $bytes -TimeoutSec 10 | Out-Null
} catch {
  Write-Output "Quick capture failed (is python server.py running?): $($_.Exception.Message)"
}
