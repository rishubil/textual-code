#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
if [[ "${TRACE-0}" == "1" ]]; then
    set -o xtrace
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Resolve devcontainer.json path (prefer local override)
resolve_devcontainer_json() {
    local devcontainer_dir=".devcontainer"
    if [[ -f "${devcontainer_dir}/local/devcontainer.json" ]]; then
        echo "${devcontainer_dir}/local/devcontainer.json"
    else
        echo "${devcontainer_dir}/devcontainer.json"
    fi
}

# Extract a string field from devcontainer.json
# Usage: extract_field <json_file> <field_name>
extract_field() {
    local json_file="$1"
    local field="$2"
    local value
    value=$(grep -o "\"${field}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$json_file" \
        | sed "s/.*\"${field}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/")
    if [[ -z "$value" ]]; then
        echo "Error: ${field} not found in $json_file" >&2
        exit 1
    fi
    echo "$value"
}

DEVCONTAINER_JSON="$(resolve_devcontainer_json)"
COMPOSE_FILE="$(dirname "$DEVCONTAINER_JSON")/$(extract_field "$DEVCONTAINER_JSON" dockerComposeFile)"

# Help message function
show_help() {
    cat << EOF
Usage: $0 [OPTIONS] [-- DOCKER_BUILD_OPTIONS...]

This script builds the devcontainer image.

Options:
    -h, --help  Show this help message and exit

Any additional arguments after '--' are passed directly to 'docker compose build'.

Examples:
    $0                      # Build the devcontainer image
    $0 --help               # Show this help message
    $0 -- --no-cache        # Build without using cache
    $0 -- --no-cache --pull # Build without cache, pulling latest base images

Description:
    This script builds the devcontainer Docker image using docker compose.
    It will force remove any existing containers and rebuild the image from scratch.

EOF
}

# Check for help flag
if [[ "${1-}" =~ ^-*h(elp)?$ ]]; then
    show_help
    exit 0
fi

# Collect extra docker build arguments after '--'
docker_build_args=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --)
            shift
            docker_build_args+=("$@")
            break
            ;;
        *)
            echo "Error: Unknown argument '$1'." >&2
            echo "Use '$0 --help' for usage information." >&2
            exit 1
            ;;
    esac
done

echo "Building devcontainer image..."
sudo -E docker compose -f "$COMPOSE_FILE" build --force-rm "${docker_build_args[@]}"
