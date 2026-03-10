#!/usr/bin/env bash

# Ensure AI tool directories and files exist in devcontainer
# This script is called during devcontainer post-create phase

set -eu

# Define base paths
DEVCONTAINER_DIR="/project/.devcontainer"
HOME_DIR="/home/$(whoami)"

# Create directories if they don't exist
mkdir -p "${DEVCONTAINER_DIR}/.claude"
mkdir -p "${DEVCONTAINER_DIR}/qmd-config"
mkdir -p "${DEVCONTAINER_DIR}/qmd-cache"

# Create files if they don't exist
if [ ! -f "${DEVCONTAINER_DIR}/.claude.json" ]; then
    echo "{}" > "${DEVCONTAINER_DIR}/.claude.json"
fi
if [ ! -f "${DEVCONTAINER_DIR}/.claude.json.backup" ]; then
    echo "{}" > "${DEVCONTAINER_DIR}/.claude.json.backup"
fi

# Ensure proper ownership
chown -R $(whoami):$(whoami) "${DEVCONTAINER_DIR}/.claude"
chown -R $(whoami):$(whoami) "${DEVCONTAINER_DIR}/qmd-config"
chown -R $(whoami):$(whoami) "${DEVCONTAINER_DIR}/qmd-cache"
chown $(whoami):$(whoami) "${DEVCONTAINER_DIR}/.claude.json"
chown $(whoami):$(whoami) "${DEVCONTAINER_DIR}/.claude.json.backup"

# Create symlinks if they don't exist
if [ ! -L "${HOME_DIR}/.claude" ]; then
    ln -sf "${DEVCONTAINER_DIR}/.claude" "${HOME_DIR}/"
fi

if [ ! -L "${HOME_DIR}/.config/qmd" ]; then
    ln -sf "${DEVCONTAINER_DIR}/qmd-config" "${HOME_DIR}/.config/qmd"
fi

if [ ! -L "${HOME_DIR}/.cache/qmd" ]; then
    ln -sf "${DEVCONTAINER_DIR}/qmd-cache" "${HOME_DIR}/.cache/qmd"
fi
    
if [ ! -L "${HOME_DIR}/.claude.json" ]; then
    ln -sf "${DEVCONTAINER_DIR}/.claude.json" "${HOME_DIR}/.claude.json"
fi

if [ ! -L "${HOME_DIR}/.claude.json.backup" ]; then
    ln -sf "${DEVCONTAINER_DIR}/.claude.json.backup" "${HOME_DIR}/.claude.json.backup"
fi