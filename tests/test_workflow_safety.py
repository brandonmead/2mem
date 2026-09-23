"""Static safety checks on .github/workflows/*.yml.

Run from the repo root:  python3 -m unittest discover -s tests

okf-lint.yml runs on `pull_request_target`: it holds a write token while it reads a pull request's
files, possibly from a fork. These tests pin the rules that keep that safe (okf-lint.yml's
SECURITY MODEL), so a later edit cannot quietly undo them:

- every Python runs as `python3 -I`, so a `json.py` (or any module) in the pull request is never
  imported from the working directory or the script's folder;
- no step changes into the pull request's checkout (`cd pr`, `working-directory: pr`);
- no `run:` script contains `${{ }}`: expressions are expanded into the script text before bash
  reads it, so event data there is code. Values reach scripts through `env:` only.

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


if __name__ == "__main__":
    unittest.main()
