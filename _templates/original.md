---
type: original
title: <Title of the preserved text>
description: <One sentence.>
status: stable
creator: <Person's name, "human:<id>", or "<producer>/<version>" for AI-produced text>
rights: <What use is permitted, in plain words>
license: <SPDX id or URL, if the text carries a license — omit if none>
# superseded_by: the paths this master was split into — only on a master that was split
# superseded_by:
#   - /concept/<slug>.md
#   - /procedure/<slug>.md
---

<!--
ORIGINAL — not addressed to a reader; preserved text. Lives only in _originals/, deposited
verbatim, and exempt from the body-shape checks above. Two kinds:

  THIRD-PARTY TEXT — an article, a manual excerpt, a letter someone else wrote. `creator` and
  `rights` (required) tell owned text from borrowed text; `license` is optional.

  A MASTER — a composite document that was split into typed parts because fusing types
  serves no reader. Add `superseded_by:` listing the breakout documents. Each breakout then
  carries, on ITSELF (not here):
    derived_from: /_originals/<this-file>.md
    derived_sections: ["## Heading it took over", ...]
  The linter compares the union of every breakout's derived_sections against this file's
  headings and reports any heading with no destination.

FROZEN: once this file is committed, its body may not change and it may not be deleted — the
linter's --base check refuses both without the PR label allow-loss. Frontmatter may still
change (e.g. adding superseded_by later). Only third-party text and masters belong here; a
single-type document with known provenance is just written in its type folder, with
`sources:` for provenance.
-->

<!-- body below is preserved verbatim as received — do not restyle it to house conventions -->
