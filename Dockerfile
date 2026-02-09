# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tmux \
    fzf \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy package files
COPY package.json ./

# Install Node.js dependencies
RUN npm install

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy Python project files
COPY pyproject.toml ./

# Install Python dependencies with uv
RUN /root/.local/bin/uv pip install --system -r pyproject.toml

# Create tmux config with keybindings
RUN mkdir -p /root && cat > /root/.tmux.conf << 'EOF'
# Minimal tmux config for testing
set -g status off
set -g default-terminal "screen-256color"

# Keybindings for session-zx.mjs script
# Ctrl+Shift+L to switch sessions
bind-key -n C-S-l run-shell "/app/session-zx.mjs popup-switch"

# Ctrl+Shift+O to switch to CAPITAL letter sessions only
bind-key -n C-S-o run-shell "/app/session-zx.mjs popup-capital-switch"

# Ctrl+Shift+P to switch sessions filtered by git worktrees
bind-key -n C-S-p run-shell "/app/session-zx.mjs popup-worktree-switch"
EOF

# Set environment variables
ENV TERM=xterm-256color
ENV NODE_ENV=test

# Copy application files
COPY . .

# Make session-zx.mjs executable
RUN chmod +x session-zx.mjs

# Default command runs tests
CMD ["pytest", "-v"]
