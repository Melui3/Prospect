# Prospect Qualification Implementation Plan

> **For agentic workers:** Implement task by task with TDD. Do not stage or commit the pre-existing local changes.

**Goal:** Turn existing campaign results into evidence-backed prospect reviews and editable email drafts, with an explicit approval before any send.

**Architecture:** Reuse Prospect, Campaign, SearchJob, the local worker, existing owner-only API, ContactDrawer, and SMTP configuration. Add persisted qualification evidence/review state and persisted drafts. Website inspection uses bounded HTTP requests and records observations without treating failures as proof; no paid APIs, AI service, or worker email sending.

**Tech Stack:** Django 5, Django REST Framework, SQLite local database, React 18, Vite, existing Node and Django tests.

**Spec:** NateOS register `1sfrM2xcbRzHL5XyMxb5xS5CVDbHG5wixK8_kie1djNk`, tab `t.8iin8x5rrga`; local changes audited on 2026-11-11.

## Global Constraints

- Keep every pre-existing local change; do not overwrite, stage, or commit it.
- Do not inspect or mutate the user's real database during tests.
- Do not send real email, publish to GitHub, or deploy.
- No new paid service or dependency.
- Exclude do-not-contact, already contacted, duplicate/merged, and previously sent prospects from review queues.
- A qualification or draft job must never send email.
- Surface source, observation time, and uncertainty; a missing listed website is not proof that no website exists.

## Review Focus

- An unavailable website is unknown, not a verified defect; test timeout/unsafe URLs and safe evidence output.
- Refused, already-contacted, merged, and duplicate prospects never enter the actionable queue; test each exclusion.
- Direct API calls cannot send for rejected, deferred, or unapproved reviews; test server-side guards.
- Draft edits persist across reloads, but never send automatically; test save and queue completion.
- Migration and tests must use isolated in-memory databases and a non-network email backend.

---

### Task 1: Qualification evidence and queue

**Files:** Create `backend/prospection/qualification.py` and a Django migration. Modify `backend/prospection/models.py`, `jobs.py`, `personal_api.py`, `urls.py`. Test in `backend/prospection/test_personal.py`.

- [x] Add tests for qualification evidence on listed/missing websites and exclusions for do-not-contact, contacted/sent, merged, and duplicates.
- [x] Run the focused tests and confirm the expected missing behavior.
- [x] Implement persisted `QualificationReview` with status, priority, reasons, evidence, checked time; bounded safe site inspection; owner-only list and approve/reject/defer actions; run qualification through the existing worker after searches and for unreviewed existing contacts.
- [x] Run focused tests; confirm network inspection is mocked and no email calls occur.

### Task 2: Persistent drafts and enforced send approval

**Files:** Modify `backend/prospection/models.py`, `personal_api.py`, `mail.py`, `urls.py`; add migration. Test in `backend/prospection/test_personal.py`.

- [x] Add tests proving drafts persist, unapproved prospects cannot send, do-not-contact remains blocked, and no worker sends.
- [x] Run focused tests and confirm the failures are caused by missing draft/approval behavior.
- [x] Add one draft per prospect, evidence-grounded deterministic draft generation, editable save endpoint, and a send endpoint that requires an approved review and exact saved draft plus explicit confirmation.
- [x] Run focused tests with the in-memory email backend; verify only an explicit test-confirmed send reaches the mock backend.

### Task 3: Prospect review and message UI

**Files:** Create `frontend/src/personal/Qualification.jsx`. Modify `frontend/src/personal/App.jsx`, `api.js`, `Contacts.jsx`, `ContactDrawer.jsx`, `common.jsx`, `personal.css`. Add frontend tests where existing pure helpers cover behavior.

- [x] Run the existing frontend unit tests for template substitution and desktop/demo routing.
- [x] Add a Qualification view showing evidence, date, reasons and uncertainty with approve/reject/defer actions; reuse ContactDrawer for editable persisted drafts and make send available only for approved prospects with a saved draft and final confirmation.
- [x] Run frontend tests and build into the isolated visualization directory.

### Task 4: Regression and demo verification

**Files:** Test only; no live data.

- [x] Run all 53 Django tests on `sqlite:///:memory:` with locmem email.
- [x] Run all frontend tests (7) and production build to isolated output.
- [x] Verify refusal/no-approval blocks a send in API tests, and run coverage only against synthetic fixtures.
- [x] Report test evidence, limitations, and the next recommended lot. Drive handoff awaits approval of its exact final text.
