# Live verification checklist (maintainers and advanced users)

You do not need this to set up or use your 2mem — [SETUP.md](SETUP.md) step 7 is the everyday
check. This list is for maintainers of the template, and for anyone whose gate does not behave as
SETUP describes.

Run it on a live repository set up per [SETUP.md](SETUP.md) steps 1–5 (and step 9 for the
connector items). The workflow, hook and ruleset are checked offline by the tests and by static
review; the items below are the parts only GitHub can confirm. A failed item uses its fallback;
the fix lands as a governance PR.

Needs: `gh` signed in as the owner; a second GitHub account (for the fork case); Claude with the
GitHub connector for this repo. `OWNER/REPO` = your repository.

---

## A. Live-only assumptions

Each: **assumption** — *test* — *fallback if it fails*.

1. **A commit status satisfies the required check.** The ruleset requires context `okf-lint`; the
   workflow posts it as a commit *status* from `pull_request_target`, not as a check run.
   - Test: a good PR (B1) shows `okf-lint` as required and green, and becomes mergeable.
   - Fallback: require the job's check run (`lint pull request`) instead, after confirming it
     appears on the PR head commit.

2. **The ruleset imports as-is and is enforced** on the plan in use (public on Free; private on
   Pro, or Team for an organisation). No `integration_id` is set, so anyone with write access
   could post the status by hand — acceptable on a single-owner repo.
   - Test: web import and `gh api --method POST repos/OWNER/REPO/rulesets --input setup/ruleset.json`
     both succeed (delete one); B9 is refused.
   - Fallback: create the rules by hand from the SETUP §4 table. With more writers, pin the
     required check to the GitHub Actions app — `{ "context": "okf-lint", "integration_id": 15368 }`
     (15368 = `id` of `GET /apps/github-actions`, read 2026-09-23) — and re-run B1. It stops a
     person's token from posting the status; it does not tell this repository's workflows apart
     from a fork's (item 25).

3. **`pull_request_target` runs the base branch's workflow and linter for every same-repo PR,**
   including PRs opened by the web editor and by the Claude connector (a user token; only
   events made with `GITHUB_TOKEN` start no workflow).
   - Test: B8 (linter-edit PR judged by the base linter), B10 (web editor), B1 (Claude).
   - Fallback: none inside this design — if connector PRs do not trigger, the connector must act
     as a user, not as the repo's own Actions token.

4. **`GITHUB_TOKEN` may merge under the ruleset** with an empty bypass list: 0 approvals, squash
   (merge commit for the Obsidian PR, item 16), `okf-lint` green → `gh pr merge --squash` succeeds
   without bypass. Default workflow permissions read-only; the job-level `contents: write` still
   applies.
   - Test: B1 merges with no click.
   - Fallback: a GitHub App installation token (contents + pull requests write, not a bypass
     actor) for the merge job only.

5. **`gh pr merge --squash --delete-branch --match-head-commit` works with no checkout**
   (`--repo` only), and refuses a head that moved after the check.
   - Test: B1 log shows the merge and the branch is gone. Race: push a second commit to a passing
     PR right after the first run's lint step; the old merge job logs "A newer commit" or `gh`
     refuses; only the newer run merges.
   - Fallback: drop `--delete-branch` and rely on "Automatically delete head branches" (not
     on an instance edited in Obsidian, where that setting is off).

6. **A merge made with `GITHUB_TOKEN` starts no workflow run; a person's merge does.**
   - Test: after B1, Actions shows no `push` run for that merge commit; after a human merge (B7),
     `lint whole repo` runs.
   - Fallback: harmless either way (push lint is read-only). If a human merge does not trigger
     it, run the workflow by hand (**Run workflow**).

7. **Label events re-run the check with current labels** (`labeled`/`unlabeled` of `hold` or
   `allow-loss`; `allow-loss` is read from the event), and `edited` re-runs it when the PR's base
   branch changes (`github.event.changes.base` is set). Any other label, and a title or
   description edit, starts a run whose jobs are all skipped at job level (no runner).
   - Test: B5 — adding `allow-loss` turns red to green and merges; B12 — removing `hold` merges;
     changing a PR's base branch starts a new run against the new base. On a held PR, add a label
     such as `question` and edit the title: each run shows every job **skipped**, with no status
     change.
   - Fallback: after changing a label, push an empty commit (a plain re-run reuses the old
     event, with the old labels).

8. **A superseded run never leaves the status stuck.** `cancel-in-progress` cancels the older run;
   the newer run posts the final status for the same head.
   - Test: on a passing PR, add and remove `hold` within a few seconds: final status is not
     `pending`, and the outcome (held or merged) matches the final labels. An ignored event (item
     7) has a concurrency group of its own (`…-ignored-<run id>`): add a `question` label while a
     check is running → that check is not cancelled and posts its status.
   - Fallback: drop `cancel-in-progress` so runs queue instead.

9. **The pinned checkout (v7.0.1 by SHA) resolves, accepts `allow-unsafe-pr-checkout`, and with
   `fetch-depth: 0` leaves `origin/<base>` for the would-be-merge build.** (Checked offline
   2026-09-23: tag `v7.0.1` = the pinned SHA, and that SHA's `action.yml` declares the input.)
   - Test: the first PR run passes both checkout steps and "Build the would-be merge result".
   - Fallback: re-pin to the current v7 SHA; if the input is unknown, drop it and fetch
     `refs/pull/N/head` into `pr/` with plain `git fetch`.

10. **Fork PRs are linted, never merged.** The fork head checks out as data, the status posts on
    the fork's head SHA, and the merge job holds it.
    - Test: from the second account, fork, add a good document, open a PR: green, held comment
      "comes from a fork".
    - Fallback: if the fork checkout is refused, fork PRs show "could not run"; say in SETUP that
      a person reviews and merges them.

11. **The token can comment on PRs with `pull-requests: write`** (no `issues: write`) through the
    issue-comments API, as `github-actions[bot]`, so the one comment is found and edited.
    - Test: a red PR (B11), then a second failing commit: still exactly one `okf-lint` comment,
      edited in place; green afterwards marks it resolved.
    - Fallback: add `issues: write` to both jobs; if the login differs, match on the marker only.

12. **Squash commits carry the PR title and description** (SETUP §2 default), so the title is the
    permanent provenance.
    - Test: after B1, `git log -1 main` subject = PR title, body = description.
    - Fallback: re-set the default in Settings → General; else pass `--subject`/`--body` from
      the PR to `gh pr merge`.

### Obsidian (SETUP step 10) — only on an instance that uses it

13. **`GITHUB_TOKEN` can start okf-lint by `workflow_dispatch`** (`gh workflow run okf-lint.yml
    -f pr=N`, job permission `actions: write`), and the dispatched run — on the default branch —
    passes the job condition and reads the PR from the API.
    - Test: B13 — Actions shows a `workflow_dispatch` run of okf-lint for the new PR.
    - Fallback: dispatch with a GitHub App token (actions write) from obsidian.yml.

14. **The dispatched run's commit status satisfies the required check** on the PR head (the
    status is posted by API, whatever started the run).
    - Test: B13/B15 — `okf-lint` green on the PR's latest commit, PR mergeable and merged.
    - Fallback: none needed while item 1 holds; if item 1 fell back to a check run, the dispatch
      path needs the same fallback.

15. **`GITHUB_TOKEN` can open the PR** once "Allow GitHub Actions to create and approve pull
    requests" is ticked.
    - Test: B13 — PR `obsidian: update from vault` opened by `github-actions[bot]`.
    - Fallback: a GitHub App token for the PR-opening call.
    - Organisation-owned repository: an organisation owner must first allow the option at
      organisation level, or the repository setting is greyed out (seen live; SETUP 10a).

16. **A merge commit is allowed** by the ruleset (`allowed_merge_methods: [squash, merge]`) and the
    repo setting: `gh pr merge --merge --match-head-commit --subject` succeeds with no bypass.
    - Test: B13 — `git log --first-parent main -1` subject is `obsidian: update from vault (#N)`,
      with two parents.
    - Fallback: none inside this design — squash would cut the vault's history from main.

17. **The `obsidian` branch survives**: "Automatically delete head branches" off, and
    `setup/ruleset-obsidian.json` (deletion and force-push rules) refuses the **Delete branch**
    button and a force push. Docs say
    rulesets "can also prevent branches being automatically deleted"; not relied on alone.
    - Test: B13 — branch still there after the merge; B19.
    - Fallback: if the ruleset import fails, rely on the setting and on not clicking the button.

18. **The reusable call works from a `pull_request_target` run** (`uses:
    ./.github/workflows/obsidian.yml`, taken from the base branch, with the calling job's
    permissions).
    - Test: B14 — the merging run shows the job "update the obsidian branch" and it succeeds.
      It runs only with the repository variable `OBSIDIAN_SYNC` = `true` (SETUP 10a): the
      variable must be readable in the job's `if:` in both files, including inside the called
      workflow. Without it (an instance not using Obsidian) the job shows **skipped**, and so does
      obsidian.yml's run for a person's merge.
    - Fallback: replace the call with `gh workflow run obsidian.yml` in the merge job
      (`actions: write`).

19. **Fast-forward by API**: `PATCH git/refs/heads/obsidian` with `force=false` succeeds when
    `obsidian` is behind, and is refused ("not a fast forward") when it moved.
    - Test: B13, B14 — `obsidian` equals main after the sync.
    - Fallback: the merges API (a no-op merge commit) instead of the ref update.

20. **The merges API on `obsidian`**: `POST /merges` returns 201 with a merge commit when both
    moved, 204 when there is nothing to merge, 409 on a conflict; compare returns
    `identical|ahead|behind|diverged` as used.
    - Test: B15 (201), B16 (409).
    - Fallback: none needed; on an unexpected response the run fails loudly.

21. **The PR catches up with a head moved by API** within the sync's one-minute wait, and
    `refs/pull/N/head` with it, so the dispatched check lints and marks the new commit.
    - Test: B15 — the status sits on the merge commit the sync made, not the one before.
    - Fallback: lengthen the wait, or check out the head by SHA in the dispatched run.

22. **A vault push fires both** `push` (obsidian.yml) and `pull_request_target: synchronize` on the
    open PR (it is a push made with the owner's own credentials).
    - Test: B15 — after the vault pushes a fix, a `pull_request_target` run checks it.
    - Fallback: have obsidian.yml dispatch the check on every vault push.

23. **Obsidian Git pulls the server's merge cleanly**: with no local changes it fast-forwards;
    with unpushed local commits it makes a local merge and pushes; the starter `data.json`
    (copied after installing the plugin) shows in its settings.
    - Test: B14, B15 on desktop; B13 once on mobile.
    - Fallback: pull by hand (plugin command **Pull**) and report the plugin version.

### Claude connector (SETUP step 9)

24. **The connector reaches this repository and nothing else.** GitHub's MCP server
    (`https://api.githubcopilot.com/mcp/`) accepts the user token of your own GitHub App, and that
    token reaches only the repositories the App is installed on.
    - Test: B20.
    - Fallback, in order: the connector with no client ID of your own, if the app it installs
      (the "Claude GitHub MCP Connector" app) can be limited to **Only select repositories** = this
      repository — GitHub's docs did not yet support this; a separate GitHub account (or
      organization) that holds only this repository; a self-hosted GitHub MCP server with a
      fine-grained token limited to this repository. Never a connector with access to all
      repositories.
    - Organisation-owned repository: the App is created and installed under the organisation
      (SETUP 9a); not yet tested live.

### Public instance

25. **A fork cannot fake the required check.** A fork PR can add its own `pull_request` workflow
    with a job named `okf-lint`; its check run then carries the required check's name (while this
    repository's run posts the real `okf-lint` status on the same commit).
    - Test: from the second account, a fork PR that adds `.github/workflows/fake.yml` (`on:
      pull_request`, one job named `okf-lint` that just succeeds) plus a bad document. With fork
      approval off, let it run: does the PR show the required `okf-lint` as passing, or blocked by
      the real failing status?
    - Fallback: if the fake check run satisfies the rule, keep SETUP step 3's **Require approval
      for all external contributors** (never approve a workflow change from a fork) — the fork's
      workflow then never runs. `integration_id` alone does not help here: a fork's workflow also
      reports as the GitHub Actions app. Fork PRs are never merged automatically either way.

### Actions minutes

26. **A job skipped by its `if:` is not billed**, and each job that runs is billed rounded up to a
    whole minute (the basis of SETUP's "Actions minutes" figures).
    - Test: on a private instance, note the Actions usage, make a few content changes, an
      unrelated label and a title edit, and compare the usage report: about 2 minutes per merged
      change (3 with `OBSIDIAN_SYNC`), nothing for the label and title edit.
    - Fallback: if skipped jobs are billed, the filters save nothing but cost nothing either;
      correct the SETUP figures.

---

## B. Acceptance suite

Each: *do* → *expect*. Throwaway documents; remove them at the end (with `allow-loss`).

1. **Create** — Claude creates `concept/acceptance-create.md` on a branch, PR titled
   `claude-ai: create concept/acceptance-create.md` → green, squash-merged, branch deleted, file on
   main.
2. **Update** — Claude reads the file (keeps `sha`), edits, opens a PR → merged; read back from
   main matches.
3. **Stale `sha` → 409** — read the `sha`; change the file through another merged PR; write with
   the old `sha` → refused 409; re-read, re-apply, write → succeeds.
4. **Link pair** — two new documents linking each other in one PR → green, merged. The same pair as
   two PRs → the first is red (unresolved `relates_to` path).
5. **Shrink refused / `allow-loss`** — cut a document's body by ≥25% → red, comment names
   `allow-loss`; add the label → re-runs, merges. Same for a delete.
6. **Originals edit refused** — change the body of an `_originals/` file → red. Frontmatter-only
   change → green, merged.
7. **Governance held** — PR that adds an area in `_meta/conventions.md` → green, not merged, held
   comment names the path; merge by hand. Repeat with a root `README.md` edit, a `tests/` edit, and
   a non-`.md` file in a new top-level folder (`notes/a.txt`) → each green and held. A content-only
   PR meanwhile → merged.
8. **Linter-edit PR judged by the base linter** — one PR: `_meta/okf-lint.py` edited to exit 0 at
   the top, plus a document with `status: finished` → red (the base linter ran). Remove the bad
   document → green, held (governance). Close without merging.
9. **Direct push refused** — `git push origin main` from a clone → rejected; web editor offers no
   "commit directly to main"; force push and branch deletion → rejected.
10. **Web-editor PR** — SETUP §7 a, b, d on github.com → as described there.
11. **Lint comment readable from claude.ai** — Claude opens a PR with a bad `status`; ask Claude why
    it did not merge → it quotes the `okf-lint` comment, fixes the file on the same branch → green,
    merged.
12. **`hold` and draft** — a passing PR with `hold` → held; remove the label → merged. A draft PR →
    held; **Ready for review** → merged.

**Obsidian** (on an instance set up per SETUP step 10; a vault on desktop):

13. **Vault edit** — add a document in `concept/` in Obsidian → sync opens `obsidian: update from
    vault`, check green, merged with a merge commit; `obsidian` == main afterwards; vault's next
    pull is a fast-forward.
14. **Claude merge, vault idle** — Claude merges a PR → `obsidian` fast-forwarded; the vault
    receives the file on its next pull.
15. **Claude merge, vault pending** — make the vault PR red (bad `status`), then Claude merges a
    PR → main merged into `obsidian`, check re-run on the new head (still red, same comment); fix
    in Obsidian → green → merged; `git log main` contains the vault's commits.
16. **Conflict** — edit the same line in the vault (PR open, held with `hold`) and via Claude
    (merged) → sync leaves `obsidian` as is; the PR comment gives the Obsidian conflict wording;
    **Resolve conflicts** on GitHub → green (remove `hold`) → merged; vault pulls cleanly.
17. **Root note** — create `Untitled.md` at the vault root → PR red with the "move it into the folder
    of its type" error (conventions §11); move it into `concept/` in Obsidian → green → merged.
18. **Rename** — rename a note that another note's `relates_to` points at → red: deleted document
    and unresolved `relates_to` path; fix the path by hand, add `allow-loss` → merged.
19. **Branch kept** — on the merged vault PR, click **Delete branch** → refused.

**Claude connector** (SETUP step 9; needs a second private repository of yours with a file in it):

20. **Connector boundary** — in a chat in the 2mem Project:
    - ask Claude to read a file from the other private repository by its exact path, and to
      `search_code` in it (`repo:OWNER/OTHER <a word in that file>`) → both fail: not found, or
      0 results;
    - in this repository: read a document, create a branch, write a file, open a PR → all work
      (as B1);
    - ask Claude to write a file straight to `main` → refused by the ruleset (it must not merge
      or bypass, either);
    - github.com/settings/installations → your App has **only this repository**; no other app
      Claude uses has **All repositories**.
