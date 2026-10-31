## What does this change?

## Why?

## Checklist

- [ ] `ruff check src tests scripts`, `ruff format --check src tests scripts` and `mypy` pass
- [ ] `pytest` passes (and `pytest -m slow` if the physics changed)
- [ ] New behaviour is tested; coverage stays above 85%
- [ ] Every new scientific statement or formula cites a verified source (DOI) in the code and docs
- [ ] New choices (thresholds, defaults) are recorded in DECISIONS.md
- [ ] CHANGELOG.md is updated under "Unreleased"
- [ ] If the CLI changed: `docs/cli.md` regenerated (`python scripts/cli_page.py`)
