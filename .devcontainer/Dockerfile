FROM ubuntu:24.04 AS base

ENV DEBIAN_FRONTEND=noninteractive

# install basic packages
RUN apt-get update && apt-get upgrade -y && apt-get install -y --fix-broken && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    locales \
    ssh \
    sudo \
    vim \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN locale-gen en_US.UTF-8

ARG USER_UID=1000
ARG USER_GID=1000

RUN (groupadd --gid $USER_GID appuser || true) \
    && (useradd --uid $USER_UID --gid $USER_GID -m appuser -s /bin/bash || true) \
    && export USERNAME=$(getent passwd $USER_UID | cut -d: -f1) \
    && echo "$USERNAME ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

RUN mkdir -p /project \
    && chown $USER_UID:$USER_GID /project

# set LANG env variable
USER $USER_UID
RUN echo 'export LANG="en_US.UTF-8"' >> ~/.bashrc \
    && echo 'export LC_ALL="en_US.UTF-8"' >> ~/.bashrc \
    && echo 'export NODE_LLAMA_CPP_CMAKE_OPTION_GGML_CUDA=OFF' >> ~/.bashrc

FROM base AS tools

# install lazygit
USER root
RUN export LAZYGIT_VERSION=$(curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" | \grep -Po '"tag_name": *"v\K[^"]*') \
    && export ARCH=$(dpkg --print-architecture) \
    && if [ "$ARCH" = "amd64" ]; then export LAZYGIT_ARCH="x86_64"; elif [ "$ARCH" = "arm64" ]; then export LAZYGIT_ARCH="arm64"; else export LAZYGIT_ARCH="$ARCH"; fi \
    && curl -Lo lazygit.tar.gz "https://github.com/jesseduffield/lazygit/releases/download/v${LAZYGIT_VERSION}/lazygit_${LAZYGIT_VERSION}_Linux_${LAZYGIT_ARCH}.tar.gz" \
    && tar xf lazygit.tar.gz lazygit \
    && install lazygit -D -t /usr/local/bin/ \
    && rm -rf lazygit.tar.gz lazygit

FROM tools AS dev

### PROJECT-SPECIFIC SETUP BEGIN

# install dependencies
USER root
# shellcheck is for linting shell scripts
RUN apt-get update && apt-get install -y --no-install-recommends \
    shellcheck \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# install uv
USER $USER_UID
COPY --from=ghcr.io/astral-sh/uv:0.10.2 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_CACHE_DIR=/project/.devcontainer/uv/cache
ENV UV_PYTHON_INSTALL_DIR=/project/.devcontainer/uv/python
ENV UV_PYTHON_BIN_DIR=/project/.devcontainer/uv/python-bin

# install python using uv
USER $USER_UID
RUN uv python install 3.12 --default \
    && echo 'export PATH="/project/.devcontainer/uv/python-bin:$PATH"' >> ~/.bashrc \
    && export PATH="/project/.devcontainer/uv/python-bin:$PATH"

# set TERM and COLORTERM env variable for correct color rendering in textual
USER $USER_UID
RUN echo 'export TERM="xterm-256color"' >> ~/.bashrc \
    && echo 'export COLORTERM="truecolor"' >> ~/.bashrc \
    && echo 'alias tc="uv run --project /project textual-code"' >> ~/.bashrc \
    && export TERM="xterm-256color" \
    && export COLORTERM="truecolor"

### PROJECT-SPECIFIC SETUP END

USER $USER_UID
WORKDIR /project
