$wd = 'C:\Users\Vincent\Claude\DataRead_Claude\veto-history-site-publish'
$port = 4173
$existing = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
  $existing | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
    try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {}
  }
  Start-Sleep -Seconds 1
}
$pythonPath = (Get-Command python -ErrorAction Stop).Source
Start-Process -FilePath $pythonPath -ArgumentList '-m', 'http.server', $port -WorkingDirectory $wd -PassThru
Start-Sleep -Seconds 2
Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -UseBasicParsing -TimeoutSec 5
