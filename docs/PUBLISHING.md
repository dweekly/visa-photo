# Publishing a release

Fresh as of 2026-09-07. A release tag lands on a commit whose docs already state the release.

## One version

`visaphoto/__init__.py` holds `__version__`; `pyproject.toml` reads it (`dynamic = ["version"]`);
`.claude-plugin/plugin.json` names the same string (the plugin's own manifest is what Claude
Code reads, so it is not repeated in `marketplace.json`). `tests/test_version.py` fails when the
CHANGELOG, the README or the plugin manifest disagree with `__version__`.

## Checklist

1. `CHANGELOG.md`: move the unreleased sections under `## <version> - <date>`.
2. `README.md`: the status line names the version and what each profile does.
3. `__version__` and `plugin.json` bumped; `pytest` green, including `test_version.py`.
4. `tools/release_check.sh`: builds the wheel with `uv build`, installs it into a fresh
   environment outside the checkout, runs `visa-photo --list-specs` from it, and checks the
   wheel's metadata version against `__version__`.
5. Commit, review, merge. Then tag the merge commit: `git tag -a v<version> -m "<version>"` and
   `git push origin v<version>`.
6. Publish: `uv build` (already done by the check) then `uv publish` with a PyPI token in
   `UV_PUBLISH_TOKEN`. This step needs the project owner's credentials.
7. Smoke test from a machine that has never seen the repo:
   `uvx --python 3.12 visa-photo --list-specs`, then `--fetch-models` and one real photo.
8. GitHub release notes: paste the CHANGELOG section.

## The plugin

Users add the repository as a marketplace and install the plugin from it:

```sh
claude plugin marketplace add dweekly/visa-photo
claude plugin install visa-photo@visa-photo
```

Before merging a change to the skill, install it from a clean Claude configuration
(`CLAUDE_CONFIG_DIR` pointing at an empty directory) with the local path as the marketplace
source, and confirm the skill is listed.
