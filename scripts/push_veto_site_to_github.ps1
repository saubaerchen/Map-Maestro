$ErrorActionPreference = "Stop"

if (-not $env:GITHUB_TOKEN) {
    throw "GITHUB_TOKEN environment variable is required."
}

$workspaceRoot = Split-Path -Parent $PSScriptRoot
$repo = "Zescht/Veto-Stage2"
$branch = "main"
$headers = @{
    Authorization = "Bearer $($env:GITHUB_TOKEN)"
    Accept = "application/vnd.github+json"
    "User-Agent" = "Codex"
}

$files = @(
    @{ local = "veto-history-site/index.html"; remote = "index.html"; message = "Update veto history site" },
    @{ local = "veto-history-site/styles.css"; remote = "styles.css"; message = "Update veto history site" },
    @{ local = "veto-history-site/app.js"; remote = "app.js"; message = "Update veto history site" },
    @{ local = "veto-history-site/data.js"; remote = "data.js"; message = "Update veto history site" }
)

foreach ($file in $files) {
    $localPath = Join-Path $workspaceRoot $file.local
    if (-not (Test-Path -LiteralPath $localPath)) {
        throw "Missing local file: $localPath"
    }

    $contentBytes = [System.IO.File]::ReadAllBytes($localPath)
    $contentBase64 = [System.Convert]::ToBase64String($contentBytes)
    $apiUrl = "https://api.github.com/repos/$repo/contents/$($file.remote)?ref=$branch"

    $existing = $null
    try {
        $existing = Invoke-RestMethod -Method Get -Uri $apiUrl -Headers $headers
    } catch {
        if (-not $_.Exception.Message.Contains("404")) {
            throw
        }
    }

    $body = @{
        message = $file.message
        content = $contentBase64
        branch = $branch
    }

    if ($existing -and $existing.sha) {
        $body.sha = $existing.sha
    }

    Invoke-RestMethod -Method Put -Uri ("https://api.github.com/repos/$repo/contents/$($file.remote)") -Headers $headers -Body ($body | ConvertTo-Json) | Out-Null
}

Write-Output "Uploaded site files to $repo on $branch"
