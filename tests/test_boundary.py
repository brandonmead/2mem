"""The codebase is self-contained.

2mem is a template. Each copy (an "instance") holds one owner's knowledge in that owner's own
repository, and nowhere else. So the code around the documents — rules, linter, workflows, hook,
setup docs, templates, tests — must never point at anything outside the repository: not at the
author's own knowledge base, not at anyone's. A link like that would tie every copy of the template
to one person's data, or quietly pull someone else's content or code into your instance.

This test scans every tracked file OUTSIDE the document folders (the nine type folders and
`_originals/`) and fails on:

- a web address whose host is not in HOSTS below, or a github.com address whose owner is not the
  `OWNER` placeholder (or one of the few public repositories in GITHUB_REPOS);
- a GitHub `owner/repo` reference in a workflow `uses:`, a `gh ... --repo`, or an API path under
  repos/, other than this repository's placeholders and GitHub's own `actions/`;
- an absolute path into someone's home folder (macOS, Linux or Windows);
- an email address other than a reserved example or placeholder address;
- a way to pull another repository in: a `.gitmodules` file, a symbolic link (checked in every
  folder), a checkout with a `repository:` input, a secret other than the built-in GITHUB_TOKEN,
  or a git clone / curl / wget in a workflow or hook without a checkable, listed address.

The document folders are read from CONTENT_RE in .github/workflows/okf-lint.yml — the same list
that decides which pull requests merge by themselves — so the two can never disagree. Documents
are yours and may link anywhere; everything else is the template, and ships to every instance.

A legitimate new address (a public page every user of the template needs) is added to HOSTS in a
pull request that changes this file — a governance change, merged by a person.

Run from the repo root:  python3 -m unittest discover -s tests
"""

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORKFLOW = ".github/workflows/okf-lint.yml"

# Web hosts the template may name. Keep this list short and explain each entry.
HOSTS = {
    "github.com",             # only github.com/OWNER/... placeholders and github.com/settings
    "api.githubcopilot.com",  # GitHub's hosted MCP server (setup/SETUP.md, Connect Claude)
    "claude.ai",              # the connector's sign-in callback (setup/SETUP.md, Connect Claude)
    "obsidian.md",            # where to get Obsidian (setup/SETUP.md, Edit in Obsidian)
    "example.com",            # example addresses in docs and tests
    "example.org",
    "example.gov",            # conventions.md's sample `source:` value
}
GITHUB_OWNERS = {"OWNER"}          # the placeholder the setup docs use for "your account"
GITHUB_PAGES = {"settings"}        # github.com/settings/... is the reader's own account page
# Public repositories the template may link to, as owner/repo — the repository only, never the
# whole owner. Each must be a public reference every user needs.
GITHUB_REPOS = {
    "GoogleCloudPlatform/knowledge-catalog",   # the OKF specification (index.md)
}
ACTION_OWNERS = {"actions"}        # GitHub's own actions, pinned by commit in the workflows
REPO_PLACEHOLDERS = {"$REPO", "${REPO}", "OWNER/REPO", "{owner}/{repo}", "${{ github.repository }}"}
EMAIL_DOMAINS = {"example.com", "example.org"}

MESSAGE = ("These files link outside the repository. The template must be self-contained — an "
           "instance's knowledge lives only in its own repo, and nothing here may point at "
           "anyone's.\nIf an address is legitimate (a public page every user needs), add its "
           "host to HOSTS in tests/test_boundary.py; that is a governance change a person reviews.")

URL_RE = re.compile(r"https?://[^\s<>\"'`)\]]+")
GITHUB_RE = re.compile(r"(?<![\w.-])(?:www\.)?github\.com[/:]([A-Za-z0-9_.-]+)(?:/([A-Za-z0-9_.-]+))?")
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*[\"']?([^\s\"'#]+)")
REPO_FLAG_RE = re.compile(r"(?:--repo(?:=|\s+)|\bgh\b[^\n]*?\s-R\s+)[\"']?(\$\{\{[^}]*\}\}|[A-Za-z0-9_.${}/-]+)")
REPOS_PATH_RE = re.compile(r"(?<![\w.-])repos/(\$\{\{[^}]*\}\}|\$\{?\w+\}?|\{owner\}|[A-Za-z0-9_.-]+)"
                           r"(?:/([A-Za-z0-9_.{}$-]+))?")
# Home folders (macOS, Linux, Windows, tilde). Written so that this file does not match itself.
LOCAL_PATH_RE = re.compile(r"(?<![\w.~-])/(?:Users|home)/[^\s/]"
                           r"|(?<![\w])[A-Za-z]:\\{1,2}(?:Users|Documents and Settings)\b"
                           r"|(?<![\w~])~/[\w.-]")
EMAIL_RE = re.compile(r"(?<![\w.%+-])([\w.%+-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})\b")
NOREPLY_PLACEHOLDER_RE = re.compile(r"^[A-Z_]+(?:\+[A-Z_]+)?$")   # e.g. ID+LOGIN, at GitHub's noreply domain
SECRET_RE = re.compile(r"\bsecrets\s*(?:\.\s*(\w+)|\[)")
SECRET_EXPR_RE = re.compile(r"\$\{\{[^}]*\bsecrets\b[^}]*\}\}")
CROSS_CHECKOUT_RE = re.compile(r"^\s*repository:\s*\S")
FETCH_RE = re.compile(r"\b(?:git\s+clone|gh\s+repo\s+clone|git\s+submodule|git\s+remote\s+add|curl|wget)\b")


def content_pattern(root):
    """CONTENT_RE from the okf-lint workflow: the document folders, which this test skips."""
    try:
        with open(os.path.join(root, WORKFLOW), encoding="utf-8") as fh:
            m = re.search(r"^\s*CONTENT_RE:\s*'([^']+)'", fh.read(), re.M)
    except OSError:
        m = None
    if not m:
        raise AssertionError("could not read CONTENT_RE from %s — the list of document folders "
                             "this test must skip" % WORKFLOW)
    return re.compile(m.group(1))


def tracked_files(root):
    """(path, is_symlink) for every tracked file; every file under root if it is not a git clone."""
    p = subprocess.run(["git", "-C", root, "ls-files", "-s", "-z"],
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if p.returncode == 0 and p.stdout:
        out = []
        for entry in p.stdout.decode("utf-8", "surrogateescape").split("\0"):
            if entry:
                meta, path = entry.split("\t", 1)
                out.append((path, meta.split()[0] == "120000"))
        return out
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x != ".git"]
        for f in files:
            full = os.path.join(d, f)
            out.append((os.path.relpath(full, root).replace(os.sep, "/"), os.path.islink(full)))
    return out


def host_ok(url):
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    return host in HOSTS


def email_ok(local, domain):
    domain = domain.lower()
    if domain in EMAIL_DOMAINS or domain.endswith(".invalid"):
        return True
    return domain == "users.noreply.github.com" and bool(NOREPLY_PLACEHOLDER_RE.match(local))


def repo_ref_ok(first, second=None):
    if first.startswith("${{"):
        return re.sub(r"\s+", " ", first) == "${{ github.repository }}"
    if second is not None:
        return first in REPO_PLACEHOLDERS or "%s/%s" % (first, second) in REPO_PLACEHOLDERS
    return first in REPO_PLACEHOLDERS


def check_line(path, line):
    """Every reason this line links outside the repository."""
    found = []
    is_yaml = path.endswith((".yml", ".yaml"))
    is_automation = path.startswith((".github/", ".githooks/"))

    for url in URL_RE.findall(line):
        if not host_ok(url):
            found.append("web address outside the allowed hosts: %s" % url)
    for owner, repo in GITHUB_RE.findall(line):
        if owner not in GITHUB_OWNERS | GITHUB_PAGES and "%s/%s" % (owner, repo) not in GITHUB_REPOS:
            found.append("GitHub account or repository other than the OWNER placeholder: "
                         "github.com/%s" % owner)
    m = USES_RE.match(line)
    if m:
        ref = m.group(1)
        if not ref.startswith("./") and ref.split("/")[0] not in ACTION_OWNERS:
            found.append("workflow step or call from another repository: uses: %s" % ref)
    for ref in REPO_FLAG_RE.findall(line):
        if not repo_ref_ok(ref):
            found.append("gh command aimed at another repository: %s" % ref)
    for first, second in REPOS_PATH_RE.findall(line):
        if not repo_ref_ok(first, second or None):
            found.append("API path into another repository: %s/%s" % (first, second))
    for m in LOCAL_PATH_RE.finditer(line):
        found.append("absolute path on someone's computer: %s" % line[m.start():].split()[0])
    for local, domain in EMAIL_RE.findall(line):
        if not email_ok(local, domain):
            found.append("email address: %s@%s" % (local, domain))
    for name in SECRET_RE.findall(line):
        if name != "GITHUB_TOKEN":
            found.append("a secret other than GITHUB_TOKEN")
            break
    else:
        for expr in SECRET_EXPR_RE.findall(line):
            if not re.fullmatch(r"\$\{\{\s*secrets\.GITHUB_TOKEN\s*\}\}", expr):
                found.append("a secret other than GITHUB_TOKEN: %s" % expr)
    if is_yaml and CROSS_CHECKOUT_RE.match(line):
        found.append("checkout of another repository (a `repository:` input)")
    if is_automation and FETCH_RE.search(line) and not URL_RE.search(line):
        found.append("downloads from an address this test cannot check (use a literal, listed URL)")
    return found


def scan(root, content_re=None):
    """All violations under root, as 'path:line: reason' strings."""
    content_re = content_re or content_pattern(root)
    problems = []
    for path, is_link in sorted(tracked_files(root)):
        if is_link:
            problems.append("%s: symbolic link — it can point outside the repository; "
                            "replace it with a normal file" % path)
            continue
        if os.path.basename(path) == ".gitmodules":
            problems.append("%s: git submodule — it pulls another repository into this one" % path)
            continue
        if content_re.match(path):
            continue
        try:
            with open(os.path.join(root, path), "rb") as fh:
                data = fh.read()
        except OSError:
            continue    # tracked but deleted in the working folder: nothing to read
        if b"\0" in data:
            continue    # binary
        for n, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
            for reason in check_line(path, line):
                problems.append("%s:%d: %s" % (path, n, reason))
    return problems


class TestThisRepository(unittest.TestCase):
    def test_codebase_is_self_contained(self):
        problems = scan(REPO)
        if problems:
            self.fail(MESSAGE + "\n\n" + "\n".join(problems))


class TestScanner(unittest.TestCase):
    """The scanner itself: each kind of planted link is caught, and documents are left alone."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="boundary-test-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.root, ".github", "workflows"))
        shutil.copy(os.path.join(REPO, WORKFLOW), os.path.join(self.root, WORKFLOW))
        self.env = dict(os.environ, HOME=self.tmp, XDG_CONFIG_HOME=self.tmp, GIT_CONFIG_NOSYSTEM="1")
        self.git("init", "--quiet", ".")
        self.git("add", "--", WORKFLOW)

    def git(self, *args):
        subprocess.run(["git"] + list(args), cwd=self.root, env=self.env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def plant(self, rel, text):
        full = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        self.git("add", "--", rel)

    def scan(self):
        return scan(self.root)

    # Planted strings are assembled from pieces so that this file does not match itself.
    OUTSIDE = "someone" + ".example.net"
    VIOLATIONS = [
        ("setup/notes.md", "See https" + "://" + OUTSIDE + "/notes", "web address"),
        ("setup/notes.md", "See https" + "://github.com/" + "someone/notes", "GitHub account"),
        ("setup/notes.md", "Clone github.com/" + "someone/notes", "GitHub account"),
        ("setup/notes.md", "git clone git" + "@github.com:" + "someone/notes.git", "GitHub account"),
        ("setup/notes.md", "See https" + "://github.com/" + "GoogleCloudPlatform/other-repo", "GitHub account"),
        ("setup/notes.md", "See https" + "://github.com/" + "GoogleCloudPlatform", "GitHub account"),
        (".github/workflows/x.yml", "      - uses: " + "someone/action@v1", "another repository"),
        (".github/workflows/x.yml", "  call:\n    uses: " + "someone/notes/.github/workflows/x.yml@main",
         "another repository"),
        (".github/workflows/x.yml", "        run: gh pr view 1 --repo " + "someone/notes", "gh command"),
        (".github/workflows/x.yml", "        run: gh api " + "repos/" + "someone/notes/contents", "API path"),
        (".githooks/pre-commit", "cp x " + "/" + "Users/someone/notes", "absolute path"),
        ("setup/notes.md", "Put it in " + "/" + "home/someone/notes", "absolute path"),
        ("setup/notes.md", "Put it in C:" + "\\" + "Users\\someone", "absolute path"),
        ("setup/notes.md", "Put it in ~" + "/notes", "absolute path"),
        ("setup/notes.md", "Write to someone" + "@" + OUTSIDE, "email address"),
        ("setup/notes.md", "      token: $" + "{{ " + "secrets" + ".MY_TOKEN }}", "secret"),
        ("setup/notes.md", "      env: $" + "{{ toJSON(" + "secrets" + ") }}", "secret"),
        (".github/workflows/x.yml", "        with:\n          " + "repository" + ": someone/notes",
         "checkout of another repository"),
        (".github/workflows/x.yml", "        run: " + "curl" + " -fsSL \"$URL\" | sh", "downloads"),
        (".githooks/pre-commit", "wget" + " \"$SOURCE\"", "downloads"),
    ]

    def test_clean_tree_passes(self):
        self.plant("setup/ok.md", "\n".join([
            "git clone https://github.com/OWNER/REPO.git",
            "gh api --method POST repos/OWNER/REPO/rulesets --input setup/ruleset.json",
            "Check github.com/settings/installations and https://example.org/x",
            "Spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md",
            "Write to test@example.com or okf-lint@invalid; ${{ secrets.GITHUB_TOKEN }}",
            "work=$(mktemp -d \"${TMPDIR:-/tmp}/x.XXXXXX\") > /dev/null",
        ]))
        self.plant(".github/workflows/ok.yml", "\n".join([
            "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
            "    uses: ./.github/workflows/obsidian.yml",
            "        run: gh pr view 1 --repo \"$REPO\"; gh api \"repos/$REPO/pulls\"",
            "      REPO: ${{ github.repository }}",
        ]))
        self.assertEqual(self.scan(), [])

    def test_each_kind_of_link_is_caught(self):
        for rel, text, kind in self.VIOLATIONS:
            with self.subTest(text=text):
                self.setUp()
                self.plant(rel, text)
                problems = self.scan()
                self.assertTrue(any(p.startswith(rel + ":") and kind in p for p in problems),
                                "not caught (%s): %r\n%s" % (kind, text, "\n".join(problems)))

    def test_documents_may_link_anywhere(self):
        for rel, text, _ in self.VIOLATIONS:
            if rel == "setup/notes.md":
                self.plant("concept/" + "a-note.md", text)
                self.plant("_originals/" + "a-source.md", text)
        self.assertEqual(self.scan(), [])

    def test_submodule_file_is_caught(self):
        self.plant(".gitmodules", "[submodule \"notes\"]\n\tpath = notes")
        self.assertTrue(any(p.startswith(".gitmodules:") and "submodule" in p for p in self.scan()))

    def test_symlink_is_caught_anywhere(self):
        for rel in ("setup/link.md", "concept/link.md"):
            with self.subTest(rel=rel):
                self.setUp()
                os.makedirs(os.path.join(self.root, os.path.dirname(rel)))
                os.symlink(os.path.join(self.tmp, "elsewhere"), os.path.join(self.root, rel))
                self.git("add", "--", rel)
                self.assertTrue(any(p.startswith(rel + ":") and "symbolic link" in p
                                    for p in self.scan()))

    def test_missing_content_list_is_an_error(self):
        os.remove(os.path.join(self.root, WORKFLOW))
        with self.assertRaises(AssertionError):
            self.scan()


if __name__ == "__main__":
    unittest.main()
