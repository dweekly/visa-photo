"""One version, named identically everywhere a reader or a tool looks for it."""

import json
import re
from pathlib import Path

from visaphoto import __version__

ROOT = Path(__file__).resolve().parent.parent


def test_version_is_a_release_string():
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_pyproject_reads_the_version_from_the_package():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'dynamic = ["version"]' in text
    assert 'attr = "visaphoto.__version__"' in text
    assert not re.search(r'^version = "', text, re.M), "a literal version would be a second copy"


def test_plugin_manifest_names_the_same_version():
    manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "visa-photo" and manifest["version"] == __version__
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    entry = marketplace["plugins"][0]
    assert entry["name"] == "visa-photo" and entry["source"] == "./"
    assert "version" not in entry, "the plugin manifest is the one place the version lives"


def test_changelog_and_readme_name_the_release():
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert re.search(rf"^## {re.escape(__version__)} - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.M)
    readme = (ROOT / "README.md").read_text()
    assert f"**Status: {__version__}.**" in readme


def test_the_skill_names_the_same_version():
    skill = (ROOT / "skills" / "visa-photo" / "SKILL.md").read_text()
    assert f"version: {__version__}" in skill
