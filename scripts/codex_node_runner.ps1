$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Split-Path -Parent $scriptDir
$requestPath = Join-Path $scriptDir "codex_node_request.json"

if (-not (Test-Path -LiteralPath $requestPath)) {
    throw "Request file not found: $requestPath"
}

$request = Get-Content -LiteralPath $requestPath -Raw | ConvertFrom-Json

if (-not $request.script) {
    throw "The request file must include a script field."
}

$resolvedScript = [System.IO.Path]::GetFullPath((Join-Path $workspaceRoot $request.script))
$resolvedWorkspace = [System.IO.Path]::GetFullPath($workspaceRoot)

if (-not $resolvedScript.StartsWith($resolvedWorkspace, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Only scripts inside the workspace may be executed."
}

$extension = [System.IO.Path]::GetExtension($resolvedScript)
if ($extension -notin @(".js", ".mjs", ".cjs")) {
    throw "Only Node script files are allowed."
}

$args = @()
if ($request.args) {
    foreach ($arg in $request.args) {
        $args += [string]$arg
    }
}

& node $resolvedScript @args
