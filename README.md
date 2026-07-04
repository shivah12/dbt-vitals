# dbt-vitals

Static analysis and health scoring for dbt projects — the "cargo clippy for dbt."

Unlike a SQL linter (indentation, keyword casing), dbt-vitals looks at your
project's *structure*: dead models, missing tests, duplicated business logic,
documentation coverage, and (given warehouse stats) incremental-model
candidates. It parses `manifest.json` / `catalog.json` — the artifacts dbt
already generates — so it needs no warehouse credentials of its own.

```
Overall Health
76/100
Warnings: 8   Critical: 0   Info: 4
```

## What it checks

| Module | What it flags | Needs `catalog.json`? |
|---|---|---|
| Lineage | Dead/unused models, circular dependencies | No |
| Testing | Models missing `unique`/`not_null` on their likely primary key | No |
| Duplicate Logic | Repeated `CASE WHEN` blocks across models (candidates for a macro) | No |
| Documentation | Model/column description coverage % | No |
| Incremental Candidates | Large `table`-materialized models that could be `incremental` | Yes |

## Local setup

Requires Python 3.9+.

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/dbt-vitals.git
cd dbt-vitals

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

Run the test suite against the bundled synthetic example project:

```bash
pytest
```

Try the CLI against the bundled example (no real dbt project needed):

```bash
dbt-vitals analyze . --manifest examples/sample_manifest.json --catalog examples/sample_catalog.json
```

Run it against a real dbt project:

```bash
cd /path/to/your/dbt/project
dbt compile               # or `dbt docs generate` to also get catalog.json
dbt-vitals analyze .
```

### CLI options

```bash
dbt-vitals analyze <target_dir>          # target_dir defaults to "."
  --manifest PATH        # override manifest.json location
  --catalog PATH         # override catalog.json location
  --json                 # machine-readable output
  --ci-comment           # markdown summary for a PR comment
  --fail-under N         # exit 1 if health score < N (CI gating)
```

## CI integration

`.github/workflows/dbt-vitals.yml` is included — it runs `dbt-vitals` on every
PR, posts the health score as a comment, and fails the build if the score
drops below a threshold. Adjust the `dbt compile` step for your adapter/profile.

## Publishing to PyPI

This is a **Python** package, so it's published to [PyPI](https://pypi.org),
not npm — `pip install dbt-vitals` is the equivalent of `npm install`.

1. Create accounts at [pypi.org](https://pypi.org/account/register/) and
   [test.pypi.org](https://test.pypi.org/account/register/) (the sandbox —
   publish here first to make sure everything works).
2. Generate an API token: PyPI account settings → API tokens → scope it to
   this project (after the first upload) or "entire account" (for the first
   upload, since the project doesn't exist yet).
3. Update `pyproject.toml`: bump `version`, fix the `Homepage`/`Issues` URLs
   to your actual GitHub repo, add a real `authors` email if you want one.
4. Build and check the package:

   ```bash
   pip install build twine
   python -m build                # creates dist/*.whl and dist/*.tar.gz
   twine check dist/*
   ```



To ship a new version later: bump `version` in `pyproject.toml`, delete the
old `dist/` folder, rebuild (`python -m build`), and `twine upload dist/*`
again — PyPI rejects re-uploading an existing version number.

## Pushing to GitHub

```bash
cd dbt-vitals
git init
git add .
git commit -m "Initial commit: dbt-vitals MVP"

# Create the repo on GitHub first (via github.com or `gh repo create`),
# then:
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/dbt-vitals.git
git branch -M main
git push -u origin main
```

If you use the [GitHub CLI](https://cli.github.com/) instead of the website:

```bash
gh repo create dbt-vitals --public --source=. --remote=origin --push
```

## Project layout

```
dbt-vitals/
  dbt_doctor/
    cli.py              # click CLI entry point
    parser.py           # manifest.json / catalog.json loading
    graph.py            # dependency graph (networkx)
    scoring.py           # health score calculation
    report.py           # terminal + CI markdown rendering
    findings.py          # shared Finding data structure
    modules/
      lineage.py         # dead models, circular deps
      testing.py         # missing test coverage
      duplicates.py       # repeated CASE-WHEN logic (via sqlglot AST)
      documentation.py    # doc coverage
      incremental.py       # incremental-model candidates
  examples/               # synthetic manifest/catalog for demos & tests
  tests/                  # pytest suite
  .github/workflows/       # CI action
```

## Known limitations (by design, for v0.1)

- **Duplicate detection** only looks at `CASE WHEN` expressions, not arbitrary
  repeated subqueries or joins.
- **Incremental candidates** use a fixed row-count threshold, not a real
  cost/runtime estimate — that would require warehouse-specific query plans.
- **Primary key inference** for the testing module is a naming heuristic
  (`id`, `<model>_id`, or any `*_id` column) since dbt's manifest has no
  first-class primary key concept.
- No plugin system yet (warehouse-specific checks) — deliberately deferred,
  see the original scoping notes for why.

## License

MIT — see [LICENSE](LICENSE).
