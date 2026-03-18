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
APP_SERVICE_NAME="$(extract_field "$DEVCONTAINER_JSON" service)"

show_help() {
    cat << EOF
Usage: $0 [OPTIONS] [-- COMMAND]

This script runs commands inside the devcontainer.

Arguments:
    COMMAND     Command to execute inside the devcontainer (optional)
                Must be preceded by -- to separate from script options
                If no command is provided, starts an interactive bash session

Options:
    -h, --help          Show this help message and exit
    --worktree <name>   Create an isolated dev environment using git worktree.
                        Creates branch 'worktree/<name>' and database 'textual-code_<name>'.
                        On exit, the worktree and database are deleted. The branch is preserved.

Examples:
    $0                              # Start interactive bash session
    $0 -- ls -la                    # List files in the container
    $0 -- npm install               # Run npm install
    $0 --worktree feature-x         # Start isolated worktree environment
    $0 --worktree feature-x -- bash # Run command in worktree environment

EOF
}

# Parse arguments
worktree_name=""
command_args=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        --worktree)
            if [[ -z "${2-}" ]]; then
                echo "Error: --worktree requires a name argument." >&2
                exit 1
            fi
            worktree_name="$2"
            shift 2
            ;;
        --)
            shift
            command_args=("$@")
            break
            ;;
        *)
            echo "Error: Unknown option '$1'. Use '--' to separate command arguments." >&2
            echo "Use '$0 --help' for usage information." >&2
            exit 1
            ;;
    esac
done

# Run ensure-ai-symlinks and then the container command.
# Arguments: compose file paths to pass as -f flags.
run_in_container() {
    local compose_args=()
    for f in "$@"; do
        compose_args+=(-f "$f")
    done

    # Ensure AI tool directories and files exist before running container
    sudo -E docker compose "${compose_args[@]}" run --rm --no-deps "$APP_SERVICE_NAME" bash /project/.devcontainer/ensure-ai-symlinks.sh

    if [[ ${#command_args[@]} -eq 0 ]]; then
        echo "Starting interactive bash session in devcontainer..."
        sudo -E docker compose "${compose_args[@]}" run --rm --no-deps "$APP_SERVICE_NAME" bash
    else
        echo "Executing command in devcontainer: ${command_args[*]}"
        sudo -E docker compose "${compose_args[@]}" run --rm --no-deps "$APP_SERVICE_NAME" "${command_args[@]}"
    fi
}

# Global variables for worktree mode (must survive past run_worktree return for cleanup trap)
wt_name=""
wt_project_root=""
wt_worktree_path=""
wt_branch_name=""
wt_override_file=""

copy_files_to_worktree() {
    local src="$1"
    local dst="$2"

    local items=(
        ".claude"
        ".devcontainer/qmd-cache"
        ".env.local"
        ".env"
        "CLAUDE.local.md"
    )

    echo "Copying files to worktree..."
    for item in "${items[@]}"; do
        local src_path="${src}/${item}"
        local dst_path="${dst}/${item}"
        if [[ -e "$src_path" ]]; then
            if [[ -d "$src_path" ]]; then
                mkdir -p "$dst_path"
                cp -r "${src_path}/." "${dst_path}/"
            else
                mkdir -p "$(dirname "$dst_path")"
                cp "$src_path" "$dst_path"
            fi
            echo "  Copied: ${item}"
        else
            echo "  Skipped (not found): ${item}"
        fi
    done
}

cleanup_worktree() {
    echo ""
    echo "Cleaning up worktree '${wt_name}'..."

    # Remove override file
    rm -f "$wt_override_file"

    # Remove git worktree (branch is preserved for later use)
    git -C "$wt_project_root" worktree remove --force "$wt_worktree_path" 2>/dev/null || true

    echo "Cleanup complete."
}

run_worktree() {
    wt_name="$1"

    # Validate name
    if [[ ! "$wt_name" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo "Error: Worktree name must contain only alphanumeric characters, hyphens, and underscores." >&2
        exit 1
    fi

    wt_project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
    local worktree_base
    worktree_base="$(cd "${wt_project_root}/.." && pwd -P)/textual-code-worktrees"
    wt_worktree_path="${worktree_base}/${wt_name}"
    wt_branch_name="worktree/${wt_name}"
    wt_override_file="/tmp/textual-code-worktree-${wt_name}.yml"

    if [[ -d "$wt_worktree_path" ]]; then
        echo "Error: Worktree already exists: $wt_worktree_path" >&2
        echo "Remove it first: git worktree remove '$wt_worktree_path'" >&2
        exit 1
    fi

    # Create git worktree
    echo "Creating git worktree '${wt_name}' (branch: ${wt_branch_name})..."
    mkdir -p "$worktree_base"
    if git -C "$wt_project_root" show-ref --verify --quiet "refs/heads/${wt_branch_name}"; then
        echo "Branch '${wt_branch_name}' already exists."
        echo "  1) Delete branch and create new"
        echo "  2) Reuse existing branch"
        echo "  3) Exit"
        read -r -p "Choice [1/2/3]: " branch_choice
        case "$branch_choice" in
            1)
                git -C "$wt_project_root" branch -D "$wt_branch_name"
                git -C "$wt_project_root" worktree add -b "$wt_branch_name" "$wt_worktree_path"
                ;;
            2)
                git -C "$wt_project_root" worktree add "$wt_worktree_path" "$wt_branch_name"
                ;;
            *)
                echo "Exiting." >&2
                exit 1
                ;;
        esac
    else
        git -C "$wt_project_root" worktree add -b "$wt_branch_name" "$wt_worktree_path"
    fi

    # Set cleanup trap after worktree creation succeeds
    trap cleanup_worktree EXIT

    copy_files_to_worktree "$wt_project_root" "$wt_worktree_path"

    # Generate docker-compose override
    # - Keep /project as main repo mount (so .git is accessible for worktree)
    # - Add worktree at /worktree and set as working directory
    # - Reset network_mode (remove tailscale sidecar, use default compose network)
    cat > "$wt_override_file" << YAML
services:
  "$APP_SERVICE_NAME":
    volumes:
      - ${wt_worktree_path}:/worktree
    working_dir: /worktree
YAML

    echo ""
    echo "Worktree environment ready."
    echo "  Branch:   ${wt_branch_name}"
    echo "  Path:     ${wt_worktree_path}"
    echo ""
    echo "Exit to clean up worktree and database."
    echo ""

    # Fix git worktree path references inside the container.
    # Worktree's .git file contains "gitdir: <host_project_root>/.git/worktrees/<name>"
    # which must resolve inside the container where the repo is mounted at /project.
    # Create symlinks so host paths resolve to container mount points.
    # Uses positional args ($1..$4) to avoid shell injection from paths with special chars.
    local fix_paths_cmd
    fix_paths_cmd=$(cat << 'FIXSCRIPT'
host_proj="$1"; host_wt="$2"; cont_proj="$3"; cont_wt="$4"
if [ "$host_proj" != "$cont_proj" ]; then
    sudo mkdir -p "$(dirname "$host_proj")" && sudo ln -sfn "$cont_proj" "$host_proj" \
        || { echo "Error: failed to create symlink '$host_proj' -> '$cont_proj'" >&2; exit 1; }
fi
if [ "$host_wt" != "$cont_wt" ]; then
    sudo mkdir -p "$(dirname "$host_wt")" && sudo ln -sfn "$cont_wt" "$host_wt" \
        || { echo "Error: failed to create symlink '$host_wt' -> '$cont_wt'" >&2; exit 1; }
fi
FIXSCRIPT
)

    local compose_args=(-f "$COMPOSE_FILE" -f "$wt_override_file")

    # Ensure AI tool directories
    sudo -E docker compose "${compose_args[@]}" run --rm --no-deps "$APP_SERVICE_NAME" \
        bash /project/.devcontainer/ensure-ai-symlinks.sh

    # Start container with symlinks for git worktree compatibility
    if [[ ${#command_args[@]} -eq 0 ]]; then
        echo "Starting interactive bash session in devcontainer..."
        sudo -E docker compose "${compose_args[@]}" run --rm --no-deps "$APP_SERVICE_NAME" \
            bash -c "$fix_paths_cmd && exec bash" \
            -- "$wt_project_root" "$wt_worktree_path" /project /worktree
    else
        echo "Executing command in devcontainer: ${command_args[*]}"
        sudo -E docker compose "${compose_args[@]}" run --rm --no-deps "$APP_SERVICE_NAME" \
            bash -c "$fix_paths_cmd && shift 4 && exec \"\$@\"" \
            -- "$wt_project_root" "$wt_worktree_path" /project /worktree "${command_args[@]}"
    fi
}

if [[ -n "$worktree_name" ]]; then
    run_worktree "$worktree_name"
else
    run_in_container "$COMPOSE_FILE"
fi
