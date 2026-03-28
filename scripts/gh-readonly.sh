#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
if [[ "${TRACE-0}" == "1" ]]; then
    set -o xtrace
fi

if [[ "${1-}" =~ ^-*h(elp)?$ ]]; then
    echo 'Usage: ./scripts/gh-readonly.sh <gh-subcommand> [args...]

Wrapper around the gh CLI that only allows read-only operations.
Blocks any command that could modify remote state (create, edit, delete, merge, etc.).

Examples:
  ./scripts/gh-readonly.sh issue list
  ./scripts/gh-readonly.sh pr view 123
  ./scripts/gh-readonly.sh api repos/owner/repo/pulls

Exit codes:
  0  Command executed successfully
  1  Command blocked (not read-only)
  2  Usage error
'
    exit
fi

if [[ $# -lt 1 ]]; then
    echo "Error: no subcommand provided" >&2
    echo "Usage: ./scripts/gh-readonly.sh <gh-subcommand> [args...]" >&2
    exit 2
fi

# --- Read-only subcommand allowlist ---
# Format: "group subcommand" pairs that are safe to run.
# For top-level commands (no subcommand), use "GROUP" alone.

is_readonly() {
    local cmd="$1"
    shift
    local sub="${1-}"

    case "$cmd" in
        # Top-level read-only commands
        status|completion)
            return 0
            ;;
        browse)
            return 0
            ;;

        # Two-level commands: cmd + readonly subcommand
        auth)
            [[ "$sub" == "status" || "$sub" == "token" ]] && return 0
            ;;
        gist)
            [[ "$sub" == "list" || "$sub" == "ls" || "$sub" == "view" ]] && return 0
            ;;
        issue)
            case "$sub" in
                list|ls|status|view|develop)
                    # "develop" is only allowed with --list flag
                    if [[ "$sub" == "develop" ]]; then
                        shift
                        for arg in "$@"; do
                            [[ "$arg" == "--list" ]] && return 0
                        done
                        return 1
                    fi
                    return 0
                    ;;
            esac
            ;;
        org)
            [[ "$sub" == "list" || "$sub" == "ls" ]] && return 0
            ;;
        pr)
            [[ "$sub" =~ ^(list|ls|status|checks|diff|view)$ ]] && return 0
            ;;
        project)
            [[ "$sub" =~ ^(field-list|item-list|list|ls|view)$ ]] && return 0
            ;;
        release)
            [[ "$sub" =~ ^(list|view|download)$ ]] && return 0
            ;;
        repo)
            case "$sub" in
                list|view)
                    return 0
                    ;;
                gitignore|license|autolink)
                    local subsub="${2-}"
                    [[ "$subsub" == "list" || "$subsub" == "view" ]] && return 0
                    ;;
                deploy-key)
                    local subsub="${2-}"
                    [[ "$subsub" == "list" ]] && return 0
                    ;;
            esac
            ;;
        cache)
            [[ "$sub" == "list" || "$sub" == "ls" ]] && return 0
            ;;
        run)
            [[ "$sub" =~ ^(list|view|watch|download)$ ]] && return 0
            ;;
        workflow)
            [[ "$sub" =~ ^(list|ls|view)$ ]] && return 0
            ;;
        alias)
            [[ "$sub" == "list" ]] && return 0
            ;;
        attestation)
            [[ "$sub" == "download" || "$sub" == "trusted-root" ]] && return 0
            ;;
        config)
            [[ "$sub" == "get" || "$sub" == "list" ]] && return 0
            ;;
        extension)
            [[ "$sub" == "list" || "$sub" == "search" ]] && return 0
            ;;
        gpg-key)
            [[ "$sub" == "list" ]] && return 0
            ;;
        label)
            [[ "$sub" == "list" ]] && return 0
            ;;
        preview)
            [[ "$sub" == "prompter" ]] && return 0
            ;;
        ruleset)
            [[ "$sub" =~ ^(check|list|view)$ ]] && return 0
            ;;
        secret)
            [[ "$sub" == "list" ]] && return 0
            ;;
        ssh-key)
            [[ "$sub" == "list" ]] && return 0
            ;;
        variable)
            [[ "$sub" == "get" || "$sub" == "list" ]] && return 0
            ;;
        search)
            [[ "$sub" =~ ^(code|commits|issues|prs|repos)$ ]] && return 0
            ;;

        # gh api — only allow GET requests
        api)
            # Block explicit write methods
            local method="GET"
            local args_copy=("$@")
            for i in "${!args_copy[@]}"; do
                case "${args_copy[$i]}" in
                    -X|--method)
                        method="${args_copy[$((i + 1))]-}"
                        ;;
                    --paginate|--jq|--template|-q|--hostname|-H|--header|-t|-f|-F|--field|--raw-field|-p|--preview|--cache|--slurp|-i|--include)
                        # safe flags, skip
                        ;;
                esac
            done
            [[ "${method^^}" == "GET" ]] && return 0
            ;;
    esac

    return 1
}

if is_readonly "$@"; then
    exec gh "$@"
else
    echo "Blocked: 'gh $*' is not a read-only command" >&2
    exit 1
fi
