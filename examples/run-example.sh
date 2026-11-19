#!/bin/sh
# Run the checker over each example file and show the result.
# The unsorted example fails on purpose, so each run is allowed to fail.
cd "$(dirname "$0")/.."
for f in examples/sorted.csv examples/unsorted.csv examples/edge.csv; do
  echo "== $f =="
  python3 src/csv_sorted_checker.py --column name "$f" || true
  echo
done
echo "== examples/ : the whole folder =="
python3 src/csv_sorted_checker.py --column name examples/ || true
