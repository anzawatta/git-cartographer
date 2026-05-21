"""
Tests for git_scanner.commits_since_last_change_bulk.

Uses unittest.mock.patch to mock _run_git so no actual git calls are made.
"""

import unittest
from unittest.mock import patch

from src import git_scanner


class TestCommitsSinceLastChangeBulk(unittest.TestCase):

    def test_basic_distance(self):
        """file_a.py found in first commit (distance=0), file_b.py in second (distance=1)."""
        mock_output = (
            "COMMIT:abc123\n"
            "\n"
            "file_a.py\n"
            "\n"
            "COMMIT:def456\n"
            "\n"
            "file_b.py\n"
        )
        with patch("src.git_scanner._run_git", return_value=mock_output):
            result = git_scanner.commits_since_last_change_bulk(
                "/fake/repo", ["file_a.py", "file_b.py"], "abc123"
            )
        self.assertEqual(result["file_a.py"], 0)
        self.assertEqual(result["file_b.py"], 1)

    def test_scan_limit(self):
        """When scan_limit_commits=5 is passed, git args must contain '-5'."""
        mock_output = "COMMIT:abc123\n\nfile_a.py\n"
        with patch("src.git_scanner._run_git", return_value=mock_output) as mock_run:
            git_scanner.commits_since_last_change_bulk(
                "/fake/repo", ["file_a.py"], "abc123", scan_limit_commits=5
            )
        called_args = mock_run.call_args[0][0]  # first positional arg = list of git args
        self.assertIn("-5", called_args)

    def test_file_not_in_range(self):
        """A file not found in the log output should have distance=None."""
        mock_output = "COMMIT:abc123\n\nother_file.py\n"
        with patch("src.git_scanner._run_git", return_value=mock_output):
            result = git_scanner.commits_since_last_change_bulk(
                "/fake/repo", ["missing_file.py"], "abc123"
            )
        self.assertIsNone(result["missing_file.py"])

    def test_empty_files(self):
        """Empty file list should return empty dict without calling git."""
        with patch("src.git_scanner._run_git") as mock_run:
            result = git_scanner.commits_since_last_change_bulk(
                "/fake/repo", [], "abc123"
            )
        self.assertEqual(result, {})
        mock_run.assert_not_called()

    def test_git_failure(self):
        """RuntimeError from _run_git should cause all files to get None."""
        with patch("src.git_scanner._run_git", side_effect=RuntimeError("git died")):
            result = git_scanner.commits_since_last_change_bulk(
                "/fake/repo", ["file_a.py", "file_b.py"], "abc123"
            )
        self.assertIsNone(result["file_a.py"])
        self.assertIsNone(result["file_b.py"])


if __name__ == "__main__":
    unittest.main()
