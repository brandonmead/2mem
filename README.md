# 2mem

2mem is a **second memory**: a governed knowledge base that you and your AI assistants both read
before advising and write back to, with every change checked before it lands. It is not a task list
or an inbox — it is where what you know and have decided actually lives, in plain markdown, in a
GitHub repository you own.

## What's in this repo

- **Nine record-type folders** (`concept/`, `procedure/`, `reference/`, `specification/`,
  `decision/`, `profile/`, `analysis/`, `narrative/`, `record/`) plus `_originals/` for preserved
  text. The folder a document lives in *is* its type — it tells a reader (human or AI) what they're
  about to get before they open it.
- **`_meta/conventions.md`** — the single source of truth: the schema, the closed vocabularies, and
  the rules every other file here follows.
- **`_meta/okf-lint.py`** — a validator (Python, no dependencies) that checks every document against
  those conventions. It runs locally before each commit and again as a required check on every pull
  request, so nothing malformed reaches the default branch.
- **`_templates/`** — a starting shape for each record type.
- **`index.md`** — the root landing page.

## Getting started

**Start with [`setup/SETUP.md`](setup/SETUP.md).** It walks through the one-time steps to turn this
template into your own working instance.

**Day to day, read [`setup/quickstart.md`](setup/quickstart.md):** how to ask Claude to remember or
look something up, what happens to a change, and how to undo one.

This repo is built to be used as a GitHub template ("Use this template" → your own **private**
copy). This template repository itself is public; your copy holds personal notes, so keep it
private. Nothing you write into your copy is visible here.

## Self-contained by design

The template contains no link to any personal knowledge base: your instance's content lives only
in your own repository. `tests/test_boundary.py` enforces this for everything outside the document
folders.
