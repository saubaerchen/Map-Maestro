$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$requestPath = Join-Path $scriptDir "codex_curl_request.json"

if (-not (Test-Path -LiteralPath $requestPath)) {
    throw "Request file not found: $requestPath"
}

$request = Get-Content -LiteralPath $requestPath -Raw | ConvertFrom-Json

if (-not $request.url) {
    throw "The request file must include a url field."
}

$uri = [System.Uri]$request.url
$requestHost = $uri.Host.ToLowerInvariant()

$allowed =
    $requestHost -eq "liquipedia.net" -or
    $requestHost -eq "www.liquipedia.net" -or
    $requestHost.EndsWith(".valolytics.gg")

if (-not $allowed) {
    throw "Only Liquipedia and Valolytics hosts are allowed."
}

$args = @("-L", "--max-time", "30", $uri.AbsoluteUri)

if ($request.raw -eq $true) {
    $separator = if ($uri.Query) { "&" } else { "?" }
    $args[-1] = $uri.AbsoluteUri + $separator + "action=raw"
}

& curl.exe @args
