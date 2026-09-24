"""Unit tests: commit filtering (ship_or_exit/github.py)."""
import unittest

from ship_or_exit import github
from ship_or_exit.github import is_dependency_bump, is_docs_only, is_human


def make_commit(message, login="alice", name="Alice", is_merge=False, files=None):
    commit = {"sha": "abc123", "date": "2026-09-01T00:00:00+00:00",
              "author_login": login, "author_name": name,
              "message": message, "is_merge": is_merge}
    if files is not None:
        commit["files"] = files
    return commit


ENGINEERING = [
    "feat: route optimizer",
    "fix: off-by-one in fee calc",
    "refactor: split pool manager",
    "test: fuzz swap paths",
    "perf: cache slot reads",
    "feat: hook registry",
    "fix: revert on zero liquidity",
    "chore: lint pass",
]

DOCS_ONLY = [
    "docs: update README",
    "doc: fix typo",
    "docs(api): describe pagination",
    "documentation: rewrite install guide",
    "Update the docs for v2",
    "Fix README install instructions",
    "update readme with new endpoints",
    "documentation only changes",
    "Fix typo in code comments",
    "README typo fix",
    "wiki: add validator guide",
]

DEP_BUMPS = [
    "Bump lodash from 4.17.20 to 4.17.21",
    "chore(deps): bump requests to 2.32",
    "build(deps): update all dependencies",
    "deps: upgrade openzeppelin contracts",
    "dep: bump solc version",
    "chore: update lockfile",
    "chore: bump version to 1.2.3",
    "renovate: update dependency ethers to v6",
    "ci: update dependencies",
    "Bump actions/checkout from 3 to 4",
]


class TestIsHuman(unittest.TestCase):
    def test_engineering_commits_are_human(self):
        for msg in ENGINEERING:
            with self.subTest(msg=msg):
                self.assertTrue(is_human(make_commit(msg)))

    def test_merges_are_not_human(self):
        self.assertFalse(is_human(make_commit("Merge pull request #42", is_merge=True)))
        self.assertFalse(is_human(make_commit("feat: real work", is_merge=True)))

    def test_bot_logins_are_not_human(self):
        for login in ("dependabot[bot]", "renovate[bot]", "github-actions[bot]",
                      "some-bot[bot]", "dependabot", "renovate"):
            with self.subTest(login=login):
                self.assertFalse(is_human(make_commit("feat: real work", login=login)))

    def test_bot_names_are_not_human(self):
        self.assertFalse(is_human(make_commit("feat: real work", name="dependabot")))

    def test_docs_only_are_not_human(self):
        for msg in DOCS_ONLY:
            with self.subTest(msg=msg):
                self.assertFalse(is_human(make_commit(msg)))

    def test_dep_bumps_are_not_human(self):
        for msg in DEP_BUMPS:
            with self.subTest(msg=msg):
                self.assertFalse(is_human(make_commit(msg)))

    def test_multiline_message_uses_first_line(self):
        commit = make_commit("feat: route optimizer\n\ndocs: extra notes")
        self.assertTrue(is_human(commit))

    def test_missing_fields_default_to_human(self):
        self.assertTrue(is_human({}))


class TestIsDocsOnly(unittest.TestCase):
    def test_engineering_not_docs(self):
        for msg in ENGINEERING:
            with self.subTest(msg=msg):
                self.assertFalse(is_docs_only(make_commit(msg)))

    def test_docs_messages_detected(self):
        for msg in DOCS_ONLY:
            with self.subTest(msg=msg):
                self.assertTrue(is_docs_only(make_commit(msg)))

    def test_docs_file_list_detected(self):
        commit = make_commit("fix: stuff",
                             files=["docs/guide.md", "README.md", "wiki/Home.md"])
        self.assertTrue(is_docs_only(commit))

    def test_mixed_file_list_not_docs_only(self):
        commit = make_commit("fix: stuff", files=["src/pool.py", "docs/guide.md"])
        self.assertFalse(is_docs_only(commit))

    def test_no_file_list_falls_back_to_message(self):
        self.assertFalse(is_docs_only(make_commit("fix: off-by-one in fee calc")))


class TestIsDependencyBump(unittest.TestCase):
    def test_engineering_not_bumps(self):
        for msg in ENGINEERING:
            with self.subTest(msg=msg):
                self.assertFalse(is_dependency_bump(make_commit(msg)))

    def test_bump_messages_detected(self):
        for msg in DEP_BUMPS:
            with self.subTest(msg=msg):
                self.assertTrue(is_dependency_bump(make_commit(msg)))

    def test_lockfile_only_commit_is_bump(self):
        commit = make_commit("fix: stuff", files=["yarn.lock", "package-lock.json"])
        self.assertTrue(is_dependency_bump(commit))

    def test_lockfile_plus_code_is_not_bump(self):
        commit = make_commit("fix: stuff", files=["yarn.lock", "src/pool.py"])
        self.assertFalse(is_dependency_bump(commit))


if __name__ == "__main__":
    unittest.main()
