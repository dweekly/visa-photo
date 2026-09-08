#!/usr/bin/env bash
# Build the wheel, install it outside the checkout, run it, and check its version against
# visaphoto.__version__. The reproducible pre-release check named in docs/PUBLISHING.md.
set -euo pipefail
cd "$(dirname "$0")/.."
version=$(python3 -c "import re,pathlib;print(re.search(r'__version__ = \"([^\"]+)\"', pathlib.Path('src/visaphoto/__init__.py').read_text()).group(1))")
rm -rf dist
uv build --quiet
wheel=$(ls dist/visa_photo-*.whl)
echo "wheel: $wheel"
tmp=$(mktemp -d)
uv venv --python 3.12 --quiet "$tmp/venv"
uv pip install --python "$tmp/venv/bin/python" --quiet "$wheel"
installed=$("$tmp/venv/bin/python" -c "import importlib.metadata as m; print(m.version('visa-photo'))")
echo "installed metadata version: $installed (expected $version)"
[ "$installed" = "$version" ] || { echo "VERSION MISMATCH"; exit 1; }
"$tmp/venv/bin/visa-photo" --list-specs | head -3
echo "--- metadata header:"
unzip -p "$wheel" "visa_photo-$version.dist-info/METADATA" | awk '/^$/{exit} {print}' \
  | grep -E "^(Name|Version|Author-email|License-Expression|License-File|Requires-Python|Classifier|Project-URL|Description-Content-Type):"
if unzip -p "$wheel" "visa_photo-$version.dist-info/METADATA" | awk '/^$/{exit} {print}' | grep -q "^Classifier: License ::"; then
  echo "licence classifier present - use the SPDX expression instead"; exit 1
fi
rm -rf "$tmp"
echo "release check OK"
