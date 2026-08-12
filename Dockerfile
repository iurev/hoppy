# syntax=docker/dockerfile:1

# =============================================================================
# stage: gotools — the Go toolchain, used by the compose "build" service.
# It never lands in the test image. The binary is compiled THROUGH the bind
# mount into /app/session-zx, so a build-time COPY would be shadowed anyway.
# =============================================================================
FROM golang:1.26-bookworm AS gotools

# Static binary: the same file must run on Debian (container) and on the host.
ENV CGO_ENABLED=0
ENV GOFLAGS=-trimpath

WORKDIR /app
CMD ["go", "build", "-o", "session-zx", "."]

# =============================================================================
# stage: test — Python + pytest + tmux + fzf. This is the default target.
# =============================================================================
FROM python:3.11-slim AS test

# System dependencies. fzf is NOT installed from apt: the apt version drifts
# with the base image and we need a known floor (see below).
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    git \
    curl \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Pinned fzf. Minimum for this project is 0.51.0:
#   0.36.0 added pos(N)      -> the 1..9 quick-switch bindings
#   0.51.0 added --with-shell -> lets us force `sh` for --bind commands,
#                                which makes POSIX quoting of the binary path
#                                provably correct even if $SHELL is fish.
ARG FZF_VERSION=0.60.3
RUN curl -fsSL "https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/fzf-${FZF_VERSION}-linux_amd64.tar.gz" \
    | tar -xz -C /usr/local/bin fzf \
    && chmod +x /usr/local/bin/fzf \
    && fzf --version

# Pinned asciinema (~8 MB static musl binary, no runtime deps).
# It is ONLY used when RECORD_CAST=1. A normal test run never starts it.
# See ARCHITECTURE.md "Recording a test run".
ARG ASCIINEMA_VERSION=3.2.1
RUN curl -fsSL -o /usr/local/bin/asciinema \
      "https://github.com/asciinema/asciinema/releases/download/v${ASCIINEMA_VERSION}/asciinema-x86_64-unknown-linux-musl" \
    && chmod +x /usr/local/bin/asciinema \
    && asciinema --version

# Set working directory
WORKDIR /app

# Install uv (project rule: uv is the Python project manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy Python project files
COPY pyproject.toml ./

# Install Python dependencies with uv
RUN /root/.local/bin/uv pip install --system -r pyproject.toml

# Create tmux config with keybindings
RUN mkdir -p /root && cat > /root/.tmux.conf << 'EOF'
# Minimal tmux config for testing
# status off matters: capture-pane assertions depend on no status bar
set -g status off
set -g default-terminal "screen-256color"

# Keybindings for the session-zx binary
# Ctrl+Shift+L to switch sessions
bind-key -n C-S-l run-shell "/app/session-zx popup-switch"

# Ctrl+Shift+O to switch to CAPITAL letter sessions only
bind-key -n C-S-o run-shell "/app/session-zx popup-capital-switch"

# Ctrl+Shift+P to switch sessions filtered by git worktrees
bind-key -n C-S-p run-shell "/app/session-zx popup-worktree-switch"
EOF

# Set environment variables
ENV TERM=xterm-256color

# Copy application files.
# At run time docker-compose bind-mounts . over /app, so this COPY only matters
# for a plain `docker run` without the mount.
COPY . .

# Default command runs tests
CMD ["pytest", "-v"]

# =============================================================================
# stage: media — .cast -> .gif -> animated .webp. Used by the compose "media"
# service only. It is deliberately NOT part of the `test` stage: agg, Pillow
# and the font package are needed once, when we cut a README demo, and would
# otherwise sit in every test run.
#
#   docker compose run --rm media scripts/cast2webp.sh <cast-name>
#
# See ARCHITECTURE.md 4.2.
# =============================================================================
FROM python:3.11-slim AS media

# agg renders text with a real font; the slim image ships none.
# DejaVu Sans Mono is agg's last default-family fallback, so it always matches.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Pinned agg (asciinema's official gif generator, static musl binary, no deps).
# Installed exactly like asciinema above: released binary, not cargo.
ARG AGG_VERSION=1.9.0
RUN curl -fsSL -o /usr/local/bin/agg \
      "https://github.com/asciinema/agg/releases/download/v${AGG_VERSION}/agg-x86_64-unknown-linux-musl" \
    && chmod +x /usr/local/bin/agg \
    && agg --version

# Pinned Pillow. It does the GIF -> animated WebP step, and it is the reason
# ffmpeg is not used here: ffmpeg rewrites every frame to a constant frame
# rate, which destroys the pacing of a terminal recording. Pillow copies the
# per-frame delays across unchanged.
ARG PILLOW_VERSION=12.3.0
RUN pip install --no-cache-dir "Pillow==${PILLOW_VERSION}" \
    && python3 -c "import PIL; print('Pillow', PIL.__version__)"

WORKDIR /app

# No COPY: docker-compose bind-mounts the repo over /app, which is where both
# the casts and the script live.
CMD ["scripts/cast2webp.sh"]
