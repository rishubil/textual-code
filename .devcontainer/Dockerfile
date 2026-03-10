FROM ubuntu:24.04 AS base

ENV DEBIAN_FRONTEND=noninteractive

# change apt mirrors to mirror.kakao.com
RUN sed -i 's|http://archive.ubuntu.com|http://ftp.kaist.ac.kr|g' /etc/apt/sources.list.d/ubuntu.sources && \
    sed -i 's|http://kr.archive.ubuntu.com|http://ftp.kaist.ac.kr|g' /etc/apt/sources.list.d/ubuntu.sources && \
    sed -i 's|http://security.ubuntu.com|http://ftp.kaist.ac.kr|g' /etc/apt/sources.list.d/ubuntu.sources

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

# install claude cli
USER $USER_UID
RUN curl -fsSL https://claude.ai/install.sh | bash
RUN echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
USER root
RUN ln -s /home/$(getent passwd $USER_UID | cut -d: -f1)/.local/bin/claude /usr/local/bin/claude

# link user's .claude settings to the project directory
USER $USER_UID
RUN rm -r ~/.claude \
    && mkdir -p /project/.devcontainer/.claude \
    && touch /project/.devcontainer/.claude.json \
    && touch /project/.devcontainer/.claude.json.backup \
    && chown -R $USER_UID:$USER_GID /project/.devcontainer \
    && ln -sf /project/.devcontainer/.claude ~/ \
    && ln -sf /project/.devcontainer/.claude.json ~/.claude.json \
    && ln -sf /project/.devcontainer/.claude.json.backup ~/.claude.json.backup

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
# cmake/unzip is for qmd
# jq is for claude hook
# shellcheck is for linting shell scripts
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    jq \
    shellcheck \
    unzip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
# node for qmd
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get update && apt-get install -y --no-install-recommends \
    nodejs \
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

# install qmd
USER $USER_UID
RUN curl -fsSL https://bun.com/install | bash \
    && echo 'export PATH="$HOME/.bun/bin:$PATH"' >> ~/.bashrc \
    && export PATH="$HOME/.bun/bin:$PATH" \
    && bun install -g @tobilu/qmd \
    && mkdir -p /project/.devcontainer/qmd-config \
    && mkdir -p /project/.devcontainer/qmd-cache \
    && mkdir -p ~/.cache \
    && mkdir -p ~/.config \
    && ln -sf /project/.devcontainer/qmd-config ~/.config/qmd \
    && ln -sf /project/.devcontainer/qmd-cache ~/.cache/qmd

# run qmd status for first time to initialize qmd
USER $USER_UID
ENV NODE_LLAMA_CPP_CMAKE_OPTION_GGML_CUDA=OFF
RUN $HOME/.bun/bin/qmd status

### PROJECT-SPECIFIC SETUP END

USER $USER_UID
WORKDIR /project
