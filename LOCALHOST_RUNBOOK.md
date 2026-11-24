# Localhost Runbook (Veto Site)

Last updated: 2026-04-14

## Goal

Start the veto site preview fast and reliably without repeating trial/error.

## Site Path

- `c:\Users\Vincent\Codex\DataRead\veto-history-site-publish`
- URL: `http://127.0.0.1:4173/`

## Why It Sometimes Fails

- In this Codex environment, some background processes started in sandbox mode are cleaned up after the command returns.
- Result: server can show `200` once, then die a few seconds later.

## Reliable Start Procedure (Codex)

Use an **escalated** launch (outside sandbox) with the stable pattern:

1. Stop existing listeners on `4173`.
2. Start Python HTTP server from `veto-history-site-publish`.
3. Verify with `Invoke-WebRequest` against `127.0.0.1:4173`.

Reference PowerShell flow:

```powershell
$wd='c:\Users\Vincent\Codex\DataRead\veto-history-site-publish'
$port=4173
$existing=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if($existing){
  $existing | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
    try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {}
  }
  Start-Sleep -Seconds 1
}
$pythonPath=(Get-Command python -ErrorAction Stop).Source
Start-Process -FilePath $pythonPath -ArgumentList '-m','http.server',$port -WorkingDirectory $wd -PassThru
Start-Sleep -Seconds 2
Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -UseBasicParsing -TimeoutSec 5
```

## Health Check

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:4173/" -UseBasicParsing -TimeoutSec 5
```

Expected: `StatusCode = 200`.

## Fast Retry Checklist

1. Re-run the reliable start procedure above (same port, same path).
2. Confirm `200`.
3. Hard refresh browser (`Ctrl+F5`) if old JS is cached.

## Rule For Future Sessions

- Always use this runbook first for localhost startup.
- Keep port fixed at `4173`.
- Keep command shape stable to reuse granted permissions.
