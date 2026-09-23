---
okf_version: 0.2
title: 2mem
description: A second memory — a governed knowledge base of what you know and have decided, meant to be read and written by you and your AI assistants.
---

# 2mem

OKF bundle root. **Format: Google Open Knowledge Format v0.2**
([specification](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)).

**All conventions live in one file: [_meta/conventions.md](/_meta/conventions.md).** Read it before
writing anything. The templates, the linter, the git hook, and CI all derive from it.

## Record types

Nine authorable types, each a top-level folder, each answering *what the reader needs on arrival* —
never what the document is about (that is `area` and `tags`):

| Type | Reader arrives asking… |
|---|---|
| [concept](/concept/) | What is this, and why does it matter? |
| [procedure](/procedure/) | How do I do this, step by step? |
| [reference](/reference/) | What is the value, spec, or fact? |
| [specification](/specification/) | What should be built, and to what design? |
| [decision](/decision/) | What was chosen, why, and what was rejected? |
| [profile](/profile/) | Who or what is this named entity? |
| [analysis](/analysis/) | What did we find when we looked? |
| [narrative](/narrative/) | What am I saying to an audience? |
| [record](/record/) | What happened, and when? |

Plus [`_originals/`](/_originals/) — preserved text (`type: original`), deposited verbatim, never
authored directly: third-party material and the masters that composite documents were split from.

## Non-content

| Path | Purpose |
|---|---|
| `_meta/` | `conventions.md` (source of truth), `okf-lint.py` |
| `_templates/` | One canonical body shape per authorable type, plus `original.md` |
| `setup/` | One-time setup steps for a new instance |
| `CLAUDE.md` | Pointer for Claude sessions working in a clone |
