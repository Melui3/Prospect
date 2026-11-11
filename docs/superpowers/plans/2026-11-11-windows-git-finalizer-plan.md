# Plan — Windows Git finalizer

> Build a local Windows helper; never commit or push this Prospect working tree from the restricted Codex session.

## Safety requirements

- Read only during preview. Abort commit if the Git index is already staged.
- Use literal, validated paths from a lot manifest; never stage every change.
- Display unrelated working-tree changes as excluded from this lot.
- Block paths outside the repository, `.git`, credentials, databases, backups, and detected secret or likely private-contact patterns.
- Show the exact candidate diff and the current commit/upstream context before action.
- Commit only after the user types `COMMIT`; push only after a separate `PUSH`. Never force-push.
- Log exact Git failures locally, redacting credentials in remote URLs.

## Task 1 — Preview and explicit local commit

**Files:** `scripts/Finalize-Git.ps1`, `scripts/git-finalizer/README.md`, `scripts/git-finalizer/plan.example.json`, `.git-finalizer-plan.json`.

1. Add `Get-ValidatedPlan`, `Get-RepositoryState`, `Get-CandidateDiff`, and `Test-CandidateSafety` to the PowerShell 5.1 script. Accept `-RepoPath`, `-PlanPath`, and `-Action` (`Preview`, `Commit`, `Push`). The manifest contains one commit message, a non-empty validation summary, and an array of literal relative paths; reject globs, absolute paths, traversal, duplicates, and paths that resolve outside the repository.
2. For preview and commit, report branch, HEAD, upstream, every changed/untracked path, allowlisted paths, and excluded unrelated paths. Abort if any planned path is missing/unchanged, already staged, ignored, a reparse point, or blocked by filename/content checks. Show the candidate diff with `git diff --no-index` for untracked files and normal `git diff` for tracked files.
3. For commit, require an initially clean index. After the first safety check, stage only manifest paths with `git add -- <literal paths>`, verify the staged path set is exactly the manifest set, rescan the staged diff, show it, and run `git commit -m <manifest message>` only after exact `COMMIT` input. On every Git failure, print and append command, exit code, stdout and stderr to the per-user local log; sanitize remote credentials.

## Task 2 — Separate explicit push

**Files:** `scripts/Finalize-Git.ps1`, `scripts/Finaliser Git.bat`, `scripts/git-finalizer/README.md`.

1. In `Push` action, require a clean index and unchanged manifest paths while displaying unrelated working-tree changes as excluded; require a configured upstream, refresh it with `git fetch --no-tags`, show the remote host/path without credentials, every outgoing commit and full file diff, and scan the complete outgoing range.
2. Refuse detached HEAD, missing upstream, force-push, zero or multiple outgoing commits, unlisted paths, and any unsafe file/content. Offer only ordinary `git push <remote> HEAD:<upstream-branch>` after exact `PUSH` input; never commit as part of push.
3. Add a double-click batch wrapper that invokes the script from its own folder and preserves the PowerShell exit code. Document reuse in another repository and the manifest format.

## Task 3 — Isolated safety verification

**Target:** a disposable repository under the writable task scratch directory, never `D:\Projets\Prospect\.git` or any real remote.

1. Run `Preview` against synthetic modified and unrelated files; confirm the listed candidate is shown and unrelated paths are excluded.
2. Confirm a staged leftover, traversal path, blocked database/credential filename, and synthetic secret or private-contact data each stop before staging/commit.
3. In the disposable repository only, type `COMMIT` and confirm exactly the manifest paths are committed. Run `Push` against a local bare fixture remote; verify it first displays the outgoing commit and does not push when confirmation is absent or incorrect. Do not contact GitHub.
4. Confirm the script still parses under Windows PowerShell and that current Prospect tracked/untracked files remain untouched.

## Handoff

Explain that local commits cannot be created from this session because `.git` writes are restricted; distinguish that from push networking. Provide the exact Windows invocation and describe the required per-lot manifest. Prepare a NateOS register entry with implementation details and verification evidence, and publish only after Nate approves the exact content and document destination.
