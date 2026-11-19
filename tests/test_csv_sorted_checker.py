#!/usr/bin/env python3
"""Tests for csv_sorted_checker — stdlib unittest only."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import csv_sorted_checker as checker

REPO = Path(__file__).resolve().parent.parent


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


def findings_of(text, column="name", reverse=False):
    return checker.check_text(text, column, reverse)


class TestSortedness(unittest.TestCase):
    def test_sorted_file_passes(self):
        bad, errors = findings_of("name,age\namy,30\nbob,22\ncara,25\n")
        self.assertEqual(bad, [])
        self.assertEqual(errors, [])

    def test_first_out_of_order_row_reported(self):
        bad, _ = findings_of(
            "name,age\namy,30\ncara,25\nbob,22\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 4)
        self.assertEqual(bad[0]["column"], "name")
        self.assertEqual(bad[0]["value"], "bob")
        self.assertEqual(bad[0]["previous"], "cara")

    def test_only_first_violation_reported(self):
        bad, _ = findings_of(
            "name\namy\ncara\nbob\naaron\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 4)
        self.assertEqual(bad[0]["value"], "bob")

    def test_violation_in_second_column(self):
        bad, _ = findings_of(
            "name,city\namy, York\nbob, Bath\ncara, York\n", "city")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 3)
        self.assertEqual(bad[0]["column"], "city")
        self.assertEqual(bad[0]["value"], " Bath")
        self.assertEqual(bad[0]["previous"], " York")

    def test_reverse_flag_descending_passes(self):
        bad, errors = findings_of(
            "name\ncara\nbob\namy\n", "name", reverse=True)
        self.assertEqual(bad, [])
        self.assertEqual(errors, [])

    def test_reverse_flag_flags_ascending(self):
        bad, _ = findings_of(
            "name\namy\nbob\ncara\n", "name", reverse=True)
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 3)
        self.assertEqual(bad[0]["value"], "bob")

    def test_equal_values_pass_in_either_direction(self):
        bad, _ = findings_of("name\nbaker\nbaker\nbaker\n")
        self.assertEqual(bad, [])
        bad, _ = findings_of("name\nbaker\nbaker\nbaker\n",
                             "name", reverse=True)
        self.assertEqual(bad, [])

    def test_quoted_field_with_comma(self):
        bad, errors = findings_of(
            'name,score\n"Adams, Ann",10\nBaker,9\n')
        self.assertEqual(bad, [])
        self.assertEqual(errors, [])

    def test_quoted_field_out_of_order(self):
        bad, _ = findings_of(
            'name\n"Zed, Zoe"\n"Adams, Ann"\n')
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 3)
        self.assertEqual(bad[0]["value"], "Adams, Ann")

    def test_multiline_quoted_field_line_numbers(self):
        bad, _ = findings_of(
            'name,note\namy,"first\nline"\nbob,"second"\n'
            'aaron,"third"\n')
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 5)
        self.assertEqual(bad[0]["value"], "aaron")

    def test_blank_lines_skipped(self):
        bad, errors = findings_of("name\namy\n\nbob\n")
        self.assertEqual(bad, [])
        self.assertEqual(errors, [])

    def test_blank_line_before_violation_keeps_line_number(self):
        bad, _ = findings_of("name\namy\n\ncara\nbob\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 5)

    def test_header_only_passes(self):
        bad, errors = findings_of("name,age\n")
        self.assertEqual(bad, [])
        self.assertEqual(errors, [])

    def test_empty_file_is_an_error(self):
        bad, errors = findings_of("")
        self.assertEqual(bad, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("header row is required", errors[0])

    def test_missing_column_is_an_error(self):
        bad, errors = findings_of("name,age\namy,30\n", "city")
        self.assertEqual(bad, [])
        self.assertEqual(len(errors), 1)
        self.assertIn('column "city" is not in the header', errors[0])
        self.assertIn("name, age", errors[0])

    def test_duplicate_column_is_an_error(self):
        bad, errors = findings_of("name,name\namy,bob\n", "name")
        self.assertEqual(bad, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("appears twice", errors[0])

    def test_short_row_is_an_error(self):
        bad, errors = findings_of("name,age,city\namy,30\nbob,22, York\n")
        self.assertEqual(bad, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("line 2 has 2 field(s)", errors[0])

    def test_short_row_does_not_hide_a_violation(self):
        bad, errors = findings_of(
            "name,age\namy,30\nbob\ncara,25\naaron,40\n")
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 5)

    def test_unclosed_quote_is_an_error(self):
        bad, errors = findings_of('name\n"amy\n')
        self.assertEqual(bad, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("could not parse", errors[0])

    def test_case_sensitive_compare(self):
        # Plain text order: capitals sort before lowercase,
        # so a lowercase name before a capital one is out
        # of order.
        bad, _ = findings_of("name\napple\nZebra\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["value"], "Zebra")

    def test_capitals_before_lowercase_passes(self):
        bad, _ = findings_of("name\nZebra\napple\n")
        self.assertEqual(bad, [])

    def test_numbers_compare_as_text(self):
        # "10" sorts before "9" as plain text, so "10"
        # after "9" is out of order.
        bad, _ = findings_of("id\n9\n10\n", "id")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["value"], "10")

    def test_numbers_in_text_order_pass(self):
        bad, _ = findings_of("id\n10\n2\n3\n", "id")
        self.assertEqual(bad, [])

    def test_empty_values_sort_first(self):
        bad, _ = findings_of("name\n\namy\n")
        self.assertEqual(bad, [])

    def test_empty_value_after_a_name_is_a_violation(self):
        bad, _ = findings_of("name\namy\n,\n")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["value"], "")

    def test_single_data_row_passes(self):
        bad, errors = findings_of("name\namy\n")
        self.assertEqual(bad, [])
        self.assertEqual(errors, [])


class TestCli(unittest.TestCase):
    def test_sorted_file_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.csv", "name\namy\nbob\n")
            code, out, _ = run_cli(["--column", "name", path])
            self.assertEqual(code, 0)
            self.assertIn("OK", out)
            self.assertIn('sorted by "name"', out)

    def test_unsorted_file_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.csv", "name\nbob\namy\n")
            code, out, _ = run_cli(["--column", "name", path])
            self.assertEqual(code, 1)
            self.assertIn('FAIL %s: line 3 column "name": "amy"'
                          % path, out)
            self.assertIn("1 out-of-order row(s)", out)

    def test_missing_column_fails_with_error_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.csv", "name\namy\n")
            code, out, _ = run_cli(["--column", "city", path])
            self.assertEqual(code, 1)
            self.assertIn("ERROR %s:" % path, out)
            self.assertIn("not in the header", out)

    def test_reverse_flag_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "down.csv", "name\ncara\nbob\namy\n")
            code, out, _ = run_cli(
                ["--column", "name", "--reverse", path])
            self.assertEqual(code, 0)
            self.assertIn("OK", out)

    def test_folder_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.csv", "name\namy\n")
            write(tmp, "b.csv", "name\nbob\namy\n")
            write(tmp, "notes.txt", "name\nbob\namy\n")
            code, out, _ = run_cli(["--column", "name", tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s)", out)
            self.assertNotIn("notes.txt", out)

    def test_nested_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "sub/deep.csv", "name\nbob\namy\n")
            code, out, _ = run_cli(["--column", "name", tmp])
            self.assertEqual(code, 1)
            self.assertIn("deep.csv", out)

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "top.csv", "name\namy\n")
            write(tmp, "sub/deep.csv", "name\nbob\namy\n")
            code, out, _ = run_cli(
                ["--column", "name", "--no-recursive", tmp])
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)

    def test_exclude_skips_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "a.csv", "name\nbob\namy\n")
            write(tmp, "skip.csv", "name\nbob\namy\n")
            code, out, _ = run_cli(
                ["--column", "name", "--exclude", "skip.csv", tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 1 file(s)", out)
            self.assertNotIn("skip.csv", out)

    def test_git_folder_skipped_in_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/hooks/bad.csv", "name\nbob\namy\n")
            write(tmp, "a.csv", "name\namy\n")
            code, out, _ = run_cli(["--column", "name", tmp])
            self.assertEqual(code, 0)
            self.assertIn("OK — 1 file(s) checked", out)

    def test_direct_file_checked_whatever_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "data.txt", "name\nbob\namy\n")
            code, out, _ = run_cli(["--column", "name", path])
            self.assertEqual(code, 1)
            self.assertIn("data.txt", out)

    def test_duplicate_paths_checked_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", "name\nbob\namy\n")
            code, out, _ = run_cli(["--column", "name", path, path])
            self.assertEqual(code, 1)
            self.assertIn("Checked 1 file(s)", out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.csv", "name\nbob\namy\n")
            code, out, _ = run_cli(["--column", "name", "--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["findings"], 1)
            self.assertEqual(
                data["files"][0]["findings"][0]["value"], "amy")
            self.assertEqual(
                data["files"][0]["findings"][0]["line"], 3)
            self.assertEqual(data["files"][0]["errors"], [])

    def test_json_output_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.csv", "name\namy\nbob\n")
            code, out, _ = run_cli(["--column", "name", "--json", path])
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertEqual(data["findings"], 0)

    def test_stdin_clean(self):
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("name\namy\nbob\n")
        try:
            code, out, _ = run_cli(["--column", "name", "--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn('sorted by "name"', out)

    def test_stdin_dirty(self):
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("name\nbob\namy\n")
        try:
            code, out, _ = run_cli(["--column", "name", "--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn('FAIL <stdin>: line 3 column "name"', out)

    def test_stdin_with_paths_is_usage_error(self):
        code, _, err = run_cli(["--column", "name", "--stdin", "a.csv"])
        self.assertEqual(code, 2)

    def test_no_paths_is_usage_error(self):
        code, _, err = run_cli(["--column", "name"])
        self.assertEqual(code, 2)

    def test_missing_column_flag_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.csv", "name\namy\n")
            code, _, err = run_cli([path])
            self.assertEqual(code, 2)

    def test_missing_path_exit_2(self):
        code, _, err = run_cli(["--column", "name", "/no/such/file.csv"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli(["--column", "name", tmp])
            self.assertEqual(code, 2)
            self.assertIn("no .csv files found", err)

    def test_bad_flag_exit_2(self):
        code, _, _ = run_cli(["--column", "name", "--nope", "a.csv"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("csv_sorted_checker", out)

    def test_non_utf8_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.csv", b"\xff\xfe,name\n")
            code, out, _ = run_cli(["--column", "name", path])
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)

    def test_input_files_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "name\nbob\namy\n"
            path = write(tmp, "bad.csv", text)
            run_cli(["--column", "name", path])
            self.assertEqual(Path(path).read_text(), text)

    def test_cli_runs_from_another_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.csv", "name\nbob\namy\n")
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src" / "csv_sorted_checker.py"),
                 "--column", "name", path],
                capture_output=True, text=True, cwd="/")
            self.assertEqual(result.returncode, 1)
            self.assertIn('"amy" is out of order', result.stdout)

    def test_cli_runs_under_fake_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.csv", "name\nbob\namy\n")
            env = dict(os.environ, HOME=tmp)
            result = subprocess.run(
                [sys.executable,
                 str(REPO / "src" / "csv_sorted_checker.py"),
                 "--column", "name", path],
                capture_output=True, text=True, cwd=tmp, env=env)
            self.assertEqual(result.returncode, 1)

    def test_run_example_output_matches_sample(self):
        sample = (REPO / "examples" / "sample-output.md").read_text()
        result = subprocess.run(
            ["sh", str(REPO / "examples" / "run-example.sh")],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), sample.strip())

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        unsorted = (REPO / "examples" / "unsorted.csv").read_text()
        bad, _ = checker.check_text(unsorted, "name")
        for item in bad:
            line = ('FAIL examples/unsorted.csv: line %d column "%s": '
                    '"%s" %s'
                    % (item["line"], item["column"],
                       item["value"], item["reason"]))
            self.assertIn(line, readme)


class TestExamples(unittest.TestCase):
    def test_sorted_example_passes(self):
        code, _, _ = run_cli(["--column", "name",
                              str(REPO / "examples" / "sorted.csv")])
        self.assertEqual(code, 0)

    def test_unsorted_example_fails_with_one(self):
        bad, _ = checker.check_text(
            (REPO / "examples" / "unsorted.csv").read_text(), "name")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["line"], 4)
        self.assertEqual(bad[0]["value"], "bob")

    def test_edge_example_passes(self):
        code, _, _ = run_cli(["--column", "name",
                              str(REPO / "examples" / "edge.csv")])
        self.assertEqual(code, 0)

    def test_edge_example_sorted_by_score_fails(self):
        bad, _ = checker.check_text(
            (REPO / "examples" / "edge.csv").read_text(), "score")
        self.assertEqual(len(bad), 1)
        self.assertEqual(bad[0]["value"], "8")


class TestHygiene(unittest.TestCase):
    def _repo_files(self, skip_tests=True):
        """Every file in the repo, minus .git and caches."""
        for path in REPO.rglob("*"):
            if path.is_dir():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix == ".pyc":
                continue
            if skip_tests and "tests" in path.parts:
                continue
            yield path

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files(skip_tests=True):
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files(skip_tests=True):
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\", "/tmp/"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        import ast
        stdlib = set(sys.stdlib_module_names)
        for target in (REPO / "src" / "csv_sorted_checker.py",
                       REPO / "tests" / "test_csv_sorted_checker.py"):
            tree = ast.parse(target.read_text())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(a.name.split(".")[0]
                                    for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            self.assertFalse(
                imported - stdlib - {"csv_sorted_checker"},
                (target.name, imported))
            self.assertNotIn("yaml", imported)

    def test_no_network_use_in_src(self):
        src = (REPO / "src" / "csv_sorted_checker.py").read_text()
        for marker in ("urllib.request", "requests", "socket",
                       "http.client", "urlopen", "urlretrieve"):
            self.assertNotIn(marker, src, marker)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertTrue(lines, ".gitignore is empty")
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github" / "workflows" / "ci.yml").read_text()
        self.assertIn("tests/test_csv_sorted_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)
        self.assertIn("push", ci)
        self.assertIn("pull_request", ci)

    def test_readme_names_the_neighbouring_repos(self):
        readme = (REPO / "README.md").read_text()
        for name in ("csv-bom-checker-cli",
                     "csv-date-format-checker-cli",
                     "csv-delimiter-checker-cli"):
            self.assertIn(name, readme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
