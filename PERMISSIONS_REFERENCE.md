# Claude Code — Permission Reference

This document lists all actions Claude is pre-approved to take without asking for confirmation each time.
Copy the relevant blocks into a new project's `.claude/settings.json` to replicate the same setup.

---

## How permissions work

Claude Code has two files that control permissions:

| File | Purpose |
|---|---|
| `.claude/settings.json` | Project-level permissions (committed to the repo) |
| `.claude/settings.local.json` | Local overrides + accumulated session-specific approvals |

Entries go in the `permissions.allow` array. Wildcards (`*`) match any argument.
The `.md` reminder file (e.g. `permission_rules.md`) is just a note for Claude — it has no enforcement power on its own. The `settings.json` is what actually suppresses the YES/NO prompts.

---

## Core permissions (clean, reusable set)

These are in `settings.json` and use wildcards — they cover the broadest, most useful cases for a data/scripting project.

### Running code

```json
"Bash(python3 *)",
"Bash(python *)",
"Bash(node *)",
"Bash(pip install *)"
```

**What it covers:** Any Python script, any inline `-c` command, any Node.js script or inline `-e` expression, installing Python packages. Claude can run data pipelines, analysis scripts, build scripts, and syntax checks without asking each time.

---

### Shell utilities

```json
"Bash(curl *)",
"Bash(sed *)",
"Bash(xargs *)",
"Bash(powershell.exe *)"
```

**What it covers:**
- `curl` — HTTP requests (useful for checking localhost server status or hitting local APIs)
- `sed` — reading line ranges of files (e.g. `sed -n '100,120p' file.js`)
- `xargs` — chaining file operations (e.g. `xargs -I{} basename {}`)
- `powershell.exe` — calling PowerShell from inside a Bash tool call

---

### PowerShell tool (native)

```json
"PowerShell(*)"
```

**What it covers:** Any command via the native PowerShell tool — starting servers, reading files with `Get-Content`, checking network connections with `Get-NetTCPConnection`, copying files with `Copy-Item`, creating directories with `New-Item`, etc.

This is separate from `Bash(powershell.exe *)` because Claude Code has both a Bash tool and a dedicated PowerShell tool. Both need to be allowed.

---

### Git operations

```json
"Bash(git add *)",
"Bash(git commit *)",
"Bash(git push)",
"Bash(git push *)",
"Bash(git log *)",
"Bash(git diff *)",
"Bash(git status *)",
"Bash(git check-ignore *)"
```

Or, to allow all git commands at once:

```json
"Bash(git *)"
```

**What it covers:** Staging files, committing, pushing to remote, inspecting history and diffs. The broad `Bash(git *)` was added in a later session to also cover `git fetch`, `git branch`, etc. without needing individual approvals.

**Note:** Even with these permissions, destructive git operations (force-push, reset --hard) still get flagged by Claude's own caution — these permissions don't override that judgment, they only suppress the YES/NO prompt for standard operations.

---

### File editing

```json
"Edit"
```

**What it covers:** The Edit tool (in-place text replacements). Without this, every single file edit requires confirmation — extremely disruptive for coding sessions. This is one of the first permissions to grant.

---

### Web access

```json
"WebSearch",
"WebFetch(domain:liquipedia.net)",
"WebFetch(domain:www.vlr.gg)",
"WebFetch(domain:zescht.github.io)",
"WebFetch(domain:www.twitch.tv)",
"WebFetch(domain:twitchtracker.com)",
"WebFetch(domain:sullygnome.com)",
"WebFetch(domain:youtu.be)",
"WebFetch(domain:www.youtube.com)"
```

**What it covers:**
- `WebSearch` — general web searches (no domain restriction)
- `WebFetch(domain:X)` — fetching pages from specific domains. Add per domain as needed.

**Note:** `WebSearch` without a domain qualifier allows all searches. `WebFetch` is per-domain — Claude will still ask for new domains until you add them.

---

### GitHub CLI

```json
"Bash(gh api *)"
```

**What it covers:** GitHub API calls via the `gh` CLI tool (checking repo status, PR info, etc.).

---

### Skills

```json
"Skill(valolytics-fetch)",
"Skill(scouting-page-build)",
"Skill(superpowers:using-superpowers)",
"Skill(superpowers:systematic-debugging)",
"Skill(superpowers:writing-skills)",
"Skill(update-config)",
"Skill(code-review)"
```

**What it covers:** Invoking named Claude Code skills without a confirmation prompt. Add any skill you use regularly. Skills that run subagents or modify files will prompt for those actions separately unless they're also pre-approved.

---

## The session-start hook (auto-load permission rules)

This hook reads `permission_rules.md` and injects it into Claude's context at the start of every session, so Claude "remembers" the agreed rules without you having to repeat them.

```json
"hooks": {
  "SessionStart": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "python -c \"import json; content = open('permission_rules.md').read(); print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': 'PERMISSION RULES (auto-loaded from permission_rules.md):\\n\\n' + content}}))\"",
          "statusMessage": "Loading permission rules..."
        }
      ]
    }
  ]
}
```

**Requirements:** `permission_rules.md` must exist in the project root. The hook runs Python inline (no script file needed). Works as long as Python is available in the terminal environment.

---

## What is NOT pre-approved (requires YES/NO every time)

Even with all of the above, the following always prompt for confirmation — by design:

- **Deleting files** (`rm`, `Remove-Item`, `unlink`) — except specific pre-approved `rm -f` calls for known stale files
- **Force-pushing** (`git push --force`, `git push -f`)
- **Hard resets** (`git reset --hard`)
- **Dropping data** (database drops, truncating large files)
- **Reading files outside the project directory** — unless explicitly added as `Read(path/**)`

---

## Minimal starter `settings.json` for a new project

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 *)",
      "Bash(python *)",
      "Bash(node *)",
      "Bash(pip install *)",
      "Bash(curl *)",
      "Bash(sed *)",
      "Bash(xargs *)",
      "Bash(powershell.exe *)",
      "PowerShell(*)",
      "Bash(git *)",
      "Edit",
      "WebSearch"
    ]
  }
}
```

Add `WebFetch(domain:X)` entries for any external sites Claude will regularly fetch from. Add `Skill(name)` entries for skills you use in that project.

---

## Notes on `settings.local.json`

Over time, Claude Code accumulates very specific permission entries in `settings.local.json` — exact command strings from one-off approvals you clicked YES on during a session. These are not clean or reusable as-is (they contain hardcoded paths from this machine). The `settings.json` wildcards above replace all of them. Start with `settings.json` wildcards and let `settings.local.json` accumulate naturally for edge cases.
