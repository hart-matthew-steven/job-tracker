# Temporary Scripts

This directory contains one-off or exploratory scripts used for:
- migrations
- data fixes
- investigations / diagnostics
- refactor support tooling

Rules:
- Scripts here are disposable by default.
- Scripts here should not be imported by production code.
- Each script should include a short header:
  - purpose
  - inputs/outputs
  - expected lifespan (e.g., “delete after migration”)
- If a script becomes permanent, move it into the appropriate source directory.

Output:
- If a script produces output files, store them under `logs/` (timestamped and descriptive).