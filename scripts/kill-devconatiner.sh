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

    # 1. docker compose down - run-devcontainer.sh 및 VS Code가 같은 compose 파일로
    #    실행한 컨테이너 종료 (이미 없으면 조용히 통과)
    sudo -E docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true

    # 2. 이름 패턴으로 남은 컨테이너 정리 - VS Code가 다른 프로젝트 이름으로
    #    실행했거나 compose 외 방식으로 실행된 경우 처리
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
