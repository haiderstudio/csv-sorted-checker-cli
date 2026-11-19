# Security Policy

This tool runs locally, collects no data, sends nothing anywhere, and needs no API key or secret. It only reads the CSV files you point it at, and it never rewrites a file and never changes anything. It writes nothing except the report on standard output (and usage errors on standard error). It never fetches a URL: remote addresses are skipped, not opened.

If you find a case where the tool edits a file, reports a pass for a CSV file that is not sorted by the named column, or flags a row that is in order, please open an issue describing the exact commands and input.
