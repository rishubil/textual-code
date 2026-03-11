#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
if [[ "${TRACE-0}" == "1" ]]; then
    set -o xtrace
fi

if [[ "${1-}" =~ ^-*h(elp)?$ ]]; then
    echo 'Usage: ./scripts/download-libs-docs.sh

Downloads Textual framework documentation from GitHub into docs/libs/textual/,
using the same version tag as the installed package.
Requires: git (sparse checkout), uv

'
    exit
fi

cd "$(dirname "$0")/.."

DEST_DIR="docs/libs/textual"
REPO_URL="https://github.com/Textualize/textual.git"
SPARSE_PATH="docs"
WORK_DIR="$(mktemp --directory)"

cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

# Resolve installed Textual version
TEXTUAL_VERSION="$(uv run python -c "import textual; print(textual.__version__)")"
GIT_TAG="v${TEXTUAL_VERSION}"
echo "Detected Textual version: ${TEXTUAL_VERSION} (tag: ${GIT_TAG})" >&2

echo "Cloning Textual docs (sparse checkout, tag ${GIT_TAG})..." >&2

git clone \
    --depth=1 \
    --no-checkout \
    --filter=blob:none \
    --branch "${GIT_TAG}" \
    "$REPO_URL" \
    "$WORK_DIR/repo"

git -C "$WORK_DIR/repo" sparse-checkout set --no-cone "$SPARSE_PATH"
git -C "$WORK_DIR/repo" checkout

echo "Copying docs to $DEST_DIR..." >&2
rm -rf "$DEST_DIR"
mkdir -p "$(dirname "$DEST_DIR")"
cp -r "$WORK_DIR/repo/$SPARSE_PATH" "$DEST_DIR"

echo "Done. Textual ${TEXTUAL_VERSION} docs saved to $DEST_DIR" >&2
