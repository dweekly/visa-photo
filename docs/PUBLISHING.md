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
6. Rehearse on TestPyPI first, as the packaging tutorial recommends: with a TestPyPI token
   (a separate account from PyPI),
   `UV_PUBLISH_TOKEN=... uv publish --publish-url https://test.pypi.org/legacy/ dist/*`, then in
   a fresh environment `pip install --index-url https://test.pypi.org/simple/ --no-deps
   visa-photo` (`--no-deps` because TestPyPI does not carry the dependencies) and check the
   project page renders the README and the metadata. TestPyPI is not permanent storage.
7. Publish: `uv publish dist/*` with a PyPI token in `UV_PUBLISH_TOKEN`. This step needs the
   project owner's credentials. A filename uploaded to PyPI can never be replaced: get the
   metadata right before this step, not after.
8. Smoke test from a machine that has never seen the repo:
   `uvx --python 3.12 visa-photo --list-specs`, then `--fetch-models` and one real photo.
9. GitHub release notes: paste the CHANGELOG section.

## What the wheel's metadata should say

`License-Expression: MIT` and `License-File: LICENSE` (PEP 639, via `license = "MIT"` and
`license-files` in `pyproject.toml`; no licence classifier), `Author-email`, `Requires-Python`,
Python-version and operating-system classifiers, `Description-Content-Type: text/markdown`, and
the `Project-URL` set. `tools/release_check.sh` prints the header; read it before publishing.

## The plugin

Users add the repository as a marketplace and install the plugin from it:

```sh
claude plugin marketplace add dweekly/visa-photo
claude plugin install visa-photo@visa-photo
```

Before merging a change to the skill, install it from a clean Claude configuration
(`CLAUDE_CONFIG_DIR` pointing at an empty directory) with the local path as the marketplace
source, and confirm the skill is listed.
