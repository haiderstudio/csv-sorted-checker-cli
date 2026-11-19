# csv-sorted-checker-cli

Check a CSV file is sorted by one named column, fail CI when a row is out of order.

[![CI](https://github.com/haiderstudio/csv-sorted-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/csv-sorted-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`csv_sorted_checker` reads a CSV file, looks at one
column you name with `--column`, and checks the values
in that column run in order from top to bottom. It
reports the first row that is out of order, with the
file, the line, and the column, and exits 1 so it can
fail a CI run. A file that is sorted exits 0.

- A data file that is supposed to be sorted but is not
  breaks every merge, diff, and binary search that
  trusts the order — and the breakage shows up in the
  consumer, not in the file. A gate that names the
  first out-of-order row turns it into a re-sort.
- Only the first out-of-order row is reported: once
  the order is broken, the file has already failed, and
  the first break is where the fix starts.
- `--reverse` expects descending order instead of
  ascending, for files that are meant to run largest
  first.
- Values compare as plain text, exactly as written:
  "10" sorts before "9", because the character "1"
  comes before "9". Numbers, dates, and mixed case get
  no special treatment — the check is that the text is
  in plain sorted order, nothing more.
- Quoted fields are read properly: a value like
  "Adams, Ann" is one value, not two, and a quoted
  field that runs over several lines still reports the
  right line number. Blank lines are skipped.
- A header row is required, and the named column must
  be in it. A missing column, a column listed twice, a
  row with fewer fields than the header, and a file
  that is not valid UTF-8 are all reported as errors
  and fail the check the same way a finding does.
- A file given directly on the command line is always
  checked, whatever its name. A folder is walked for
  files ending in `.csv` only, recursively by default
  (`--no-recursive` stops at the top level). `.git`
  folders are never walked, and directory links are
  never followed.
- `--json` prints the result as JSON, and `--stdin`
  checks one CSV document read from standard input.

## Who it is for

Anyone who ships CSV data files — which is every team
that hands data to another team, another tool, or a
customer. A sorted file is a promise the consumer
relies on, and a file that quietly stops being sorted
breaks the consumer far from the cause. This is the
gate that checks the promise at the pull request,
before the file ships.

## What it does NOT do

- It does not sort the file. That is a different job —
  it reports, you re-sort.
- It does not check the values in the column, only
  their order. That is repo #125,
  csv-date-format-checker-cli, which checks date
  values — values are a different check on the same
  files.
- It does not check for a byte-order mark at the start
  of the file. That is repo #105, csv-bom-checker-cli
  — a byte-order mark is a different check on the same
  files.
- It does not check the delimiter. That is repo #95,
  csv-delimiter-checker-cli — the delimiter is a
  different check on the same files.
- It does not sort numbers as numbers: "10" sorts
  before "9", because the comparison is plain text.
  If your column holds numbers that must sort by
  value, this is the wrong tool.
- It does not sort by more than one column. One
  column, one order, one gate.
- It does not remove a row or rewrite the file. It
  reports, you fix the file.
- It never touches the network, and it only reads the
  files and folders you point it at.

## How this differs

- A fresh search of GitHub on Nov 17, 2026 found 0
  results for `"csv-sorted-checker-cli"` and 8 results
  for `csv sorted checker` — all noise: a CVE
  downloader, a sortable-table theme, a C# desktop
  app that sorts files instead of checking them, a
  PubMed list sorter, and a link checker. No rival is
  a tested command-line gate for CSV sortedness.
- So the narrow slice stands: one named column, plain
  text order, the first out-of-order row, per-line
  reporting, a CI exit code, and a report-only tool
  that never edits a file.

## Install

```sh
git clone https://github.com/haiderstudio/csv-sorted-checker-cli.git
cd csv-sorted-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one data file, sorted by the `name` column:

```sh
python3 src/csv_sorted_checker.py --column name data.csv
```

A file that is sorted passes:

```sh
$ python3 src/csv_sorted_checker.py --column name examples/sorted.csv
OK — 1 file(s) checked, sorted by "name".
```

A file that is not sorted fails, with the first
out-of-order row:

```sh
$ python3 src/csv_sorted_checker.py --column name examples/unsorted.csv
FAIL examples/unsorted.csv: line 4 column "name": "bob" is out of order after "cara"
Checked 1 file(s), 1 out-of-order row(s) in 1 file(s).
```

Check a whole folder (`.csv` files only):

```sh
$ python3 src/csv_sorted_checker.py --column name examples/
FAIL examples/unsorted.csv: line 4 column "name": "bob" is out of order after "cara"
Checked 3 file(s), 1 out-of-order row(s) in 1 file(s).
```

Check one document from standard input:

```sh
$ python3 src/csv_sorted_checker.py --column name --stdin < examples/unsorted.csv
FAIL <stdin>: line 4 column "name": "bob" is out of order after "cara"
Checked 1 file(s), 1 out-of-order row(s) in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/csv_sorted_checker.py --column name --json examples/unsorted.csv
{
  "files": [
    {
      "path": "examples/unsorted.csv",
      "findings": [
        {
          "line": 4,
          "column": "name",
          "value": "bob",
          "previous": "cara",
          "reason": "is out of order after \"cara\""
        }
      ],
      "errors": []
    }
  ],
  "checked": 1,
  "findings": 1
}
```

Exit codes: 0 when every file is sorted, 1 when any
row is out of order or any file has an error, 2 for a
usage error (a missing path, a missing `--column`, a bad
flag, or no `.csv` files found).

## Examples

A file meant to run largest first passes with
`--reverse`:

```sh
$ printf 'city\nYork\nBath\n' > cities.csv
$ python3 src/csv_sorted_checker.py --column city --reverse cities.csv
OK — 1 file(s) checked, sorted by "city".
```

The same file checked with `--reverse` fails — the order
you ask for is the order that is checked:

```sh
$ python3 src/csv_sorted_checker.py --column name --reverse examples/sorted.csv
FAIL examples/sorted.csv: line 3 column "name": "bob" is out of order after "amy"
Checked 1 file(s), 1 out-of-order row(s) in 1 file(s).
```

A quoted field with a comma inside it is one value,
and equal values are fine — `examples/edge.csv` has
"Adams, Ann" followed by two Bakers, and it passes by
name. But the same file is not sorted by score, and
that fails:

```sh
$ python3 src/csv_sorted_checker.py --column score examples/edge.csv
FAIL examples/edge.csv: line 4 column "score": "8" is out of order after "9"
Checked 1 file(s), 1 out-of-order row(s) in 1 file(s).
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_csv_sorted_checker.py
```

The tests cover sortedness (a sorted file passing, the
first out-of-order row reported with line, column,
value and previous value, only the first violation
reported, a violation in a second column, the
`--reverse` flag both ways, equal values passing in
either direction, a quoted field holding a comma, a
quoted field out of order, a quoted field over several
lines keeping the right line number, blank lines
skipped, a header-only file, an empty file, a missing
column, a column listed twice, a short row, a short
row not hiding a later violation, an unclosed quote,
case-sensitive compare, numbers comparing as text,
empty values sorting first, a single data row), the
CLI (exit 0/1/2, folder walking for several CSV files,
nested folders, `--no-recursive`, `--exclude`, `.git`
skipped, a direct file checked whatever its name,
duplicate paths checked once, `--json` output,
`--stdin`, bad flags, a missing `--column`, missing
paths, empty folders, `--version`, a non-UTF-8 file
reported, input files left unchanged, the tool run
from `/` and under a fake HOME), the bundled examples
(sample output compared against a fresh run, and the
README-quoted outputs checked against it), and
hygiene checks (no placeholder text, no absolute
paths, stdlib imports only, no network use in the
source, `.env` first in `.gitignore`, CI file runs the
test file, README names the neighbouring repos).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The
idea of checking a file is not new, and reading CSV
with Python's standard library is standard — but no
existing tool does this one job, checking a local CSV
file for sortedness as a tested command-line gate, as
the search above shows — and every line of code here
is original, built on nothing but Python's standard
library.
