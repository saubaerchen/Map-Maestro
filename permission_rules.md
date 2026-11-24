# Permission Rules

The following commands and tools are pre-approved and do not require individual confirmation in this project directory (`C:\Users\Vincent\Claude\DataRead_Claude`).

These permissions were explicitly granted by the user in sessions on 15.04.2026, 16.04.2026, 20.04.2026, 13.05.2026, and 16.06.2026.

> **Note:** These are also enforced via `.claude/settings.json` `permissions.allow` — the harness-level rules. The `.md` file is a reminder for Claude; the `settings.json` is what actually suppresses approval prompts.

## Pre-approved commands

- **`node`** — any node command (e.g. syntax checks, inline `-e` scripts, module runs)
- **`powershell.exe`** — any PowerShell command via Bash (e.g. reading JSONL, checking file contents, running ConvertFrom-Json queries)
- **`PowerShell` tool** — any PowerShell command via the native PowerShell tool (e.g. starting localhost server, Get-NetTCPConnection, Start-Process, Invoke-WebRequest)
- **`python3`** / **`python`** — any Python script or inline `-c` command (e.g. reading raw data, fetching from API, building bundles)
- **`sed`** — read operations on project files (e.g. inspecting line ranges of `.css` or `.js` files)
- **`curl`** — HTTP requests against localhost (e.g. checking server status at `127.0.0.1:4173`)
- **`xargs`** — any xargs command (e.g. `xargs -I{} basename {}` for listing/processing file paths)

## Scope

These approvals apply within this project directory only. They do not apply to destructive operations (deleting files, force-pushing, dropping data) — those still require explicit confirmation.
