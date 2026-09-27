"""Static safety checks on .github/workflows/*.yml.

Run from the repo root:  python3 -m unittest discover -s tests

okf-lint.yml runs on `pull_request_target`: it holds a write token while it reads a pull request's
files, possibly from a fork. These tests pin the rules that keep that safe (okf-lint.yml's
SECURITY MODEL), so a later edit cannot quietly undo them:

- every Python runs as `python3 -I`, so a `json.py` (or any module) in the pull request is never
  imported from the working directory or the script's folder;
- no step changes into the pull request's checkout (`cd pr`, `working-directory: pr`);
- no `run:` script contains `${{ }}`: expressions are expanded into the script text before bash
  reads it, so event data there is code. Values reach scripts through `env:` only;
- the job that reads the pull request never holds `contents: write`, and the job that holds it
  never checks anything out (the lint/merge split: see okf-lint.yml's SECURITY MODEL);
- the events the lint job ignores get a concurrency group of their own, so they never cancel a
  real run (the two copies of that test must match).

Text-based on purpose (stdlib only, no YAML library): comment lines are skipped, `run:` blocks are
found by indentation.
"""

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS = os.path.join(os.path.dirname(HERE), ".github", "workflows")

RUN_KEY_RE = re.compile(r"^(\s*)(-\s+)?run:\s*(.*)$")


def workflow_files():
    return sorted(os.path.join(WORKFLOWS, n) for n in os.listdir(WORKFLOWS)
                  if n.endswith((".yml", ".yaml")))


def code_lines(path):
    """(line number, line) for every line that is not a YAML/shell comment."""
    with open(path, encoding="utf-8") as fh:
        for no, line in enumerate(fh.read().split("\n"), 1):
            if not line.lstrip().startswith("#"):
                yield no, line


def run_blocks(path):
    """(line number, script text) for every `run:` value, inline or block (`|`, `>`)."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    blocks = []
    for i, line in enumerate(lines):
        m = RUN_KEY_RE.match(line)
        if not m:
            continue
        indent = len(m.group(1)) + len(m.group(2) or "")
        value = m.group(3)
        if not value.startswith(("|", ">")):
            blocks.append((i + 1, value))
            continue
        body = []
        for nxt in lines[i + 1:]:
            if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                break
            body.append(nxt)
        blocks.append((i + 1, "\n".join(body)))
    return blocks


def job_block(path, job):
    """The text of `jobs.<job>` (two-space indented job key), up to the next job."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"\n  %s:\n(.*?)(?=\n  [A-Za-z0-9_-]+:\n|\Z)" % re.escape(job), text, re.S)
    return m.group(1) if m else ""


def permissions_of(block):
    """{scope: access} from the job's `permissions:` mapping."""
    m = re.search(r"\n    permissions:\n((?:      [a-z-]+: [a-z]+.*\n)+)", "\n" + block + "\n")
    return dict(re.findall(r"^      ([a-z-]+): ([a-z]+)", m.group(1), re.M)) if m else {}


def folded(block, key, indent):
    """A `key: >-` (or inline) value at `indent` spaces, joined into one line."""
    lines = block.split("\n")
    for i, line in enumerate(lines):
        if line.startswith(" " * indent + key + ":"):
            value = line.split(":", 1)[1].strip()
            if value not in (">-", ">", "|"):
                return value
            body = []
            for nxt in lines[i + 1:]:
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                body.append(nxt.strip())
            return " ".join(b for b in body if b)
    return ""


def squash(s):
    return re.sub(r"\s+", "", s)


class TestWorkflowSafety(unittest.TestCase):

    def test_found_the_workflows_and_their_scripts(self):
        names = [os.path.basename(p) for p in workflow_files()]
        self.assertIn("okf-lint.yml", names)
        blocks = run_blocks(os.path.join(WORKFLOWS, "okf-lint.yml"))
        self.assertGreaterEqual(len(blocks), 6, "run: blocks not found — did the layout change?")
        self.assertTrue(any("<<'PY'" in text for _, text in blocks), "Report script not found")

    def test_every_python_is_isolated(self):
        for path in workflow_files():
            for no, line in code_lines(path):
                for m in re.finditer(r"\bpython[0-9.]*\b", line):
                    with self.subTest(file=os.path.basename(path), line=no):
                        self.assertRegex(line[m.start():], r"^python3 -I\b",
                                         "run Python as `python3 -I`: %s" % line.strip())

    def test_nothing_runs_inside_the_pull_request_checkout(self):
        bad = re.compile(r"\b(cd|pushd)\s+[\"']?(\./)?pr\b|working-directory:\s*[\"']?(\./)?pr\b")
        for path in workflow_files():
            for no, line in code_lines(path):
                with self.subTest(file=os.path.basename(path), line=no):
                    self.assertIsNone(bad.search(line), "use `git -C pr`: %s" % line.strip())

    def test_no_expressions_inside_run_scripts(self):
        for path in workflow_files():
            for no, text in run_blocks(path):
                with self.subTest(file=os.path.basename(path), line=no):
                    self.assertNotIn("${{", text, "pass the value through `env:` instead")

    def test_pull_request_job_sets_safe_python_path(self):
        with open(os.path.join(WORKFLOWS, "okf-lint.yml"), encoding="utf-8") as fh:
            found = re.search(r"\n\s+PYTHONSAFEPATH: '1'\n", fh.read())
        self.assertTrue(found, "okf-lint.yml: set PYTHONSAFEPATH: '1' in the pull request job's env")

    def test_lint_and_merge_jobs_keep_their_privileges_apart(self):
        wf = os.path.join(WORKFLOWS, "okf-lint.yml")
        lint, merge = job_block(wf, "okf-lint"), job_block(wf, "merge")
        self.assertTrue(lint and merge, "okf-lint / merge jobs not found — did the layout change?")
        self.assertEqual(permissions_of(lint),
                         {"contents": "read", "pull-requests": "write", "statuses": "write"})
        self.assertEqual(permissions_of(merge), {"contents": "write", "pull-requests": "write"})
        self.assertNotIn("uses:", merge, "the merge job must not check anything out")
        self.assertIn("--match-head-commit", merge)

    def test_ignored_events_never_cancel_a_real_run(self):
        wf = os.path.join(WORKFLOWS, "okf-lint.yml")
        with open(wf, encoding="utf-8") as fh:
            top = fh.read().split("\njobs:\n")[0]
        group = folded(top.split("\nconcurrency:\n")[1], "group", 2)
        job_if = folded(job_block(wf, "okf-lint"), "if", 4)
        m = re.search(r"github\.ref,(\(.*\)\)\))&&format\('-ignored-\{0\}',github\.run_id\)",
                      squash(group))
        self.assertTrue(m, "concurrency group lost its per-run group for ignored events: %s" % group)
        ignored = m.group(1)
        self.assertIn("!" + ignored[len("(github.event_name=='pull_request_target'&&"):-1],
                      squash(job_if), "the okf-lint job's `if:` and the concurrency group must "
                      "ignore exactly the same events")
        for label in ("'hold'", "'allow-loss'"):
            self.assertIn(label, ignored)

    def test_obsidian_sync_runs_only_where_the_vault_is_used(self):
        wf = os.path.join(WORKFLOWS, "okf-lint.yml")
        self.assertIn("vars.OBSIDIAN_SYNC == 'true'", folded(job_block(wf, "obsidian"), "if", 4))
        sync_if = folded(job_block(os.path.join(WORKFLOWS, "obsidian.yml"), "sync"), "if", 4)
        self.assertIn("vars.OBSIDIAN_SYNC == 'true'", sync_if)
        self.assertIn("github.ref_name == 'obsidian'", sync_if)


if __name__ == "__main__":
    unittest.main()
