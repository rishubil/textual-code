#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
if [[ "${TRACE-0}" == "1" ]]; then
    set -o xtrace
fi

COMPOSE_FILE=".devcontainer/docker-compose.yml"
COMMON_SERVICE_NAME="textual-code-devcontainer"

if [[ "${1-}" =~ ^-*h(elp)?$ ]]; then
    echo 'Usage: ./kill-devcontainer.sh

Stop all devcontainers regardless of how they were started
(run-devcontainer.sh or VS Code devcontainer extension).
Does NOT affect devcontainers from other projects.

'
    exit
fi

cd "$(dirname "${BASH_SOURCE[0]}")/.."

main() {
    echo "Stopping devcontainers..."

    # 1. docker compose down - stops containers started by run-devcontainer.sh or VS Code
    #    using the same compose file (silently passes if already stopped)
    sudo -E docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true

    # 2. clean up remaining containers by name pattern - handles cases where VS Code
    #    used a different project name or started containers outside of compose
    local container_ids
    container_ids=$(sudo docker ps --all --quiet --filter "name=$COMMON_SERVICE_NAME" 2>/dev/null || true)

    if [[ -n "$container_ids" ]]; then
        echo "Stopping remaining containers matching '$COMMON_SERVICE_NAME'..."
        echo "$container_ids" | xargs sudo docker stop
        echo "$container_ids" | xargs sudo docker rm
    fi

    echo "Done."
}

main "$@"
