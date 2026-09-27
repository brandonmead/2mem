# Setting up your 2mem

This turns the template into **your own knowledge base with a write gate**: every change arrives as
a proposal (a *pull request* — the words are explained below), an automatic check (`okf-lint`)
reads it, and only a change that passes is merged — by the repository itself, with no one clicking
anything. Rule changes wait for you.

Plan on about 20 minutes for steps 1–8, plus 20–30 minutes for step 9a (connecting Claude to
GitHub) — the hardest step. You need a GitHub account and a web browser; nothing here needs a
terminal except the optional steps for editing in a clone (6, 9c, 10).

**Words used below:**

- **Repository** — the project folder on GitHub that holds your knowledge base and its history.
- **Branch** — a named line of changes. `main` is the real one; others hold proposed changes.
- **Pull request (PR)** — a request to merge one branch into `main`, where it can be checked first.
- **Status check** — a pass/fail result GitHub shows on a pull request; here it is `okf-lint`.
- **Ruleset** — repository rules GitHub enforces, such as "changes to `main` only by pull request".
- **Fork** — someone else's copy of a repository; they can propose pull requests to yours from it.

> **Public or private?** The write gate is a GitHub *ruleset*. Rulesets are free on **public**
> repositories. On a **private** repository they need a paid plan: GitHub Pro for a personal
> account; Team or Enterprise for an organisation. A private repository on the Free plan still
> works, but nothing *enforces* the gate: anyone with write access could change the main branch
> directly. Choose public only if you are comfortable with everything you write being readable by
> anyone.

---

## 1. Make your copy

1. On this template's GitHub page, click **Use this template → Create a new repository**.
2. Pick the owner (your account, or an organisation — see the notes in steps 3, 9a and 10a), a
   name, and **Public** or **Private** (see the box above).
   Leave **Include all branches** unticked.
3. Click **Create repository**.

A template copies files only — not settings, rules, or labels. Steps 2–5 put those back.

## 2. Pull request settings

**Settings → General**, scroll to **Pull Requests**:

- **Allow merge commits** — untick.
- **Allow squash merging** — tick. Set its default message to **Pull request title and
  description**, so each change's title (who made it and what) and reason become the permanent
  history.
- **Allow rebase merging** — untick.
- **Automatically delete head branches** — tick.
- **Allow auto-merge** — leave unticked. It is not used; the check merges by itself (step 7).

(Editing in Obsidian? Step 10 changes two of these.)

## 3. Actions settings

**Settings → Actions → General**:

- **Actions permissions** — leave **Allow all actions and reusable workflows**, or choose the
  option that allows actions created by GitHub. The workflow uses only `actions/checkout`.
- **Workflow permissions** — choose **Read repository contents and packages permissions**
  (read-only). The workflow asks, job by job, for exactly the extra access it needs.
- **Allow GitHub Actions to create and approve pull requests** — leave **unticked**. The merge job
  *merges* pull requests; it never creates or approves one, so it does not need this.
- **Public repository only:** under **Approval for running fork pull request workflows**, choose
  **Require approval for all external contributors**. Anyone can propose a change to a public
  repository from their own copy (a fork); this stops workflow files they add from running until
  you approve them.

Click **Save** for each section you changed.

**Organisation-owned repository:** a greyed-out option here is set for the whole organisation
under **Organization settings → Actions → General**; ask an organisation owner to change it there.

## 4. Turn on the write gate (the ruleset)

The file [`setup/ruleset.json`](ruleset.json) holds the rules for your main branch:

| Rule | What it does |
|---|---|
| Restrict deletions | The main branch cannot be deleted. |
| Block force pushes | History on the main branch cannot be rewritten. |
| Require a pull request before merging | Every change arrives as a pull request. **0 approvals** needed (you work alone; the check is the reviewer). Squash and merge commits are allowed here; step 2 leaves squash the only one switched on (step 10 adds merge commits for Obsidian). |
| Require status checks to pass: `okf-lint` | Nothing merges until the check has passed on the pull request's latest commit. |
| Bypass list: empty | Nobody — not you, not the automation — can skip these rules. |

"Require branches to be up to date before merging" is **off** on purpose. The check already
examines what the branch *would look like after merging* with the current main branch, so the
extra rule adds nothing — and turning it on would stall every pull request that falls behind,
because an update made by the automation does not trigger a new check.

**To import it (web):**

1. In your repository, open `setup/ruleset.json` and click **Download raw file**.
2. Go to **Settings → Rules → Rulesets**.
3. Click **New ruleset → Import a ruleset**, choose the file you downloaded.
4. Review the rules shown (they match the table above) and click **Create**.

**Or, with the GitHub command line** (`gh`, already signed in), from a clone of your repository:

```bash
gh api --method POST repos/OWNER/REPO/rulesets --input setup/ruleset.json
```

(replace `OWNER/REPO` with your account and repository name).

## 5. Create the two labels

**Issues → Labels → New label** (or **Pull requests → Labels**), and create:

| Label | Meaning |
|---|---|
| `hold` | "Don't merge this yet." A passing pull request with this label waits until you remove it. |
| `allow-loss` | "This removal is intended." Lets a pull request delete or rename a document, cut a document's text by a quarter or more, or change the text of an original. Without it, the check refuses those. |

Command-line alternative:

```bash
gh label create hold --description "Passing, but do not merge yet"
gh label create allow-loss --description "Intended deletion, rename, large cut, or change to an original"
```

## 6. (Optional) The local check, for anyone who edits in a clone

Only needed if you — or Claude Code — edit the repository on a computer with `git`. It runs the
same check before each commit, where a fix is cheapest. It needs Python 3.8 or newer.

```bash
git clone https://github.com/OWNER/REPO.git
cd REPO
git config core.hooksPath .githooks
```

Run the last line once in every new clone. It makes git run this clone's own `.githooks/` and
`_meta/okf-lint.py` on every commit, so enable it only in a repository you trust, and review changes
to those two paths before you pull them. The hook checks exactly what you have staged; unstaged
edits are left alone and never lost. If a commit is refused for removing content you meant to
remove, commit with `OKF_ALLOW_LOSS=1 git commit ...` and put the `allow-loss` label on the pull
request.

## 7. Check that it works

Do all four. Each takes a minute or two; watch the pull request's **Checks** area and comments.

**a. A good change merges by itself.**

1. Open the `concept` folder, click **Add file → Create new file**, name it
   `concept/setup-test.md`, and paste:

   ```markdown
   ---
   type: concept
   title: Setup test
   description: A throwaway document that proves the write gate merges a good change.
   status: draft
   area: home
   ---

   # Setup test

   This document exists only to test the setup. It is removed again in step d.
   ```

   (If you already replaced the starter areas in step 8, use one of yours instead of `home`.)
2. Click **Commit changes**. Because the main branch is protected, GitHub offers only **Create a
   new branch for this commit and start a pull request** — that alone shows the ruleset is on.
   Title it `web: create concept/setup-test.md` and click **Propose changes → Create pull request**.
3. Within a minute or two: the `okf-lint` check turns green, the pull request is **merged**, and
   its branch is deleted. You clicked nothing after creating it.

**b. A bad change is stopped and explained.**

1. Create `concept/setup-test-bad.md` the same way, but with `status: finished` (not an allowed
   value).
2. The check turns red, a comment appears explaining the problem in plain words, and the pull
   request **stays open**. Close it with **Close pull request** (and delete its branch).

**c. Nobody can skip the gate.** Open any file, click the pencil, change a word, then **Commit
changes**: "Commit directly to the main branch" is not available. Cancel.

**d. An intended removal needs the label.**

1. Open `concept/setup-test.md`, click **⋯ → Delete file**, commit it to a new branch as a pull
   request titled `web: delete concept/setup-test.md`.
2. The check turns red: deleting a document is refused. Add the **`allow-loss`** label to the pull
   request. The check re-runs, passes, and the pull request merges.

If all four behave as described, the gate is working. (For maintainers, or if something here
does not behave as described: the [live verification checklist](acceptance.md) tests each
assumption the gate makes.)

## 8. Replace the starter areas with your own

Every document belongs to one **area** — a part of your life that would own it. The template ships
six neutral starters (`home`, `family`, `health`, `work`, `learning`, `community`); replace them
with the handful that fit you. This is a **governance change**, so it is checked but not merged
automatically: you merge it yourself.

1. Open `_meta/conventions.md` and click the pencil.
2. Find the block that starts with ` ```valueset name=area ` (section 3). Replace its lines with
   your own — one per line: the area name (lowercase, hyphens allowed), some spaces, then a short
   description. Keep the opening and closing ` ``` ` lines.
3. **Commit changes → Create a new branch… → Propose changes**, title it
   `web: update _meta/conventions.md`, say in the description why these areas, and create the pull
   request.
4. The check runs. If you removed an area that a document still uses, the check says which
   documents; change their `area` in the same pull request.
5. When the check is green, a comment says the pull request is **held for a person** because it
   changes the rules. Read the diff, then click **Squash and merge** yourself.

The same applies to any change outside the nine document folders and `_originals/` — `_meta/`,
`_templates/`, `setup/`, `tests/`, `.github/`, `.githooks/`, the files at the top of the repository
(`index.md`, `README.md`, `CLAUDE.md`, `LICENSE`, `.gitignore`), or a new top-level folder: checked
automatically, merged only by you.

## 9. Connect Claude

Claude reads and writes your 2mem through GitHub. Give it **this repository only** — never all
your repositories: the write gate protects this one, not the others.

> **Check your Claude plan first.** Part a adds a *custom connector* in claude.ai, which may
> require a paid Claude plan. Check what your plan includes before you start.

**a. Connect GitHub, limited to this repository** (once, on github.com and claude.ai). This is the
hardest step; allow 20–30 minutes.

Here you register your own small *GitHub App* — not software you write or publish, just an entry in
your GitHub settings — so that Claude can only ever see this one repository. Three terms come up:
the **Client ID** (the App's public name for sign-in), the **client secret** (its password: paste
it only into claude.ai), and the **Callback URL** (the claude.ai address GitHub returns you to after
you approve). This part follows GitHub's and Anthropic's documentation but has not yet been
confirmed on a live setup; the [verification checklist](acceptance.md) (A24, B20) shows how to
confirm the one-repository limit.

Why an App: its sign-in reaches only the repositories it is installed on. (claude.ai's built-in
**Add from GitHub** only copies files in, read-only. A GitHub *OAuth* App, or a personal access
token that is not fine-grained, reaches every repository you have.)

1. GitHub → **Settings → Developer settings → GitHub Apps → New GitHub App**:
   - **GitHub App name:** anything not yet taken, such as `2mem-claude-` plus your username.
     **Homepage URL:** your repository's address.
   - **Callback URL:** `https://claude.ai/api/mcp/auth_callback`.
   - **Webhook:** untick **Active**.
   - **Repository permissions:** **Contents** Read and write, **Pull requests** Read and write,
     **Issues** Read-only, **Metadata** Read-only (set for you). Nothing else, and no account
     permissions.
   - **Where can this GitHub App be installed?** **Only on this account.** Click **Create GitHub
     App**.

   **Organisation-owned repository:** create the App under the organisation instead —
   **Organization settings → Developer settings → GitHub Apps → New GitHub App**. An App created
   under your personal account with **Only on this account** cannot be installed on an
   organisation's repository. Keep **Only on this account** (it now means the organisation), and
   in step 3 install it on the organisation with **Only select repositories**. Creating or
   installing it needs an organisation owner, or someone an owner has made an App manager; your
   organisation's third-party access policy may also need an owner to approve it. Like the rest of
   this part, this is not yet confirmed on a live setup.

2. On the App's page, copy the **Client ID**. Click **Generate a new client secret** and copy it —
   GitHub shows it only once.
3. **Install App** (left menu) → your account → **Only select repositories** → choose this
   repository → **Install**. Never choose **All repositories**.
4. In claude.ai: **Settings → Connectors → Add custom connector**. Name it (for example `2mem
   GitHub`), URL `https://api.githubcopilot.com/mcp/` (GitHub's own connector server). Open
   **Advanced settings** and paste the Client ID and client secret. **Add**, then **Connect**, and
   approve on GitHub.
5. Check on github.com/settings/installations: your App lists **only this repository**, and no
   other app Claude uses (for example one named "Claude") has **All repositories**.

**b. A Claude Project for your 2mem** (claude.ai or Claude Desktop):

1. **Projects → New project**, named for example `2mem`.
2. Open [claude-instructions.md](claude-instructions.md) and copy everything inside its fenced
   block. Replace `OWNER/REPO` (and `OWNER`, `REPO`) with your account and repository name, and
   `main` if your default branch has another name.
3. Paste it into the Project's **Instructions** and save. In a chat in this Project, make sure the
   connector from part a is switched on (the tools menu under the message box).

Talk to Claude about your 2mem in this Project, so it always has these instructions.

**c. Claude Code** (optional, in a clone): nothing to paste — it reads [`CLAUDE.md`](../CLAUDE.md)
and the conventions by itself. Install the local check (step 6) in its clone. It works with your
own `git` and `gh` sign-in.

**d. Start using it:** read [quickstart.md](quickstart.md).

## 10. Edit in Obsidian (optional)

[Obsidian](https://obsidian.md) can edit this knowledge base as a folder of notes. Its changes go
through the same check as everything else: they are never written straight to the main branch.
Skip this step if you will not use Obsidian. Needs a computer with `git` for the first setup.

**How a change flows.** The vault is a clone of this repository on its own branch, `obsidian`.
The Obsidian **Git** plugin commits your edits and syncs them every few minutes. The first sync
opens one pull request, "obsidian: update from vault"; the check runs, and if it passes the
pull request merges by itself (as a merge commit — the `obsidian` branch is kept). Changes made
anywhere else (Claude, the web) are copied onto `obsidian` after they merge, and arrive in the
vault on its next sync.

**a. Repository settings** (once, on GitHub):

1. **Settings → General → Pull Requests:** tick **Allow merge commits**, and **untick
   Automatically delete head branches** — it would delete `obsidian` after each merge. (The check
   already deletes the branches it merges; after merging a pull request by hand, click **Delete
   branch** yourself — never on the Obsidian pull request.)
2. **Settings → Actions → General:** tick **Allow GitHub Actions to create and approve pull
   requests**, so the vault's pull request can be opened for you. This is safe only while the
   ruleset requires **0 approvals** (step 4): if you ever require approvals, untick it, or the
   automation could supply an approval itself.

   **Organisation-owned repository:** this box can be greyed out until an organisation owner
   ticks the same option under **Organization settings → Actions → General → Workflow
   permissions**. That only *allows* repositories to turn it on; then tick it here as usual.

3. **Settings → Rules → Rulesets → New ruleset → Import a ruleset:** import
   [`setup/ruleset-obsidian.json`](ruleset-obsidian.json) (download it first, as in step 4). It
   stops the `obsidian` branch from being deleted or force-pushed (its history rewritten).

**b. The vault** (once per computer):

```bash
git clone https://github.com/OWNER/REPO.git
cd REPO
git switch obsidian 2>/dev/null || { git switch -c obsidian && git push -u origin obsidian; }
```

(The last line creates the `obsidian` branch the first time, and just switches to it on any later
computer.)

1. In Obsidian: **Open folder as vault** → choose the `REPO` folder.
2. **Settings → Community plugins → Turn on community plugins → Browse**, find **Git** (by
   Vinzent), **Install**, then **Enable**.
3. Quit Obsidian, then copy the starter settings into the vault's hidden settings folder:

   ```bash
   cp -R setup/obsidian/. .obsidian/
   ```

   They set: markdown links written relative to the note (`../concept/x.md`), links updated when a
   note is renamed, new notes created in the folder you are in, pasted images saved in an
   `attachments/` folder beside the note, deleted notes sent to the system trash, `_templates/` as
   the templates folder, and the Git plugin to commit and sync 10 minutes after you stop typing
   (pulling first, on the `obsidian` branch only). `.obsidian/` is never committed.
4. Reopen Obsidian. Create notes inside a type folder (`concept/`, `procedure/`, …) and start each
   with **Insert template** — the templates carry the required fields.

**Signing in.** On a computer the plugin uses your normal `git` sign-in (the one `git clone`
used). On a phone or tablet it needs a **fine-grained personal access token** limited to **this
one repository** with **Contents: Read and write** and nothing else (GitHub → Settings → Developer
settings → Fine-grained tokens); enter it in the plugin's settings with your GitHub username.
Mobile support in the Git plugin is **experimental** and slow or unreliable on large vaults — a
computer is the dependable way. On a phone there is no terminal: create an empty vault, install
the Git plugin, run its commands **Clone an existing remote repo** and then **Switch to remote
branch** → `origin/obsidian` (the branch must already exist — create it from a computer first), and
set the options from `setup/obsidian/app.json` and `templates.json` by hand under **Settings →
Files and links** and **Templates**.

**Good to know:**

- **A failed check shows on GitHub, not in Obsidian.** Look at the open "obsidian: update from
  vault" pull request: its comment lists what to fix. Fix it in Obsidian; the next sync re-runs the
  check. Until then, *all* vault changes wait — they travel in one pull request.
- **Renaming, moving or deleting a note** is refused by the check unless you add the
  `allow-loss` label to the pull request (step 5), and the links in other notes' `relates_to`
  field are **not** updated by Obsidian — the check names each one to fix by hand.
- **A note created at the top of the vault** (`Untitled.md`, a daily note) is outside the document
  folders: the pull request waits until you move it into one (`concept/`, `procedure/`, …) or
  delete it. New notes land in the folder of the note you have open, so open one in the right
  folder first.
- **If the pull request says a note conflicts** (it was changed both in Obsidian and elsewhere),
  follow the comment: **Resolve conflicts** on GitHub, then the vault picks up the result.

---

## How the gate works (for the curious)

- **Every pull request** runs `.github/workflows/okf-lint.yml`. It uses the workflow and the
  checker **from the main branch**, never from the pull request, so a pull request cannot change
  the code that judges it. The allowed values (areas, statuses, types) are read from the pull
  request's own `_meta/conventions.md`, but a pull request that changes them is a rule change, so
  it is never merged automatically. The pull request's files are only read, never run.
- The check examines the pull request **as it would look merged** with the current main branch,
  and reports a commit status named `okf-lint` — the one the ruleset requires.
- If the check fails, **one** comment on the pull request lists what to fix; it is updated, not
  repeated, on each new attempt. It lists every problem anywhere in the repository (a rule change
  can break a document nobody touched), but advice-only warnings just for the documents the pull
  request changes.
- If the check passes, the **merge job** squash-merges the pull request (the Obsidian pull
  request: a merge commit, branch kept — step 10) — unless it comes from a
  fork, is a draft, has the `hold` label, or changes anything outside the document folders and
  `_originals/` (step 8). Then it leaves one comment saying why it is waiting.
- A second workflow, `.github/workflows/tests.yml`, runs the repository's own tests (including
  `tests/test_boundary.py`, which keeps the template self-contained) when a pull request changes
  anything outside the document folders. It is advice for the person merging that change, not a
  required check.
- Merges made by the automation do not start another run of the workflow (GitHub does not let
  automation trigger itself). That is fine: what was merged is exactly what was checked. The one
  thing the automation does start itself is the check on the Obsidian pull request, after it opens
  or updates it (`.github/workflows/obsidian.yml`).
- **The check stays "Expected — waiting for status"?** Actions may be off (**Settings → Actions**),
  or the run failed to start: open the **Actions** tab, find the run, and click **Re-run jobs**.
- **Your main branch is not called `main`?** Change `branches: [main]` near the top of
  `.github/workflows/okf-lint.yml` to its name (a governance pull request).
