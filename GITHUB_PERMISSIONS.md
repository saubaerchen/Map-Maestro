# GitHub Standing Permissions

This file records the user's standing GitHub-related permissions and preferences for this workspace so routine GitHub tasks do not need to be re-explained each time.

Last updated: 2026-04-13

## Scope

These permissions are preferences and standing consent from the user for this workspace.
They do not override platform safety rules, sandbox restrictions, or any approval prompt that the environment itself may still require.

For broader prompt-minimization across non-GitHub workflows, see:
- `PERMISSIONS_SETUP.md`

## Standing Permission Granted

The user has granted ongoing permission for me to do the following GitHub-related tasks when relevant to the current work:

- Use the GitHub connector/app tools available in this environment.
- Inspect GitHub repositories, files, commits, pull requests, and issues that are accessible through the connected account.
- Create new repositories for the user when explicitly requested.
- Create private repositories when explicitly requested.
- Upload project files to GitHub repositories the user owns or has granted access to.
- Update existing files in those repositories.
- Create commits through the GitHub connector workflow.
- Move the target branch/ref forward when publishing approved changes.
- Sync local static-site files or similar project assets to GitHub repositories.
- Make follow-up adjustments to previously created GitHub repos for this project without re-asking each time.
- Proceed with routine Git command execution for publishing without re-asking each time.

## Current Known GitHub Context

- GitHub account/login used in this workspace: `Zescht`
- Known repository created for this project: `Zescht/Veto-Stage2`

## Important Security Preference

- Do not store GitHub personal access tokens in the repository or in workspace files.
- If a token is ever needed again, treat it as temporary and sensitive.
- Prefer GitHub connector/app access over token-based shell workflows whenever possible.

## Practical Working Rule

Unless the user says otherwise, routine GitHub publishing and update tasks for this workspace can proceed under this standing permission model.

Additional explicit user instruction (2026-04-13):
- "You don't have to ask me for those git permissions, you are permitted to continue without asking."

Examples:

- pushing updated website files to `Zescht/Veto-Stage2`
- adjusting repo contents after design/content changes
- creating a new repo when the user explicitly asks for one
- using GitHub connector tools instead of asking again for ordinary repo maintenance

## When To Still Pause

Even with this standing permission, I should still pause or explicitly confirm if:

- the action is destructive in a non-routine way
- the target repo/account is unclear
- a new secret/token is required
- the requested GitHub action has unusual consequences the user may not expect
