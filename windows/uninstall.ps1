$key = 'HKCU:\Software\Classes\*\shell\QuickCaptureToBase'
if (Test-Path $key) {
  Remove-Item -Path $key -Recurse -Force -Confirm:$false
  Write-Output 'Context menu entry removed.'
} else {
  Write-Output 'Nothing to remove.'
}
