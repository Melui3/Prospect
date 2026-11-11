# Design — Windows Git finalizer

## Intent

Make tested local changes easy to commit and publish from the user's Windows session, where Git has the user's normal repository and network access. Keep Codex's current limited `.git` access from being mistaken for a network-only failure.

## Goals

- Reuse PowerShell and Git already installed on Windows; add no application or paid service.
- Reuse one portable PowerShell launcher across repositories, with an exact per-lot manifest of approved paths and a commit message.
- Show repository, branch, tracked and untracked changes, declared verification evidence, the exact proposed diff, and the destination before any write.
- Reject staged leftovers, paths outside the repository, unlisted paths, sensitive filenames, detected secrets, and likely private contact data.
- Stage only manifest paths; never use `git add -A` or `git add .`.
- Require separate typed confirmations for local commit and remote push. Never force-push.
- Retain exact Git errors in a local log so access and network failures can be diagnosed.

## Non-goals

- No automatic commit or push, GitHub API, credential storage, new app, background watcher, or modification of `.git` from Codex.
- No attempt to combine unrelated dirty changes into a commit.
- Secret scanning is a guardrail, not a claim of perfect detection; the explicit path manifest and full diff review remain mandatory.

## Approaches considered

1. **Portable launcher plus exact per-lot manifest — selected.** Codex prepares a list of literal repository-relative paths and a commit message after a lot is tested. The Windows launcher validates and displays that manifest, scans the candidate, then asks for explicit commit and push confirmations. This minimizes selection work while keeping the commit boundary reviewable.
2. Interactive path selection on every run. This avoids a manifest file but repeats manual selection and makes it easier to include an unrelated file. It does not fit the request to reduce manual commit work.

## Constraints and behavior

- Target Windows PowerShell 5.1 and existing Git; no downloaded module.
- The launcher is read-only in preview mode. Commit mode requires a clean Git index, stages only listed files, verifies the staged path set and diff, and asks for `COMMIT` before running `git commit`.
- Push mode requires a clean index and unchanged manifest paths, while displaying unrelated local changes as excluded. It fetches the configured upstream to refresh its state, displays every outgoing commit and file, refuses force-push and unexpected outgoing ranges, scans the entire range, and asks for `PUSH` separately.
- Ignore files outside the manifest and report them as excluded. Block common secret and private-data file names (`.env` credentials, keys, databases, backups), credential patterns, and obvious email/phone records. If any manifest path is missing, ambiguous, unsafe, ignored, or matches a blocked pattern, stop without staging or publishing.
- Save command, exit code, and exact stderr to a per-user local log outside the repository; also print the error. Never log credentials embedded in remote URLs.
- Keep the existing Prospect working tree and safety snapshot untouched. Do not commit or push during implementation from this restricted session.

## Approval boundary

Before the user's confirmation, the deliverable is only this design. After approval, prepare an implementation plan, add the reusable launcher and Prospect manifest, exercise it against a disposable local Git fixture, and document the tested workflow and current permission limitation in the NateOS register after the exact entry is approved.
