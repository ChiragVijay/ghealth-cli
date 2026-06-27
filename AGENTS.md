## API Schema Discipline

When adding or changing commands that render API responses:

1. Verify response field names against the official API reference or a captured real JSON response.
2. Do not invent friendly table columns from assumed field names.
3. Add at least one test fixture using documented response fields for every new table renderer.
4. Prefer JSON output passthrough for unknown or unstable schemas.
5. If a human-friendly column is derived, keep the raw source field available in `--format json`.

For each API resource renderer, include a table-output regression test using realistic documented field names.
The test should assert that important documented fields appear in table output.

## Post-Task Checks

- Run:
  ```bash
  uv run ruff format --check .
  uv run ruff check .
  uv run ty check
  ```
