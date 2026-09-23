#!/usr/bin/env python3
"""okf-lint.py — conformance validator for a 2mem knowledge base (Google OKF v0.2).

_meta/conventions.md is the single source of truth. Every closed vocabulary — record types,
statuses, areas, link relationships, link-entry keys — is read live from its ```valueset fences
on every run. This file holds no copy of any of them: changing a vocabulary is one edit to
conventions.md and nothing else.

Stdlib only, Python 3.8+. No dependencies by design: the same script runs from the pre-commit hook
and from the GitHub Action that is the required status check on the default branch.

Usage:
    okf-lint.py                                   # validate the whole repo
    okf-lint.py concept/sourdough.md [...]        # all errors; warnings/suggestions for these
    okf-lint.py --json                            # machine-readable result
    okf-lint.py --base origin/main                # also refuse content loss since a git ref
    okf-lint.py --base origin/main --allow-loss   # ...when the loss is intended

Exit 1 if there are errors; exit 0 if only warnings or suggestions.
"""

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
from urllib.parse import unquote

# --------------------------------------------------------------------------------------
# Structure — the shape of the schema, not its vocabularies
# --------------------------------------------------------------------------------------
#
# The value sets themselves come from conventions.md (load_value_sets). What lives here is only
# the behaviour the code attaches to two particular values, and the list of field *names*.

# The one unauthorable record type: third-party text and split masters, frozen once committed.
ORIGINAL_TYPE = "original"
ORIGINALS_DIR = "_originals"

# The one relationship a document may claim at most once, and that must be reciprocated.
REL_SINGLETON = "part_of"

# Fences conventions.md must declare. A missing one is an error, never a silent "anything goes".
REQUIRED_VALUE_SETS = ["type", "status", "area", "rel", "relates_to_key"]

# Required on every document; `area` is added for every type except `original`.
REQUIRED_FIELDS = ["type", "title", "description", "status"]
ORIGINAL_REQUIRED_FIELDS = ["creator", "rights"]

# Every top-level key a document may carry. Anything else is an error: a `tag:` typo would
# otherwise validate clean while the document silently drops out of every tag search.
KNOWN_FIELDS = [
    "type", "title", "description", "status", "area",
    "tags", "aliases", "relates_to",
    "sources", "generated", "verified",
    "creator", "rights", "license",
    "superseded_by", "derived_from", "derived_sections",
]

# These three must be written as one canonical `key: value` line — no quotes, no flow or block
# form — because exact-phrase code search (`"status: draft"`) is how they are queried.
CANONICAL_FIELDS = ["type", "status", "area"]

# Body shape per type — warnings only; the templates in _templates/ are the canonical shapes.
EXPECTED_HEADINGS = {
    "procedure": ["Steps"],
    "specification": ["Target state"],
    "decision": ["Context", "Decision", "Alternatives considered", "Consequences"],
    "analysis": ["Findings"],
}

# Paths that hold no documents.
NON_DOC_DIRS = {"_meta", "_templates", "setup", "tests", ".github", ".githooks", ".git"}
NON_DOC_ROOT_FILES = {"README.md", "LICENSE", "LICENSE.md", "CLAUDE.md", "index.md"}

OKF_VERSION = "0.2"

# GitHub code search skips files larger than 384 KB; warn with some headroom.
SIZE_WARN_BYTES = 350000

# --base: a body losing this share or more since the base ref is refused without --allow-loss.
SHRINK_LIMIT = 0.25

TAG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FILENAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
HEADING_START_RE = re.compile(r"^(#{1,6})\s+")
URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
# A literal block scalar header: `|`, `|-`, `|+`, with an optional indentation digit either side
# of the chomping sign (Obsidian writes `|-2` for text that starts with a space).
BLOCK_HEADER_RE = re.compile(r"^\|(?:[1-9][+-]?|[+-][1-9]?)?$")
# Where a block scalar header can sit: `key: |`, `- |`, `- key: |`.
BLOCK_LINE_RE = re.compile(r"^(?P<indent> *)(?P<dash>- +)?(?:(?P<key>[^\s#'\"-][^:]*):[ ]+)?"
                           r"(?P<header>\|\S*)[ ]*(?:#.*)?$")
VALUESET_RE = re.compile(r"^```valueset\s+name=([a-z_]+)\s*$(.*?)^```", re.M | re.S)
# `key: value` exactly: one space, an unquoted single token, nothing after it.
CANONICAL_LINE_RE = re.compile(r"^([A-Za-z_]+): ([^\s\"'\[\]{}&*!|>%@`#,]\S*)$")

# A link-poor repo would otherwise bury real errors under hundreds of proposals.
MAX_SUGGESTIONS_PER_DOC = 5
# Below this length a title matches too much ordinary prose to be evidence of anything.
MIN_MENTION_LEN = 12
# A name recurring across this share of the repo is subject vocabulary, not a relationship —
# it belongs in `tags`. The floor keeps a young repo from calling its third mention "ambient".
AMBIENT_MENTION_SHARE = 0.05
AMBIENT_MENTION_FLOOR = 4


# --------------------------------------------------------------------------------------
# YAML subset parser (conventions.md, "Frontmatter — the accepted YAML subset")
# --------------------------------------------------------------------------------------

# --- body scanners -------------------------------------------------------------------------
# Document bodies are pull-request content, so everything run over them must take linear time: the
# obvious regexes for these four (named in each docstring, and checked equal to it by the tests)
# retry from every start position and go quadratic — 40 KB of `](` took ~20 s. Each scanner below
# returns exactly what its regex would, reading the text once.

def strip_html_comments(text):
    """`re.sub(r"<!--.*?-->", "", text, flags=re.S)`. HTML comments do not render, so links and
    wikilinks inside them are not links (the templates' guidance comments say "never [[wikilinks]]",
    and Obsidian's Templates plugin copies them in). An unclosed `<!--` is left as it is."""
    out, i = [], 0
    while True:
        start = text.find("<!--", i)
        end = text.find("-->", start + 4) if start >= 0 else -1
        if end < 0:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:start])
        i = end + 3


def find_wikilink(text):
    """`re.search(r"\\[\\[[^\\]]+\\]\\]", text)` -> the matched text, or None."""
    i = 0
    while True:
        start = text.find("[[", i)
        if start < 0:
            return None
        close = text.find("]", start + 2)
        if close < 0:
            return None
        if close > start + 2 and text.startswith("]]", close):
            return text[start:close + 2]
        i = close + 1   # every `[[` before this `]` stops at the same `]`, so it fails too


def md_link_targets(text):
    """`re.findall(r"\\]\\(([^)\\s#]*)(?:#[^)\\s]*)?\\)", text)`: each markdown link's target,
    `#fragment` dropped. Repo-absolute (`/concept/x.md`) and relative (`../concept/x.md`, what
    Obsidian writes) targets are both checked; URLs are not."""
    targets, start, target_end = [], None, None
    for m in _LINK_TOKEN_RE.finditer(text):
        tok = m.group()
        if tok == "](":
            if start is None:            # a `](` inside an open target ends where it does
                start, target_end = m.end(), None
        elif start is None:
            continue
        elif tok == ")":
            targets.append(text[start:m.start() if target_end is None else target_end])
            start = None
        elif tok == "#":
            if target_end is None:
                target_end = m.start()
        else:                            # whitespace: no link here
            start = None
    return targets


_LINK_TOKEN_RE = re.compile(r"\]\(|[)#\s]")


def match_heading(line):
    """`re.match(r"^(#{1,6})\\s+(.*?)\\s*#*$", line)` -> (hashes, text), or None. `line` has no
    newline (callers split on it)."""
    m = HEADING_START_RE.match(line)
    if not m:
        return None
    return m.group(1), line[m.end():].rstrip("#").rstrip()


class YamlSubsetError(Exception):
    def __init__(self, line_no, message):
        super().__init__("line %d: %s" % (line_no, message))
        self.line_no = line_no
        self.message = message


DQ_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t", "r": "\r"}


def _scan_quoted(s, start, line_no):
    """Read the quoted scalar beginning at s[start]. Return (value, index_after_close).

    The two quote styles escape differently, exactly as YAML says they do, and the difference
    is the whole reason this function exists:

      single  '…'   the ONLY escape is a doubled quote, `''` → `'`. A backslash is a backslash.
      double  "…"   backslash escapes, per DQ_ESCAPES. An unknown one is an error, not a guess.

    Every place that needs to know where a quoted string ends calls this, so the unquoting rule,
    the flow-entry split, and the comment strip cannot disagree about it.
    """
    q = s[start]
    i, buf = start + 1, []
    while i < len(s):
        ch = s[i]
        if q == "'":
            if ch == "'":
                if s[i + 1:i + 2] == "'":       # '' is a literal quote, not the end
                    buf.append("'")
                    i += 2
                    continue
                return "".join(buf), i + 1
        else:
            if ch == "\\":
                nxt = s[i + 1:i + 2]
                if not nxt:
                    break
                if nxt not in DQ_ESCAPES:
                    raise YamlSubsetError(
                        line_no, "unsupported escape '\\%s' in a double-quoted string "
                                 "(allowed: \\\" \\\\ \\/ \\n \\t \\r)" % nxt)
                buf.append(DQ_ESCAPES[nxt])
                i += 2
                continue
            if ch == '"':
                return "".join(buf), i + 1
        buf.append(ch)
        i += 1
    raise YamlSubsetError(line_no, "unterminated quoted string")


def _split_top(text, sep):
    """Split on `sep` at nesting depth 0, respecting quotes and brackets."""
    parts, buf, depth, i = [], [], 0, 0
    while i < len(text):
        ch = text[i]
        if ch in "\"'":
            try:
                _, end = _scan_quoted(text, i, 0)
            except YamlSubsetError:
                end = len(text)                 # let _scalar report it, with the real line number
            buf.append(text[i:end])
            i = end
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def _strip_comment(s):
    """Remove a trailing ` #` comment outside quotes (YAML plain-scalar rule)."""
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in "\"'":
            try:
                _, i = _scan_quoted(s, i, 0)
            except YamlSubsetError:
                return s                        # unterminated: not ours to report
            continue
        if ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i]
        i += 1
    return s


def _scalar(raw, line_no):
    s = raw.strip()
    if s[:1] in ("\"", "'"):
        value, end = _scan_quoted(s, 0, line_no)
        trailing = _strip_comment(s[end:]).strip()
        if trailing:
            raise YamlSubsetError(line_no, "unexpected text after quoted value: %r" % trailing)
        return value
    s = _strip_comment(s).strip()
    if s == "" or s in ("~", "null", "Null", "NULL"):
        return None
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    if re.match(r"^-?\d+$", s):
        return int(s)
    if re.match(r"^-?\d+\.\d+$", s):
        return float(s)
    if s[0] in "&*":
        raise YamlSubsetError(
            line_no, "unsupported YAML feature %r (anchors and aliases are outside the accepted "
                     "subset)" % s[0])
    if s[0] == ">":
        raise YamlSubsetError(
            line_no, "folded text ('>') is outside the accepted subset — use a literal block "
                     "('|' or '|-') or one quoted line")
    if s[0] == "|":
        raise YamlSubsetError(
            line_no, "a literal block must be written `key: |` (or `|-`, `|+`) with its text on "
                     "the following, more-indented lines — got %r" % s)
    return s


def _flow(raw, line_no):
    s = raw.strip()
    if s.startswith("["):
        if not s.endswith("]"):
            raise YamlSubsetError(line_no, "unterminated flow sequence")
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_scalar(p, line_no) for p in _split_top(inner, ",")]
    if s.startswith("{"):
        if not s.endswith("}"):
            raise YamlSubsetError(line_no, "unterminated flow mapping")
        inner = s[1:-1].strip()
        if not inner:
            return {}
        out = {}
        for p in _split_top(inner, ","):
            if ":" not in p:
                raise YamlSubsetError(line_no, "flow mapping entry without ':' — %r" % p.strip())
            k, v = p.split(":", 1)
            out[k.strip()] = _scalar(v, line_no)
        return out
    return None


def _value(raw, line_no):
    s = raw.strip()
    if s.startswith("[") or s.startswith("{"):
        return _flow(s, line_no)
    return _scalar(s, line_no)


def _encode_dq(value):
    """`value` as a double-quoted scalar that _scan_quoted reads back unchanged."""
    return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") \
        .replace("\t", "\\t").replace("\r", "\\r")


def _fold_block_scalars(fm_lines):
    """Rewrite each literal block scalar (`key: |-` plus its indented text) as one double-quoted
    line, so the line-based parser below never sees the block. This is how Obsidian writes any
    multi-line value; it is the only multi-line scalar form accepted.

    The block's text is every following line that is blank or indented deeper than the key (or
    the `-` of a bare list item). Its indentation is the indicator digit when there is one,
    otherwise that of its first non-blank line. Chomping: `|` keeps one final newline, `|-` none,
    `|+` all of them.
    """
    out, i = [], 0
    while i < len(fm_lines):
        line_no, line = fm_lines[i]
        m = BLOCK_LINE_RE.match(line)
        if not m or not (m.group("dash") or m.group("key")) \
                or not BLOCK_HEADER_RE.match(m.group("header")):
            out.append((line_no, line))
            i += 1
            continue
        header = m.group("header")
        base = len(m.group("indent")) + (len(m.group("dash") or "") if m.group("key") else 0)
        j, raw = i + 1, []
        while j < len(fm_lines):
            ln = fm_lines[j][1]
            if ln.strip(" ") and len(ln) - len(ln.lstrip(" ")) <= base:
                break
            raw.append(fm_lines[j])
            j += 1
        digit = [c for c in header if c.isdigit()]
        if digit:
            indent = base + int(digit[0])
        else:
            firsts = [len(ln) - len(ln.lstrip(" ")) for _, ln in raw if ln.strip(" ")]
            indent = firsts[0] if firsts else base + 1
        text = []
        for n, ln in raw:
            if not ln.strip(" "):
                text.append(ln[indent:])
            elif len(ln) - len(ln.lstrip(" ")) < indent:
                raise YamlSubsetError(n, "line is indented less than the first line of the "
                                         "'|' block above it")
            else:
                text.append(ln[indent:])
        trailing = 0
        while text and text[-1] == "":
            text.pop()
            trailing += 1
        value = "\n".join(text)
        if "+" in header:
            value += "\n" * (trailing + (1 if text else 0))
        elif "-" not in header and text:
            value += "\n"
        out.append((line_no, line[:m.start("header")] + _encode_dq(value)))
        i = j
    return out


def _frontmatter_lines(text):
    """Return (numbered frontmatter lines, index of the closing fence). Raises YamlSubsetError.

    The closing fence is an unindented `---`: an indented one is text inside a literal block.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise YamlSubsetError(1, "file must begin with a '---' frontmatter fence")
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return [(n + 1, ln) for n, ln in enumerate(lines[1:i], start=1)], i
    raise YamlSubsetError(1, "frontmatter fence is never closed")


def parse_frontmatter(text):
    """Return (frontmatter_dict, body_string). Raises YamlSubsetError."""
    fm_lines, end = _frontmatter_lines(text)
    body = "\n".join(text.split("\n")[end + 1:])
    fm_lines = _fold_block_scalars(fm_lines)

    data = {}
    i = 0
    while i < len(fm_lines):
        line_no, line = fm_lines[i]
        if "\t" in line[:len(line) - len(line.lstrip())]:
            raise YamlSubsetError(line_no, "tab used for indentation — use spaces")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if line[:1] in (" ", "\t"):
            raise YamlSubsetError(line_no, "unexpected indentation — no key is open here")
        if ":" not in stripped:
            raise YamlSubsetError(line_no, "expected 'key: value' — got %r" % stripped)

        key, rest = stripped.split(":", 1)
        key = key.strip()
        if not key:
            raise YamlSubsetError(line_no, "empty key")
        if key in data:
            raise YamlSubsetError(line_no, "duplicate key '%s' — the second value would "
                                           "silently replace the first" % key)
        rest_clean = _strip_comment(rest).strip() if not rest.strip()[:1] in ("\"", "'") \
            else rest.strip()

        if rest_clean:
            data[key] = _value(rest, line_no)
            i += 1
            continue

        # Block: gather the indented run that follows.
        block = []
        j = i + 1
        while j < len(fm_lines):
            ln_no, ln = fm_lines[j]
            if ln.strip() == "" or ln.strip().startswith("#"):
                block.append((ln_no, ln))
                j += 1
                continue
            if not ln[:1].isspace():
                break
            block.append((ln_no, ln))
            j += 1
        data[key] = _parse_block(block, line_no)
        i = j

    return data, body


def _parse_block(block, parent_line):
    entries = [(n, ln) for n, ln in block if ln.strip() and not ln.strip().startswith("#")]
    if not entries:
        return None
    first = entries[0][1].strip()
    if first.startswith("- "):
        return _parse_block_seq(entries)
    return _parse_block_map(entries)


def _parse_block_map(entries):
    out = {}
    for line_no, line in entries:
        s = line.strip()
        if s.startswith("- "):
            raise YamlSubsetError(line_no, "sequence item inside a mapping block")
        if ":" not in s:
            raise YamlSubsetError(line_no, "expected 'key: value' — got %r" % s)
        k, v = s.split(":", 1)
        out[k.strip()] = _value(v, line_no)
    return out


def _parse_block_seq(entries):
    items = []
    current = None       # dict being accumulated for a multi-line mapping item
    current_indent = None
    for line_no, line in entries:
        indent = len(line) - len(line.lstrip())
        s = line.strip()
        if s.startswith("- "):
            rest = s[2:].strip()
            if rest.startswith("{") or rest.startswith("["):
                items.append(_value(rest, line_no))
                current = None
            elif ":" in rest and not rest[:1] in ("\"", "'"):
                k, v = rest.split(":", 1)
                current = {k.strip(): _value(v, line_no)}
                current_indent = indent + 2
                items.append(current)
            else:
                items.append(_scalar(rest, line_no))
                current = None
        elif s == "-":
            raise YamlSubsetError(line_no, "empty sequence item")
        else:
            if current is None:
                raise YamlSubsetError(
                    line_no, "continuation line with no open sequence item — %r" % s)
            if indent < current_indent:
                raise YamlSubsetError(line_no, "under-indented continuation — %r" % s)
            if ":" not in s:
                raise YamlSubsetError(line_no, "expected 'key: value' — got %r" % s)
            k, v = s.split(":", 1)
            current[k.strip()] = _value(v, line_no)
    return items


def _non_canonical(text, fields):
    """Names in `fields` whose top-level line is not the canonical `key: value` form."""
    try:
        fm_lines, _ = _frontmatter_lines(text)
    except YamlSubsetError:
        return []
    bad = []
    for _, line in fm_lines:
        m = re.match(r"^([A-Za-z_]+)\s*:", line)
        if not m or m.group(1) not in fields:
            continue
        c = CANONICAL_LINE_RE.match(line)
        if not c or c.group(1) != m.group(1):
            bad.append(m.group(1))
    return bad


# --------------------------------------------------------------------------------------
# Value sets — parsed live from conventions.md
# --------------------------------------------------------------------------------------

class Vocab:
    """The closed vocabularies, exactly as conventions.md declares them on this run."""

    def __init__(self, sets):
        self.sets = sets
        self.types = sets["type"]
        self.statuses = sets["status"]
        self.areas = sets["area"]
        self.rels = sets["rel"]
        self.entry_keys = sets["relates_to_key"]


def parse_value_sets(text):
    """{name: [values]} from every ```valueset name=<set> fence in `text`.

    One value per line: the first whitespace-delimited token is the value, the rest of the line
    is its description, for humans only. Returns (sets, problems).
    """
    out, problems = {}, []
    for m in VALUESET_RE.finditer(text):
        name = m.group(1)
        values = []
        for ln in m.group(2).split("\n"):
            ln = ln.strip()
            if ln:
                values.append(ln.split()[0])
        if name in out:
            problems.append("value set '%s' is declared twice — keep one fence" % name)
            continue
        if not values:
            problems.append("value set '%s' is empty" % name)
        out[name] = values
    return out, problems


def load_value_sets(root, report):
    """Vocab for this repo, or None (with errors reported) if conventions.md cannot supply it."""
    rel = "_meta/conventions.md"
    try:
        with open(os.path.join(root, "_meta", "conventions.md"), encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        report.error(rel, "cannot read the conventions file (%s) — every vocabulary the linter "
                          "enforces is declared there, so nothing can be validated without it"
                     % (e.strerror or e), "valueset")
        return None
    sets, problems = parse_value_sets(text)
    for p in problems:
        report.error(rel, p, "valueset")
    missing = [n for n in REQUIRED_VALUE_SETS if n not in sets]
    for name in missing:
        report.error(rel, "required value set '%s' is missing — add a ```valueset name=%s fence "
                          "listing one value per line" % (name, name), "valueset")
    if missing or problems:
        return None
    return Vocab(sets)


# --------------------------------------------------------------------------------------
# Per-document validation
# --------------------------------------------------------------------------------------

class Report:
    """Three channels. Only `errors` decides the exit code.

    Suggestions are proposals, not defects — a document with no `relates_to` is perfectly
    conformant. They exist because links are the field most likely to go silently unrecorded:
    nothing breaks when a relationship is missing, so nothing ever prompts for it.
    """

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.suggestions = []

    def error(self, path, msg, field=None):
        self.errors.append({"path": path, "field": field, "message": msg})

    def warn(self, path, msg, field=None):
        self.warnings.append({"path": path, "field": field, "message": msg})

    def suggest(self, path, msg, target=None, rel=None):
        self.suggestions.append({"path": path, "target": target, "rel": rel, "message": msg})

    @property
    def ok(self):
        return not self.errors


def _edit_distance(a, b):
    """Levenshtein distance, two-row."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _nearest(word, known, weight=None):
    """The closest candidate by edit distance, or None if nothing is plausibly a typo of it.

    `weight` (candidate -> number) breaks distance ties toward the more established candidate.
    """
    word = str(word)
    limit = max(1, len(word) // 3)
    best = None
    for cand in known:
        cand = str(cand)
        if cand == word:
            continue
        d = _edit_distance(word, cand)
        if d > limit:
            continue
        key = (d, -(weight(cand) if weight else 0), cand)
        if best is None or key < best[0]:
            best = (key, cand)
    return best[1] if best else None


def _did_you_mean(word, known):
    hint = _nearest(word, known)
    return " — did you mean '%s'?" % hint if hint else ""


def validate_doc(rel_path, text, report, vocab, size=None):
    """Validate one document. Returns the parsed frontmatter, or None if unparseable."""
    if "/" not in rel_path:
        # Typically a note Obsidian created with no note open (`Untitled.md`) or a daily note.
        # Say where it belongs, rather than list everything else wrong with a stray file.
        report.error(rel_path, "is at the top level of the repository, outside every type "
                               "folder — move it into the folder of its type (for example "
                               "concept/), or delete it", "type")
        return None
    try:
        fm, body = parse_frontmatter(text)
    except YamlSubsetError as e:
        report.error(rel_path, "frontmatter line %d: %s" % (e.line_no, e.message))
        return None

    if not isinstance(fm, dict) or not fm:
        report.error(rel_path, "frontmatter is empty")
        return None

    parts = rel_path.split("/")
    folder = parts[0]

    # --- file ---
    if not FILENAME_RE.match(parts[-1]):
        report.warn(rel_path, "filename should be lowercase-kebab-case.md")
    if size is not None and size >= SIZE_WARN_BYTES:
        report.warn(rel_path, "file is %d bytes — GitHub code search skips files over 384 KB, "
                              "so this document is close to becoming unsearchable. Split it."
                    % size, "size")

    # --- unknown keys ---
    for key in fm:
        if key not in KNOWN_FIELDS:
            report.error(rel_path, "unknown field '%s'%s (allowed: %s)"
                         % (key, _did_you_mean(key, KNOWN_FIELDS), ", ".join(KNOWN_FIELDS)), key)

    # --- canonical lines for the fields exact-phrase search depends on ---
    for key in _non_canonical(text, CANONICAL_FIELDS):
        report.error(rel_path, "'%s' must be one plain line, exactly `%s: <value>` — no quotes, "
                               "no list or block form, no trailing comment. Search for "
                               "\"%s: <value>\" only finds it written that way."
                     % (key, key, key), key)

    # --- type and folder ---
    t = fm.get("type")
    if t in (None, ""):
        report.error(rel_path, "missing required field 'type'", "type")
    elif not isinstance(t, str):
        report.error(rel_path, "'type' must be a single value", "type")
    elif t not in vocab.types:
        report.error(rel_path, "'type: %s' is not one of: %s%s"
                     % (t, ", ".join(vocab.types), _did_you_mean(t, vocab.types)), "type")
    elif t == ORIGINAL_TYPE and folder != ORIGINALS_DIR:
        report.error(rel_path, "'type: %s' is only valid under %s/ — originals are frozen there"
                     % (ORIGINAL_TYPE, ORIGINALS_DIR), "type")
    elif t != ORIGINAL_TYPE and folder != t:
        report.error(rel_path, "'type: %s' does not match its folder '%s' — the folder is the "
                               "type; expected %s/" % (t, folder, t), "type")
    is_original = t == ORIGINAL_TYPE or (t in (None, "") and folder == ORIGINALS_DIR)

    # --- remaining required fields ---
    required = REQUIRED_FIELDS[1:] + (ORIGINAL_REQUIRED_FIELDS if is_original else ["area"])
    for field in required:
        if fm.get(field) in (None, ""):
            why = " (originals must say who made the text and what use is permitted)" \
                if field in ORIGINAL_REQUIRED_FIELDS else ""
            report.error(rel_path, "missing required field '%s'%s" % (field, why), field)
        elif field == "creator" and isinstance(fm[field], list):
            if not fm[field] or any(not (isinstance(c, str) and c.strip()) for c in fm[field]):
                report.error(rel_path, "'creator' must be a name or a list of names", field)
        elif field in ("title", "description", "creator", "rights") \
                and not isinstance(fm[field], str):
            report.error(rel_path, "'%s' must be a string" % field, field)

    for field, allowed in (("status", vocab.statuses), ("area", vocab.areas)):
        v = fm.get(field)
        if v in (None, ""):
            continue
        if not isinstance(v, str) or v not in allowed:
            report.error(rel_path, "'%s: %s' is not one of: %s%s"
                         % (field, v, ", ".join(allowed), _did_you_mean(v, allowed)), field)

    if fm.get("license") is not None and not isinstance(fm["license"], str):
        report.error(rel_path, "'license' must be a string (an SPDX id or a URL)", "license")

    # --- tags / aliases ---
    tags = fm.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            report.error(rel_path, "'tags' must be a list", "tags")
        else:
            for tag in tags:
                if not isinstance(tag, str) or not TAG_RE.match(tag):
                    report.error(rel_path, "tag %r must be lowercase-kebab-case" % tag, "tags")
    aliases = fm.get("aliases")
    if aliases is not None:
        if not isinstance(aliases, list):
            report.error(rel_path, "'aliases' must be a list", "aliases")
        elif any(not isinstance(a, str) for a in aliases):
            report.error(rel_path, "every alias must be a string", "aliases")

    # --- relates_to ---
    rels = fm.get("relates_to")
    if rels is not None:
        if not isinstance(rels, list):
            report.error(rel_path, "'relates_to' must be a list", "relates_to")
        else:
            _check_relates_to(rel_path, rels, report, vocab)

    # --- split fields ---
    df = fm.get("derived_from")
    if df is not None and not (isinstance(df, str) and df.startswith("/")):
        report.error(rel_path, "'derived_from' must be one repo-absolute path (start with '/')",
                     "derived_from")
    ds = fm.get("derived_sections")
    if ds is not None and not isinstance(ds, list):
        report.error(rel_path, "'derived_sections' must be a list of headings",
                     "derived_sections")
    sb = fm.get("superseded_by")
    if sb is not None:
        if not isinstance(sb, list) or any(not (isinstance(p, str) and p.startswith("/"))
                                           for p in sb):
            report.error(rel_path, "'superseded_by' must be a list of repo-absolute paths",
                         "superseded_by")
        elif not is_original:
            report.error(rel_path, "'superseded_by' belongs on an original in %s/ (a master that "
                                   "was split). To retire a document, set 'status: deprecated' "
                                   "and link forward." % ORIGINALS_DIR, "superseded_by")

    # --- body ---
    # Originals keep whatever the source text was, so their body is not held to house style.
    rendered = strip_html_comments(body)
    if not is_original:
        found = find_wikilink(rendered)
        if found:
            report.error(rel_path, "wikilink %s — OKF v0.2 uses markdown links, e.g. "
                                   "[label](/concept/slug.md)" % found)
        headings = [m[1].strip() for m in (match_heading(ln) for ln in body.split("\n")) if m]
        for expected in (EXPECTED_HEADINGS.get(t, []) if isinstance(t, str) else []):
            if not any(h.lower() == expected.lower() for h in headings):
                report.warn(rel_path, "a '%s' normally has a '## %s' section" % (t, expected))
        if df and not ds:
            report.warn(rel_path, "'derived_from' without 'derived_sections' — the split "
                                  "coverage check cannot verify this part", "derived_sections")
        if ds and not df:
            report.warn(rel_path, "'derived_sections' without 'derived_from' — which original "
                                  "are these sections from?", "derived_from")

    links, escaping = _body_links(rel_path, rendered)
    if not is_original:
        for written in escaping:
            report.error(rel_path, "body link '%s' points outside the repository — link to a "
                                   "document in it, e.g. [label](../concept/slug.md)" % written)

    # Stashed for the repo-wide checks, so they read the parsed file rather than re-reading disk.
    fm["_body_links"] = sorted(links)
    fm["_link_text"] = links
    fm["_body"] = body
    fm["_original"] = is_original
    return fm


def _body_links(rel_path, body):
    """({repo-absolute target: as written}, [as written, for links that leave the repo]).

    Two forms count as links into the repo: repo-absolute (`/concept/x.md`) and, for `.md`
    targets, relative to this document's folder (`../concept/x.md`, `x.md` — what Obsidian
    writes). Both are `%XX`-decoded (Obsidian writes a space as `%20`). URLs are not ours.
    """
    links, escaping = {}, []
    folder = posixpath.dirname(rel_path)
    for written in md_link_targets(body):
        if not written or written.startswith("//") or URL_SCHEME_RE.match(written):
            continue
        path = unquote(written)
        if path.startswith("/"):
            links.setdefault(path, written)
            continue
        if not path.endswith(".md"):
            continue
        target = posixpath.normpath(posixpath.join(folder, path))
        if target == ".." or target.startswith("../"):
            escaping.append(written)
        else:
            links.setdefault("/" + target, written)
    return links, escaping


def _check_relates_to(rel_path, rels, report, vocab):
    singletons = 0
    for entry in rels:
        if not isinstance(entry, dict):
            report.error(rel_path, "each 'relates_to' entry must be a mapping, e.g. "
                                   "{path: /concept/x.md, note: \"why\"}", "relates_to")
            continue

        # Unknown keys are rejected, not ignored — a misspelled key that validates clean is a
        # relationship silently lost.
        for key in sorted(str(k) for k in entry if k not in vocab.entry_keys):
            report.error(rel_path, "relates_to entry has unknown key %r — an entry takes %s%s"
                         % (key, ", ".join(vocab.entry_keys),
                            _did_you_mean(key, vocab.entry_keys)), "relates_to")

        who = entry.get("path") or "?"
        if "path" not in entry or entry["path"] in (None, ""):
            report.error(rel_path, "each 'relates_to' entry needs a 'path'", "relates_to")
        elif not str(entry["path"]).startswith("/"):
            report.error(rel_path, "relates_to path %r must be repo-absolute (start with '/')"
                         % entry["path"], "relates_to")

        # `rel` is enforced only when it carries a value: an absent key and an explicit null are
        # the same statement, that this link claims nothing structural.
        kind = entry.get("rel")
        if kind is not None:
            if kind not in vocab.rels:
                report.error(rel_path, "rel %r is not in the 'rel' value set (%s)%s"
                             % (kind, ", ".join(vocab.rels), _did_you_mean(kind, vocab.rels)),
                             "relates_to")
            elif kind == REL_SINGLETON:
                singletons += 1

        # A typed link explains itself. An untyped one says only "see also", so it has to carry
        # the reason — otherwise relates_to fills up with links nobody can evaluate later.
        note = entry.get("note")
        if note is not None and not (isinstance(note, str) and note.strip()):
            report.error(rel_path, "relates_to note on '%s' must be a non-empty string" % who,
                         "relates_to")
        elif note is None and kind is None:
            report.error(rel_path, "untyped relates_to entry for '%s' needs a 'note' saying why "
                                   "the link is there — add one, or give the entry a 'rel' (%s)"
                         % (who, ", ".join(vocab.rels)), "relates_to")
    if singletons > 1:
        report.error(rel_path, "%d '%s' entries — a document has at most one parent. Two parents "
                               "means these are related documents, not parts."
                     % (singletons, REL_SINGLETON), "relates_to")


# --------------------------------------------------------------------------------------
# Repo-wide checks
# --------------------------------------------------------------------------------------

def is_document_path(rel):
    """True for a repo-relative path that should hold a document."""
    if not rel.endswith(".md"):
        return False
    parts = rel.split("/")
    if len(parts) == 1 and parts[0] in NON_DOC_ROOT_FILES:
        return False
    if parts[0] in NON_DOC_DIRS or any(p.startswith(".") for p in parts[:-1]):
        return False
    return True


def iter_docs(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if not d.startswith(".") and not (dirpath == root
                                                                and d in NON_DOC_DIRS))
        for fn in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/")
            if is_document_path(rel):
                yield rel


def check_index(root, report):
    """index.md is the OKF bundle root; it must declare the spec version it follows."""
    path = os.path.join(root, "index.md")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        report.error("index.md", "missing — the repo root needs an index.md whose frontmatter "
                                 "declares 'okf_version: %s'" % OKF_VERSION, "okf_version")
        return
    try:
        fm, _ = parse_frontmatter(text)
    except YamlSubsetError as e:
        report.error("index.md", "frontmatter line %d: %s" % (e.line_no, e.message),
                     "okf_version")
        return
    if str(fm.get("okf_version")) != OKF_VERSION:
        report.error("index.md", "frontmatter must declare 'okf_version: %s' (found %r)"
                     % (OKF_VERSION, fm.get("okf_version")), "okf_version")


def _in_root(root, target):
    """Absolute filesystem path for a repo-absolute link target, or None if it escapes root."""
    full = os.path.normpath(os.path.join(root, target.lstrip("/")))
    if full != root and not full.startswith(root.rstrip(os.sep) + os.sep):
        return None
    return full


def repo_checks(root, docs, report, vocab, scope=None):
    """docs: {rel_path: frontmatter}. Cross-document invariants.

    `scope` holds paths named on the command line. They are checked last so a collision is
    reported against the incoming document rather than against the one already committed.
    """
    titles, aliases = {}, {}
    scope_set = set(scope or ())
    ordered = sorted(docs.items(), key=lambda kv: (kv[0] in scope_set, kv[0]))
    for rel, fm in ordered:
        if not fm:
            continue
        title = fm.get("title")
        if isinstance(title, str):
            key = title.strip().lower()
            if key in titles:
                report.error(rel, "duplicate title %r — also in %s. Keep one canonical document "
                                  "and link to it." % (title, titles[key]), "title")
            else:
                titles[key] = rel
        for al in (fm.get("aliases") or []) if isinstance(fm.get("aliases"), list) else []:
            if not isinstance(al, str):
                continue
            key = al.strip().lower()
            if key in aliases:
                report.error(rel, "duplicate alias %r — also claimed by %s"
                             % (al, aliases[key]), "aliases")
            else:
                aliases[key] = rel

    _tag_checks(docs, report)
    _link_checks(root, docs, report, vocab)
    _split_checks(root, docs, report)
    # In targeted mode, suggest only for the named files — the pre-commit hook should talk
    # about what you just changed, not about the whole repo.
    _suggest_links(docs, report, scope)


def _tag_checks(docs, report):
    """Tags are open, so the risk is a fork: `bread-baking` next to `baking`. With no seed list to
    compare against, the signal is a tag nobody else uses — a typo, or a genuinely new topic."""
    usage = {}
    for rel, fm in docs.items():
        tags = fm.get("tags") if fm else None
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if isinstance(tag, str) and TAG_RE.match(tag):
                usage.setdefault(tag, set()).add(rel)
    for tag in sorted(usage):
        users = usage[tag]
        if len(users) != 1:
            continue
        hint = _nearest(tag, usage, weight=lambda c: len(usage[c]))
        msg = "tag '%s' is used by no other document" % tag
        if hint:
            msg += " — did you mean '%s' (used by %d)?" % (hint, len(usage[hint]))
        else:
            msg += " — fine if it is a new topic; otherwise reuse an existing tag"
        report.warn(next(iter(users)), msg, "tags")


def _link_checks(root, docs, report, vocab):
    """Links must resolve, and `part_of` must reciprocate."""
    def exists(target):
        full = _in_root(root, target)
        return bool(full) and os.path.isfile(full)

    # Everything each document points at, by either mechanism — a hub may enumerate its parts as
    # a readable table of body links rather than as frontmatter.
    refs = {}
    for rel, fm in docs.items():
        if not fm:
            continue
        out = set(fm.get("_body_links") or [])
        for entry in _entries(fm):
            if entry.get("path"):
                out.add(str(entry["path"]))
        refs[rel] = {t.lstrip("/") for t in out}

    for rel, fm in sorted(docs.items()):
        if not fm:
            continue
        for entry in _entries(fm):
            target = str(entry.get("path") or "")
            if not target.startswith("/"):
                continue                      # already reported by validate_doc
            if not exists(target):
                report.error(rel, "relates_to path '%s' does not exist" % target, "relates_to")
                continue
            if entry.get("rel") != REL_SINGLETON or REL_SINGLETON not in vocab.rels:
                continue
            hub = target.lstrip("/")
            if hub == rel:
                report.error(rel, "'%s' points at itself" % REL_SINGLETON, "relates_to")
            elif hub in docs and rel not in refs.get(hub, set()):
                report.error(rel, "declares '%s: %s' but %s never links back — a hub must list "
                                  "its parts, as a relates_to entry or as a markdown link in its "
                                  "body." % (REL_SINGLETON, target, hub), "relates_to")

        # Prose, not structured data, so a dangling body link is a warning. Originals are frozen
        # text: a dead link in one cannot be fixed, so it is not reported.
        if fm.get("_original"):
            continue
        for target in (fm.get("_body_links") or []):
            if target.endswith(".md") and not exists(target):
                written = (fm.get("_link_text") or {}).get(target, target)
                shown = "'%s'" % target if written == target \
                    else "'%s' (that is '%s')" % (written, target)
                report.warn(rel, "body links to %s, which does not exist" % shown)


def _entries(fm):
    rels = fm.get("relates_to")
    if not isinstance(rels, list):
        return []
    return [e for e in rels if isinstance(e, dict)]


def _split_checks(root, docs, report):
    """A master (an original with `superseded_by`) and its breakouts must agree, and every
    section of the master should have somewhere to live.

    The paths are structured data, so a dangling one is an error. Disagreement and uncovered
    headings are warnings: they mislead a reader, but lose nothing — the master is still there.
    """
    def exists(target):
        full = _in_root(root, target)
        return bool(full) and os.path.isfile(full)

    claims = {}         # original rel -> {breakout rel: [sections]}
    for rel, fm in sorted(docs.items()):
        if not fm or not isinstance(fm.get("derived_from"), str):
            continue
        origin = fm["derived_from"]
        if not origin.startswith("/"):
            continue                          # already reported by validate_doc
        if not exists(origin):
            report.error(rel, "derived_from '%s' does not exist" % origin, "derived_from")
            continue
        key = origin.lstrip("/")
        if not key.startswith(ORIGINALS_DIR + "/"):
            report.error(rel, "derived_from must point at an original in %s/, not '%s'"
                         % (ORIGINALS_DIR, origin), "derived_from")
            continue
        sections = fm.get("derived_sections")
        claims.setdefault(key, {})[rel] = [str(s).strip() for s in sections] \
            if isinstance(sections, list) else []

    for rel, fm in sorted(docs.items()):
        if not fm or not fm.get("_original"):
            continue
        sb = fm.get("superseded_by")
        parts = claims.get(rel, {})
        if not isinstance(sb, list):
            if parts:
                report.warn(rel, "%d document(s) declare derived_from this original (%s) but it "
                                 "has no 'superseded_by' listing them"
                            % (len(parts), ", ".join(sorted(parts))), "superseded_by")
            continue

        listed = set()
        for p in sb:
            if not isinstance(p, str) or not p.startswith("/"):
                continue                      # already reported by validate_doc
            if not exists(p):
                report.error(rel, "superseded_by path '%s' does not exist" % p, "superseded_by")
                continue
            listed.add(p.lstrip("/"))
            if p.lstrip("/") in docs and p.lstrip("/") not in parts:
                report.warn(rel, "lists '%s' in superseded_by, but that document does not "
                                 "declare 'derived_from: /%s'" % (p, rel), "superseded_by")
        for part in sorted(parts):
            if part not in listed:
                report.warn(part, "declares derived_from '/%s', but that original's "
                                  "superseded_by does not list it" % rel, "derived_from")

        headings = []
        for ln in (fm.get("_body") or "").split("\n"):
            m = match_heading(ln)
            if m and len(m[0]) > 1:     # H1 is the document title, not a content section
                headings.append("%s %s" % (m[0], m[1].strip()))
        claimed = {c.lstrip("#").strip().lower() for secs in parts.values() for c in secs}
        orphans = [h for h in headings if h.lstrip("#").strip().lower() not in claimed]
        if orphans:
            report.warn(rel, "%d heading(s) claimed by no breakout's derived_sections: %s"
                        % (len(orphans), "; ".join(orphans[:8])
                           + (" …" if len(orphans) > 8 else "")), "derived_sections")


def _suggest_links(docs, report, scope=None):
    """Propose relates_to entries the repo already has evidence for."""
    live = {rel: fm for rel, fm in docs.items() if fm and not fm.get("_original")}

    claims = {}         # title/alias (lowercased) -> [paths claiming it]
    by_origin = {}      # original -> breakouts
    by_source = {}      # sources[].resource -> documents citing it
    for rel, fm in live.items():
        names = [fm.get("title")]
        if isinstance(fm.get("aliases"), list):
            names += fm["aliases"]
        for name in names:
            if isinstance(name, str) and len(name.strip()) >= MIN_MENTION_LEN:
                claims.setdefault(name.strip().lower(), []).append(rel)
        if isinstance(fm.get("derived_from"), str):
            by_origin.setdefault(fm["derived_from"].lstrip("/"), []).append(rel)
        for s in (fm.get("sources") or []) if isinstance(fm.get("sources"), list) else []:
            if isinstance(s, dict) and s.get("resource"):
                by_source.setdefault(str(s["resource"]), []).append(rel)

    # Two documents answering to one name is a taxonomy problem, and guessing between them
    # would point the reader at the wrong document — so say so and match neither.
    names = {}
    for name in sorted(claims):
        owners = claims[name]
        if len(owners) > 1:
            report.warn(sorted(owners)[0], "'%s' is the title or alias of %d documents (%s) — "
                        "link suggestions skip it until the name is unique"
                        % (name, len(owners), ", ".join("/" + o for o in sorted(owners))))
        else:
            names[name] = owners[0]

    # Longest first, so a long title is not also read as a mention of a shorter one inside it.
    ordered = sorted(names, key=len, reverse=True)
    patterns = {n: re.compile(r"\b%s\b" % re.escape(n)) for n in ordered}

    def mentions(body):
        """Names appearing in `body`, each match consumed by the longest name that claims it."""
        hits, spans = [], []
        for name in ordered:
            for m in patterns[name].finditer(body):
                if any(s <= m.start() and m.end() <= e for s, e in spans):
                    continue
                spans.append((m.start(), m.end()))
                hits.append(name)
                break
        return hits

    # A name the whole repo uses is a subject, and subjects are `tags`. Proposing it as a link
    # nine times over teaches the reader to stop reading suggestions.
    threshold = max(AMBIENT_MENTION_FLOOR, int(len(live) * AMBIENT_MENTION_SHARE))
    mentioned_in = {}
    for rel, fm in live.items():
        for name in mentions((fm.get("_body") or "").lower()):
            if names[name] != rel:
                mentioned_in.setdefault(name, []).append(rel)
    ambient = {n for n, where in mentioned_in.items() if len(where) > threshold}

    for rel in sorted(scope if scope is not None else live):
        fm = live.get(rel)
        if not fm:
            continue
        entries = _entries(fm)
        linked = {str(e["path"]).lstrip("/") for e in entries if e.get("path")}
        has_parent = any(e.get("rel") == REL_SINGLETON for e in entries)
        body = (fm.get("_body") or "").lower()
        found = []                                    # (target, rel, why)

        # 1 — the body already links it; the frontmatter has not caught up.
        for target in (fm.get("_body_links") or []):
            t = target.lstrip("/")
            if t.endswith(".md") and t in live and t != rel and t not in linked:
                found.append((t, None, "the body already links it"))

        # 2 — this document's own name is repo-wide vocabulary; that is a tag, not 20 links.
        #     Ranked above the link proposals because acting on it is what stops the noise.
        for name in sorted(ambient):
            if names[name] == rel:
                found.append((None, None,
                              "%r appears in %d other documents — that is subject vocabulary, so "
                              "it belongs in their `tags`, not in %d `relates_to` entries"
                              % (name, len(mentioned_in[name]), len(mentioned_in[name]))))

        # 3 — split from the same original as other documents, but claiming no parent.
        origin = str(fm.get("derived_from") or "").lstrip("/")
        sibs = [s for s in by_origin.get(origin, []) if s != rel] if origin else []
        if sibs and not has_parent:
            found.append((None, REL_SINGLETON,
                          "split from the same original as %d other document(s) (%s) but claims "
                          "no parent — name the hub"
                          % (len(sibs), ", ".join(sorted(sibs)[:3]))))

        # 4 — cites the same source.
        for s in (fm.get("sources") or []) if isinstance(fm.get("sources"), list) else []:
            if not isinstance(s, dict) or not s.get("resource"):
                continue
            for sib in sorted(by_source.get(str(s["resource"]), [])):
                if sib != rel and sib not in linked:
                    found.append((sib, None, "cites the same source"))

        # 5 — the body names another document outright.
        for name in mentions(body):
            target = names[name]
            if target != rel and target not in linked and name not in ambient:
                found.append((target, None, "the body mentions %r" % name))

        seen, unique = set(), []
        for target, kind, why in found:
            # Targetless proposals are distinguished by their text, not by a path.
            key = (target, kind) if target else (target, kind, why)
            if key not in seen:
                seen.add(key)
                unique.append((target, kind, why))

        for target, kind, why in unique[:MAX_SUGGESTIONS_PER_DOC]:
            if target is None:
                report.suggest(rel, "%s (rel: %s)" % (why, kind) if kind else why, rel=kind)
            else:
                yaml = "{path: /%s%s}" % (target, ", rel: %s" % kind if kind else "")
                report.suggest(rel, "%s — consider %s" % (why, yaml), target="/" + target,
                               rel=kind)
        if len(unique) > MAX_SUGGESTIONS_PER_DOC:
            report.suggest(rel, "%d further suggestion(s) withheld — rerun after acting on these"
                           % (len(unique) - MAX_SUGGESTIONS_PER_DOC))


# --------------------------------------------------------------------------------------
# Content-loss guard (--base)
# --------------------------------------------------------------------------------------
#
# Every change reaches the default branch through a pull request, and this is the check that
# makes a destructive one visible before it merges: a deleted document, a body that lost a
# quarter or more of its text, or any change to the body of an original. Each is refused unless
# the loss is declared intended (--allow-loss; in CI, the PR label `allow-loss`), in which case it
# is still reported, as a warning, so the PR record says what was removed.
#
# Read-only git only: rev-parse, diff, show.

def _git(root, *args):
    return subprocess.run(["git", "-C", root] + list(args),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, encoding="utf-8", errors="replace")


def _split_body(text):
    """Body after the frontmatter — frontmatter churn is not content loss."""
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    return text[m.end():] if m else text


def base_checks(root, ref, report, allow_loss=False):
    """Compare the working tree against `ref`; flag deletions, heavy shrinks, originals edits."""
    how = "--allow-loss (the PR label 'allow-loss')"

    def loss(path, msg, field):
        if allow_loss:
            report.warn(path, "allowed by --allow-loss: " + msg, field)
        else:
            report.error(path, msg + " If this is intended, re-run with %s." % how, field)

    probe = _git(root, "rev-parse", "--verify", "--quiet", "%s^{commit}" % ref)
    if probe.returncode != 0:
        # An unresolvable ref is a wiring fault, not a content fault. Say so rather than passing
        # silently, which would leave the guard looking green while doing nothing.
        report.error("--base", "cannot resolve git ref %r in %s (%s)"
                     % (ref, root, probe.stderr.strip() or "not a commit"), "git")
        return
    # --relative: paths relative to root, and only under it, even when root is a subdirectory.
    # --no-renames: the path is a document's identity, so a rename is a delete plus a create —
    # it breaks every outside reference to the old path, and needs --allow-loss like a delete.
    diff = _git(root, "diff", "--relative", "--no-ext-diff", "--no-renames", "--name-status",
                "-z", ref, "--", "*.md")
    if diff.returncode != 0:
        report.error("--base", "git diff failed (%s)" % diff.stderr.strip(), "git")
        return

    # -z output is NUL-separated: STATUS \0 PATH for most entries, and STATUS \0 OLD \0 NEW for
    # renames and copies, which is why this walks the fields rather than splitting lines.
    fields = [f for f in diff.stdout.split("\0") if f]
    i = 0
    while i < len(fields):
        status = fields[i]
        if status[:1] in ("R", "C"):
            old, new, i = fields[i + 1], fields[i + 2], i + 3
        else:
            old = new = fields[i + 1]
            i += 2
        if not is_document_path(old):
            continue
        frozen = old.split("/")[0] == ORIGINALS_DIR

        if status.startswith("D"):
            what = "original" if frozen else "document"
            loss(old, "%s deleted (or renamed) since %s. Deleting is not a normal edit — to "
                      "retire a document, set 'status: deprecated' and link forward; a rename "
                      "must also update every link to the old path. To restore it: "
                      "git checkout %s -- %s." % (what, ref, ref, old), "deleted")
            continue
        if not (status.startswith("M") or status[:1] in ("R", "C")):
            continue

        before = _git(root, "show", "%s:./%s" % (ref, old))
        if before.returncode != 0:
            continue
        try:
            with open(os.path.join(root, new), encoding="utf-8") as fh:
                after_text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        b_body, a_body = _split_body(before.stdout), _split_body(after_text)

        if frozen:
            if b_body != a_body:
                loss(new, "the body of an original changed since %s. Originals in %s/ are "
                          "frozen: frontmatter may change, the text may not. Put commentary in "
                          "a breakout document instead." % (ref, ORIGINALS_DIR), "original")
            continue

        b, a = len(b_body), len(a_body)
        if not b or a >= b:
            continue
        removed = (b - a) / float(b)
        if removed >= SHRINK_LIMIT:
            loss(new, "body shrank %d%% since %s (%d -> %d characters). A cut this size is "
                      "refused unless declared intended."
                 % (round(removed * 100), ref, b, a), "shrank")


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

def _read(path):
    """(text, size_in_bytes). Text mode, so CRLF files parse like LF ones."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return text, os.path.getsize(path)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="okf-lint.py",
        description="OKF v0.2 conformance validator for a 2mem knowledge base. Vocabularies are "
                    "read from _meta/conventions.md on every run.",
        epilog="Exit status: 0 = no errors (warnings and suggestions allowed), 1 = errors.")
    ap.add_argument("paths", nargs="*",
                    help="documents to advise on (default: whole repo). Errors are always "
                         "reported for the whole repo; warnings and suggestions narrow to these.")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--quiet", action="store_true", help="print errors only")
    ap.add_argument("--suggest", action="store_true",
                    help="print only the relates_to link suggestions")
    ap.add_argument("--base", metavar="REF",
                    help="git ref to compare the working tree against: error on a deleted "
                         "document, a body that shrank 25%% or more, or any change to the body "
                         "of an original")
    ap.add_argument("--allow-loss", action="store_true",
                    help="with --base, report those losses as warnings instead of errors "
                         "(in CI: the PR label 'allow-loss')")
    ap.add_argument("--root", help="repo root (default: the directory above _meta/)")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root) if args.root else \
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    report = Report()
    docs = {}
    targets = set()
    vocab = load_value_sets(root, report)

    if vocab is not None:
        check_index(root, report)

        targeted = bool(args.paths)
        for p in args.paths:
            abs_p = os.path.abspath(p)
            if not os.path.isabs(p) and not os.path.exists(abs_p) \
                    and os.path.exists(os.path.join(root, p)):
                abs_p = os.path.join(root, p)
            rel = os.path.relpath(abs_p, root).replace(os.sep, "/")
            if rel.startswith(".."):
                report.error(p, "path is outside the repo root %s" % root)
                continue
            if is_document_path(rel):
                targets.add(rel)

        # Every document is validated, named or not: an error anywhere fails the run, so the
        # verdict never depends on which files were named (a vocabulary edit can break a document
        # nobody touched). Naming files narrows only the advice — warnings and suggestions.
        for rel in sorted(set(iter_docs(root)) | targets):
            try:
                text, size = _read(os.path.join(root, rel))
            except (OSError, UnicodeDecodeError) as e:
                report.error(rel, "unreadable: %s" % e)
                docs[rel] = None
                continue
            docs[rel] = validate_doc(rel, text, report, vocab, size)

        repo_checks(root, docs, report, vocab, sorted(targets) if targeted else None)
        if targeted:
            report.warnings = [w for w in report.warnings if w["path"] in targets]

    # Runs against the whole tree regardless of `paths`: a deletion is invisible to a per-file
    # check, because the file whose absence is the defect is never in the list.
    if args.base:
        base_checks(root, args.base, report, args.allow_loss)

    if args.json:
        print(json.dumps({"ok": report.ok, "checked": len(docs),
                          "errors": report.errors, "warnings": report.warnings,
                          "suggestions": report.suggestions}, indent=2))
        return 0 if report.ok else 1

    if args.suggest:
        for s in report.suggestions:
            print("suggest: %s: %s" % (s["path"], s["message"]))
        print("\n%d suggestion(s). Nothing here fails a run — these are proposals."
              % len(report.suggestions))
        return 0

    if not args.quiet:
        for w in report.warnings:
            loc = "%s%s" % (w["path"], ": %s" % w["field"] if w["field"] else "")
            print("warning: %s: %s" % (loc, w["message"]))
        if report.suggestions:
            # Name the same scope back, or the suggested command prints a different set than
            # the count just quoted.
            how = "--suggest %s" % " ".join(sorted(targets)) if args.paths else "--suggest"
            print("\n%d link suggestion(s) — run okf-lint.py %s to see them."
                  % (len(report.suggestions), how))
    sys.stdout.flush()  # keep warnings above errors when both streams hit a terminal
    for e in report.errors:
        loc = "%s%s" % (e["path"], ": %s" % e["field"] if e["field"] else "")
        print("ERROR: %s: %s" % (loc, e["message"]), file=sys.stderr)

    if report.errors:
        print("\n%d error(s), %d warning(s)." % (len(report.errors), len(report.warnings)),
              file=sys.stderr)
        return 1
    if not args.quiet:
        print("ok: %d document(s), %d warning(s), %d suggestion(s)."
              % (len(docs), len(report.warnings), len(report.suggestions)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
