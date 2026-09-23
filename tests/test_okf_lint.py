"""Tests for _meta/okf-lint.py.

Run from the repo root:  python3 -m unittest discover -s tests

Each test copies a fixture mini-repo from tests/fixtures/ into a fresh temp directory, changes it,
and runs the linter there as a subprocess — the same way the hook and CI run it. Nothing is
written outside the temp directories.
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LINT = os.path.join(REPO, "_meta", "okf-lint.py")
FIXTURES = os.path.join(HERE, "fixtures")


class LintCase(unittest.TestCase):
    fixture = "clean"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="okf-lint-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "repo")
        shutil.copytree(os.path.join(FIXTURES, self.fixture), self.root)
        # Isolate git (and anything else) from the developer's own config.
        self.env = dict(os.environ, HOME=self.tmp, XDG_CONFIG_HOME=self.tmp,
                        GIT_CONFIG_NOSYSTEM="1",
                        GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.com",
                        GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.com")

    # --- helpers -------------------------------------------------------------------------

    def path(self, rel):
        return os.path.join(self.root, rel)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as fh:
            return fh.read()

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def replace(self, rel, old, new):
        text = self.read(rel)
        self.assertIn(old, text, "fixture drifted: %r not in %s" % (old, rel))
        self.write(rel, text.replace(old, new, 1))

    def run_raw(self, *args):
        return subprocess.run([sys.executable, LINT, "--root", self.root] + list(args),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, env=self.env, cwd=self.tmp)

    def lint(self, *args):
        p = self.run_raw("--json", *args)
        try:
            result = json.loads(p.stdout)
        except ValueError:
            self.fail("linter did not emit JSON (exit %d)\nstdout: %s\nstderr: %s"
                      % (p.returncode, p.stdout, p.stderr))
        result["exit"] = p.returncode
        return result

    def _find(self, items, path, text, field):
        return [i for i in items
                if (path is None or i["path"] == path)
                and text.lower() in i["message"].lower()
                and (field is None or i["field"] == field)]

    def assertError(self, result, path, text, field=None):
        self.assertEqual(result["exit"], 1, "expected exit 1")
        self.assertFalse(result["ok"])
        if not self._find(result["errors"], path, text, field):
            self.fail("no error on %s containing %r (field %r). Errors:\n%s"
                      % (path, text, field, json.dumps(result["errors"], indent=1)))

    def assertNoError(self, result, text):
        hits = self._find(result["errors"], None, text, None)
        self.assertFalse(hits, "unexpected error(s): %s" % json.dumps(hits, indent=1))

    def assertWarning(self, result, path, text, field=None):
        if not self._find(result["warnings"], path, text, field):
            self.fail("no warning on %s containing %r. Warnings:\n%s"
                      % (path, text, json.dumps(result["warnings"], indent=1)))

    def assertClean(self, result):
        self.assertEqual(result["errors"], [], json.dumps(result["errors"], indent=1))
        self.assertTrue(result["ok"])
        self.assertEqual(result["exit"], 0)


# ------------------------------------------------------------------------------------------
# Passing repos
# ------------------------------------------------------------------------------------------

class TestPasses(LintCase):

    def test_clean_repo_passes_with_no_warnings(self):
        r = self.lint()
        self.assertClean(r)
        self.assertEqual(r["warnings"], [])
        self.assertEqual(r["checked"], 7)

    def test_text_output_and_exit_code(self):
        p = self.run_raw()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("ok: 7 document(s), 0 warning(s)", p.stdout)

    def test_non_document_paths_are_not_linted(self):
        for rel in ("CLAUDE.md", "_templates/concept.md", "setup/SETUP.md", "tests/x.md",
                    ".github/notes.md", ".githooks/readme.md", "_meta/other.md"):
            self.write(rel, "no frontmatter here\n")
        self.assertClean(self.lint())

    def test_json_shape(self):
        self.replace("record/passport-renewed.md", "tags: [travel, paperwork]",
                     "tags: [travel, paperwork, postage]")
        self.replace("record/passport-renewed.md", "status: stable", "status: bogus")
        r = self.lint()
        self.assertEqual(set(r) - {"exit"},
                         {"ok", "checked", "errors", "warnings", "suggestions"})
        self.assertIs(r["ok"], False)
        self.assertIsInstance(r["checked"], int)
        for item in r["errors"] + r["warnings"]:
            self.assertEqual(set(item), {"path", "field", "message"})
        for item in r["suggestions"]:
            self.assertEqual(set(item), {"path", "target", "rel", "message"})
        self.assertTrue(r["errors"] and r["warnings"] and r["suggestions"])

    def test_original_body_is_not_held_to_house_style(self):
        self.replace("_originals/sourdough-notes.md", "It never", "It [[never]]")
        self.assertClean(self.lint())

    def test_quoted_title_and_escapes_are_fine(self):
        self.replace("concept/sourdough-starter.md", "title: Sourdough starter",
                     "title: 'The baker''s \"starter\"'")
        self.assertClean(self.lint())


class TestAlternateArea(LintCase):
    """The area set is instance data: a different conventions file, zero code edits."""
    fixture = "alt-area"

    def test_alternate_area_repo_passes(self):
        r = self.lint()
        self.assertClean(r)
        self.assertEqual(r["warnings"], [])

    def test_area_valid_elsewhere_is_rejected_here(self):
        self.replace("concept/composting.md", "area: garden", "area: home")
        self.assertError(self.lint(), "concept/composting.md", "'area: home' is not one of: "
                                                               "garden, workshop", "area")


# ------------------------------------------------------------------------------------------
# Errors
# ------------------------------------------------------------------------------------------

class TestErrors(LintCase):

    def test_missing_required_field(self):
        self.replace("reference/passport-renewal-checklist.md",
                     "description: The documents and steps a passport renewal needs.\n", "")
        self.assertError(self.lint(), "reference/passport-renewal-checklist.md",
                         "missing required field 'description'", "description")

    def test_missing_area_on_authorable_type(self):
        self.replace("reference/passport-renewal-checklist.md", "area: family\n", "")
        self.assertError(self.lint(), "reference/passport-renewal-checklist.md",
                         "missing required field 'area'", "area")

    def test_type_must_match_folder(self):
        self.replace("concept/sourdough-starter.md", "type: concept", "type: reference")
        self.assertError(self.lint(), "concept/sourdough-starter.md",
                         "does not match its folder 'concept'", "type")

    def test_unknown_type(self):
        self.replace("concept/sourdough-starter.md", "type: concept", "type: recipe")
        self.assertError(self.lint(), "concept/sourdough-starter.md",
                         "'type: recipe' is not one of", "type")

    def test_document_outside_a_type_folder(self):
        self.write("notes/loose.md", self.read("concept/sourdough-starter.md")
                   .replace("title: Sourdough starter", "title: Loose note"))
        self.assertError(self.lint(), "notes/loose.md", "does not match its folder 'notes'",
                         "type")

    def test_document_at_the_top_level(self):
        self.write("Untitled.md", "")
        r = self.lint()
        self.assertError(r, "Untitled.md", "outside every type folder", "type")
        self.assertEqual([e for e in r["errors"] if e["path"] == "Untitled.md"][1:], [])

    def test_unknown_top_level_key(self):
        self.replace("record/passport-renewed.md", "tags: [travel, paperwork]",
                     "tag: [travel, paperwork]")
        self.assertError(self.lint(), "record/passport-renewed.md",
                         "unknown field 'tag' — did you mean 'tags'?", "tag")

    def test_non_canonical_quoted_status(self):
        self.replace("record/passport-renewed.md", "status: stable", 'status: "stable"')
        r = self.lint()
        self.assertError(r, "record/passport-renewed.md", "must be one plain line", "status")
        # The value itself is valid — only the spelling is wrong.
        self.assertNoError(r, "is not one of")

    def test_non_canonical_block_and_flow_forms(self):
        self.replace("record/passport-renewed.md", "area: family", "area:\n  - family")
        self.replace("concept/sourdough-starter.md", "type: concept", "type: [concept]")
        self.replace("reference/passport-renewal-checklist.md", "status: stable",
                     "status: stable # reviewed")
        r = self.lint()
        self.assertError(r, "record/passport-renewed.md", "must be one plain line", "area")
        self.assertError(r, "concept/sourdough-starter.md", "must be one plain line", "type")
        self.assertError(r, "reference/passport-renewal-checklist.md", "must be one plain line",
                         "status")

    def test_bad_area(self):
        self.replace("record/passport-renewed.md", "area: family", "area: famly")
        self.assertError(self.lint(), "record/passport-renewed.md",
                         "'area: famly' is not one of: home, family", "area")

    def test_bad_status(self):
        self.replace("record/passport-renewed.md", "status: stable", "status: final")
        self.assertError(self.lint(), "record/passport-renewed.md", "'status: final'", "status")

    def test_bad_rel(self):
        self.replace("procedure/feed-a-starter.md", "rel: part_of", "rel: part-of")
        self.assertError(self.lint(), "procedure/feed-a-starter.md",
                         "rel 'part-of' is not in the 'rel' value set (part_of) — did you mean "
                         "'part_of'?", "relates_to")

    def test_unknown_relates_to_key(self):
        self.replace("record/passport-renewed.md", "note: \"the checklist",
                     "nots: \"the checklist")
        self.assertError(self.lint(), "record/passport-renewed.md",
                         "unknown key 'nots'", "relates_to")

    def test_duplicate_title(self):
        self.replace("decision/choose-a-dutch-oven.md", "title: Choose a Dutch oven",
                     "title: Feed a Starter")
        self.assertError(self.lint(), "procedure/feed-a-starter.md", "duplicate title",
                         "title")

    def test_duplicate_alias(self):
        self.replace("record/passport-renewed.md", "tags: [travel, paperwork]",
                     "tags: [travel, paperwork]\naliases: [Dutch oven choice]")
        self.assertError(self.lint(), "record/passport-renewed.md",
                         "duplicate alias 'Dutch oven choice'", "aliases")

    def test_broken_relates_to_path(self):
        self.replace("record/passport-renewed.md", "/reference/passport-renewal-checklist.md",
                     "/reference/passport-checklist.md")
        self.assertError(self.lint(), "record/passport-renewed.md",
                         "relates_to path '/reference/passport-checklist.md' does not exist",
                         "relates_to")

    def test_relative_relates_to_path(self):
        self.replace("record/passport-renewed.md", "{path: /reference/",
                     "{path: reference/")
        self.assertError(self.lint(), "record/passport-renewed.md", "must be repo-absolute",
                         "relates_to")

    def test_non_reciprocal_part_of(self):
        self.replace("concept/sourdough-starter.md",
                     "| Keep it alive | [Feed a starter](/procedure/feed-a-starter.md) |\n", "")
        self.assertError(self.lint(), "procedure/feed-a-starter.md", "never links back",
                         "relates_to")

    def test_more_than_one_part_of(self):
        self.replace("procedure/feed-a-starter.md",
                     "  - {path: /concept/sourdough-starter.md, rel: part_of}",
                     "  - {path: /concept/sourdough-starter.md, rel: part_of}\n"
                     "  - {path: /decision/choose-a-dutch-oven.md, rel: part_of}")
        self.assertError(self.lint(), "procedure/feed-a-starter.md",
                         "2 'part_of' entries", "relates_to")

    def test_untyped_link_without_note(self):
        self.replace("record/passport-renewed.md",
                     ', note: "the checklist that was followed"}', "}")
        self.assertError(self.lint(), "record/passport-renewed.md",
                         "untyped relates_to entry for '/reference/passport-renewal-checklist.md'"
                         " needs a 'note'", "relates_to")

    def test_original_missing_creator(self):
        self.replace("_originals/sourdough-notes.md", "creator: Example Baker\n", "")
        self.assertError(self.lint(), "_originals/sourdough-notes.md",
                         "missing required field 'creator'", "creator")

    def test_original_missing_rights(self):
        self.replace("_originals/sourdough-notes.md",
                     "rights: Shared by the author for personal, non-commercial use.\n", "")
        self.assertError(self.lint(), "_originals/sourdough-notes.md",
                         "missing required field 'rights'", "rights")

    def test_original_creator_may_be_a_list(self):
        self.replace("_originals/sourdough-notes.md", "creator: Example Baker",
                     "creator: [Example Baker, Second Baker]")
        self.assertClean(self.lint())
        self.replace("_originals/sourdough-notes.md", "creator: [Example Baker, Second Baker]",
                     "creator: []")
        self.assertError(self.lint(), "_originals/sourdough-notes.md",
                         "'creator' must be a name or a list of names", "creator")

    def test_original_outside_originals_dir(self):
        self.write("concept/stray-original.md",
                   "---\ntype: original\ntitle: Stray original\ndescription: Misfiled.\n"
                   "status: stable\ncreator: Someone\nrights: All rights reserved.\n---\n\nText.\n")
        self.assertError(self.lint(), "concept/stray-original.md",
                         "'type: original' is only valid under _originals/", "type")

    def test_superseded_by_path_must_exist(self):
        self.replace("_originals/sourdough-notes.md", "  - /procedure/feed-a-starter.md",
                     "  - /procedure/feed-a-sourdough-starter.md")
        self.assertError(self.lint(), "_originals/sourdough-notes.md",
                         "superseded_by path '/procedure/feed-a-sourdough-starter.md' does not "
                         "exist", "superseded_by")

    def test_links_inside_html_comments_are_not_links(self):
        self.replace("record/passport-renewed.md", "Lesson for next time",
                     "<!-- never [[wikilinks]]; see [x](/concept/nowhere.md) -->\nLesson for next time")
        r = self.lint()
        self.assertClean(r)
        self.assertEqual(r["warnings"], [])

    def test_wikilink_in_document(self):
        self.replace("record/passport-renewed.md", "Lesson for next time",
                     "See [[passport-renewal-checklist]]. Lesson for next time")
        self.assertError(self.lint(), "record/passport-renewed.md", "wikilink")

    def test_unparseable_frontmatter_names_the_line(self):
        self.replace("record/passport-renewed.md", "title: Passport renewed",
                     "title: Passport renewed\ntitle: Again")
        self.assertError(self.lint(), "record/passport-renewed.md", "duplicate key 'title'")

    def test_missing_value_set_fence(self):
        conv = self.read("_meta/conventions.md")
        start = conv.index("```valueset name=area")
        end = conv.index("```", start + 3) + 3
        self.write("_meta/conventions.md", conv[:start] + conv[end:])
        r = self.lint()
        self.assertError(r, "_meta/conventions.md", "required value set 'area' is missing",
                         "valueset")

    def test_missing_conventions_file(self):
        os.remove(self.path("_meta/conventions.md"))
        self.assertError(self.lint(), "_meta/conventions.md", "cannot read the conventions file",
                         "valueset")

    def test_index_must_declare_okf_version(self):
        self.replace("index.md", "okf_version: 0.2\n", "")
        self.assertError(self.lint(), "index.md", "okf_version: 0.2", "okf_version")

    def test_index_must_exist(self):
        os.remove(self.path("index.md"))
        self.assertError(self.lint(), "index.md", "missing", "okf_version")


# ------------------------------------------------------------------------------------------
# Warnings
# ------------------------------------------------------------------------------------------

class TestWarnings(LintCase):

    def test_first_use_tag_names_nearest_existing(self):
        self.replace("decision/choose-a-dutch-oven.md", "tags: [baking]", "tags: [bakng]")
        r = self.lint()
        self.assertClean(r)
        self.assertWarning(r, "decision/choose-a-dutch-oven.md",
                           "tag 'bakng' is used by no other document — did you mean 'baking' "
                           "(used by 3)?", "tags")

    def test_first_use_tag_with_nothing_close(self):
        self.replace("decision/choose-a-dutch-oven.md", "tags: [baking]",
                     "tags: [baking, cast-iron-care]")
        r = self.lint()
        self.assertClean(r)
        self.assertWarning(r, "decision/choose-a-dutch-oven.md",
                           "tag 'cast-iron-care' is used by no other document — fine if it is a "
                           "new topic", "tags")

    def test_tag_used_twice_is_quiet(self):
        self.replace("decision/choose-a-dutch-oven.md", "tags: [baking]",
                     "tags: [baking, kitchen-gear]")
        self.replace("procedure/bake-a-sourdough-loaf.md", "tags: [baking]",
                     "tags: [baking, kitchen-gear]")
        self.assertEqual(self.lint()["warnings"], [])

    def test_bad_tag_format_is_an_error(self):
        self.replace("decision/choose-a-dutch-oven.md", "tags: [baking]", "tags: [Baking_Day]")
        self.assertError(self.lint(), "decision/choose-a-dutch-oven.md",
                         "must be lowercase-kebab-case", "tags")

    def test_broken_body_link(self):
        self.replace("record/passport-renewed.md", "Lesson for next time",
                     "See [the old notes](/record/passport-renewed-last-time.md). Lesson")
        r = self.lint()
        self.assertClean(r)
        self.assertWarning(r, "record/passport-renewed.md",
                           "body links to '/record/passport-renewed-last-time.md', which does "
                           "not exist")

    def test_size_warning_at_350_kb(self):
        text = self.read("record/passport-renewed.md")
        filler = ("Filler line for the size check, repeated to cross the threshold.\n" * 6000)
        self.write("record/passport-renewed.md", text + "\n" + filler)
        self.assertGreaterEqual(os.path.getsize(self.path("record/passport-renewed.md")), 350000)
        r = self.lint()
        self.assertClean(r)
        self.assertWarning(r, "record/passport-renewed.md", "bytes", "size")

    def test_no_size_warning_below_threshold(self):
        text = self.read("record/passport-renewed.md")
        self.write("record/passport-renewed.md", text + "x" * (349000 - len(text)))
        self.assertEqual(self.lint()["warnings"], [])

    def test_missing_expected_heading(self):
        self.replace("procedure/feed-a-starter.md", "## Steps", "## How")
        r = self.lint()
        self.assertClean(r)
        self.assertWarning(r, "procedure/feed-a-starter.md", "'## Steps'")

    def test_uncovered_master_heading(self):
        self.replace("_originals/sourdough-notes.md", "## Baking day",
                     "## Storing the loaf\n\nWrap it in a cloth.\n\n## Baking day")
        r = self.lint()
        self.assertClean(r)
        self.assertWarning(r, "_originals/sourdough-notes.md",
                           "claimed by no breakout's derived_sections: ## Storing the loaf")

    def test_breakout_missing_from_superseded_by(self):
        self.replace("_originals/sourdough-notes.md", "  - /procedure/feed-a-starter.md\n", "")
        r = self.lint()
        self.assertClean(r)
        self.assertWarning(r, "procedure/feed-a-starter.md",
                           "superseded_by does not list it", "derived_from")

    def test_targeted_run_narrows_warnings_not_errors(self):
        self.replace("decision/choose-a-dutch-oven.md", "tags: [baking]", "tags: [bakng]")
        self.replace("record/passport-renewed.md", "status: stable", "status: final")
        r = self.lint("reference/passport-renewal-checklist.md")
        # Advice narrows to the named file: the unnamed document's first-use tag is not reported...
        self.assertEqual(r["warnings"], [])
        self.assertEqual(r["suggestions"], [])
        # ...but errors never do: an unnamed document's per-document error still fails the run.
        self.assertError(r, "record/passport-renewed.md", "final", "status")
        # Cross-document invariants cover the whole repo too.
        self.replace("decision/choose-a-dutch-oven.md", "title: Choose a Dutch oven",
                     "title: Passport renewed")
        r = self.lint("reference/passport-renewal-checklist.md")
        self.assertError(r, None, "duplicate title", "title")

    def test_naming_a_non_document_gives_errors_only(self):
        # The hook names every staged .md, exempt files included; those narrow advice to nothing.
        self.replace("decision/choose-a-dutch-oven.md", "tags: [baking]", "tags: [bakng]")
        r = self.lint("README.md")
        self.assertClean(r)
        self.assertEqual(r["warnings"], [])
        self.assertEqual(r["suggestions"], [])
        self.replace("record/passport-renewed.md", "status: stable", "status: final")
        r = self.lint("README.md")
        self.assertError(r, "record/passport-renewed.md", "final", "status")


# ------------------------------------------------------------------------------------------
# What Obsidian writes (conventions.md §2, §4, §11)
# ------------------------------------------------------------------------------------------

def _load_linter():
    spec = importlib.util.spec_from_file_location("okf_lint", LINT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestObsidianFixture(LintCase):
    """Hand-written in the exact form Obsidian's Properties editor saves: indented block lists,
    `key: ` nulls, quoted values, a `|-` description, relative body links."""
    fixture = "obsidian"

    def test_obsidian_style_repo_lints_clean(self):
        r = self.lint()
        self.assertClean(r)
        self.assertEqual(r["warnings"], [])
        self.assertEqual(r["checked"], 3)

    def test_relative_body_link_reciprocates_part_of(self):
        self.replace("concept/houseplant-watering.md",
                     "- [Water a houseplant](../procedure/water-a-houseplant.md)\n", "")
        self.assertError(self.lint(), "procedure/water-a-houseplant.md", "never links back",
                         "relates_to")


class TestBlockScalars(LintCase):

    def parse(self, fm):
        return _load_linter().parse_frontmatter("---\n" + fm + "---\nbody\n")[0]

    def test_chomping(self):
        self.assertEqual(self.parse("d: |-\n  one\n  two\n")["d"], "one\ntwo")
        self.assertEqual(self.parse("d: |\n  one\n  two\n")["d"], "one\ntwo\n")
        self.assertEqual(self.parse("d: |+\n  one\n  two\n\nx: 1\n")["d"], "one\ntwo\n\n")

    def test_text_that_looks_like_yaml_is_text(self):
        fm = self.parse("d: |-\n  # not a comment\n  ---\n  x: \"y\" \\ z\n\n  more\nn: 2\n")
        self.assertEqual(fm["d"], "# not a comment\n---\nx: \"y\" \\ z\n\nmore")
        self.assertEqual(fm["n"], 2)

    def test_indent_indicator_and_deeper_lines(self):
        self.assertEqual(self.parse("d: |-2\n    lead\n  two\n")["d"], "  lead\ntwo")
        self.assertEqual(self.parse("d: |-\n  a\n    b\n")["d"], "a\n  b")

    def test_nested_positions(self):
        fm = self.parse("g:\n  by: |-\n    a\n    b\n  at: x\n"
                        "r:\n  - path: /x.md\n    note: |-\n      c\n      d\n"
                        "l:\n  - |-\n    e\n    f\n  - g\n")
        self.assertEqual(fm["g"], {"by": "a\nb", "at": "x"})
        self.assertEqual(fm["r"], [{"path": "/x.md", "note": "c\nd"}])
        self.assertEqual(fm["l"], ["e\nf", "g"])

    def test_under_indented_line_is_an_error(self):
        mod = _load_linter()
        with self.assertRaises(mod.YamlSubsetError):
            mod.parse_frontmatter("---\nd: |-\n    a\n  b\n---\n")

    def test_block_description_lints_clean(self):
        self.replace("record/passport-renewed.md",
                     "description: When the family passports were renewed and how long it took.",
                     "description: |-\n  When the family passports were renewed.\n  And how long.")
        self.assertClean(self.lint())

    def test_block_on_a_canonical_field_is_an_error(self):
        self.replace("record/passport-renewed.md", "status: stable", "status: |-\n  stable")
        self.assertError(self.lint(), "record/passport-renewed.md", "must be one plain line",
                         "status")

    def test_folded_block_is_still_refused(self):
        self.replace("record/passport-renewed.md",
                     "description: When the family passports were renewed and how long it took.",
                     "description: >-\n  folded\n  text")
        self.assertError(self.lint(), "record/passport-renewed.md", "folded text")


class TestRelativeLinks(LintCase):

    DOC = "record/passport-renewed.md"

    def link(self, target):
        self.replace(self.DOC, "Lesson for next time", "See [it](%s). Lesson" % target)
        return self.lint()

    def test_valid_relative_link(self):
        for target in ("../reference/passport-renewal-checklist.md",
                       "../reference/passport-renewal-checklist.md#photos",
                       "../reference/passport-renewal%2Dchecklist.md",
                       "passport-renewed.md", "./passport-renewed.md"):
            with self.subTest(target=target):
                self.setUp()
                r = self.link(target)
                self.assertClean(r)
                self.assertEqual(r["warnings"], [])

    def test_broken_relative_link_warns_with_resolved_path(self):
        r = self.link("../reference/no%20such%20page.md")
        self.assertClean(r)
        self.assertWarning(r, self.DOC, "body links to '../reference/no%20such%20page.md' "
                                        "(that is '/reference/no such page.md'), which does not "
                                        "exist")

    def test_vault_root_form_resolves_like_github_does(self):
        # Obsidian's "absolute" link format has no leading slash; GitHub resolves it relative to
        # the file, so from record/ it points at record/reference/… and is broken.
        r = self.link("reference/passport-renewal-checklist.md")
        self.assertWarning(r, self.DOC, "that is '/record/reference/passport-renewal-checklist.md'")

    def test_link_escaping_the_repo_is_an_error(self):
        self.assertError(self.link("../../outside.md"), self.DOC,
                         "points outside the repository")

    def test_urls_and_non_documents_are_ignored(self):
        for target in ("https://example.org/x.md", "mailto:someone@example.org",
                       "//example.org/x.md", "photo.png", "#lesson"):
            with self.subTest(target=target):
                self.setUp()
                r = self.link(target)
                self.assertClean(r)
                self.assertEqual(r["warnings"], [])

    def test_relative_body_link_feeds_suggestions(self):
        self.replace("reference/passport-renewal-checklist.md", "Keep a photocopy",
                     "See [the last renewal](../record/passport-renewed.md). Keep a photocopy")
        r = self.lint("--suggest")
        self.assertTrue(any(s["path"] == "reference/passport-renewal-checklist.md"
                            and s["target"] == "/record/passport-renewed.md"
                            for s in r["suggestions"]), r["suggestions"])


# ------------------------------------------------------------------------------------------
# --base content-loss guard
# ------------------------------------------------------------------------------------------

class TestBase(LintCase):

    def git(self, *args):
        p = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false"]
                           + list(args), cwd=self.root, env=self.env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           universal_newlines=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout

    def setUp(self):
        super().setUp()
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "fixture")

    def test_unchanged_tree_passes(self):
        self.assertClean(self.lint("--base", "HEAD"))

    def test_deleted_document_refused_then_allowed(self):
        os.remove(self.path("record/passport-renewed.md"))
        self.assertError(self.lint("--base", "HEAD"), "record/passport-renewed.md",
                         "document deleted (or renamed) since HEAD", "deleted")
        r = self.lint("--base", "HEAD", "--allow-loss")
        self.assertClean(r)
        self.assertWarning(r, "record/passport-renewed.md", "allowed by --allow-loss", "deleted")

    def test_deleted_non_document_is_ignored(self):
        os.remove(self.path("README.md"))
        self.assertClean(self.lint("--base", "HEAD"))

    def _shrink(self, rel, keep):
        text = self.read(rel)
        head, body = text.split("\n---\n", 1)
        new_body = body[:int(len(body) * keep)]
        self.write(rel, head + "\n---\n" + new_body)
        return len(body), len(new_body)

    def test_thirty_percent_shrink_refused_then_allowed(self):
        before, after = self._shrink("record/passport-renewed.md", 0.70)
        r = self.lint("--base", "HEAD")
        self.assertError(r, "record/passport-renewed.md",
                         "body shrank 30%% since HEAD (%d -> %d characters)" % (before, after),
                         "shrank")
        r = self.lint("--base", "HEAD", "--allow-loss")
        self.assertClean(r)
        self.assertWarning(r, "record/passport-renewed.md", "body shrank 30%", "shrank")

    def test_small_shrink_passes(self):
        self._shrink("record/passport-renewed.md", 0.90)
        self.assertClean(self.lint("--base", "HEAD"))

    def test_frontmatter_churn_is_not_shrink(self):
        self.replace("record/passport-renewed.md",
                     "description: When the family passports were renewed and how long it took.",
                     "description: Renewal date.")
        self.assertClean(self.lint("--base", "HEAD"))

    def test_originals_body_edit_refused_then_allowed(self):
        self.replace("_originals/sourdough-notes.md", "once a week", "twice a week")
        self.assertError(self.lint("--base", "HEAD"), "_originals/sourdough-notes.md",
                         "the body of an original changed since HEAD", "original")
        self.assertClean(self.lint("--base", "HEAD", "--allow-loss"))

    def test_originals_growth_is_still_an_edit(self):
        self.write("_originals/sourdough-notes.md",
                   self.read("_originals/sourdough-notes.md") + "\nAn added paragraph.\n")
        self.assertError(self.lint("--base", "HEAD"), "_originals/sourdough-notes.md",
                         "the body of an original changed", "original")

    def test_originals_frontmatter_edit_allowed(self):
        self.replace("_originals/sourdough-notes.md", "license: CC-BY-4.0", "license: CC0-1.0")
        self.assertClean(self.lint("--base", "HEAD"))

    def test_rename_counts_as_delete(self):
        os.rename(self.path("record/passport-renewed.md"),
                  self.path("record/passports-renewed.md"))
        self.assertError(self.lint("--base", "HEAD"), "record/passport-renewed.md",
                         "deleted (or renamed) since HEAD", "deleted")
        self.assertClean(self.lint("--base", "HEAD", "--allow-loss"))

    def test_originals_delete_refused(self):
        os.remove(self.path("_originals/sourdough-notes.md"))
        self.assertError(self.lint("--base", "HEAD"), "_originals/sourdough-notes.md",
                         "original deleted (or renamed) since HEAD", "deleted")

    def test_new_file_allowed(self):
        self.write("record/loaf-baked.md",
                   "---\ntype: record\ntitle: First loaf baked\n"
                   "description: The first loaf from the new starter.\nstatus: stable\n"
                   "area: home\ntags: [baking]\n---\n\n# First loaf baked\n\nIt rose.\n")
        self.assertClean(self.lint("--base", "HEAD"))

    def test_unresolvable_ref_is_an_error(self):
        self.assertError(self.lint("--base", "no-such-branch"), "--base",
                         "cannot resolve git ref 'no-such-branch'", "git")

    def test_ci_invocation_narrows_advice_to_the_named_documents(self):
        # As okf-lint.yml runs it: cwd is the folder ABOVE the tree, `--root <tree>`, and the PR's
        # changed documents named after `--` with the tree's folder in front.
        self.replace("decision/choose-a-dutch-oven.md", "tags: [baking]", "tags: [bakng]")
        self.git("commit", "-qam", "a first-use tag already on the base branch")
        self.replace("reference/passport-renewal-checklist.md", "tags: [travel, paperwork]",
                     "tags: [travel, paperwork, visas]")
        os.remove(self.path("record/passport-renewed.md"))
        # `--root repo` (relative, resolved against the cwd as in CI) overrides the helper's
        # absolute --root: on macOS the temp dir sits under a symlink the cwd does not show.
        args = ["--root", "repo", "--base", "HEAD", "--allow-loss",
                 "--", "repo/reference/passport-renewal-checklist.md"]
        r = self.lint(*args)
        self.assertClean(r)
        # The PR's own document and its allowed deletion are reported; the base branch's
        # untouched first-use tag is not.
        self.assertWarning(r, "reference/passport-renewal-checklist.md", "visas", "tags")
        self.assertWarning(r, "record/passport-renewed.md", "allowed by --allow-loss", "deleted")
        self.assertEqual(self._find(r["warnings"], "decision/choose-a-dutch-oven.md", "", None), [])
        # The verdict never narrows: an error in a document the PR did not touch still fails it.
        self.replace("decision/choose-a-dutch-oven.md", "status: stable", "status: final")
        self.assertError(self.lint(*args),
                         "decision/choose-a-dutch-oven.md", "final", "status")

    def test_repo_in_a_subdirectory(self):
        # CI may lint a checkout nested inside a larger repo; paths must stay root-relative.
        outer = os.path.join(self.tmp, "outer")
        os.makedirs(outer)
        shutil.move(os.path.join(self.root, ".git"), os.path.join(outer, ".git"))
        shutil.move(self.root, os.path.join(outer, "repo"))
        self.root = os.path.join(outer, "repo")
        subprocess.run(["git", "-C", outer, "add", "-A"], env=self.env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "-C", outer, "-c", "core.hooksPath=/dev/null", "-c",
                        "commit.gpgsign=false", "commit", "-q", "-m", "nest"], env=self.env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertClean(self.lint("--base", "HEAD"))
        self.replace("_originals/sourdough-notes.md", "once a week", "twice a week")
        self.assertError(self.lint("--base", "HEAD"), "_originals/sourdough-notes.md",
                         "the body of an original changed", "original")


# ------------------------------------------------------------------------------------------
# The shipped templates (_templates/) lint clean once filled
# ------------------------------------------------------------------------------------------

class TestFilledTemplates(unittest.TestCase):
    """Each template, with its placeholders filled in the plainest way, is a valid document of its
    type in this repo's own conventions — with the guidance comments dropped (as Claude fills a
    template) and kept (as a person filling it in place might leave them)."""

    def fill(self, text, typ, dst, keep_comments):
        text = text.replace("<YYYY-MM-DDT00:00:00Z>", "2026-01-01T00:00:00Z") \
                   .replace("<YYYY-MM-DD>", "2026-01-01")
        if not keep_comments:
            text = re.sub(r"<!--.*?-->\n?", "", text, flags=re.S)
        # A placeholder relates_to row points at no real document: drop it, as a writer would.
        text = re.sub(r"^\s*(?:- )?\{path: /\w+/<[^>]+>\.md[^\n]*\n", "", text, flags=re.M)
        # A placeholder body link: point it at the document itself, which exists.
        text = re.sub(r"\(/\w+/<[^>]+>\.md\)", "(/%s)" % dst, text)
        # Every other <placeholder>, innermost first (`creator` nests `<id>` inside one); an HTML
        # comment `<!-- ... -->` is not a placeholder.
        placeholder = re.compile(r"<(?!!--)([^<>\n]+)>")
        while placeholder.search(text):
            text = placeholder.sub(
                lambda m: "Filled %s %s" % (typ, re.sub(r"[^\w ]", "", m.group(1))[:40]), text)
        return text

    def check(self, keep_comments):
        tmp = tempfile.mkdtemp(prefix="okf-lint-templates-")
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "_meta"))
        shutil.copy(os.path.join(REPO, "_meta", "conventions.md"), os.path.join(tmp, "_meta"))
        shutil.copy(os.path.join(REPO, "index.md"), tmp)
        names = sorted(n for n in os.listdir(os.path.join(REPO, "_templates")) if n.endswith(".md"))
        self.assertEqual(len(names), 10, names)
        for name in names:
            typ = name[:-3]
            dst = "%s/filled-%s.md" % ("_originals" if typ == "original" else typ, typ)
            with open(os.path.join(REPO, "_templates", name), encoding="utf-8") as fh:
                text = self.fill(fh.read(), typ, dst, keep_comments)
            os.makedirs(os.path.join(tmp, os.path.dirname(dst)), exist_ok=True)
            with open(os.path.join(tmp, dst), "w", encoding="utf-8") as fh:
                fh.write(text)
        p = subprocess.run([sys.executable, LINT, "--root", tmp, "--json"], stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, universal_newlines=True)
        r = json.loads(p.stdout)
        self.assertEqual(r["errors"], [], json.dumps(r["errors"], indent=1))
        self.assertEqual(r["warnings"], [], json.dumps(r["warnings"], indent=1))
        self.assertEqual((p.returncode, r["checked"]), (0, 10))

    def test_filled_templates_lint_clean(self):
        self.check(keep_comments=False)

    def test_filled_templates_with_guidance_comments_left_in(self):
        self.check(keep_comments=True)



# ------------------------------------------------------------------------------------------
# Linear time on hostile input: document bodies come from pull requests
# ------------------------------------------------------------------------------------------

class TestLinearTime(LintCase):
    """Each body scanner equals the regex it replaced (those regexes went quadratic: 40 KB of `](`
    took ~20 s), and a 200 KB document built to trip them lints in well under 2 s."""

    REFERENCE = {   # the replaced regexes: the scanners must return exactly what these do
        "strip_html_comments": lambda s: re.sub(r"<!--.*?-->", "", s, flags=re.S),
        "find_wikilink": lambda s: (lambda m: m.group(0) if m else None)(
            re.search(r"\[\[[^\]]+\]\]", s)),
        "md_link_targets": lambda s: re.findall(r"\]\(([^)\s#]*)(?:#[^)\s]*)?\)", s),
        "match_heading": lambda s: (lambda m: m.groups() if m else None)(
            re.match(r"^(#{1,6})\s+(.*?)\s*#*$", s)),
    }

    def test_scanners_equal_the_regexes_they_replace(self):
        import random
        mod = _load_linter()
        rnd = random.Random(7)
        alphabet = list("[]()#<!->a \t") + ["\xa0", "\u2028", "\x1c", "](", "<!--", "-->", "[[", "]]"]
        for _ in range(20000):
            s = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(0, 12)))
            for name, ref in self.REFERENCE.items():
                self.assertEqual(getattr(mod, name)(s), ref(s), "%s(%r)" % (name, s))

    def test_pathological_bodies_lint_fast(self):
        import time
        doc = "concept/sourdough-starter.md"
        base = self.read(doc)
        size = 200000
        for piece in ["](", "](#", "<!--", "[[", "\n# a" + "#" * size + "b", "#"]:
            with self.subTest(piece=piece[:6]):
                self.write(doc, base + "\n" + piece * max(1, size // len(piece)) + "\n")
                t = time.monotonic()
                self.lint()
                self.assertLess(time.monotonic() - t, 2.0)

if __name__ == "__main__":
    unittest.main()
