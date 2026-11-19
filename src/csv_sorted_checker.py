#!/usr/bin/env python3
"""Check a CSV file is sorted by one named column.

Run: python3 src/csv_sorted_checker.py --column name data.csv
     python3 src/csv_sorted_checker.py --column name --reverse data.csv
     python3 src/csv_sorted_checker.py --column name folder/
     python3 src/csv_sorted_checker.py --column name --stdin < data.csv

A data file that is supposed to be sorted but is not
breaks every merge, diff, and binary search that trusts
the order — and the breakage shows up in the consumer,
not in the file. This tool checks the order in the file
itself: it reads the named column top to bottom and
reports the first row that is out of order, with the
file, the line, and the column, and exits 1 so it can
fail a CI run. A file that is sorted exits 0.

Values compare as plain text, exactly as written:
"10" sorts before "9", because the character "1" comes
before "9". Numbers, dates, and mixed case are not
given special treatment — the check is that the text is
in plain sorted order, nothing more.

A header row is required, and the named column must be
in it. The tool reads CSV only. It never edits a file,
never touches the network, and reads only the files and
folders you point it at.
"""

import argparse
import csv
import fnmatch
import io
import json
import os
import sys
from pathlib import Path

__version__ = "1.0.0"

CSV_SUFFIX = ".csv"


def check_text(text, column, reverse=False):
    """Check one CSV document given as text.

    Returns (findings, errors). A finding is a dict with
    "line", "column", "value", "previous", and "reason".
    Only the first out-of-order row is reported: once the
    order is broken, the file has already failed, and the
    first break is where the fix starts.
    """
    reader = csv.reader(io.StringIO(text), strict=True)
    try:
        header = next(reader)
    except StopIteration:
        return [], ["empty file — a header row is required"]
    except csv.Error as exc:
        return [], ["could not parse the CSV: %s" % exc]
    if column not in header:
        names = ", ".join(header)
        return [], [
            'column "%s" is not in the header (header has: %s)'
            % (column, names)]
    if header.count(column) > 1:
        return [], ['column "%s" appears twice in the header' % column]
    index = header.index(column)
    findings = []
    errors = []
    previous = None
    try:
        for row in reader:
            line_no = reader.line_num
            if not row:
                continue
            if len(row) < len(header):
                errors.append(
                    "line %d has %d field(s), the header has %d"
                    % (line_no, len(row), len(header)))
                continue
            value = row[index]
            if previous is not None:
                if reverse:
                    out_of_order = value > previous
                else:
                    out_of_order = value < previous
                if out_of_order:
                    findings.append({
                        "line": line_no,
                        "column": column,
                        "value": value,
                        "previous": previous,
                        "reason": 'is out of order after "%s"' % previous,
                    })
                    break
            previous = value
    except csv.Error as exc:
        errors.append("could not parse the CSV: %s" % exc)
    return findings, errors


def check_file(path, column, reverse=False):
    """Check one file. Returns (findings, errors)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], ["not valid UTF-8"]
    except OSError as exc:
        return [], ["could not read the file: %s" % exc]
    return check_text(text, column, reverse)


def _is_excluded(name, patterns):
    return any(fnmatch.fnmatch(name, pat) for pat in patterns)


def collect_paths(paths, recursive, exclude):
    """Turn command-line paths into a sorted list of files.

    A file given directly is always checked, whatever its
    name. A folder is walked for files ending in .csv
    only. .git folders are never walked, and directory
    links are never followed.
    """
    found = []
    seen = set()
    for given in paths:
        target = Path(given)
        if target.is_file():
            key = str(target.resolve())
            if key not in seen:
                seen.add(key)
                found.append(str(target))
        elif target.is_dir():
            if recursive:
                walker = os.walk(target, followlinks=False)
            else:
                walker = [(str(target), [], sorted(
                    p.name for p in target.iterdir() if p.is_file()))]
            for root, dirs, files in walker:
                dirs[:] = sorted(
                    d for d in dirs if d != ".git")
                for name in sorted(files):
                    if not name.endswith(CSV_SUFFIX):
                        continue
                    if _is_excluded(name, exclude):
                        continue
                    full = os.path.join(root, name)
                    key = str(Path(full).resolve())
                    if key not in seen:
                        seen.add(key)
                        found.append(full)
        else:
            found.append(given)
    return sorted(found)


def _fail_line(path, finding):
    return ('FAIL %s: line %d column "%s": "%s" %s'
            % (path, finding["line"], finding["column"],
               finding["value"], finding["reason"]))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="csv_sorted_checker",
        description="Check a CSV file is sorted by one named column.")
    parser.add_argument("paths", nargs="*", metavar="PATH",
                        help="CSV file or folder to check")
    parser.add_argument("--column", required=False, default=None,
                        help="name of the column the file must be "
                        "sorted by (required)")
    parser.add_argument("--reverse", action="store_true",
                        help="expect descending order instead of "
                        "ascending")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one CSV document from standard input")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        metavar="PATTERN",
                        help="skip files whose name matches the pattern "
                        "(may be given more than once)")
    parser.add_argument("--version", action="version",
                        version="csv_sorted_checker " + __version__)
    args = parser.parse_args(argv)

    if args.column is None:
        parser.error("--column is required")

    results = []
    if args.stdin:
        if args.paths:
            print("error: --stdin takes no paths",
                  file=sys.stderr)
            return 2
        text = sys.stdin.read()
        findings, errors = check_text(text, args.column, args.reverse)
        results.append(("<stdin>", findings, errors))
    else:
        if not args.paths:
            print("error: give at least one file or folder to check",
                  file=sys.stderr)
            return 2
        missing = [p for p in args.paths
                   if not Path(p).exists()]
        if missing:
            for path in missing:
                print("error: no such file or folder: %s" % path,
                      file=sys.stderr)
            return 2
        files = collect_paths(args.paths, not args.no_recursive,
                              args.exclude)
        if not files:
            print("error: no .csv files found", file=sys.stderr)
            return 2
        for path in files:
            findings, errors = check_file(path, args.column,
                                          args.reverse)
            results.append((path, findings, errors))

    checked = len(results)
    total_findings = sum(len(f) for _, f, _ in results)
    bad_files = sum(1 for _, f, e in results if f or e)

    if args.json:
        print(json.dumps({
            "files": [
                {"path": path, "findings": findings,
                 "errors": errors}
                for path, findings, errors in results
            ],
            "checked": checked,
            "findings": total_findings,
        }, indent=2))
    else:
        for path, findings, errors in results:
            for finding in findings:
                print(_fail_line(path, finding))
            for error in errors:
                print("ERROR %s: %s" % (path, error))
        if total_findings == 0 and bad_files == 0:
            print('OK — %d file(s) checked, sorted by "%s".'
                  % (checked, args.column))
        else:
            print("Checked %d file(s), %d out-of-order row(s) in "
                  "%d file(s)." % (checked, total_findings, bad_files))

    if total_findings or bad_files:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
