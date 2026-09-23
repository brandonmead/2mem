# 2mem Conventions

**This file is the single source of truth for this knowledge base.** The templates, `okf-lint.py`,
the pre-commit hook and the GitHub workflow all derive from it. If a rule stated anywhere else
disagrees with this file, this file wins and the other surface is a bug. **Any session that reads or
writes here reads this file first.**

The linter has no built-in vocabularies: it parses the `valueset` blocks in §3 on every run, so
changing a vocabulary is one edit here. Changing this file is a **governance PR** — held for a human
merge (§8).

---

## 1. What this is, and the record types

A second memory: a **reference knowledge base** of what the owner knows and has decided, stored as
Google OKF v0.2 markdown with YAML frontmatter in one GitHub repository.

**It is not a task list or an inbox.** Work state is a frontmatter field or lives in a task tool;
never a checklist of to-dos in prose. A plan describes a target; it does not track who does what by
Friday.

### The arrival question decides the type

**The type answers what the reader needs on arrival, never what the document is about.** Subject
matter is `area` and `tags`. **The type is the top-level folder** — `path:` is the only typed filter
code search has, so the folder must carry it.

| Type | Reader arrives asking… | Examples |
|---|---|---|
| `concept` | *What is this, and why does it matter?* | a sourdough starter, a budgeting method |
| `procedure` | *How do I do this, step by step?* | renew a passport, winterize the garden hose |
| `reference` | *What is the value, spec, or fact?* | appliance model numbers, clothing sizes, vaccination dates |
| `specification` | *What should be built, and to what design?* | a shed plan, a home-network design |
| `decision` | *What was chosen, why, and what was rejected?* | which car to buy, which school to choose |
| `profile` | *Who or what is this named entity?* | a family doctor, a local club, a contractor |
| `analysis` | *What did we find when we looked?* | a utility-cost comparison, a mortgage-rate review |
| `narrative` | *What am I saying to an audience?* | a speech, an essay, a newsletter piece |
| `record` | *What happened, and when?* | meeting notes, a trip log, a repair history |
| `original` | *(not addressed to a reader — it is preserved text)* | a third-party article, a master document that was split |

Nine are **authorable**. `original` is not: it lives only in `_originals/`, is deposited verbatim,
and is exempt from body-shape checks (§5). The authoritative list is the `type` value set (§3).

**Claude picks the type, not the owner.** The owner says what they want remembered; Claude applies
the arrival question and the rules below. Asking a non-technical owner "concept or reference?" puts
the taxonomy's work on the person it exists to serve.

### Disambiguation

1. **`concept` vs `analysis`** — true until the idea changes → `concept`. True *as of a date*, and
   new evidence would revise it → `analysis`.
2. **`specification` vs `decision`** — a specification describes a target state; a decision records
   one choice and its rejected alternatives. Specs *link to* decisions; never inline them.
3. **`procedure` vs `specification`** — a procedure is run many times; a specification is built once
   and then exists.
4. **`profile` vs `concept`** — a profile is about a **named entity** (a person, organization,
   product, place). A concept is about an idea.
5. **`record` vs `analysis`** — a record says what happened; an analysis says what it means.

### Extend before you create

Before creating a document, **name what breaks if this content lived as a section of an existing
document** — a search that would return the wrong record, a `type` or `area` that no longer fits the
host, an original that needs its own frozen copy. If nothing breaks, it is a section: add it to the
closest existing document. A new document earns its own path only when it answers a different
arrival question, belongs to a different `area` than any suitable host, or would bloat the host past
what one reader needs on arrival — never merely because the subject has a name.

**On a close call, ask.** When reasonable writers could disagree on new-document versus section,
name the leading option with a one-line reason and let the owner choose. Ambiguous cases are
surfaced, not guessed.

---

## 2. Frontmatter

YAML between `---` fences at the very top of the file. **Required:** `type`, `title`,
`description`, `status`, plus `area` on the nine authorable types, plus `creator` and `rights` on
originals. Everything else is optional. A small required set keeps a failed lint from being the
most common thing a session sees; mandatory provenance teaches writers to fabricate it.

| Field | Required | Meaning | Example |
|---|---|---|---|
| `type` | yes | The record type; **must equal the top-level folder**. | `type: procedure` |
| `title` | yes | Human title. **Unique repo-wide** (case-insensitive). | `title: Renew a passport` |
| `description` | yes | One sentence. This is what search results show. | `description: Steps and documents to renew an adult passport by mail.` |
| `status` | yes | Is the document trustworthy? (`status` set, §3) | `status: stable` |
| `area` | authorable types | The one owning area; closed set (§3). Optional on originals. | `area: home` |
| `tags` | – | Open kebab-case list of what the doc is about (§6). | `tags: [travel, paperwork]` |
| `aliases` | – | Other names people search by. **Unique repo-wide** (case-insensitive). | `aliases: [passport renewal]` |
| `relates_to` | – | Links to other documents in this repo (§4). | `- {path: /reference/travel-documents.md, note: "where the passport number lives"}` |
| `sources` | – | OKF provenance: where content came from. List of `{resource, title?, last_modified?}`. | `- {resource: "https://example.gov/passports", title: Renewal guide}` |
| `generated` | – | OKF: who or what wrote it, and when. `{by, at}`. | `generated: {by: claude-opus/5, at: "2026-01-15T10:00:00Z"}` |
| `verified` | – | OKF: who checked it, and when. List of `{by, at}`. Never stamp without checking. | `- {by: "human:owner", at: "2026-01-20"}` |
| `creator` | originals | Who made the original text (§5). String or list of strings. | `creator: Jane Example` |
| `rights` | originals | Permitted-use statement for the original (§5). | `rights: "Personal reference copy; not for redistribution."` |
| `license` | – | SPDX id or URL, when the text carries a license. | `license: CC-BY-4.0` |
| `superseded_by` | masters | Paths of the documents a master original was split into (§5). | `superseded_by: [/concept/sourdough-starter.md, /procedure/feed-sourdough-starter.md]` |
| `derived_from` | breakouts | Path of the original this document was split from (§5). | `derived_from: /_originals/sourdough-master.md` |
| `derived_sections` | breakouts | Headings of that original this document takes over. | `derived_sections: ["## Feeding schedule", "## Troubleshooting"]` |

**Unknown top-level keys are an error.** A `tag:` typo that validated clean would silently drop the
document out of every tag search.

**`type`, `status` and `area` are written as canonical single lines:** `key: value` at the start of
the line, one space after the colon, unquoted, no trailing comment. Code search matches exact
phrases, so `"area: health"` finds nothing written as `area: "health"` or `area:  health`.

### Accepted YAML subset

The linter accepts a deliberately strict subset and errors, naming the line, on anything outside it.
The schema is closed and mostly machine-written; exotic YAML buys nothing and costs predictability.

```yaml
key: scalar                  # string, number, true/false, quoted string
key:                         # null: nothing after the colon (also null or ~)
key: [a, b, c]               # flow sequence of scalars
key: {a: 1, b: two}          # flow mapping of scalars
key:                         # block sequence of scalars
  - a
key:                         # block sequence of mappings
  - resource: /path
    title: Something
key:                         # block sequence of flow mappings (one entry per line)
  - {path: /concept/x.md, note: "why"}
key:                         # block mapping
  by: claude-opus/5
  at: "2026-01-15T10:00:00Z"
key: |-                      # literal block: text over several lines, kept as written
  First line.                #   (|- drops the final newline, | keeps one, |+ keeps all;
  Second line.               #    a digit, e.g. |-2, sets the indent when text starts with a space)
```

List-valued fields (`relates_to`, `sources`, `verified`) are written as block sequences, one entry
per line — the table examples above show a single entry. The literal block is the form Obsidian
writes for any value with a line break (§11); it may stand anywhere a scalar may, and everything in
it is text — a `#` or `---` inside it is not a comment or a fence. Not accepted: a flow sequence of
mappings (`[{…}]`), anchors/aliases (`&`/`*`), folded text (`>`), sequences inside sequences,
mappings deeper than two levels, tab indentation. Quote any value containing `: ` or starting with
`[`, `{` or `#`; ` #` starts a comment in a plain scalar. Quoting is YAML's: in single quotes the
only escape is `''`; in double quotes the escapes are `\" \\ \/ \n \t \r`, and any other backslash
escape is an error, not a guess.

---

## 3. Value sets

Every closed vocabulary is defined **once, here**, in a `valueset` fence. The linter reads these
fences directly. One value per line: the first whitespace-delimited token is the value, the rest of
the line is its description.

```valueset name=type
concept          what is this, and why does it matter
procedure        how do I do this, step by step
reference        what is the value, spec, or fact
specification    what should be built, and to what design
decision         what was chosen, why, and what was rejected
profile          who or what is this named entity
analysis         what did we find when we looked
narrative        what am I saying to an audience
record           what happened, and when
original         third-party or master text, preserved verbatim — `_originals/` only
```

```valueset name=status
draft            not yet trustworthy, or reconstructed rather than final
stable           trustworthy as written
deprecated       kept for history, not to be relied on
```

**Replace these with your own areas; one area per document, closed set.** An area is a part of life
that would *own* a document. Use lowercase words: a value that reads as a number, `true`/`false` or
`null` gets quoted by YAML writers such as Obsidian, and a quoted `area` fails the canonical-line
rule (§2). Pick the handful that, if they were separate filing cabinets, every
document would clearly belong in one of.

```valueset name=area
home             house, property, maintenance, household running
family           relationships, children, relatives, family events
health           physical and mental health, medical, fitness
work             job, career, business, professional practice
learning         study, skills, hobbies pursued to get better at something
community        faith, service, neighbours, clubs, civic life
```

```valueset name=rel
part_of          this document is an enumerated member of the target (max 1, reciprocated)
```

```valueset name=relates_to_key
path             repo-absolute path to another document in this repo
rel              what the link is for (see rel); omit or null for "see also"
note             why the link is there — required when there is no rel
```

**`area` tie-break:** the area whose loss would orphan the document. Anything else it serves goes in
`tags` — every area value is also a valid tag. A document spanning two areas is **one** document
plus links from elsewhere, never a duplicate.

**`tags` is deliberately not a value set** (§6).

### Changing a value set

1. **Check for a field that already says it.** A value duplicating an existing field is debt.
2. **Edit the fence here** in a governance PR. Nothing else needs changing — the linter reads it.
   One exception: a new `type` value is a new folder, so also add it to `CONTENT_RE` in
   `.github/workflows/okf-lint.yml` (§8); until then, PRs into that folder are held for a person.
3. **Removing or renaming a value is a migration:** documents carrying the old value fail lint.
   Rewrite them in the same PR.
4. **Say why in the PR description.** The squash commit is the permanent record.

---

## 4. Links: `relates_to` and body links

```yaml
relates_to:
  - {path: /concept/sourdough-starter.md, rel: part_of}
  - {path: /reference/kitchen-equipment.md, note: "which proofing box and scale the steps assume"}
```

Each entry is `{path, rel?, note?}` — keys from the `relates_to_key` set. **Unknown keys are an
error**: a misspelled `rell: part_of` that validated clean is a relationship silently lost.

- **Untyped entry = "see also" and must carry a `note`.** A bare see-also link cannot be evaluated
  six months later; the note says why it is there. A relationship that is real but not `part_of` is
  an untyped entry whose note says it in full — not a new `rel` value.
- **`part_of`: at most one per document**, and **reciprocated** — the target must list the member,
  either in its own `relates_to` or as a markdown link in its body (a hub can carry its parts as a
  readable table). Test: *if the target were deleted, would this document need rehoming?* A member
  of an enumerated set — yes. A document that merely shares a subject — no; that is `area`/`tags`.
- **Every `path` resolves.** A `relates_to` path to a missing file is an error; a broken body link
  into the repo is a warning (prose can point ahead of a document not yet written; `relates_to` cannot).

**Body links are markdown links, in one of two forms** — both render on github.com, both are
checked the same way:

- **repo-absolute:** `[sourdough starter](/concept/sourdough-starter.md)` — starts with `/`, means
  the same from any folder. Claude writes this form.
- **relative to the document's folder:** `[sourdough starter](../concept/sourdough-starter.md)`, or
  `[x](x.md)` for a document in the same folder — what Obsidian writes with the starter settings
  (§11). `%20` and other `%XX` escapes are decoded; a `#heading` part is ignored. A relative link
  that climbs out of the repository is an error.

**No `[[wikilinks]]`** — the linter errors on any `[[` outside an HTML comment. Links inside
`<!-- … -->` do not render, so they are not checked. Frontmatter paths (`relates_to`,
`derived_from`, `superseded_by`) are always repo-absolute.

**Tags vs. mentions.** Tag a document only for what it **is about**. A subject it names in passing
gets a body link at that spot instead — otherwise it turns up in every filtered search for a subject
it barely touches. A mention becomes a link only when the subject has a document; never guess a
target by fuzzy-matching titles. An unlinked mention is honest; a wrong link is not.

**Suggestions.** The linter also proposes links the repo already has evidence for (a body link not in
`relates_to`, a body mention of another document's title or alias, two documents sharing a
`derived_from` or a `sources` resource). Suggestions never fail a run and are never applied
automatically — an unreviewed inferred link is indistinguishable from a real one a week later.

---

## 5. `_originals/` — preserved text

`_originals/` holds text that must stay exactly as received: **third-party material** (an article, a
manual excerpt, a letter) and **masters** — composite documents that were split into typed parts.
Every file there has `type: original`.

**Frozen.** After an original lands, its **body may not change and the file may not be deleted**:
the linter's `--base` check refuses both unless the PR carries the `allow-loss` label. Frontmatter
may still change (e.g. adding `superseded_by`). The freeze is what lets a split be checked against
what it came from, and what keeps third-party text faithful.

**Dublin Core provenance tells owned text from borrowed text:**

- `creator` (required) — who made the text: a person's name (`Jane Example`), `human:<id>` for a
  known person in this instance, or `<producer>/<version>` for AI-produced text (`claude-opus/5`).
- `rights` (required) — what use is permitted, in plain words
  (`"Copyright the publisher; personal reference copy only."`).
- `license` (optional) — an SPDX identifier (`CC-BY-4.0`, `MIT`) or a license URL.

**Masters and breakouts.** Fusing types serves no reader, so a composite is split into typed
documents; the master is kept in `_originals/` as the guarantee against loss.

```yaml
# _originals/sourdough-master.md
type: original
superseded_by: [/concept/sourdough-starter.md, /procedure/feed-sourdough-starter.md]
```
```yaml
# procedure/feed-sourdough-starter.md
derived_from: /_originals/sourdough-master.md
derived_sections: ["## Feeding schedule", "## Troubleshooting"]
```

The linter compares the union of every breakout's `derived_sections` against the master's headings
and **reports any heading with no destination** — loss is caught at split time. Only composites and
third-party text go in `_originals/`; a single-type document is just written in its type folder,
with `sources:` for provenance.

---

## 6. Tags

Open, flat, lowercase kebab-case (`home-network`, `passport`). **No seed list** — the vocabulary is
whatever documents actually use.

**Fork detection:** the linter **warns** on a first-use tag (one no other document carries) and names
the nearest existing tag. `car-insurance` next to an existing `auto-insurance` is caught when it is
one document, not twenty. The write still lands; a genuinely new topic never waits on a conventions
edit. Before adding a tag, prefer one already in use.

`type`, `status`, `area` and `rel` stay strictly closed. Tags are the taxonomy's loose edge, on
purpose.

---

## 7. Validation

`_meta/okf-lint.py` — stdlib-only Python 3.8+. One implementation, two gates: the pre-commit hook
(`.githooks/pre-commit`, installed once per clone with `git config core.hooksPath .githooks`) and
the required `okf-lint` check on every PR.

**Records live in the nine type folders and `_originals/`.** `index.md` (declares `okf_version`),
`README.md`, `CLAUDE.md`, `LICENSE`, `_meta/`, `_templates/`, `setup/`, `tests/`, `.github/` and
`.githooks/` are exempt. Filenames are lowercase kebab-case `.md`; subfolders inside a type folder
are allowed for grouping and do not change `type`.

**Errors** (exit 1; block the merge):

- missing required field; unknown top-level key; value outside its value set (nearest value named)
- `type` ≠ folder; `original` outside `_originals/`; non-canonical `type`/`status`/`area` line;
  a `.md` file at the top level of the repo (other than the exempt root files)
- YAML outside the accepted subset (§2)
- duplicate `title` or alias (case-insensitive)
- `relates_to`: unknown key, bad `rel`, untyped entry without `note`, more than one `part_of`,
  unreciprocated `part_of`, unresolved `path`; any `[[` outside `_originals/`
- a relative body link that leads outside the repository
- original missing `creator` or `rights`; `derived_from` not pointing at an `_originals/` file

**Warnings** (exit 0; printed):

- expected body headings missing — `procedure`: `## Steps`; `specification`: `## Target state`;
  `decision`: `## Context`, `## Decision`, `## Alternatives considered`, `## Consequences`;
  `analysis`: `## Findings` (the templates in `_templates/` are the canonical shapes)
- first-use tag, with the nearest existing tag (§6)
- body link into the repo that does not resolve
- master heading claimed by no breakout's `derived_sections` (§5)
- **file larger than ~350 KB** — GitHub code search skips files over 384 KB, so the document is about
  to become unsearchable; split it

**Suggestions** (exit 0): proposed links (§4). `--suggest` prints them alone; `--json` emits
`{"ok", "errors", "warnings", "suggestions"}`.

Errors are always reported for the whole repo — per-document and cross-document alike — so the
verdict never depends on which files are named. Naming files narrows only warnings and suggestions.

### Content-loss guard: `--base <ref>`

Compares the tree against `<ref>` (the PR's base). **Error unless `--allow-loss`** (the PR label
`allow-loss`):

- a document was **deleted** — renaming is a delete plus a create, so a rename needs the label too,
  and must update every link to the old path in the same PR;
- a document's body **shrank by 25% or more**;
- the **body of anything under `_originals/` changed** at all.

Deletion is not a normal operation — superseding is: set `status: deprecated` and link forward. The
label makes a loss something asked for rather than something noticed later.

```bash
python3 _meta/okf-lint.py                        # whole repo
python3 _meta/okf-lint.py concept/x.md           # advice scoped to one file
python3 _meta/okf-lint.py --base origin/main     # plus the content-loss guard
```

---

## 8. Write path

**Every change reaches the default branch through a pull request.** The branch is protected: no
direct push, no force push, no bypass.

1. **Branch** off the default branch (`update-feed-sourdough-starter`).
2. **Commit** the change. In a local clone the pre-commit hook lints first.
3. **Open a PR.** **The PR title is the provenance:** `<surface>: <create|update|deprecate> <path>`,
   e.g. `claude-ai: update concept/sourdough-starter.md`, `claude-code: create procedure/renew-passport.md`,
   `web: update reference/clothing-sizes.md`. The description says what changed and why.
4. **`okf-lint` runs** (required check). The workflow and the linter code come from the base
   branch, so a PR cannot change the code that judges it. The vocabularies (§3) are read from the
   PR's own tree, so a vocabulary edit is judged by itself — but it touches `_meta/`, a governance
   path, so it can never merge automatically. On failure the check posts one plain-language comment
   on the PR; read it, fix the document on the same branch, and the check reruns. The comment lists
   every error in the tree, but warnings only for the documents the PR changes (§7).
5. **The merge job squash-merges** (the `obsidian` branch's PR: a merge commit, and the branch is
   kept — §11) when the check is green **and** the PR is from this repo (not a
   fork), not a draft, has no `hold` label, and every changed path is **content** — inside one of
   the nine type folders or `_originals/`. **Any other path is a governance path:** `_meta/`,
   `_templates/`, `setup/`, `tests/`, `.github/`, `.githooks/`, every root file (`index.md`,
   `README.md`, `CLAUDE.md`, `LICENSE`, `.gitignore`) and any new top-level folder. Governance PRs
   (including any change to this file) are checked the same way, then held for a human to merge.

Put a mutually linked pair in **one PR** — lint judges the PR's tree, so neither link dangles. In a
local clone, commit both files together.

**Updating an existing file over the API needs its current blob `sha`.** Read the file, keep the
`sha`, write with it. A stale `sha` is refused (409): someone changed the file since you read it —
re-read, re-apply your edit to what is there now, write again. Never overwrite blind.

**Keep any single write payload under ~40,000 characters.** Update a large document with targeted
edits, not a whole-file rewrite; create a large document as a skeleton, then extend it section by
section. Oversized payloads fail or truncate in transit, and a truncated body then trips the shrink
guard or, worse, lands as a shorter document.

**Failures.** A **transport failure** (timeout, tool error) gets exactly **one retry** — after first
checking whether the branch or PR already exists, so the retry does not duplicate it. A **red lint
check is a verdict**, not a transport failure: retrying returns the same result; fix the document.
**Never route around a failure** — no direct push, no second repo, no local file standing in for the
write. Say plainly that the write did not land and what is owed.

**Verify a consequential write** by reading the merged file back from the default branch, not by
trusting that a PR was opened.

---

## 9. Read path

| Surface | Filters | Example |
|---|---|---|
| Claude Code (local clone) | exact, regex | `rg -l '^area: health$' concept/` · `rg -l '^status: draft$' --glob '!_originals/**'` |
| GitHub MCP `search_code` | `repo:` `path:` quoted phrase `OR` `NOT` | `repo:OWNER/REPO path:concept "area: health"` · `repo:OWNER/REPO "status: draft" NOT path:_originals` |
| Claude Project with GitHub sync | none | whole-corpus context for a small instance |
| github.com | qualifiers + regex | browsing and reading by hand |

- Code search covers the **default branch only** and **skips files over 384 KB** — unmerged PRs and
  oversized documents are invisible to it.
- The canonical `type`/`status`/`area` lines (§2) are what make the quoted-phrase filters exact.
- **Tags are recall-only.** A tag word also matches body text, so a search for `"passport"` returns
  documents that mention it. Confirm against the fetched frontmatter before treating a hit as tagged.
- Search to find, then **fetch the file** before relying on it — a search snippet is not the document.

**Reading a record back.** A recorded status is a claim about when it was written, not about now.
Report it as what the record says ("the document lists X as open"), and before a recorded item
changes how work is done, confirm it still holds.

---

## 10. OKF version

Pinned to **OKF v0.2** (`GoogleCloudPlatform/knowledge-catalog`, `okf/SPEC.md`), declared as
`okf_version: 0.2` in `index.md`. A new OKF version is adopted deliberately, never automatically.
Impact of a bump: `index.md` (trivial) → **this file (the real work)** → `okf-lint.py` →
`_templates/*.md`.

---

## 11. Editing in Obsidian

Optional (setup: `setup/SETUP.md`, "Edit in Obsidian"). The vault is a clone of this repository on
the branch **`obsidian`**; the Obsidian Git plugin commits and syncs it. Every vault change reaches
the default branch the §8 way:

1. A push to `obsidian` opens (or reuses) **one** pull request, `obsidian` → default branch, titled
   `obsidian: update from vault`. The `okf-lint` check runs on it as on any PR.
2. The merge job merges it with a **merge commit** (not squash) and **keeps the branch**, so the
   vault's own commits stay part of the default branch's history and its next pull is clean.
3. After any merge into the default branch — from any surface — `obsidian` is brought up to date:
   fast-forwarded when it has nothing unmerged, otherwise the default branch is merged into it and
   the check re-runs on the open PR. The vault receives the change on its next pull. If both sides
   changed the same lines, nothing is merged and the PR comment says how to resolve it.

What Obsidian does that matters here:

- **It rewrites frontmatter in its own style** whenever a property is edited: indented lists,
  `key:` with nothing after it for an empty value, quotes around values that need them, a `|-`
  block for text with a line break, comments dropped. All of that is inside §2's subset, and it
  writes `type`/`status`/`area` as canonical lines.
- **Comments in frontmatter are dropped**, so a template's frontmatter comments are hints for a
  person reading the raw file, never rules. Every rule lives in this file.
- **Links are written relative** (`../concept/x.md`) with the starter settings — accepted (§4).
- **Renaming or moving a note** rewrites body links to it, but **not `relates_to` paths**: the
  check then reports the old path as unresolved — fix those by hand. A rename is also a delete plus
  a create, so the PR needs the `allow-loss` label (§7). Deleting a note is the same.
- **A note outside the nine type folders** — `Untitled.md` or a daily note at the vault root, a note
  in a new top-level folder — fails the check; any other file there (a canvas, an image) is a
  governance path (§8) and holds the vault PR. Either way: move it into a type folder, or delete it.
- **Attachments** (a pasted image, a PDF) land in an `attachments/` folder beside the note, so they
  sit inside a type folder and merge like content; the linter reads only `.md` files. At the vault
  root they would be governance and hold the PR. Keep them small — they stay in the history for
  good, and GitHub refuses any file over 100 MB.
- **One PR carries every vault change.** A document that fails the check holds back the rest until
  it is fixed. The check's result shows on GitHub, not in Obsidian.
